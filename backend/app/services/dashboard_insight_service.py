"""
Dashboard洞察分析服务
负责数据聚合、条件应用、洞察生成编排
优化：支持异步后台处理
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
import asyncio
from sqlalchemy.orm import Session

from app import crud, schemas
from app.models.dashboard_widget import DashboardWidget
from app.services.graph_relationship_service import graph_relationship_service
from app.db.session import SessionLocal
from app.services.text2sql_utils import retrieve_relevant_schema, format_schema_for_prompt
from app.core.agent_config import get_agent_llm, CORE_AGENT_SQL_GENERATOR
from langchain_core.messages import SystemMessage, HumanMessage

class DashboardInsightService:
    """Dashboard洞察分析服务"""
    
    def _build_table_column_whitelist(self, schema_context: dict) -> tuple[str, set, dict]:
        """
        构建表/列白名单，防止 LLM 幻觉
        
        Returns:
            whitelist_str: 格式化的白名单字符串
            valid_tables: 有效表名集合
            valid_columns: {table_name: [column_names]} 字典
        """
        valid_tables = set()
        valid_columns = {}  # {table_name: [column_names]}
        
        tables = schema_context.get("tables", [])
        columns = schema_context.get("columns", [])
        relationships = schema_context.get("relationships", [])
        
        # 构建表名集合
        for t in tables:
            table_name = t.get("name", "")
            if table_name:
                valid_tables.add(table_name)
                valid_columns[table_name] = []
        
        # 构建列名映射
        for c in columns:
            table_name = c.get("table_name", "")
            col_name = c.get("name", "")
            if table_name and col_name:
                if table_name not in valid_columns:
                    valid_columns[table_name] = []
                valid_columns[table_name].append(col_name)
        
        # 构建白名单字符串
        whitelist_parts = []
        whitelist_parts.append("=" * 60)
        whitelist_parts.append("【重要】可用表和字段白名单（仅允许使用以下表和字段）")
        whitelist_parts.append("=" * 60)
        
        for table_name in sorted(valid_tables):
            cols = valid_columns.get(table_name, [])
            # 找到表的描述
            table_desc = ""
            for t in tables:
                if t.get("name") == table_name:
                    table_desc = t.get("description", "")
                    break
            
            whitelist_parts.append(f"\n表名: {table_name}")
            if table_desc:
                whitelist_parts.append(f"  描述: {table_desc}")
            whitelist_parts.append(f"  可用字段: {', '.join(cols)}")
        
        # 添加关系信息
        if relationships:
            whitelist_parts.append("\n" + "-" * 40)
            whitelist_parts.append("表间关系（JOIN 时必须使用这些关联字段）:")
            # 遍历所有关系，不限制数量以确保 JOIN 准确性
            for rel in relationships:
                src = f"{rel.get('source_table', '')}.{rel.get('source_column', '')}"
                tgt = f"{rel.get('target_table', '')}.{rel.get('target_column', '')}"
                whitelist_parts.append(f"  - {src} -> {tgt}")
        
        whitelist_parts.append("\n" + "=" * 60)
        whitelist_parts.append("【警告】严禁使用上述白名单之外的任何表或字段！")
        whitelist_parts.append("=" * 60)
        
        return "\n".join(whitelist_parts), valid_tables, valid_columns
    
    def _validate_sql_against_whitelist(
        self, 
        sql: str, 
        valid_tables: set, 
        valid_columns: dict,
        db_type: str = "MYSQL"
    ) -> tuple[bool, str, list]:
        """
        验证 SQL 是否只使用了白名单中的表和列
        
        Returns:
            is_valid: 是否有效
            error_msg: 错误信息
            invalid_refs: 无效引用列表
        """
        import re
        
        sql_upper = sql.upper()
        invalid_refs = []
        
        # 1. 检查是否是 SELECT 语句（支持 WITH CTE）
        sql_stripped = sql_upper.strip()
        if not (sql_stripped.startswith("SELECT") or sql_stripped.startswith("WITH")):
            return False, "SQL 必须是 SELECT 语句或 WITH CTE", ["non-select"]
        
        # 2. 检查危险关键词
        dangerous_keywords = ["DROP", "DELETE", "TRUNCATE", "UPDATE", "INSERT", "ALTER", "CREATE"]
        for kw in dangerous_keywords:
            if kw in sql_upper and "SELECT" not in sql_upper[:20]:
                return False, f"检测到危险操作: {kw}", [kw]
        
        # 3. 提取 SQL 中的表名
        # 匹配 FROM/JOIN 后的表名
        table_pattern = r'(?:FROM|JOIN)\s+[`"\[]?([a-zA-Z_][a-zA-Z0-9_]*)[`"\]]?'
        found_tables = re.findall(table_pattern, sql, re.IGNORECASE)
        
        # 检查表名是否在白名单中
        valid_tables_lower = {t.lower() for t in valid_tables}
        for table in found_tables:
            if table.lower() not in valid_tables_lower:
                invalid_refs.append(f"表 '{table}' 不在白名单中")
        
        # 4. 提取并检查列名（简化检查，只检查 table.column 格式）
        # 匹配 table.column 或 alias.column 格式
        col_pattern = r'([a-zA-Z_][a-zA-Z0-9_]*)\s*\.\s*[`"\[]?([a-zA-Z_][a-zA-Z0-9_]*)[`"\]]?'
        found_cols = re.findall(col_pattern, sql, re.IGNORECASE)
        
        # 构建所有有效列名的小写集合
        all_valid_cols_lower = set()
        for cols in valid_columns.values():
            for col in cols:
                all_valid_cols_lower.add(col.lower())
        
        # 检查列名（容忍一些常见的别名）
        common_aliases = {'t', 't1', 't2', 'a', 'b', 'c', 's', 'm', 'o', 'p', 'd', 'main', 'sub'}
        for table_or_alias, col in found_cols:
            # 如果是常见别名，只检查列名是否存在
            if table_or_alias.lower() in common_aliases:
                if col.lower() not in all_valid_cols_lower:
                    invalid_refs.append(f"列 '{col}' 不在白名单中")
            else:
                # 检查表名和列名
                table_lower = table_or_alias.lower()
                col_lower = col.lower()
                
                # 在所有表中查找该列
                col_found = False
                for t_name, t_cols in valid_columns.items():
                    if col_lower in [c.lower() for c in t_cols]:
                        col_found = True
                        break
                
                if not col_found and col_lower not in all_valid_cols_lower:
                    invalid_refs.append(f"列 '{table_or_alias}.{col}' 不在白名单中")
        
        if invalid_refs:
            return False, f"发现 {len(invalid_refs)} 个无效引用", invalid_refs
        
        return True, "", []
    
    async def generate_mining_suggestions(self, db: Session, request: schemas.MiningRequest) -> schemas.MiningResponse:
        """生成智能挖掘建议（优化版：防幻觉 + SQL 验证）"""
        import logging
        logger = logging.getLogger(__name__)
        
        logger.info(f"[Mining] 开始生成挖掘建议, connection_id={request.connection_id}, intent={request.intent}")
        
        # 0. 获取数据库连接信息
        from app.models.db_connection import DBConnection
        connection = db.query(DBConnection).filter(DBConnection.id == request.connection_id).first()
        db_type = connection.db_type.upper() if connection else "MYSQL"
        logger.info(f"[Mining] 数据库类型: {db_type}")
        
        # 1. 获取上下文
        if request.intent:
            schema_context = retrieve_relevant_schema(db, request.connection_id, request.intent)
        else:
            tables = crud.schema_table.get_by_connection(db=db, connection_id=request.connection_id)
            
            if not tables:
                logger.warning(f"[Mining] 未找到表, connection_id={request.connection_id}")
                return schemas.MiningResponse(suggestions=[])
            
            logger.info(f"[Mining] 找到 {len(tables)} 个表")
            
            tables_list = []
            columns_list = []
            table_names = []
            
            # 遍历所有表，不限制数量以确保 SQL 生成准确性
            for table in tables:
                table_names.append(table.table_name)
                tables_list.append({
                    "id": table.id,
                    "name": table.table_name,
                    "description": table.description or ""
                })
                
                columns = crud.schema_column.get_by_table(db=db, table_id=table.id)
                for col in columns:
                    columns_list.append({
                        "id": col.id,
                        "name": col.column_name,
                        "type": col.data_type,
                        "description": col.description or "",
                        "is_primary_key": col.is_primary_key,
                        "is_foreign_key": col.is_foreign_key,
                        "table_id": table.id,
                        "table_name": table.table_name
                    })
            
            # 获取表之间的关系
            relationships = []
            try:
                relationship_context = graph_relationship_service.query_table_relationships(
                    connection_id=request.connection_id,
                    table_names=table_names
                )
                if relationship_context.get("direct_relationships"):
                    for rel in relationship_context["direct_relationships"]:
                        relationships.append({
                            "source_table": rel.get("source_table"),
                            "source_column": rel.get("source_column"),
                            "target_table": rel.get("target_table"),
                            "target_column": rel.get("target_column"),
                            "relationship_type": rel.get("relationship_type", "references")
                        })
                    logger.info(f"[Mining] 找到 {len(relationships)} 个表间关系")
            except Exception as e:
                logger.warning(f"[Mining] 获取表关系失败: {e}")
            
            schema_context = {
                "tables": tables_list,
                "columns": columns_list,
                "relationships": relationships
            }
        
        if not schema_context.get("tables"):
            logger.warning("[Mining] schema_context 中无表")
            return schemas.MiningResponse(suggestions=[])
        
        # 2. 构建表/列白名单（防幻觉核心）
        whitelist_str, valid_tables, valid_columns = self._build_table_column_whitelist(schema_context)
        logger.info(f"[Mining] 白名单包含 {len(valid_tables)} 个表, 共 {sum(len(cols) for cols in valid_columns.values())} 个字段")
        
        # 3. 格式化 Schema
        schema_str = format_schema_for_prompt(schema_context)
        
        # 3. 构建 Prompt（要求返回 JSON 格式）
        # 根据数据库类型提供 SQL 语法指南
        sql_syntax_guides = {
            "MYSQL": """
SQL 语法注意事项（MySQL）：
- 使用 LIMIT 而不是 FETCH FIRST
- 字符串连接使用 CONCAT() 函数
- 日期格式化使用 DATE_FORMAT()
- 不支持 FULL OUTER JOIN，请使用 LEFT JOIN 或 RIGHT JOIN
- 使用反引号 ` 包裹保留字
- 布尔值使用 1/0 或 TRUE/FALSE""",
            "POSTGRESQL": """
SQL 语法注意事项（PostgreSQL）：
- 可使用 LIMIT 或 FETCH FIRST
- 字符串连接使用 || 操作符
- 日期格式化使用 TO_CHAR()
- 支持 FULL OUTER JOIN
- 使用双引号 " 包裹保留字
- 支持 ARRAY 类型和 JSON 操作""",
            "SQLITE": """
SQL 语法注意事项（SQLite）：
- 使用 LIMIT，不支持 FETCH FIRST
- 字符串连接使用 || 操作符
- 日期函数使用 strftime()
- 不支持 FULL OUTER JOIN 和 RIGHT JOIN
- 使用双引号 " 或方括号 [] 包裹保留字
- 类型系统灵活，无严格类型检查""",
            "SQLSERVER": """
SQL 语法注意事项（SQL Server / MSSQL）：
- 使用 TOP N 或 OFFSET...FETCH
- 字符串连接使用 + 操作符或 CONCAT()
- 日期格式化使用 FORMAT() 或 CONVERT()
- 支持 FULL OUTER JOIN
- 使用方括号 [] 包裹保留字
- 使用 GETDATE() 获取当前时间""",
            "ORACLE": """
SQL 语法注意事项（Oracle）：
- 使用 ROWNUM 或 FETCH FIRST（12c+）
- 字符串连接使用 || 操作符
- 日期格式化使用 TO_CHAR()
- 支持 FULL OUTER JOIN
- 使用双引号 " 包裹保留字
- 使用 SYSDATE 获取当前时间
- FROM 子句必须有表（可用 DUAL）""",
            "MARIADB": """
SQL 语法注意事项（MariaDB）：
- 语法与 MySQL 基本兼容
- 使用 LIMIT 而不是 FETCH FIRST
- 字符串连接使用 CONCAT() 函数
- 日期格式化使用 DATE_FORMAT()
- 不支持 FULL OUTER JOIN
- 使用反引号 ` 包裹保留字""",
            "CLICKHOUSE": """
SQL 语法注意事项（ClickHouse）：
- 使用 LIMIT 进行分页
- 字符串连接使用 concat() 或 ||
- 日期函数使用 formatDateTime()
- 支持 FULL OUTER JOIN (部分版本)
- 区分大小写，使用双引号包裹
- 专为 OLAP 优化，聚合查询性能优异""",
        }
        
        db_type_upper = db_type.upper()
        # 尝试匹配数据库类型，支持模糊匹配
        sql_syntax_guide = ""
        for key, guide in sql_syntax_guides.items():
            if key in db_type_upper or db_type_upper in key:
                sql_syntax_guide = guide
                break
        
        # 如果没有匹配到，提供通用指南
        if not sql_syntax_guide:
            sql_syntax_guide = f"""
SQL 语法注意事项（{db_type}）：
- 请使用标准 ANSI SQL 语法
- 避免使用数据库特定的扩展语法
- 使用通用的聚合函数（SUM, COUNT, AVG, MAX, MIN）
- 使用标准的 JOIN 语法（INNER JOIN, LEFT JOIN）
- 日期函数请根据实际数据库调整"""
        
        prompt = f"""你是一个智能数据分析师。请基于以下数据库结构，推荐 {request.limit} 个有价值的数据分析视角（图表）。

目标数据库类型：{db_type}
{sql_syntax_guide}

用户意图：{request.intent or "自动发现关键业务指标和趋势"}

{whitelist_str}

数据库结构详情：
{schema_str}

挖掘维度要求（请覆盖多个维度）：
- business（业务数据）：核心业务指标、KPI
- metric（指标分析）：关键数值的统计分布
- trend（趋势分析）：时间序列变化
- semantic（语义关联）：基于字段语义发现的关联分析

【核心约束 - 必须严格遵守】：
1. SQL 中的表名和列名必须严格匹配上述白名单，禁止使用任何白名单之外的表或字段
2. JOIN 时必须使用白名单中指定的关联字段，不得自行推测
3. 推荐的 SQL 必须是合法的 {db_type} SELECT 语句
4. 图表类型从以下选择：bar, line, pie, scatter, table
5. 每个推荐都要有明确的业务价值和推荐理由
6. SQL 尽量包含聚合分析（SUM, COUNT, AVG, GROUP BY）
7. 严格遵循 {db_type} 的 SQL 语法规范

请以 JSON 格式返回，格式如下：
{{{{
  "suggestions": [
    {{{{
      "title": "图表标题",
      "description": "简短描述（一句话）",
      "reasoning": "详细推荐理由：为什么这个分析对业务有价值，数据逻辑是什么",
      "mining_dimension": "business|metric|trend|semantic",
      "confidence": 0.85,
      "chart_type": "bar|line|pie|scatter|table",
      "sql": "SELECT ...",
      "source_tables": ["表名1", "表名2"],
      "key_fields": ["关键字段1", "关键字段2"],
      "business_value": "这个分析能帮助业务做什么决策",
      "suggested_actions": ["建议动作1", "建议动作2"],
      "analysis_intent": "分析意图描述"
    }}}}
  ]
}}}}

只返回 JSON，不要有其他文字。
"""
        
        # 4. 调用 LLM（使用 LLMWrapper 统一处理重试和超时）
        try:
            import json
            from app.core.llm_wrapper import LLMWrapper, LLMWrapperConfig
            from app.core.llms import get_default_model
            from app.models.agent_profile import AgentProfile
            from app.models.llm_config import LLMConfiguration
            from app.core.config import settings
            
            # 获取 Agent 配置
            profile = db.query(AgentProfile).filter(AgentProfile.name == CORE_AGENT_SQL_GENERATOR).first()
            
            # 获取 LLM 配置
            llm_config = None
            if profile and profile.llm_config_id:
                llm_config = db.query(LLMConfiguration).filter(
                    LLMConfiguration.id == profile.llm_config_id,
                    LLMConfiguration.is_active == True
                ).first()
            
            # 使用 LLMWrapper（统一重试策略，无超时限制）
            llm = get_default_model(config_override=llm_config, caller="dashboard_mining")
            wrapper_config = LLMWrapperConfig(
                max_retries=3,
                retry_base_delay=2.0,
                enable_tracing=settings.LANGCHAIN_TRACING_V2,
            )
            wrapper = LLMWrapper(llm=llm, config=wrapper_config, name="dashboard_mining")
            
            response = await wrapper.ainvoke([
                SystemMessage(content="你是一个专业的数据分析师。只返回 JSON 格式的响应。"),
                HumanMessage(content=prompt)
            ])
            
            # 解析 LLM 返回的 JSON
            response_text = response.content if hasattr(response, 'content') else str(response)
            # 清理可能的 markdown 代码块
            response_text = response_text.strip()
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            response_text = response_text.strip()
            
            parsed = json.loads(response_text)
            raw_suggestions = parsed.get("suggestions", [])
            logger.info(f"[Mining] LLM 返回 {len(raw_suggestions)} 个原始建议")
            
            # 5. 验证每个 SQL 并过滤无效的
            validated_suggestions = []
            invalid_count = 0
            
            for idx, s in enumerate(raw_suggestions):
                sql = s.get("sql", "")
                title = s.get("title", f"建议{idx+1}")
                
                if not sql:
                    logger.warning(f"[Mining] 建议 '{title}' 无 SQL，跳过")
                    invalid_count += 1
                    continue
                
                # 验证 SQL
                is_valid, error_msg, invalid_refs = self._validate_sql_against_whitelist(
                    sql, valid_tables, valid_columns, db_type
                )
                
                if not is_valid:
                    logger.warning(f"[Mining] 建议 '{title}' SQL 验证失败: {error_msg}")
                    for ref in invalid_refs[:3]:  # 最多显示3个无效引用
                        logger.warning(f"[Mining]   - {ref}")
                    invalid_count += 1
                    # 降低置信度但仍然保留（让用户决定）
                    s["confidence"] = max(0.3, float(s.get("confidence", 0.8)) - 0.4)
                    s["reasoning"] = f"【警告】{error_msg}\n\n" + s.get("reasoning", "")
                
                validated_suggestions.append(
                    schemas.MiningSuggestion(
                        title=s.get("title", ""),
                        description=s.get("description", ""),
                        chart_type=s.get("chart_type", "bar"),
                        sql=sql,
                        analysis_intent=s.get("analysis_intent", s.get("title", "数据分析")),
                        reasoning=s.get("reasoning", s.get("description", "")),
                        mining_dimension=s.get("mining_dimension", "business"),
                        confidence=float(s.get("confidence", 0.8)),
                        source_tables=s.get("source_tables", []),
                        key_fields=s.get("key_fields", []),
                        business_value=s.get("business_value", ""),
                        suggested_actions=s.get("suggested_actions", [])
                    )
                )
            
            # 按置信度排序，高置信度的排在前面
            validated_suggestions.sort(key=lambda x: x.confidence, reverse=True)
            
            logger.info(f"[Mining] 最终返回 {len(validated_suggestions)} 个建议, {invalid_count} 个 SQL 验证失败")
            return schemas.MiningResponse(suggestions=validated_suggestions)
            
        except json.JSONDecodeError as e:
            logger.error(f"[Mining] JSON 解析失败: {e}")
            logger.error(f"[Mining] 原始响应: {response_text[:500]}...")
            return schemas.MiningResponse(suggestions=[])
        except Exception as e:
            logger.error(f"[Mining] 建议生成失败: {e}", exc_info=True)
            return schemas.MiningResponse(suggestions=[])

    def trigger_dashboard_insights(
        self,
        db: Session,
        dashboard_id: int,
        user_id: int,
        request: schemas.DashboardInsightRequest
    ) -> schemas.DashboardInsightResponse:
        """
        触发看板洞察生成（创建占位Widget，后续由后台任务处理）
        """
        # 1. 检查权限
        self._check_permission(db, dashboard_id, user_id)
        
        # 2. 获取Dashboard
        dashboard = crud.crud_dashboard.get(db, id=dashboard_id)
        if not dashboard:
            raise ValueError(f"Dashboard {dashboard_id} not found")
            
        # 3. 创建或更新Widget为"分析中"状态
        # 创建初始的空结果
        initial_result = schemas.InsightResult(
            summary=schemas.InsightSummary(total_rows=0, key_metrics={}, time_range="分析中..."),
            trends=None, anomalies=[], correlations=[], recommendations=[]
        )
        
        # 创建或更新 Widget (同步)
        widget_id = self._create_or_update_insight_widget(
            db,
            dashboard_id,
            initial_result,
            request.conditions,
            request.use_graph_relationships,
            analyzed_widget_count=0,
            status="processing" # 标记为处理中
        )
        
        return schemas.DashboardInsightResponse(
            widget_id=widget_id,
            insights=initial_result,
            analyzed_widget_count=0,
            analysis_timestamp=datetime.utcnow(),
            applied_conditions=request.conditions,
            relationship_count=0,
            status="processing" # 新增状态字段
        )

    async def process_dashboard_insights_task(
        self,
        dashboard_id: int,
        user_id: int,
        request: schemas.DashboardInsightRequest,
        widget_id: int
    ):
        """
        后台任务：执行实际的洞察分析逻辑
        
        P1-FIX: 优化Session生命周期管理，使用上下文管理器和更健壮的错误处理
        注意: LLM 重试由 LLMWrapper 统一处理，此处不再需要外层重试逻辑
        """
        import logging
        from contextlib import contextmanager
        
        logger = logging.getLogger(__name__)
        
        @contextmanager
        def get_db_session():
            """P1-FIX: 使用上下文管理器确保Session正确关闭"""
            session = SessionLocal()
            try:
                yield session
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()
        
        with get_db_session() as db:
            try:
                logger.info(f"🚀 开始后台洞察分析 Task (Dashboard: {dashboard_id}, Widget: {widget_id})")
                
                # 1. 获取数据
                dashboard = crud.crud_dashboard.get(db, id=dashboard_id)
                if not dashboard:
                    raise ValueError(f"Dashboard {dashboard_id} not found")
                
                widgets = dashboard.widgets
                
                # 筛选Widgets
                if request.included_widget_ids:
                    widgets = [w for w in widgets if w.id in request.included_widget_ids]
                
                data_widgets = [w for w in widgets if w.widget_type != "insight_analysis"]
                
                if not data_widgets:
                    logger.warning(f"⚠️ Dashboard {dashboard_id} 无有效数据组件，跳过分析")
                    self._update_widget_status(db, widget_id, "completed", "无数据组件可分析")
                    return

                if getattr(request, "force_requery", False):
                    self._refresh_data_widgets(db, data_widgets, user_id)
                    refreshed_widgets = []
                    for w in data_widgets:
                        w2 = crud.crud_dashboard_widget.get(db, id=w.id)
                        if w2 and w2.widget_type != "insight_analysis":
                            refreshed_widgets.append(w2)
                    data_widgets = refreshed_widgets

                # 2. 聚合数据
                aggregated_data = self._aggregate_widget_data(data_widgets, request.conditions)
                logger.info(f"📊 聚合数据完成: {aggregated_data['total_rows']} 行, {len(aggregated_data['table_names'])} 个表")
                
                # 3. 图谱查询（带重试）
                relationship_context = None
                relationship_count = 0
                if request.use_graph_relationships and aggregated_data["table_names"]:
                    try:
                        connection_id = data_widgets[0].connection_id
                        relationship_context = graph_relationship_service.query_table_relationships(
                            connection_id,
                            aggregated_data["table_names"]
                        )
                        relationship_count = relationship_context.get("relationship_count", 0)
                        logger.info(f"🔗 图谱关系查询完成: {relationship_count} 个关系")
                    except Exception as e:
                        logger.warning(f"⚠️ 图谱关系查询失败: {e}")

                # 4. 洞察分析（带重试机制）
                insights = None
                retry_count = 0
                max_retries = 0  # 当前使用规则引擎，无需重试
                while retry_count <= max_retries:
                    try:
                        analysis_method_parts = [
                            "service_rule_based",
                            "widget_grouped",
                            "adaptive_time_filter",
                            "time_sorted_trend",
                            "iqr_anomaly",
                            "coerced_dimension_filters",
                        ]
                        if request.use_graph_relationships:
                            analysis_method_parts.append("graph_relationships")
                        analysis_method = "+".join(analysis_method_parts)

                        widget_groups = aggregated_data.get("by_widget") or []
                        has_time_series = any(
                            (g.get("date_columns") and g.get("numeric_columns") and (g.get("row_count") or 0) >= 2)
                            for g in widget_groups
                        )
                        confidence = 0.8
                        total_rows = int(aggregated_data.get("total_rows") or 0)
                        if total_rows < 10:
                            confidence = 0.5
                        elif total_rows < 50:
                            confidence = 0.65
                        elif total_rows < 200:
                            confidence = 0.75
                        else:
                            confidence = 0.82
                        if widget_groups and len(widget_groups) > 1:
                            confidence -= 0.02
                        if not has_time_series:
                            confidence -= 0.08
                        if relationship_count > 0:
                            confidence += 0.05
                        confidence = max(0.3, min(0.95, round(confidence, 2)))

                        insights = schemas.InsightResult(
                            summary=schemas.InsightSummary(
                                total_rows=aggregated_data["total_rows"],
                                key_metrics=self._extract_key_metrics(aggregated_data),
                                time_range="已分析"
                            ),
                            trends=self._analyze_trends(aggregated_data),
                            anomalies=self._detect_anomalies(aggregated_data),
                            correlations=self._find_correlations(aggregated_data, relationship_context),
                            recommendations=[
                                schemas.InsightRecommendation(
                                    type="info",
                                    content=f"已分析 {len(data_widgets)} 个数据组件，共 {aggregated_data['total_rows']} 条数据",
                                    priority="medium"
                                ),
                                schemas.InsightRecommendation(
                                    type="info",
                                    content="趋势：按组件分别识别时间列并按时间排序，对数值列计算变化幅度后选最显著项",
                                    priority="low"
                                ),
                                schemas.InsightRecommendation(
                                    type="info",
                                    content="异常：使用 IQR 方法检测离群值（下界=Q1-1.5×IQR，上界=Q3+1.5×IQR）",
                                    priority="low"
                                ),
                            ]
                        )

                        trend_meta = aggregated_data.get("_trend_metadata") or {}
                        if isinstance(trend_meta.get("values"), list) and len(trend_meta["values"]) >= 5:
                            try:
                                from app.services.prediction_service import prediction_service

                                accuracy = prediction_service._calculate_accuracy_enhanced(
                                    trend_meta["values"],
                                    "linear",
                                    {}
                                )
                                trend_meta["accuracy_mape"] = accuracy.mape
                                trend_meta["accuracy_rmse"] = accuracy.rmse
                                trend_meta["accuracy_mae"] = accuracy.mae
                                trend_meta["accuracy_r_squared"] = accuracy.r_squared

                                quality_conf = 1 - min(100.0, max(0.0, float(accuracy.mape))) / 100.0
                                confidence = 0.6 * confidence + 0.4 * quality_conf
                                confidence = max(0.3, min(0.95, round(confidence, 2)))

                                if trend_meta.get("r_squared") is not None:
                                    analysis_method = (
                                        f"{analysis_method}"
                                        f"+trend_r2={float(trend_meta['r_squared']):.2f}"
                                        f"+mape={float(accuracy.mape):.1f}%"
                                    )
                            except Exception:
                                pass
                        break
                    except Exception as e:
                        retry_count += 1
                        if retry_count > max_retries:
                            logger.error(f"❌ 洞察分析失败，已重试 {max_retries} 次: {e}")
                            raise
                        logger.warning(f"⚠️ 洞察分析失败，第 {retry_count} 次重试: {e}")
                        await asyncio.sleep(1)  # 重试前等待
                
                # 5. 更新 Widget 状态为完成
                self._update_insight_widget_result(
                    db, 
                    widget_id, 
                    insights, 
                    len(data_widgets),
                    status="completed",
                    analysis_method=analysis_method,
                    confidence_score=confidence,
                    relationship_count=relationship_count,
                    source_tables=aggregated_data.get("table_names"),
                    extra_metrics=aggregated_data.get("_trend_metadata")
                )
                
                logger.info(f"✅ 后台洞察分析完成 (Widget: {widget_id})")
                
            except Exception as e:
                logger.exception(f"❌ 后台洞察分析失败: dashboard_id={dashboard_id}, widget_id={widget_id}")
                # P1-FIX: 在同一个Session中更新失败状态
                try:
                    db.rollback()  # 先回滚之前的任何未提交的更改
                    self._update_widget_status(db, widget_id, "failed", str(e))
                except Exception as update_error:
                    logger.error(f"更新失败状态时出错: {update_error}")
    
    def _extract_key_metrics(self, aggregated_data: dict) -> dict:
        """从聚合数据中提取关键指标"""
        key_metrics = {}

        def _as_float(value: Any):
            if value is None:
                return None
            if isinstance(value, (int, float)):
                return float(value)
            s = str(value).strip()
            if not s:
                return None
            try:
                return float(s.replace(",", ""))
            except Exception:
                return None

        widget_groups = aggregated_data.get("by_widget")
        if widget_groups:
            total_added = 0
            for g in widget_groups:
                data = g.get("data") or []
                numeric_columns = g.get("numeric_columns") or []
                if not data or not numeric_columns:
                    continue
                prefix = g.get("table_name") or (g.get("title") or f"widget_{g.get('widget_id')}")
                for col in numeric_columns[:5]:
                    values = [_as_float(row.get(col)) for row in data]
                    numeric_values = [v for v in values if v is not None]
                    if not numeric_values:
                        continue
                    key = f"{prefix}.{col}"
                    key_metrics[key] = {
                        "sum": round(sum(numeric_values), 2),
                        "avg": round(sum(numeric_values) / len(numeric_values), 2),
                        "max": round(max(numeric_values), 2),
                        "min": round(min(numeric_values), 2),
                        "count": len(numeric_values)
                    }
                    total_added += 1
                    if total_added >= 12:
                        return key_metrics
            return key_metrics

        data = aggregated_data.get("data", [])
        numeric_columns = aggregated_data.get("numeric_columns", [])

        if not data or not numeric_columns:
            return key_metrics

        for col in numeric_columns[:5]:
            numeric_values = [_as_float(row.get(col)) for row in data]
            numeric_values = [v for v in numeric_values if v is not None]
            if numeric_values:
                key_metrics[col] = {
                    "sum": round(sum(numeric_values), 2),
                    "avg": round(sum(numeric_values) / len(numeric_values), 2),
                    "max": round(max(numeric_values), 2),
                    "min": round(min(numeric_values), 2),
                    "count": len(numeric_values)
                }
        
        return key_metrics
    
    def _analyze_trends(self, aggregated_data: dict) -> Optional[schemas.InsightTrend]:
        """分析数据趋势"""
        try:
            from datetime import datetime, date

            def _try_parse_datetime(value: Any):
                if value is None:
                    return None
                if isinstance(value, datetime):
                    return value
                if isinstance(value, date):
                    return datetime.combine(value, datetime.min.time())
                s = str(value).strip()
                if not s:
                    return None
                try:
                    return datetime.fromisoformat(s.replace("Z", "+00:00"))
                except Exception:
                    return None

            def _as_float(value: Any):
                if value is None:
                    return None
                if isinstance(value, (int, float)):
                    return float(value)
                s = str(value).strip()
                if not s:
                    return None
                try:
                    return float(s.replace(",", ""))
                except Exception:
                    return None

            def _pick_date_column(cols: List[str]) -> str:
                if not cols:
                    return ""
                for c in cols:
                    if any(kw in c.lower() for kw in ("created", "updated", "date", "time", "at", "日期", "时间")):
                        return c
                return cols[0]

            def _r_squared(values: List[float]) -> float:
                n = len(values)
                if n < 3:
                    return 0.0
                y_mean = sum(values) / n
                ss_tot = sum((y - y_mean) ** 2 for y in values)
                if ss_tot == 0:
                    return 1.0
                x_mean = (n - 1) / 2
                ss_xx = sum((i - x_mean) ** 2 for i in range(n))
                if ss_xx == 0:
                    return 0.0
                ss_xy = sum((i - x_mean) * (values[i] - y_mean) for i in range(n))
                slope = ss_xy / ss_xx
                intercept = y_mean - slope * x_mean
                predicted = [intercept + slope * i for i in range(n)]
                ss_res = sum((values[i] - predicted[i]) ** 2 for i in range(n))
                r2 = 1 - (ss_res / ss_tot)
                return max(0.0, min(1.0, float(r2)))

            widget_groups = aggregated_data.get("by_widget")
            best = None
            if widget_groups:
                for g in widget_groups:
                    data = g.get("data") or []
                    date_columns = g.get("date_columns") or []
                    numeric_columns = g.get("numeric_columns") or []
                    if not date_columns or not numeric_columns or len(data) < 2:
                        continue
                    date_col = _pick_date_column(date_columns)
                    prefix = g.get("table_name") or (g.get("title") or f"widget_{g.get('widget_id')}")

                    for num_col in numeric_columns:
                        points = []
                        for row in data:
                            dt = _try_parse_datetime(row.get(date_col))
                            val = _as_float(row.get(num_col))
                            if dt is not None and val is not None:
                                points.append((dt, val))
                        if len(points) < 2:
                            continue
                        points.sort(key=lambda x: x[0])
                        first_dt, first_val = points[0]
                        last_dt, last_val = points[-1]
                        values = [p[1] for p in points]
                        delta = last_val - first_val
                        if first_val != 0:
                            rate = (delta / first_val) * 100
                            score = abs(rate)
                        else:
                            rate = None
                            score = abs(delta)
                        metric_name = f"{prefix}.{num_col}"
                        r2 = _r_squared(values)
                        candidate = {
                            "score": score,
                            "metric_name": metric_name,
                            "first_val": first_val,
                            "last_val": last_val,
                            "rate": rate,
                            "first_dt": first_dt,
                            "last_dt": last_dt,
                            "values": values,
                            "r_squared": r2,
                        }
                        if best is None or candidate["score"] > best["score"]:
                            best = candidate

            if best is None:
                date_columns = aggregated_data.get("date_columns", [])
                numeric_columns = aggregated_data.get("numeric_columns", [])
                data = aggregated_data.get("data", [])
                if not date_columns or not numeric_columns or len(data) < 2:
                    return None
                date_col = _pick_date_column(date_columns)
                for num_col in numeric_columns:
                    points = []
                    for row in data:
                        dt = _try_parse_datetime(row.get(date_col))
                        val = _as_float(row.get(num_col))
                        if dt is not None and val is not None:
                            points.append((dt, val))
                    if len(points) < 2:
                        continue
                    points.sort(key=lambda x: x[0])
                    first_dt, first_val = points[0]
                    last_dt, last_val = points[-1]
                    values = [p[1] for p in points]
                    delta = last_val - first_val
                    if first_val != 0:
                        rate = (delta / first_val) * 100
                        score = abs(rate)
                    else:
                        rate = None
                        score = abs(delta)
                    r2 = _r_squared(values)
                    candidate = {
                        "score": score,
                        "metric_name": num_col,
                        "first_val": first_val,
                        "last_val": last_val,
                        "rate": rate,
                        "first_dt": first_dt,
                        "last_dt": last_dt,
                        "values": values,
                        "r_squared": r2,
                    }
                    if best is None or candidate["score"] > best["score"]:
                        best = candidate

            if best is None:
                return None

            metric_name = best["metric_name"]
            first_val = best["first_val"]
            last_val = best["last_val"]
            rate = best["rate"]
            first_dt = best["first_dt"]
            last_dt = best["last_dt"]
            r2 = best["r_squared"]
            direction = "up" if last_val > first_val else ("down" if last_val < first_val else "stable")
            if rate is not None:
                rate = round(rate, 2)
                desc = f"{metric_name} 从 {first_val} 变化到 {last_val}（{first_dt.date()}→{last_dt.date()}），变化率 {rate}%（R²={r2:.2f}）"
            else:
                desc = f"{metric_name} 从 {first_val} 变化到 {last_val}（{first_dt.date()}→{last_dt.date()}），变化量 {round(last_val - first_val, 2)}（R²={r2:.2f}）"

            aggregated_data["_trend_metadata"] = {
                "metric": metric_name,
                "r_squared": round(r2, 4),
                "values": best.get("values") or [],
                "point_count": len(best.get("values") or []),
            }

            return schemas.InsightTrend(
                trend_direction=direction,
                total_growth_rate=rate,
                description=desc
            )
        except Exception:
            pass
        
        return None
    
    def _detect_anomalies(self, aggregated_data: dict) -> List[schemas.InsightAnomaly]:
        """检测数据异常"""
        anomalies = []

        def _severity_score(s: Optional[str]) -> int:
            if s == "high":
                return 3
            if s == "medium":
                return 2
            return 1

        def _detect_for_series(metric_name: str, values: List[float]) -> List[schemas.InsightAnomaly]:
            if len(values) < 8:
                return []
            values_sorted = sorted(values)

            def _quantile(sorted_vals: List[float], q: float) -> float:
                n = len(sorted_vals)
                if n == 1:
                    return sorted_vals[0]
                pos = (n - 1) * q
                lo = int(pos)
                hi = min(lo + 1, n - 1)
                w = pos - lo
                return sorted_vals[lo] * (1 - w) + sorted_vals[hi] * w

            q1 = _quantile(values_sorted, 0.25)
            q3 = _quantile(values_sorted, 0.75)
            iqr = q3 - q1
            if iqr <= 0:
                return []

            lower = q1 - 1.5 * iqr
            upper = q3 + 1.5 * iqr

            max_val = values_sorted[-1]
            min_val = values_sorted[0]

            found = []
            if max_val > upper:
                exceed = (max_val - upper) / iqr
                severity = "high" if exceed >= 3 else ("medium" if exceed >= 1.5 else "low")
                found.append(schemas.InsightAnomaly(
                    type="outlier",
                    metric=metric_name,
                    description=f"{metric_name} 存在异常高值 {max_val}（上界 {round(upper, 2)}）",
                    severity=severity
                ))
            if min_val < lower:
                exceed = (lower - min_val) / iqr
                severity = "high" if exceed >= 3 else ("medium" if exceed >= 1.5 else "low")
                found.append(schemas.InsightAnomaly(
                    type="outlier",
                    metric=metric_name,
                    description=f"{metric_name} 存在异常低值 {min_val}（下界 {round(lower, 2)}）",
                    severity=severity
                ))
            return found

        def _as_float(value: Any):
            if value is None:
                return None
            if isinstance(value, (int, float)):
                return float(value)
            s = str(value).strip()
            if not s:
                return None
            try:
                return float(s.replace(",", ""))
            except Exception:
                return None

        widget_groups = aggregated_data.get("by_widget")
        if widget_groups:
            for g in widget_groups:
                data = g.get("data") or []
                numeric_columns = g.get("numeric_columns") or []
                if not data or not numeric_columns:
                    continue
                prefix = g.get("table_name") or (g.get("title") or f"widget_{g.get('widget_id')}")
                for col in numeric_columns[:3]:
                    vals = [_as_float(row.get(col)) for row in data]
                    vals = [v for v in vals if v is not None]
                    anomalies.extend(_detect_for_series(f"{prefix}.{col}", vals))
        else:
            data = aggregated_data.get("data", [])
            numeric_columns = aggregated_data.get("numeric_columns", [])
            if not data or not numeric_columns:
                return anomalies
            for col in numeric_columns[:3]:
                vals = [_as_float(row.get(col)) for row in data]
                vals = [v for v in vals if v is not None]
                anomalies.extend(_detect_for_series(col, vals))

        anomalies.sort(key=lambda a: _severity_score(a.severity), reverse=True)
        return anomalies[:5]
    
    def _find_correlations(self, aggregated_data: dict, relationship_context: Optional[dict]) -> List[schemas.InsightCorrelation]:
        """发现数据关联"""
        correlations = []
        
        # 基于图谱关系生成关联洞察
        if relationship_context:
            direct_rels = relationship_context.get("direct_relationships", [])
            for rel in direct_rels[:3]:
                src_table = rel.get("source_table", "")
                tgt_table = rel.get("target_table", "")
                if src_table and tgt_table:
                    correlations.append(schemas.InsightCorrelation(
                        type="cross_table",
                        entities=[src_table, tgt_table],
                        description=f"{src_table} 与 {tgt_table} 存在外键关联",
                        strength=0.8
                    ))
        
        return correlations

    def _check_permission(self, db: Session, dashboard_id: int, user_id: int):
        has_permission = crud.crud_dashboard.check_permission(
            db, dashboard_id=dashboard_id, user_id=user_id, required_level="viewer"
        )
        if not has_permission:
            raise PermissionError("No permission to view this dashboard")

    def _aggregate_widget_data(
        self,
        widgets: List[DashboardWidget],
        conditions: Optional[schemas.InsightConditions]
    ) -> Dict[str, Any]:
        """聚合Widget数据"""
        from datetime import datetime, date

        def _as_float(value: Any):
            if value is None:
                return None
            if isinstance(value, (int, float)):
                return float(value)
            s = str(value).strip()
            if not s:
                return None
            try:
                return float(s.replace(",", ""))
            except Exception:
                return None

        def _try_parse_datetime(value: Any):
            if value is None:
                return None
            if isinstance(value, datetime):
                return value
            if isinstance(value, date):
                return datetime.combine(value, datetime.min.time())
            s = str(value).strip()
            if not s:
                return None
            try:
                return datetime.fromisoformat(s.replace("Z", "+00:00"))
            except Exception:
                return None

        def _infer_columns(rows: List[Dict[str, Any]]) -> Dict[str, List[str]]:
            numeric = set()
            dates = set()
            if not rows:
                return {"numeric": [], "dates": []}

            sample = rows[: min(20, len(rows))]
            keys = set()
            for r in sample:
                if isinstance(r, dict):
                    keys.update(r.keys())

            for k in keys:
                k_lower = str(k).lower()
                if any(keyword in k_lower for keyword in ("date", "time", "created", "updated", "at", "日期", "时间")):
                    for r in sample:
                        dt = _try_parse_datetime(r.get(k)) if isinstance(r, dict) else None
                        if dt is not None:
                            dates.add(k)
                            break

                for r in sample:
                    if not isinstance(r, dict):
                        continue
                    v = r.get(k)
                    fv = _as_float(v)
                    if fv is not None:
                        numeric.add(k)
                        break

            return {"numeric": list(numeric), "dates": list(dates)}

        aggregated_rows = []
        table_names = set()
        numeric_columns = set()
        date_columns = set()
        widget_summaries = []
        by_widget = []
        
        for widget in widgets:
            # 提取widget数据
            if not widget.data_cache or "data" not in widget.data_cache:
                continue
            
            data = widget.data_cache["data"]
            if not data or not isinstance(data, list):
                continue
            
            # 应用条件过滤
            filtered_data = self._apply_conditions(data, conditions)

            table_name = None
            if widget.query_config and isinstance(widget.query_config, dict):
                table_name = widget.query_config.get("table_name")

            inferred = _infer_columns(filtered_data)
            widget_numeric_columns = inferred["numeric"]
            widget_date_columns = inferred["dates"]

            by_widget.append({
                "widget_id": widget.id,
                "title": getattr(widget, "title", None),
                "widget_type": getattr(widget, "widget_type", None),
                "table_name": table_name,
                "row_count": len(filtered_data),
                "numeric_columns": widget_numeric_columns,
                "date_columns": widget_date_columns,
                "data": filtered_data,
            })
            
            aggregated_rows.extend(filtered_data)
            
            # 提取表名
            if table_name:
                table_names.add(table_name)
            
            # 提取列信息
            for c in widget_numeric_columns:
                numeric_columns.add(c)
            for c in widget_date_columns:
                date_columns.add(c)
            
            widget_summaries.append({
                "id": widget.id,
                "type": widget.widget_type,
                "title": widget.title,
                "row_count": len(filtered_data)
            })
        
        return {
            "data": aggregated_rows,
            "total_rows": len(aggregated_rows),
            "table_names": list(table_names),
            "numeric_columns": list(numeric_columns),
            "date_columns": list(date_columns),
            "by_widget": by_widget,
            "widget_summaries": widget_summaries
        }

    def _refresh_data_widgets(self, db: Session, widgets: List[DashboardWidget], user_id: int) -> None:
        from app.services.dashboard_widget_service import dashboard_widget_service

        for w in widgets:
            try:
                dashboard_widget_service.refresh_widget(db, widget_id=w.id, user_id=user_id)
            except Exception:
                logger.exception("刷新数据组件失败: widget_id=%s", w.id)
    
    def _apply_conditions(
        self,
        data: List[Dict[str, Any]],
        conditions: Optional[schemas.InsightConditions]
    ) -> List[Dict[str, Any]]:
        """应用查询条件过滤数据"""
        if not conditions:
            return data
        
        filtered_data = data.copy()
        
        def _try_parse_datetime(value: Any):
            if value is None:
                return None
            from datetime import datetime, date
            if isinstance(value, datetime):
                return value
            if isinstance(value, date):
                return datetime.combine(value, datetime.min.time())
            s = str(value).strip()
            if not s:
                return None
            try:
                return datetime.fromisoformat(s.replace("Z", "+00:00"))
            except Exception:
                pass
            for fmt in (
                "%Y-%m-%d",
                "%Y/%m/%d",
                "%Y-%m-%d %H:%M:%S",
                "%Y/%m/%d %H:%M:%S",
                "%Y-%m-%dT%H:%M:%S",
                "%Y/%m/%dT%H:%M:%S",
            ):
                try:
                    return datetime.strptime(s, fmt)
                except Exception:
                    continue
            return None

        def _calc_relative_range(relative_range: str):
            from datetime import datetime, timedelta
            now = datetime.utcnow()
            key = (relative_range or "").strip().lower()
            if not key:
                return None, None
            if key in {"last_7_days", "7d", "last7days"}:
                return now - timedelta(days=7), now
            if key in {"last_30_days", "30d", "last30days"}:
                return now - timedelta(days=30), now
            if key in {"last_90_days", "90d", "last90days"}:
                return now - timedelta(days=90), now
            if key in {"this_month", "month_to_date", "mtd"}:
                start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                return start, now
            if key in {"this_year", "year_to_date", "ytd"}:
                start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
                return start, now
            return None, None

        def _select_date_column(rows: List[Dict[str, Any]]) -> Optional[str]:
            if not rows:
                return None
            sample = rows[:50]
            keys = list(sample[0].keys())
            keyword_keys = [
                k for k in keys
                if any(kw in k.lower() for kw in ("date", "time", "created", "updated", "at", "日期", "时间"))
            ]
            candidates = keyword_keys + [k for k in keys if k not in keyword_keys]
            best_key = None
            best_ratio = 0.0
            for k in candidates:
                parsed = 0
                seen = 0
                for r in sample:
                    if k not in r:
                        continue
                    seen += 1
                    if _try_parse_datetime(r.get(k)) is not None:
                        parsed += 1
                if seen == 0:
                    continue
                ratio = parsed / seen
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_key = k
            if best_ratio >= 0.6:
                return best_key
            return None

        def _coerce_number(value: Any):
            if value is None:
                return None
            if isinstance(value, (int, float)):
                return float(value)
            s = str(value).strip()
            if not s:
                return None
            try:
                return float(s.replace(",", ""))
            except Exception:
                return None

        def _values_match(row_val: Any, expected: Any) -> bool:
            if row_val is None and expected is None:
                return True
            if row_val is None or expected is None:
                return False
            if isinstance(expected, str) or isinstance(row_val, str):
                row_num = _coerce_number(row_val)
                exp_num = _coerce_number(expected)
                if row_num is not None and exp_num is not None:
                    return row_num == exp_num
                return str(row_val).strip() == str(expected).strip()
            return row_val == expected
        
        # 时间范围过滤
        if conditions.time_range:
            date_column = _select_date_column(filtered_data)
            
            if date_column:
                start_dt = _try_parse_datetime(conditions.time_range.start) if conditions.time_range.start else None
                end_dt = _try_parse_datetime(conditions.time_range.end) if conditions.time_range.end else None
                if (start_dt is None and end_dt is None) and getattr(conditions.time_range, "relative_range", None):
                    start_dt, end_dt = _calc_relative_range(conditions.time_range.relative_range)
                
                if start_dt or end_dt:
                    def _in_range(row: Dict[str, Any]) -> bool:
                        row_dt = _try_parse_datetime(row.get(date_column))
                        if row_dt is None:
                            return False
                        if start_dt and row_dt < start_dt:
                            return False
                        if end_dt and row_dt > end_dt:
                            return False
                        return True
                    
                    filtered_data = [row for row in filtered_data if _in_range(row)]
        
        # 维度筛选
        if conditions.dimension_filters:
            for column, value in conditions.dimension_filters.items():
                if isinstance(value, (list, tuple, set)):
                    allowed = list(value)
                    filtered_data = [
                        row for row in filtered_data
                        if any(_values_match(row.get(column), v) for v in allowed)
                    ]
                else:
                    filtered_data = [row for row in filtered_data if _values_match(row.get(column), value)]
        
        return filtered_data
    
    def _create_or_update_insight_widget(
        self,
        db: Session,
        dashboard_id: int,
        insights: schemas.InsightResult,
        conditions: Optional[schemas.InsightConditions],
        use_graph_relationships: bool,
        analyzed_widget_count: int,
        status: str = "completed",
        lineage: Optional[Dict[str, Any]] = None
    ) -> int:
        """创建或更新洞察Widget，保存溯源信息"""
        existing_widgets = crud.crud_dashboard_widget.get_by_dashboard(db, dashboard_id=dashboard_id)
        
        insight_widget = None
        # P0-FIX: 从现有数据Widget中获取connection_id，避免硬编码
        default_connection_id = None
        for widget in existing_widgets:
            if widget.widget_type == "insight_analysis":
                insight_widget = widget
            elif default_connection_id is None and widget.connection_id:
                # 使用第一个数据Widget的connection_id作为默认值
                default_connection_id = widget.connection_id
        
        # 如果没有找到任何数据Widget，尝试从Dashboard关联的connection获取
        if default_connection_id is None:
            dashboard = crud.crud_dashboard.get(db, id=dashboard_id)
            if dashboard and dashboard.widgets:
                for w in dashboard.widgets:
                    if w.widget_type != "insight_analysis" and w.connection_id:
                        default_connection_id = w.connection_id
                        break
        
        # 如果仍然没有找到 connection_id，记录警告（不再使用硬编码默认值）
        if default_connection_id is None:
            logger.warning(f"Dashboard {dashboard_id} 没有找到有效的 connection_id，洞察分析可能无法正常工作")
        
        # P0: 将溯源信息合并到 query_config
        query_config = {
            "analysis_scope": "all_widgets",
            "analysis_dimensions": ["summary", "trends", "correlations", "recommendations"],
            "refresh_strategy": "manual",
            "last_analysis_at": datetime.utcnow().isoformat(),
            "use_graph_relationships": use_graph_relationships,
            "analyzed_widget_count": analyzed_widget_count,
            "status": status,
        }
        
        if conditions:
            query_config["current_conditions"] = conditions.dict(exclude_none=True)
        
        # P0: 保存溯源信息
        if lineage:
            query_config["source_tables"] = lineage.get("source_tables", [])
            query_config["generated_sql"] = lineage.get("generated_sql")
            query_config["user_intent"] = lineage.get("sql_generation_trace", {}).get("user_intent")
            query_config["few_shot_samples_count"] = lineage.get("sql_generation_trace", {}).get("few_shot_samples_count", 0)
            query_config["generation_method"] = lineage.get("sql_generation_trace", {}).get("generation_method", "standard")
            query_config["execution_time_ms"] = lineage.get("execution_metadata", {}).get("execution_time_ms", 0)
            query_config["from_cache"] = lineage.get("execution_metadata", {}).get("from_cache", False)
            query_config["row_count"] = lineage.get("execution_metadata", {}).get("row_count", 0)
            query_config["db_type"] = lineage.get("execution_metadata", {}).get("db_type")
            query_config["data_transformations"] = lineage.get("data_transformations", [])
            query_config["confidence_score"] = lineage.get("confidence_score", 0.8)
            query_config["analysis_method"] = lineage.get("analysis_method", "auto")
        
        data_cache = insights.dict(exclude_none=True)
        
        if insight_widget:
            crud.crud_dashboard_widget.update(
                db,
                db_obj=insight_widget,
                obj_in=schemas.WidgetUpdate(title="看板洞察分析")
            )
            insight_widget.query_config = query_config
            insight_widget.data_cache = data_cache
            insight_widget.last_refresh_at = datetime.utcnow()
            db.commit()
            db.refresh(insight_widget)
            return insight_widget.id
        else:
            widget_create = schemas.WidgetCreate(
                widget_type="insight_analysis",
                title="看板洞察分析",
                connection_id=default_connection_id,  # P0-FIX: 使用动态获取的connection_id
                query_config=query_config,
                chart_config=None,
                position_config={"x": 0, "y": 0, "w": 12, "h": 6},
                refresh_interval=0
            )
            
            new_widget = crud.crud_dashboard_widget.create_widget(
                db,
                dashboard_id=dashboard_id,
                obj_in=widget_create
            )
            new_widget.data_cache = data_cache
            db.commit()
            db.refresh(new_widget)
            return new_widget.id

    def _update_insight_widget_result(
        self,
        db: Session,
        widget_id: int,
        insights: schemas.InsightResult,
        count: int,
        status: str,
        analysis_method: Optional[str] = None,
        confidence_score: Optional[float] = None,
        relationship_count: Optional[int] = None,
        source_tables: Optional[List[str]] = None,
        extra_metrics: Optional[Dict[str, Any]] = None,
    ):
        """更新洞察 Widget 的分析结果"""
        try:
            widget = crud.crud_dashboard_widget.get(db, id=widget_id)
            if widget:
                query_config = widget.query_config or {}
                query_config["status"] = status
                query_config["analyzed_widget_count"] = count
                query_config["last_analysis_at"] = datetime.utcnow().isoformat()
                if analysis_method is not None:
                    query_config["analysis_method"] = analysis_method
                if confidence_score is not None:
                    query_config["confidence_score"] = confidence_score
                if relationship_count is not None:
                    query_config["relationship_count"] = relationship_count
                if source_tables is not None:
                    query_config["source_tables"] = source_tables
                if extra_metrics is not None:
                    query_config["trend_metrics"] = extra_metrics
                
                widget.query_config = query_config
                widget.data_cache = insights.dict(exclude_none=True)
                widget.last_refresh_at = datetime.utcnow()
                db.commit()
        except Exception as e:
            db.rollback()
            raise

    def _update_widget_status(self, db: Session, widget_id: int, status: str, error: str = None):
        """更新 Widget 状态"""
        try:
            widget = crud.crud_dashboard_widget.get(db, id=widget_id)
            if widget:
                query_config = widget.query_config or {}
                query_config["status"] = status
                query_config["last_updated_at"] = datetime.utcnow().isoformat()
                if error:
                    # 限制错误信息长度，避免存储过大
                    query_config["error"] = str(error)[:1000]
                widget.query_config = query_config
                db.commit()
        except Exception as e:
            db.rollback()
            raise


# 创建全局实例
dashboard_insight_service = DashboardInsightService()
