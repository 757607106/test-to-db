"""
Dashboard洞察分析智能体图 - Hub-and-Spoke (Supervisor) 架构

遵循 LangGraph 官方 Supervisor 模式，与 sql_agent 架构一致:
1. Supervisor 作为中心枢纽，统一决策
2. 所有 Worker Agent 向 Supervisor 报告
3. Supervisor 动态路由到下一个 Agent

架构说明:
    START → supervisor → [Worker Agents] → supervisor → ... → FINISH

Worker Agents:
- schema_enricher: Schema增强（元数据、语义类型）
- data_sampler: 数据采样（真实数据预览）
- relationship_analyzer: 图谱关系分析
- sql_generator: SQL生成（复用 sql_generator_agent）
- sql_validator: SQL预验证（语法、安全性）
- sql_executor: SQL执行（复用 sql_executor_agent）
- insight_analyzer: 洞察分析（数据解读）
- error_recovery: 错误恢复

优化历史:
- 2026-01-25: 从 Pipeline 架构重构为 Hub-and-Spoke 架构
- 2026-01-25: 复用 sql_generator_agent 和 sql_executor_agent，减少代码重复
"""
from typing import Dict, Any, List, Optional, Literal
from typing_extensions import TypedDict
import logging
import time

from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledStateGraph

from app.services.graph_relationship_service import graph_relationship_service
from app.services.sql_helpers import (
    get_sql_syntax_guide,
    infer_semantic_type,
    is_aggregatable_type,
    is_groupable_type,
    validate_sql_safety,
    clean_sql_from_llm_response,
)

logger = logging.getLogger(__name__)


# ============================================================================
# 状态定义
# ============================================================================

class DashboardInsightState(TypedDict):
    """Dashboard洞察分析状态"""
    # 基础信息
    dashboard: Any
    connection_id: int
    db_type: str
    user_intent: Optional[str]
    
    # Schema与数据
    aggregated_data: Dict[str, Any]
    enriched_schema: Optional[Dict[str, Any]]
    sample_data: Optional[Dict[str, List]]
    relationship_context: Optional[Dict[str, Any]]
    
    # SQL相关
    generated_sql: Optional[str]
    sql_validation_result: Optional[Dict[str, Any]]
    execution_result: Optional[Dict[str, Any]]
    
    # 分析结果
    insights: Optional[Dict[str, Any]]
    final_response: Optional[Dict[str, Any]]
    
    # 流程控制
    current_stage: str
    use_graph_relationships: bool
    analysis_dimensions: Optional[List[str]]
    
    # 错误处理
    error: Optional[str]
    error_history: List[Dict[str, Any]]
    retry_count: int
    max_retries: int


# ============================================================================
# Worker Agent 节点
# ============================================================================

async def schema_enricher_node(state: DashboardInsightState) -> Dict[str, Any]:
    """
    Schema增强 Worker
    丰富元数据：列统计、样本值、语义类型推断
    """
    logger.info("[Worker] schema_enricher 开始执行")
    start_time = time.time()
    
    try:
        from app.db.session import SessionLocal
        from app import crud
        from app.models.db_connection import DBConnection
        
        db = SessionLocal()
        connection_id = state.get("connection_id") or state.get("aggregated_data", {}).get("connection_id", 1)
        
        # 获取数据库类型
        connection = db.query(DBConnection).filter(DBConnection.id == connection_id).first()
        db_type = connection.db_type.upper() if connection else "MYSQL"
        
        # 获取表信息
        tables = crud.schema_table.get_by_connection(db=db, connection_id=connection_id)
        
        enriched_tables = []
        enriched_columns = []
        column_statistics = {}
        
        for table in tables[:10]:
            table_info = {
                "id": table.id,
                "name": table.table_name,
                "description": table.description or f"表 {table.table_name}",
            }
            enriched_tables.append(table_info)
            
            columns = crud.schema_column.get_by_table(db=db, table_id=table.id)
            for col in columns:
                semantic_type = infer_semantic_type(col.column_name, col.data_type)
                col_info = {
                    "id": col.id,
                    "name": col.column_name,
                    "type": col.data_type,
                    "description": col.description or f"{table.table_name}.{col.column_name}",
                    "is_primary_key": col.is_primary_key,
                    "is_foreign_key": col.is_foreign_key,
                    "table_id": table.id,
                    "table_name": table.table_name,
                    "semantic_type": semantic_type
                }
                enriched_columns.append(col_info)
                
                key = f"{table.table_name}.{col.column_name}"
                column_statistics[key] = {
                    "data_type": col.data_type,
                    "semantic_type": semantic_type,
                    "is_aggregatable": is_aggregatable_type(col.data_type),
                    "is_groupable": is_groupable_type(col.data_type, col.column_name)
                }
        
        db.close()
        
        elapsed_ms = int((time.time() - start_time) * 1000)
        logger.info(f"[Worker] schema_enricher 完成, 耗时 {elapsed_ms}ms, {len(enriched_tables)} 表")
        
        return {
            "enriched_schema": {
                "tables": enriched_tables,
                "columns": enriched_columns,
                "column_statistics": column_statistics,
                "relationships": [],
                "db_type": db_type
            },
            "db_type": db_type,
            "connection_id": connection_id,
            "current_stage": "schema_done"
        }
        
    except Exception as e:
        logger.error(f"[Worker] schema_enricher 失败: {e}")
        return {
            "current_stage": "schema_done",
            "error_history": state.get("error_history", []) + [{
                "stage": "schema_enrichment",
                "error": str(e),
                "timestamp": time.time()
            }]
        }


async def data_sampler_node(state: DashboardInsightState) -> Dict[str, Any]:
    """
    数据采样 Worker
    从主要表中采样少量真实数据
    """
    logger.info("[Worker] data_sampler 开始执行")
    start_time = time.time()
    
    try:
        from app.services.db_service import get_db_connection_by_id, execute_query
        
        connection_id = state.get("connection_id", 1)
        connection = get_db_connection_by_id(connection_id)
        
        if not connection:
            logger.warning("无法获取数据库连接，跳过采样")
            return {"sample_data": {}, "current_stage": "sample_done"}
        
        enriched_schema = state.get("enriched_schema", {})
        tables = enriched_schema.get("tables", [])[:3]
        db_type = state.get("db_type", "MYSQL").upper()
        
        sample_data = {}
        
        for table in tables:
            table_name = table["name"]
            try:
                if db_type in ["MYSQL", "MARIADB"]:
                    sample_sql = f"SELECT * FROM `{table_name}` LIMIT 3"
                elif db_type == "POSTGRESQL":
                    sample_sql = f'SELECT * FROM "{table_name}" LIMIT 3'
                elif db_type == "SQLSERVER":
                    sample_sql = f"SELECT TOP 3 * FROM [{table_name}]"
                elif db_type == "ORACLE":
                    sample_sql = f'SELECT * FROM "{table_name}" WHERE ROWNUM <= 3'
                else:
                    sample_sql = f"SELECT * FROM {table_name} LIMIT 3"
                
                result = execute_query(connection, sample_sql)
                sample_data[table_name] = result[:3] if result else []
            except Exception as e:
                logger.debug(f"采样 {table_name} 失败: {e}")
                sample_data[table_name] = []
        
        elapsed_ms = int((time.time() - start_time) * 1000)
        logger.info(f"[Worker] data_sampler 完成, 耗时 {elapsed_ms}ms")
        
        return {
            "sample_data": sample_data,
            "current_stage": "sample_done"
        }
        
    except Exception as e:
        logger.error(f"[Worker] data_sampler 失败: {e}")
        return {"sample_data": {}, "current_stage": "sample_done"}


async def relationship_analyzer_node(state: DashboardInsightState) -> Dict[str, Any]:
    """
    图谱关系分析 Worker
    查询表间关系
    """
    logger.info("[Worker] relationship_analyzer 开始执行")
    
    if not state.get("use_graph_relationships", False):
        logger.info("未启用图谱关系分析，跳过")
        return {"relationship_context": None, "current_stage": "relationship_done"}
    
    try:
        enriched_schema = state.get("enriched_schema", {})
        table_names = [t["name"] for t in enriched_schema.get("tables", [])]
        
        if not table_names:
            return {"relationship_context": None, "current_stage": "relationship_done"}
        
        connection_id = state.get("connection_id", 1)
        relationship_context = graph_relationship_service.query_table_relationships(
            connection_id,
            table_names
        )
        
        logger.info(f"[Worker] relationship_analyzer 完成, 发现 {relationship_context.get('relationship_count', 0)} 个关系")
        
        return {
            "relationship_context": relationship_context,
            "current_stage": "relationship_done"
        }
        
    except Exception as e:
        logger.error(f"[Worker] relationship_analyzer 失败: {e}")
        return {"relationship_context": None, "current_stage": "relationship_done"}


async def sql_generator_node(state: DashboardInsightState) -> Dict[str, Any]:
    """
    SQL生成 Worker - 复用 sql_generator_agent
    
    通过适配状态格式，复用成熟的 sql_generator_agent 实现，
    获得样本检索、缓存模板、错误恢复等完整能力。
    """
    logger.info("[Worker] sql_generator 开始执行 (复用 sql_generator_agent)")
    start_time = time.time()
    
    # 如果已有SQL，直接跳过
    if state.get("generated_sql"):
        logger.info("已有SQL，跳过生成")
        return {"current_stage": "sql_generated"}
    
    try:
        from app.agents.agents.sql_generator_agent import sql_generator_agent
        from langchain_core.messages import HumanMessage
        
        enriched_schema = state.get("enriched_schema", {})
        connection_id = state.get("connection_id", 1)
        user_intent = state.get("user_intent", "自动发现关键业务指标和趋势")
        
        # 构造兼容 SQLMessageState 的状态
        # sql_generator_agent.process() 需要: messages, schema_info, connection_id
        adapted_state = {
            "messages": [HumanMessage(content=user_intent)],
            "schema_info": {
                "tables": enriched_schema
            },
            "connection_id": connection_id,
            "skip_sample_retrieval": False,  # 启用样本检索
        }
        
        # 调用复用的 sql_generator_agent
        result = await sql_generator_agent.process(adapted_state)
        
        generated_sql = result.get("generated_sql", "")
        
        if not generated_sql:
            raise ValueError("sql_generator_agent 未返回 SQL")
        
        elapsed_ms = int((time.time() - start_time) * 1000)
        logger.info(f"[Worker] sql_generator 完成 (复用), 耗时 {elapsed_ms}ms")
        
        return {
            "generated_sql": generated_sql,
            "current_stage": "sql_generated"
        }
        
    except Exception as e:
        logger.error(f"[Worker] sql_generator 失败: {e}")
        return {
            "current_stage": "sql_generated",
            "error_history": state.get("error_history", []) + [{
                "stage": "sql_generation",
                "error": str(e),
                "timestamp": time.time()
            }]
        }


async def sql_validator_node(state: DashboardInsightState) -> Dict[str, Any]:
    """
    SQL验证 Worker
    验证SQL语法和安全性
    """
    logger.info("[Worker] sql_validator 开始执行")
    
    generated_sql = state.get("generated_sql")
    
    if not generated_sql:
        return {
            "sql_validation_result": {"valid": False, "error": "没有SQL"},
            "current_stage": "validation_done"
        }
    
    validation_result = {"valid": True, "warnings": [], "suggestions": []}
    sql_upper = generated_sql.upper()
    db_type = state.get("db_type", "MYSQL").upper()
    
    # 安全检查
    dangerous = ["DROP", "DELETE", "TRUNCATE", "UPDATE", "INSERT", "ALTER", "CREATE"]
    for kw in dangerous:
        if kw in sql_upper and "SELECT" not in sql_upper[:20]:
            validation_result["valid"] = False
            validation_result["error"] = f"检测到危险操作: {kw}"
            return {"sql_validation_result": validation_result, "current_stage": "validation_done"}
    
    # 必须是SELECT
    if not sql_upper.strip().startswith("SELECT"):
        validation_result["valid"] = False
        validation_result["error"] = "必须是SELECT语句"
        return {"sql_validation_result": validation_result, "current_stage": "validation_done"}
    
    # 兼容性警告
    if db_type in ["MYSQL", "MARIADB"] and "FULL OUTER JOIN" in sql_upper:
        validation_result["warnings"].append("MySQL不支持FULL OUTER JOIN")
    
    logger.info(f"[Worker] sql_validator 完成: {'通过' if validation_result['valid'] else '失败'}")
    
    return {
        "sql_validation_result": validation_result,
        "current_stage": "validation_done"
    }


async def sql_executor_node(state: DashboardInsightState) -> Dict[str, Any]:
    """
    SQL执行 Worker - 复用 sql_executor_agent
    
    通过适配状态格式，复用成熟的 sql_executor_agent 实现，
    获得执行缓存、结果格式化等能力。
    """
    logger.info("[Worker] sql_executor 开始执行 (复用 sql_executor_agent)")
    start_time = time.time()
    
    validation = state.get("sql_validation_result", {})
    if not validation.get("valid", False):
        return {
            "execution_result": {"success": False, "error": validation.get("error", "验证失败")},
            "current_stage": "execution_done"
        }
    
    try:
        from app.agents.agents.sql_executor_agent import execute_sql_query
        import json
        
        connection_id = state.get("connection_id", 1)
        sql = state.get("generated_sql", "")
        
        if not sql:
            raise ValueError("没有找到需要执行的 SQL 语句")
        
        # 直接调用复用的 execute_sql_query 工具
        result_json = execute_sql_query.invoke({
            "sql_query": sql,
            "connection_id": connection_id,
            "timeout": 30
        })
        
        result = json.loads(result_json)
        
        elapsed_ms = int((time.time() - start_time) * 1000)
        
        if result.get("success"):
            data = result.get("data", {})
            # 转换数据格式以匹配 DashboardInsightState 期望的格式
            rows = data.get("data", [])
            columns = data.get("columns", [])
            
            # 将列表格式转换为字典格式
            formatted_data = []
            for row in rows:
                if isinstance(row, list) and len(row) == len(columns):
                    formatted_data.append(dict(zip(columns, row)))
                elif isinstance(row, dict):
                    formatted_data.append(row)
            
            logger.info(f"[Worker] sql_executor 完成 (复用), 耗时 {elapsed_ms}ms, {len(formatted_data)} 条数据")
            
            return {
                "execution_result": {
                    "success": True, 
                    "data": formatted_data, 
                    "row_count": len(formatted_data),
                    "from_cache": result.get("from_cache", False)
                },
                "current_stage": "execution_done"
            }
        else:
            raise Exception(result.get("error", "SQL 执行失败"))
        
    except Exception as e:
        logger.error(f"[Worker] sql_executor 失败: {e}")
        return {
            "execution_result": {"success": False, "error": str(e)},
            "current_stage": "execution_done",
            "error_history": state.get("error_history", []) + [{
                "stage": "sql_execution",
                "error": str(e),
                "sql": state.get("generated_sql", ""),
                "timestamp": time.time()
            }]
        }


async def insight_analyzer_node(state: DashboardInsightState) -> Dict[str, Any]:
    """
    洞察分析 Worker
    分析数据并生成洞察
    """
    logger.info("[Worker] insight_analyzer 开始执行")
    
    try:
        execution_result = state.get("execution_result", {})
        
        if execution_result.get("success") and execution_result.get("data"):
            data = execution_result["data"]
            row_count = len(data)
            
            # 提取关键指标
            key_metrics = {}
            if data and isinstance(data[0], dict):
                numeric_cols = [k for k, v in data[0].items() if isinstance(v, (int, float))]
                for col in numeric_cols[:5]:
                    values = [row.get(col, 0) for row in data if row.get(col) is not None]
                    if values:
                        key_metrics[col] = {
                            "sum": sum(values),
                            "avg": round(sum(values) / len(values), 2),
                            "max": max(values),
                            "min": min(values)
                        }
            
            insights = {
                "summary": {
                    "total_rows": row_count,
                    "key_metrics": key_metrics,
                    "time_range": "已分析",
                    "data_quality": "good"
                },
                "trends": None,
                "anomalies": [],
                "correlations": [],
                "recommendations": [{
                    "type": "info",
                    "content": f"成功分析 {row_count} 条数据",
                    "priority": "medium"
                }]
            }
        else:
            insights = {
                "summary": {"total_rows": 0, "key_metrics": {}, "time_range": "分析受限"},
                "trends": None,
                "anomalies": [],
                "correlations": [],
                "recommendations": [{
                    "type": "warning",
                    "content": "数据获取受限，请检查查询",
                    "priority": "medium"
                }]
            }
        
        logger.info("[Worker] insight_analyzer 完成")
        
        return {
            "insights": insights,
            "current_stage": "analysis_done"
        }
        
    except Exception as e:
        logger.error(f"[Worker] insight_analyzer 失败: {e}")
        return {
            "insights": {
                "summary": {"total_rows": 0, "key_metrics": {}, "time_range": "分析失败"},
                "recommendations": [{"type": "error", "content": str(e), "priority": "high"}]
            },
            "current_stage": "analysis_done"
        }


async def error_recovery_node(state: DashboardInsightState) -> Dict[str, Any]:
    """
    错误恢复 Worker
    分析错误并尝试修复
    """
    logger.info("[Worker] error_recovery 开始执行")
    
    retry_count = state.get("retry_count", 0) + 1
    error_history = state.get("error_history", [])
    
    if not error_history:
        return {"retry_count": retry_count, "current_stage": "recovery_done"}
    
    last_error = error_history[-1]
    error_msg = last_error.get("error", "")
    failed_sql = last_error.get("sql", "")
    
    logger.info(f"尝试恢复 (第 {retry_count} 次)")
    
    fixed_sql = failed_sql
    
    # 自动修复常见问题
    if "FULL OUTER JOIN" in failed_sql.upper():
        import re
        fixed_sql = re.sub(r'\bFULL\s+OUTER\s+JOIN\b', 'LEFT JOIN', fixed_sql, flags=re.IGNORECASE)
        logger.info("修复: FULL OUTER JOIN → LEFT JOIN")
    
    if "%Y" in failed_sql and "%%Y" not in failed_sql:
        fixed_sql = fixed_sql.replace("%Y", "%%Y").replace("%m", "%%m").replace("%d", "%%d")
        logger.info("修复: 日期格式转义")
    
    return {
        "generated_sql": fixed_sql if fixed_sql != failed_sql else None,
        "retry_count": retry_count,
        "current_stage": "recovery_done"
    }


# ============================================================================
# Supervisor 节点
# ============================================================================

async def supervisor_node(state: DashboardInsightState) -> Dict[str, Any]:
    """
    Supervisor 中心节点
    
    职责:
    - 决策下一步执行哪个 Worker
    - 汇总各 Agent 的执行结果
    - 构造最终响应
    """
    current_stage = state.get("current_stage", "init")
    
    # 如果已完成，汇总结果
    if current_stage == "completed":
        return _aggregate_final_response(state)
    
    if current_stage == "analysis_done":
        return _aggregate_final_response(state)
    
    return {}


def _aggregate_final_response(state: DashboardInsightState) -> Dict[str, Any]:
    """汇总最终响应"""
    execution_result = state.get("execution_result", {})
    
    final_response = {
        "success": execution_result.get("success", False),
        "sql": state.get("generated_sql"),
        "data": execution_result.get("data") if execution_result.get("success") else None,
        "insights": state.get("insights"),
        "enriched_schema": state.get("enriched_schema"),
        "relationship_context": state.get("relationship_context"),
        "metadata": {
            "connection_id": state.get("connection_id"),
            "db_type": state.get("db_type"),
            "retry_count": state.get("retry_count", 0)
        }
    }
    
    if not final_response["success"]:
        error_history = state.get("error_history", [])
        if error_history:
            final_response["error"] = error_history[-1].get("error")
    
    logger.info("[Supervisor] 结果汇总完成")
    
    return {
        "final_response": final_response,
        "current_stage": "completed"
    }


# ============================================================================
# 路由函数
# ============================================================================

def supervisor_route(state: DashboardInsightState) -> str:
    """Supervisor 路由决策"""
    current_stage = state.get("current_stage", "init")
    logger.info(f"[Route] 当前阶段: {current_stage}")
    
    # 完成状态
    if current_stage == "completed":
        return "FINISH"
    
    if current_stage == "analysis_done":
        return "FINISH"
    
    # 错误恢复检查
    execution_result = state.get("execution_result", {})
    if current_stage == "execution_done" and not execution_result.get("success", True):
        retry_count = state.get("retry_count", 0)
        max_retries = state.get("max_retries", 2)
        if retry_count < max_retries:
            logger.info(f"[Route] 执行失败，进入错误恢复 ({retry_count}/{max_retries})")
            return "error_recovery"
    
    # 恢复后重新验证
    if current_stage == "recovery_done":
        if state.get("generated_sql"):
            return "sql_validator"
        return "insight_analyzer"
    
    # 基于阶段路由
    stage_routes = {
        "init": "schema_enricher",
        "schema_done": "data_sampler",
        "sample_done": "relationship_analyzer",
        "relationship_done": "sql_generator",
        "sql_generated": "sql_validator",
        "validation_done": "sql_executor",
        "execution_done": "insight_analyzer",
    }
    
    next_agent = stage_routes.get(current_stage, "FINISH")
    logger.info(f"[Route] {current_stage} → {next_agent}")
    return next_agent


# ============================================================================
# 图构建
# ============================================================================

def create_dashboard_insight_graph() -> CompiledStateGraph:
    """
    创建 Hub-and-Spoke 架构的洞察分析图
    
    注意: 不传入 checkpointer，由 LangGraph API 框架在运行时自动管理持久化。
    """
    logger.info("创建 Dashboard Insight Hub-and-Spoke 图...")
    
    graph = StateGraph(DashboardInsightState)
    
    # 添加节点
    graph.add_node("supervisor", supervisor_node)
    graph.add_node("schema_enricher", schema_enricher_node)
    graph.add_node("data_sampler", data_sampler_node)
    graph.add_node("relationship_analyzer", relationship_analyzer_node)
    graph.add_node("sql_generator", sql_generator_node)
    graph.add_node("sql_validator", sql_validator_node)
    graph.add_node("sql_executor", sql_executor_node)
    graph.add_node("insight_analyzer", insight_analyzer_node)
    graph.add_node("error_recovery", error_recovery_node)
    
    # Supervisor 是入口
    graph.set_entry_point("supervisor")
    
    # 所有 Worker 返回 Supervisor (Hub-and-Spoke 核心)
    graph.add_edge("schema_enricher", "supervisor")
    graph.add_edge("data_sampler", "supervisor")
    graph.add_edge("relationship_analyzer", "supervisor")
    graph.add_edge("sql_generator", "supervisor")
    graph.add_edge("sql_validator", "supervisor")
    graph.add_edge("sql_executor", "supervisor")
    graph.add_edge("insight_analyzer", "supervisor")
    graph.add_edge("error_recovery", "supervisor")
    
    # Supervisor 条件路由
    graph.add_conditional_edges(
        "supervisor",
        supervisor_route,
        {
            "schema_enricher": "schema_enricher",
            "data_sampler": "data_sampler",
            "relationship_analyzer": "relationship_analyzer",
            "sql_generator": "sql_generator",
            "sql_validator": "sql_validator",
            "sql_executor": "sql_executor",
            "insight_analyzer": "insight_analyzer",
            "error_recovery": "error_recovery",
            "FINISH": END
        }
    )
    
    # 编译 - 不传入 checkpointer，由框架自动管理
    compiled = graph.compile()
    
    logger.info("✓ Dashboard Insight Hub-and-Spoke 图创建完成")
    return compiled


# 创建全局图实例 (供 LangGraph API 使用)
dashboard_insight_graph = create_dashboard_insight_graph()


# ============================================================================
# 便捷函数
# ============================================================================

async def analyze_dashboard(
    dashboard: Any,
    aggregated_data: Dict[str, Any],
    use_graph_relationships: bool = True,
    analysis_dimensions: Optional[List[str]] = None,
    connection_id: Optional[int] = None,
    user_intent: Optional[str] = None
) -> Dict[str, Any]:
    """
    分析Dashboard的便捷函数
    """
    initial_state = DashboardInsightState(
        dashboard=dashboard,
        connection_id=connection_id or aggregated_data.get("connection_id", 1),
        db_type="MYSQL",
        user_intent=user_intent or "自动发现关键业务指标和趋势",
        aggregated_data=aggregated_data,
        enriched_schema=None,
        sample_data=None,
        relationship_context=None,
        generated_sql=aggregated_data.get("generated_sql"),
        sql_validation_result=None,
        execution_result=None,
        insights=None,
        final_response=None,
        current_stage="init",
        use_graph_relationships=use_graph_relationships,
        analysis_dimensions=analysis_dimensions,
        error=None,
        error_history=[],
        retry_count=0,
        max_retries=2
    )
    
    result = await dashboard_insight_graph.ainvoke(initial_state)
    
    return result.get("final_response", {
        "insights": result.get("insights"),
        "relationship_context": result.get("relationship_context"),
        "error": result.get("error")
    })


if __name__ == "__main__":
    print("Dashboard Insight Hub-and-Spoke 图创建成功")
    print(f"图节点: {list(dashboard_insight_graph.get_graph().nodes.keys())}")
