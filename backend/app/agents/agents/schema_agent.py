"""
Schema 分析代理 (优化版本)

遵循 LangGraph 官方最佳实践:
1. 使用 InjectedState 注入状态参数
2. 工具返回标准格式 (字符串或 JSON)
3. 使用 ToolNode 配合 ReAct Agent

集成语义层 (Semantic Layer):
- 指标库: 从 Neo4j 获取业务指标定义
- 值域预检索: 获取枚举值、日期范围等

Phase 1 优化:
- 使用统一的 SchemaContext 格式输出
- 消除格式不一致问题

官方文档参考:
- https://langchain-ai.github.io/langgraph/how-tos/tool-calling
- https://langchain-ai.github.io/langgraph/reference/agents
"""
from typing import Dict, Any, Annotated, List
import json
import logging

from langchain_core.tools import tool
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.prebuilt import create_react_agent, InjectedState

from app.core.state import SQLMessageState
from app.core.agent_config import get_agent_llm, CORE_AGENT_SQL_GENERATOR
from app.core.message_utils import generate_tool_call_id
from app.db.session import SessionLocal
from app.services.text2sql_utils import retrieve_relevant_schema, get_value_mappings, analyze_query_with_llm
from app.schemas.schema_context import SchemaContext, TableInfo, ColumnInfo, RelationshipInfo, normalize_schema_info

logger = logging.getLogger(__name__)


# ============================================================================
# 工具定义 (使用 InjectedState 注入状态)
# ============================================================================

@tool
def analyze_user_query(query: str) -> str:
    """
    分析用户的自然语言查询，提取关键实体和意图
    
    Args:
        query: 用户的自然语言查询
        
    Returns:
        str: JSON 格式的分析结果，包含实体、关系和查询意图
    """
    try:
        analysis = analyze_query_with_llm(query)
        return json.dumps({
            "success": True,
            "analysis": analysis
        }, ensure_ascii=False)
    except Exception as e:
        logger.error(f"查询分析失败: {str(e)}")
        return json.dumps({
            "success": False,
            "error": str(e)
        }, ensure_ascii=False)


@tool
def retrieve_database_schema(
    query: str,
    state: Annotated[dict, InjectedState]
) -> str:
    """
    根据查询获取相关的数据库表结构信息
    
    Args:
        query: 用户查询
        state: 注入的状态 (自动从 LangGraph 状态获取 connection_id)
        
    Returns:
        str: JSON 格式的表结构和值映射信息
        
    注意:
        使用 InjectedState 自动获取 connection_id，无需显式传递
    """
    try:
        # 从状态中获取 connection_id
        connection_id = state.get("connection_id")
        if not connection_id:
            return json.dumps({
                "success": False,
                "error": "未指定数据库连接 ID"
            }, ensure_ascii=False)
        
        logger.info(f"检索数据库 schema, connection_id={connection_id}")
        
        from app.db.session import get_db_session
        with get_db_session() as db:
            # 获取相关表结构
            schema_context = retrieve_relevant_schema(
                db=db,
                connection_id=connection_id,
                query=query
            )
            
            # 获取值映射
            value_mappings = get_value_mappings(db, schema_context)
            
            return json.dumps({
                "success": True,
                "schema_context": schema_context,
                "value_mappings": value_mappings,
                "connection_id": connection_id
            }, ensure_ascii=False, default=str)
            
    except Exception as e:
        logger.error(f"Schema 检索失败: {str(e)}")
        return json.dumps({
            "success": False,
            "error": str(e)
        }, ensure_ascii=False)


# ============================================================================
# Schema 分析代理类
# ============================================================================

class SchemaAnalysisAgent:
    """
    Schema 分析代理 - 使用 InjectedState 优化
    
    重要变更:
    - retrieve_database_schema 工具现在使用 InjectedState 获取 connection_id
    - 无需在提示词中显式传递 connection_id
    """
    
    def __init__(self):
        self.name = "schema_agent"
        self.llm = get_agent_llm(CORE_AGENT_SQL_GENERATOR)
        self.tools = [analyze_user_query, retrieve_database_schema]
        
        # 创建 ReAct 代理
        self.agent = create_react_agent(
            self.llm,
            self.tools,
            prompt=self._create_system_prompt(),
            name=self.name,
            state_schema=SQLMessageState  # 指定状态 schema，让 InjectedState 能正确注入
        )
    
    def _create_system_prompt(self) -> str:
        """创建系统提示"""
        return """你是一个专业的数据库模式分析专家。

**核心职责**: 分析用户查询，获取相关的数据库表结构信息

**工作流程**:
1. 使用 analyze_user_query 工具分析用户查询意图
2. 使用 retrieve_database_schema 工具获取相关表结构
   - connection_id 会自动从状态中获取，无需手动传递
3. **只返回模式信息，不生成 SQL，不预测结果**

**输出内容**:
- 相关的表和字段信息
- 必要的值映射信息

**禁止的行为**:
- ❌ 不要生成 SQL 语句
- ❌ 不要预测查询结果
- ❌ 不要重复调用工具

**输出格式**: 只返回工具调用结果，包含表结构和值映射信息"""
    
    def _generate_schema_analysis_text(
        self,
        tables_list: List[Dict[str, Any]],
        columns_list: List[Dict[str, Any]],
        relationships: List[Dict[str, Any]],
        value_mappings: Dict[str, Any]
    ) -> str:
        """
        生成结构化的 Schema 分析文本
        
        提供清晰的表结构和关联信息，帮助 SQL Generator 生成更准确的 SQL。
        
        Args:
            tables_list: 表列表
            columns_list: 列列表
            relationships: 关系列表
            value_mappings: 值映射
            
        Returns:
            str: 结构化的分析文本
        """
        lines = []
        lines.append("根据数据库结构分析，以下是与您查询相关的表和字段信息：")
        lines.append("")
        lines.append("## 相关表结构")
        lines.append("")
        
        # 按表组织列信息
        table_columns_map = {}
        for col in columns_list:
            table_name = col.get("table_name", "unknown")
            if table_name not in table_columns_map:
                table_columns_map[table_name] = []
            table_columns_map[table_name].append(col)
        
        # 生成每个表的结构描述
        for i, table in enumerate(tables_list, 1):
            table_name = table.get("table_name", table.get("name", ""))
            table_desc = table.get("description", table.get("comment", ""))
            
            # 表标题
            if table_desc:
                lines.append(f"### {i}. {table_desc} ({table_name})")
            else:
                lines.append(f"### {i}. {table_name}")
            lines.append("")
            
            # 列信息
            columns = table_columns_map.get(table_name, [])
            for col in columns:
                col_name = col.get("column_name", col.get("name", ""))
                col_type = col.get("data_type", col.get("type", ""))
                col_desc = col.get("description", col.get("comment", ""))
                is_pk = col.get("is_primary_key", False)
                is_fk = col.get("is_foreign_key", False)
                
                # 构建列描述
                col_info = f"- **{col_name}**"
                if col_desc:
                    col_info += f": {col_desc}"
                
                # 添加类型和键信息
                extras = []
                if col_type:
                    extras.append(col_type)
                if is_pk:
                    extras.append("主键")
                if is_fk:
                    extras.append("外键")
                
                if extras:
                    col_info += f" ({', '.join(extras)})"
                
                lines.append(col_info)
            
            lines.append("")
        
        # 添加表关系信息
        if relationships:
            lines.append("## 表关联关系")
            lines.append("")
            for rel in relationships:
                from_table = rel.get("from_table", rel.get("source_table", ""))
                from_col = rel.get("from_column", rel.get("source_column", ""))
                to_table = rel.get("to_table", rel.get("target_table", ""))
                to_col = rel.get("to_column", rel.get("target_column", ""))
                rel_type = rel.get("relationship_type", "关联")
                
                if from_table and to_table:
                    lines.append(f"- {from_table}.{from_col} → {to_table}.{to_col} ({rel_type})")
            lines.append("")
        
        # 添加值映射提示
        if value_mappings:
            lines.append("## 字段值映射")
            lines.append("")
            for key, values in list(value_mappings.items())[:5]:  # 最多显示5个
                if isinstance(values, list) and values:
                    values_str = ", ".join(str(v) for v in values[:10])
                    if len(values) > 10:
                        values_str += "..."
                    lines.append(f"- {key}: {values_str}")
            lines.append("")
        
        return "\n".join(lines)
    
    async def process(self, state: SQLMessageState) -> Dict[str, Any]:
        """
        处理 Schema 分析任务 - 返回标准工具调用格式
        
        性能优化 (2026-01-22):
        - 使用异步并行版本 retrieve_relevant_schema_async
        - 批量获取列和关系
        - 预期提升: 20s -> 8-12s
        """
        import time
        from langgraph.config import get_stream_writer
        from app.schemas.stream_events import create_sql_step_event
        from app.services.text2sql_utils import retrieve_relevant_schema_async, get_value_mappings
        from app.db.session import SessionLocal
        
        try:
            # 获取 stream writer
            try:
                writer = get_stream_writer()
            except Exception:
                writer = None
            
            # 发送 schema_mapping 步骤开始事件
            step_start_time = time.time()
            if writer:
                writer(create_sql_step_event(
                    step="schema_mapping",
                    status="running",
                    result=None,
                    time_ms=0
                ))
            
            # 获取用户查询（优先使用 enriched_query）
            messages = state.get("messages", [])
            user_query = state.get("enriched_query")  # 优先使用增强后的查询
            
            if not user_query:
                # 从消息中获取最后一个 HumanMessage（最新的用户查询）
                for msg in reversed(messages):
                    if hasattr(msg, 'type') and msg.type == 'human':
                        user_query = msg.content
                        if isinstance(user_query, list):
                            user_query = user_query[0].get("text", "") if user_query else ""
                        break
            
            if not user_query:
                raise ValueError("无法获取用户查询")
            
            connection_id = state.get("connection_id")
            
            # ==========================================
            # Step 1: 调用 analyze_user_query 分析用户查询
            # 提取实体、关系、查询意图等信息
            # ==========================================
            try:
                analyze_result = analyze_user_query.invoke({"query": user_query})
                analyze_data = json.loads(analyze_result)
                
                # 创建 analyze_user_query 的工具调用消息
                analyze_tool_call_id = generate_tool_call_id("analyze_user_query", {"query": user_query})
                
                analyze_ai_message = AIMessage(
                    content="",
                    tool_calls=[{
                        "name": "analyze_user_query",
                        "args": {"query": user_query},
                        "id": analyze_tool_call_id,
                        "type": "tool_call"
                    }]
                )
                
                analyze_tool_message = ToolMessage(
                    content=analyze_result,
                    tool_call_id=analyze_tool_call_id,
                    name="analyze_user_query"
                )
                
                logger.info(f"[Tool] analyze_user_query 完成: {analyze_data.get('success', False)}")
                analyze_messages = [analyze_ai_message, analyze_tool_message]
            except Exception as e:
                logger.warning(f"analyze_user_query 失败（非关键，继续执行）: {e}")
                analyze_messages = []  # 失败时不添加消息
            
            # ==========================================
            # P3: Skills-SQL-Assistant 集成
            # Phase 3 优化: 检查全局开关，简化 Skill 模式分支
            # 如果已选中 Skill，优先使用 Skill 限定的 Schema
            # ==========================================
            from app.core.config import settings
            
            # 只有在全局开关启用且状态中标记了 skill_mode_enabled 时才使用 Skill 模式
            skill_mode_enabled = (
                settings.SKILL_MODE_ENABLED and 
                state.get("skill_mode_enabled", False)
            )
            loaded_skill_content = state.get("loaded_skill_content") if skill_mode_enabled else None
            
            if skill_mode_enabled and loaded_skill_content:
                # 使用 Skill 预加载的 Schema（Progressive Disclosure）
                logger.info(f"使用 Skill 限定的 Schema: {state.get('selected_skill_name')}")
                
                schema_context = {
                    "tables": loaded_skill_content.get("tables", []),
                    "columns": loaded_skill_content.get("columns", []),
                    "relationships": loaded_skill_content.get("relationships", [])
                }
                
                # 从 Skill 内容获取语义层信息
                semantic_layer_info = {
                    "metrics": loaded_skill_content.get("metrics", []),
                    "join_rules": loaded_skill_content.get("join_rules", []),
                    "enum_columns": loaded_skill_content.get("enum_columns", [])
                }
                
                # 值映射从 enum_columns 提取
                value_mappings = {}
                for enum_col in loaded_skill_content.get("enum_columns", []):
                    if isinstance(enum_col, dict):
                        key = f"{enum_col.get('table_name', '')}.{enum_col.get('column_name', '')}"
                        value_mappings[key] = enum_col.get("values", [])
                
                tables_list = schema_context.get("tables", [])
                columns_list = schema_context.get("columns", [])
                
                elapsed_ms = int((time.time() - step_start_time) * 1000)
                
                # 发送完成事件
                schema_detail = {
                    "summary": f"[Skill模式] 获取到 {len(tables_list)} 个相关表, {len(columns_list)} 个列",
                    "skill_name": state.get("selected_skill_name"),
                    "tables": []
                }
                
                # 按表组织列信息
                table_columns_map = {}
                for col in columns_list:
                    table_name = col.get("table_name", "unknown")
                    if table_name not in table_columns_map:
                        table_columns_map[table_name] = []
                    table_columns_map[table_name].append({
                        "name": col.get("column_name", ""),
                        "type": col.get("data_type", ""),
                        "comment": col.get("description", "")
                    })
                
                for table in tables_list:
                    table_name = table.get("table_name", "")
                    schema_detail["tables"].append({
                        "name": table_name,
                        "comment": table.get("description", ""),
                        "columns": table_columns_map.get(table_name, [])
                    })
                
                if writer:
                    writer(create_sql_step_event(
                        step="schema_mapping",
                        status="completed",
                        result=json.dumps(schema_detail, ensure_ascii=False),
                        time_ms=elapsed_ms
                    ))
                
                logger.info(f"Skill Schema 获取成功: {len(tables_list)} 个表, {len(columns_list)} 个列 [{elapsed_ms}ms]")
            
            else:
                # ✅ 强制全量加载模式 - 确保 SQL 生成准确性
                # 移除智能过滤，避免 LLM 选错表导致 SQL 错误
                from app.services.schema_loading_strategy import get_full_schema_for_connection
                from app.db.session import get_db_session
                from app import crud
                
                # 获取数据库类型
                db_type = "mysql"
                try:
                    from app.services.db_service import get_db_connection_by_id
                    conn = get_db_connection_by_id(connection_id)
                    if conn and conn.db_type:
                        db_type = conn.db_type.lower()
                    # ✅ 添加调试日志：显示连接信息
                    logger.info(f"[Schema Agent] 数据库连接: id={connection_id}, name={conn.name if conn else 'N/A'}, db_type={db_type}")
                except Exception as e:
                    logger.warning(f"[Schema Agent] 获取数据库连接信息失败: {e}")
                
                with get_db_session() as db:
                    # 获取表数量（仅用于日志）
                    all_tables = crud.schema_table.get_by_connection(db=db, connection_id=connection_id)
                    all_tables_count = len(all_tables)
                    
                    # ✅ 添加调试日志：显示所有表名
                    all_table_names = [t.table_name for t in all_tables]
                    logger.info(f"[Schema Agent] 数据库中的所有表: {all_table_names}")
                    
                    # ✅ 强制全量加载：不限制表数量，确保所有表都被加载
                    logger.info(f"[强制全量加载] 加载所有表, connection_id={connection_id}, 表数量={all_tables_count}")
                    schema_context = get_full_schema_for_connection(
                        db=db,
                        connection_id=connection_id,
                        max_tables=9999,  # 不限制表数量
                        db_type=db_type
                    )
                    
                    logger.info(f"✓ Schema 全量加载完成: {schema_context.table_count} 表, {schema_context.column_count} 列")
                    logger.info(f"✓ 加载的表名: {schema_context.table_names}")
                    
                    # ✅ Phase 1: 确保 schema_context 是 SchemaContext 实例
                    if not isinstance(schema_context, SchemaContext):
                        schema_context = normalize_schema_info(schema_context, connection_id, db_type)
                    
                    # 获取值映射 - 传入字典格式兼容旧接口
                    value_mappings = get_value_mappings(db, schema_context.to_dict())
                    # 更新到 schema_context
                    schema_context.value_mappings = value_mappings
                
                # ✅ 集成语义层 (Semantic Layer)
                semantic_layer_info = await self._fetch_semantic_layer_info(
                    connection_id=connection_id,
                    user_query=user_query,
                    tables_list=[t.model_dump() for t in schema_context.tables]
                )
                
                # 计算耗时并发送完成事件
                elapsed_ms = int((time.time() - step_start_time) * 1000)
                
                # 构建详细的 schema 信息用于前端展示
                schema_detail = {
                    "summary": f"获取到 {schema_context.table_count} 个相关表, {schema_context.column_count} 个列",
                    "tables": []
                }
                
                # 按表组织列信息
                for table in schema_context.tables:
                    table_columns = schema_context.get_columns_for_table(table.table_name)
                    schema_detail["tables"].append({
                        "name": table.table_name,
                        "comment": table.description,
                        "columns": [
                            {
                                "name": col.column_name,
                                "type": col.data_type,
                                "comment": col.description
                            }
                            for col in table_columns
                        ]
                    })
                
                if writer:
                    writer(create_sql_step_event(
                        step="schema_mapping",
                        status="completed",
                        result=json.dumps(schema_detail, ensure_ascii=False),
                        time_ms=elapsed_ms
                    ))
                
                logger.info(f"Schema 获取成功: {schema_context.table_count} 个表, {schema_context.column_count} 个列 [{elapsed_ms}ms]")
                
                # 设置变量供后续使用
                tables_list = [t.model_dump() for t in schema_context.tables]
                columns_list = [c.model_dump() for c in schema_context.columns]
            
            # ✅ Phase 1: 构建统一格式的 schema_info
            # 如果是 Skill 模式，需要转换为 SchemaContext
            if skill_mode_enabled and loaded_skill_content:
                schema_context = normalize_schema_info(
                    {"tables": tables_list, "columns": columns_list, "relationships": []},
                    connection_id,
                    "mysql"
                )
                schema_context.value_mappings = value_mappings
                semantic_layer_info = semantic_layer_info if 'semantic_layer_info' in dir() else {}
            
            # schema_info 现在直接存储 SchemaContext 的字典表示
            schema_info = schema_context.to_dict()
            schema_info["semantic_layer"] = semantic_layer_info
            
            # ✅ 记录工具调用日志
            logger.info(f"[Tool] retrieve_database_schema 完成: {len(tables_list)} 表, {len(columns_list)} 列")
            
            # ✅ 返回 analyze_user_query 的消息，让前端显示实体分析结果
            return {
                "messages": analyze_messages,
                "schema_info": schema_info,
                "current_stage": "sql_generation"
            }
            
        except Exception as e:
            logger.error(f"Schema 分析失败: {str(e)}")
            
            # 发送错误事件
            if writer:
                writer(create_sql_step_event(
                    step="schema_mapping",
                    status="error",
                    result=str(e),
                    time_ms=0
                ))
            
            # ✅ 简化错误返回，不添加消息
            return {
                "messages": [],
                "current_stage": "error_recovery",
                "error_history": state.get("error_history", []) + [{
                    "stage": "schema_analysis",
                    "error": str(e),
                    "retry_count": state.get("retry_count", 0)
                }]
            }
    
    async def _fetch_semantic_layer_info(
        self,
        connection_id: int,
        user_query: str,
        tables_list: list
    ) -> Dict[str, Any]:
        """
        获取语义层信息（指标、枚举值、日期范围）
        
        Args:
            connection_id: 数据库连接ID
            user_query: 用户查询
            tables_list: 相关表列表
            
        Returns:
            语义层信息字典
        """
        semantic_info = {
            "metrics": [],
            "enum_columns": [],
            "date_columns": [],
            "has_semantic_layer": False
        }
        
        try:
            from app.services.metric_service import metric_service
            from app.services.value_profiling_service import value_profiling_service
            
            # 1. 获取相关业务指标
            try:
                metrics = await metric_service.get_metrics_for_query(
                    user_query=user_query,
                    connection_id=connection_id
                )
                if metrics:
                    semantic_info["metrics"] = [
                        {
                            "name": m.name,
                            "business_name": m.business_name,
                            "formula": m.formula,
                            "description": m.description,
                            "source_table": m.source_table,
                            "source_column": m.source_column,
                            "aggregation": m.aggregation,
                            "unit": m.unit
                        }
                        for m in metrics
                    ]
                    semantic_info["has_semantic_layer"] = True
                    logger.info(f"获取到 {len(metrics)} 个相关指标")
            except Exception as e:
                logger.debug(f"获取指标失败（可能未配置指标库）: {e}")
            
            # 2. 获取枚举字段（从相关表中）
            table_names = [t.get("table_name", "") for t in tables_list]
            for table_name in table_names[:3]:  # 限制只查前3个表
                try:
                    enums = await value_profiling_service.get_enum_columns(
                        connection_id=connection_id,
                        table_name=table_name
                    )
                    if enums:
                        semantic_info["enum_columns"].extend(enums)
                except Exception as e:
                    logger.debug(f"获取表 {table_name} 枚举字段失败: {e}")
            
            # 3. 获取日期字段范围
            for table_name in table_names[:3]:
                try:
                    dates = await value_profiling_service.get_date_columns(
                        connection_id=connection_id,
                        table_name=table_name
                    )
                    if dates:
                        semantic_info["date_columns"].extend(dates)
                except Exception as e:
                    logger.debug(f"获取表 {table_name} 日期字段失败: {e}")
            
            if semantic_info["enum_columns"] or semantic_info["date_columns"]:
                semantic_info["has_semantic_layer"] = True
                logger.info(f"语义层: {len(semantic_info['enum_columns'])} 个枚举字段, {len(semantic_info['date_columns'])} 个日期字段")
            
        except Exception as e:
            logger.warning(f"语义层获取失败（继续执行）: {e}")
        
        return semantic_info


# ============================================================================
# 节点函数 (用于 LangGraph 图)
# ============================================================================

async def schema_analysis_node(state: SQLMessageState) -> Dict[str, Any]:
    """
    Schema 分析节点函数 - 用于 LangGraph 图
    """
    agent = SchemaAnalysisAgent()
    return await agent.process(state)


# ============================================================================
# 导出
# ============================================================================

# 创建全局实例（兼容现有代码）
schema_agent = SchemaAnalysisAgent()

__all__ = [
    "schema_agent",
    "schema_analysis_node",
    "analyze_user_query",
    "retrieve_database_schema",
    "SchemaAnalysisAgent",
]
