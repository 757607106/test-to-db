"""
Dashboard 洞察分析智能体图

Hub-and-Spoke 架构，复用 text-to-sql 的核心节点：
- sql_generator: 复用 sql_generator_agent
- sql_executor: 复用 execute_sql_query 工具
- error_recovery: 复用 error_recovery_agent

Dashboard 独有节点：
- schema_enricher: Schema 增强
- data_sampler: 数据采样
- relationship_analyzer: 图谱关系分析
- sql_validator: SQL 验证
- insight_analyzer: 洞察分析

Phase 1 优化:
- 使用统一的 SchemaContext 格式
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
from app.schemas.schema_context import SchemaContext, TableInfo, ColumnInfo, normalize_schema_info

logger = logging.getLogger(__name__)


# ============================================================================
# 状态定义
# ============================================================================

class DashboardInsightState(TypedDict):
    """Dashboard 洞察分析状态"""
    dashboard: Any
    connection_id: int
    db_type: str
    user_intent: Optional[str]
    aggregated_data: Dict[str, Any]
    enriched_schema: Optional[Dict[str, Any]]
    sample_data: Optional[Dict[str, List]]
    relationship_context: Optional[Dict[str, Any]]
    generated_sql: Optional[str]
    sql_validation_result: Optional[Dict[str, Any]]
    execution_result: Optional[Dict[str, Any]]
    insights: Optional[Dict[str, Any]]
    final_response: Optional[Dict[str, Any]]
    current_stage: str
    use_graph_relationships: bool
    analysis_dimensions: Optional[List[str]]
    error: Optional[str]
    error_history: List[Dict[str, Any]]
    retry_count: int
    max_retries: int
    # P0: 数据溯源字段
    lineage: Optional[Dict[str, Any]]


# ============================================================================
# 状态适配层 - 用于复用 text-to-sql 节点
# ============================================================================

def _adapt_for_sql_generator(state: DashboardInsightState) -> Dict[str, Any]:
    """将 DashboardInsightState 适配为 sql_generator_agent 所需格式"""
    from langchain_core.messages import HumanMessage
    
    return {
        "messages": [HumanMessage(content=state.get("user_intent", "自动发现关键业务指标和趋势"))],
        "schema_info": {"tables": state.get("enriched_schema", {})},
        "connection_id": state.get("connection_id", 1),
        "skip_sample_retrieval": False,
        "error_recovery_context": None,
    }


def _adapt_for_error_recovery(state: DashboardInsightState) -> Dict[str, Any]:
    """将 DashboardInsightState 适配为 error_recovery_agent 所需格式"""
    from langchain_core.messages import HumanMessage
    
    return {
        "messages": [HumanMessage(content=state.get("user_intent", ""))],
        "generated_sql": state.get("generated_sql"),
        "connection_id": state.get("connection_id", 1),
        "error_history": state.get("error_history", []),
        "retry_count": state.get("retry_count", 0),
        "max_retries": state.get("max_retries", 2),
        "current_stage": "error_recovery",
    }


# ============================================================================
# Worker 节点
# ============================================================================

async def schema_enricher_node(state: DashboardInsightState) -> Dict[str, Any]:
    """Schema 增强：获取表结构、列统计、语义类型 - 使用统一的 SchemaContext 格式"""
    logger.info("[Worker] schema_enricher 开始执行")
    start_time = time.time()
    
    try:
        from app.db.session import get_db_session
        from app import crud
        from app.models.db_connection import DBConnection
        
        connection_id = state.get("connection_id") or state.get("aggregated_data", {}).get("connection_id", 1)
        
        with get_db_session() as db:
            connection = db.query(DBConnection).filter(DBConnection.id == connection_id).first()
            db_type = connection.db_type.lower() if connection else "mysql"
            tables = crud.schema_table.get_by_connection(db=db, connection_id=connection_id)
            
            # Phase 1: 使用统一的 TableInfo 和 ColumnInfo 格式
            table_infos = []
            column_infos = []
            column_statistics = {}
            
            for table in tables[:10]:
                table_infos.append(TableInfo(
                    table_name=table.table_name,
                    description=table.description or f"表 {table.table_name}",
                    id=table.id
                ))
                
                columns = crud.schema_column.get_by_table(db=db, table_id=table.id)
                for col in columns:
                    semantic_type = infer_semantic_type(col.column_name, col.data_type)
                    column_infos.append(ColumnInfo(
                        table_name=table.table_name,
                        column_name=col.column_name,
                        data_type=col.data_type,
                        description=col.description or "",
                        is_primary_key=col.is_primary_key,
                        is_foreign_key=col.is_foreign_key,
                        id=col.id,
                        table_id=table.id
                    ))
                    
                    key = f"{table.table_name}.{col.column_name}"
                    column_statistics[key] = {
                        "data_type": col.data_type,
                        "semantic_type": semantic_type,
                        "is_aggregatable": is_aggregatable_type(col.data_type),
                        "is_groupable": is_groupable_type(col.data_type, col.column_name)
                    }
        
        # 构建 SchemaContext
        schema_context = SchemaContext(
            tables=table_infos,
            columns=column_infos,
            relationships=[],
            value_mappings={},
            connection_id=connection_id,
            db_type=db_type
        )
        
        elapsed_ms = int((time.time() - start_time) * 1000)
        logger.info(f"[Worker] schema_enricher 完成, 耗时 {elapsed_ms}ms, {schema_context.table_count} 表")
        
        # 返回统一格式的字典表示，附加 column_statistics
        enriched_schema = schema_context.to_dict()
        enriched_schema["column_statistics"] = column_statistics
        
        return {
            "enriched_schema": enriched_schema,
            "db_type": db_type.upper(),
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
    """数据采样：从主要表中采样少量真实数据"""
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
        
        return {"sample_data": sample_data, "current_stage": "sample_done"}
        
    except Exception as e:
        logger.error(f"[Worker] data_sampler 失败: {e}")
        return {"sample_data": {}, "current_stage": "sample_done"}


async def relationship_analyzer_node(state: DashboardInsightState) -> Dict[str, Any]:
    """图谱关系分析：查询表间关系"""
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
            connection_id, table_names
        )
        
        logger.info(f"[Worker] relationship_analyzer 完成, 发现 {relationship_context.get('relationship_count', 0)} 个关系")
        return {"relationship_context": relationship_context, "current_stage": "relationship_done"}
        
    except Exception as e:
        logger.error(f"[Worker] relationship_analyzer 失败: {e}")
        return {"relationship_context": None, "current_stage": "relationship_done"}


async def sql_generator_node(state: DashboardInsightState) -> Dict[str, Any]:
    """SQL 生成：复用 sql_generator_agent，收集溯源信息"""
    logger.info("[Worker] sql_generator 开始执行")
    start_time = time.time()
    
    if state.get("generated_sql"):
        logger.info("已有 SQL，跳过生成")
        return {"current_stage": "sql_generated"}
    
    try:
        from app.agents.agents.sql_generator_agent import sql_generator_agent
        
        adapted_state = _adapt_for_sql_generator(state)
        result = await sql_generator_agent.process(adapted_state)
        generated_sql = result.get("generated_sql", "")
        
        if not generated_sql:
            raise ValueError("sql_generator_agent 未返回 SQL")
        
        elapsed_ms = int((time.time() - start_time) * 1000)
        logger.info(f"[Worker] sql_generator 完成, 耗时 {elapsed_ms}ms")
        
        # P0: 收集SQL生成溯源信息
        enriched_schema = state.get("enriched_schema", {})
        source_tables = [t.get("table_name", "") for t in enriched_schema.get("tables", [])]
        
        lineage = state.get("lineage") or {}
        lineage.update({
            "source_tables": source_tables,
            "generated_sql": generated_sql,
            "sql_generation_trace": {
                "user_intent": state.get("user_intent"),
                "schema_tables_used": source_tables,
                "few_shot_samples_count": result.get("sample_retrieval_result", {}).get("samples_count", 0),
                "generation_method": "template" if result.get("template_based") else "standard",
                "generation_time_ms": elapsed_ms,
            }
        })
        
        return {
            "generated_sql": generated_sql,
            "current_stage": "sql_generated",
            "lineage": lineage
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
    """SQL 验证：检查语法和安全性"""
    logger.info("[Worker] sql_validator 开始执行")
    
    generated_sql = state.get("generated_sql")
    if not generated_sql:
        return {"sql_validation_result": {"valid": False, "error": "没有SQL"}, "current_stage": "validation_done"}
    
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
    
    if not sql_upper.strip().startswith("SELECT"):
        validation_result["valid"] = False
        validation_result["error"] = "必须是SELECT语句"
        return {"sql_validation_result": validation_result, "current_stage": "validation_done"}
    
    if db_type in ["MYSQL", "MARIADB"] and "FULL OUTER JOIN" in sql_upper:
        validation_result["warnings"].append("MySQL不支持FULL OUTER JOIN")
    
    logger.info(f"[Worker] sql_validator 完成: {'通过' if validation_result['valid'] else '失败'}")
    return {"sql_validation_result": validation_result, "current_stage": "validation_done"}


async def sql_executor_node(state: DashboardInsightState) -> Dict[str, Any]:
    """SQL 执行：复用 execute_sql_query 工具，收集执行元数据"""
    logger.info("[Worker] sql_executor 开始执行")
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
        
        result_json = execute_sql_query.invoke({
            "sql_query": sql,
            "connection_id": connection_id,
            "timeout": 30
        })
        result = json.loads(result_json)
        elapsed_ms = int((time.time() - start_time) * 1000)
        
        # P0: 收集执行元数据到 lineage
        lineage = state.get("lineage") or {}
        lineage["execution_metadata"] = {
            "execution_time_ms": elapsed_ms,
            "from_cache": result.get("from_cache", False),
            "row_count": result.get("data", {}).get("row_count", 0) if result.get("success") else 0,
            "db_type": state.get("db_type", "MYSQL"),
            "connection_id": connection_id,
        }
        
        if result.get("success"):
            data = result.get("data", {})
            rows = data.get("data", [])
            columns = data.get("columns", [])
            
            formatted_data = []
            for row in rows:
                if isinstance(row, list) and len(row) == len(columns):
                    formatted_data.append(dict(zip(columns, row)))
                elif isinstance(row, dict):
                    formatted_data.append(row)
            
            logger.info(f"[Worker] sql_executor 完成, 耗时 {elapsed_ms}ms, {len(formatted_data)} 条数据")
            return {
                "execution_result": {
                    "success": True, 
                    "data": formatted_data, 
                    "row_count": len(formatted_data),
                    "from_cache": result.get("from_cache", False)
                },
                "current_stage": "execution_done",
                "lineage": lineage
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
    """洞察分析：调用 LLM 智能分析 Agent 生成深度洞察"""
    logger.info("[Worker] insight_analyzer 开始执行")
    start_time = time.time()
    
    try:
        execution_result = state.get("execution_result", {})
        enriched_schema = state.get("enriched_schema")
        relationship_context = state.get("relationship_context")
        sample_data = state.get("sample_data")
        user_intent = state.get("user_intent")
        aggregated_data = state.get("aggregated_data", {})
        
        # 准备分析数据
        data = []
        if execution_result.get("success") and execution_result.get("data"):
            data = execution_result["data"]
        elif aggregated_data.get("data"):
            # 如果执行结果为空，尝试使用聚合数据
            data = aggregated_data["data"]
        
        row_count = len(data)
        
        if row_count < 2:
            # 数据量过少，跳过 LLM 分析
            logger.info(f"[Worker] 数据量过少 ({row_count} 行)，跳过 LLM 分析")
            insights = _create_minimal_insights(data, relationship_context)
            return {"insights": insights, "current_stage": "analysis_done"}
        
        # 调用 LLM 智能分析 Agent
        try:
            from app.agents.agents.dashboard_analyst_agent import dashboard_analyst_agent
            
            insights = await dashboard_analyst_agent.analyze(
                data=data,
                schema_info=enriched_schema,
                relationship_context=relationship_context,
                sample_data=sample_data,
                user_intent=user_intent
            )
            
            elapsed_ms = int((time.time() - start_time) * 1000)
            logger.info(f"[Worker] insight_analyzer LLM 分析完成, 耗时 {elapsed_ms}ms")
            
            # 更新 lineage 信息
            lineage = state.get("lineage") or {}
            lineage["insight_analysis"] = {
                "method": "llm",
                "analysis_time_ms": elapsed_ms,
                "data_rows_analyzed": row_count,
                "relationship_count": len((relationship_context or {}).get("direct_relationships", []))
            }
            
            return {
                "insights": insights,
                "current_stage": "analysis_done",
                "lineage": lineage
            }
            
        except Exception as llm_error:
            logger.warning(f"[Worker] LLM 分析失败: {llm_error}，降级到规则分析")
            # 降级到规则分析
            insights = _create_rule_based_insights(data, relationship_context)
            
            lineage = state.get("lineage") or {}
            lineage["insight_analysis"] = {
                "method": "rule_based",
                "fallback_reason": str(llm_error),
                "data_rows_analyzed": row_count
            }
            
            return {
                "insights": insights,
                "current_stage": "analysis_done",
                "lineage": lineage
            }
        
    except Exception as e:
        logger.error(f"[Worker] insight_analyzer 失败: {e}")
        return {
            "insights": {
                "summary": {"total_rows": 0, "key_metrics": {}, "time_range": "分析失败"},
                "trends": None,
                "anomalies": [],
                "correlations": [],
                "recommendations": [{"type": "error", "content": str(e), "priority": "high"}]
            },
            "current_stage": "analysis_done"
        }


def _create_minimal_insights(data: List[Dict], relationship_context: Optional[Dict] = None) -> Dict[str, Any]:
    """创建最小化的洞察（数据量过少时使用）"""
    row_count = len(data) if data else 0
    
    # 提取基础指标
    key_metrics = {}
    if data and isinstance(data[0], dict):
        for key, value in data[0].items():
            if isinstance(value, (int, float)):
                values = [row.get(key, 0) for row in data if row.get(key) is not None]
                if values:
                    key_metrics[key] = {
                        "sum": sum(values),
                        "avg": round(sum(values) / len(values), 2) if values else 0,
                        "max": max(values) if values else 0,
                        "min": min(values) if values else 0
                    }
    
    # 基于图谱关系生成关联洞察
    correlations = []
    if relationship_context:
        direct_rels = relationship_context.get("direct_relationships", [])
        for rel in direct_rels[:3]:
            src_table = rel.get("source_table", "")
            tgt_table = rel.get("target_table", "")
            if src_table and tgt_table:
                correlations.append({
                    "type": "cross_table",
                    "tables": [src_table, tgt_table],
                    "relationship": f"{src_table} 与 {tgt_table} 存在外键关联",
                    "insight": f"可分析 {src_table} 和 {tgt_table} 之间的业务关联",
                    "strength": "medium"
                })
    
    return {
        "summary": {
            "total_rows": row_count,
            "key_metrics": key_metrics,
            "time_range": "已分析",
            "data_quality": "limited" if row_count < 10 else "good"
        },
        "trends": None,
        "anomalies": [],
        "correlations": correlations,
        "recommendations": [
            {"type": "info", "content": f"分析了 {row_count} 条数据", "priority": "medium"}
        ]
    }


def _create_rule_based_insights(data: List[Dict], relationship_context: Optional[Dict] = None) -> Dict[str, Any]:
    """基于规则的洞察分析（LLM 降级方案）"""
    row_count = len(data) if data else 0
    
    # 提取关键指标
    key_metrics = {}
    numeric_cols = []
    date_cols = []
    
    if data and isinstance(data[0], dict):
        for key, value in data[0].items():
            if isinstance(value, (int, float)):
                numeric_cols.append(key)
                values = [row.get(key, 0) for row in data if row.get(key) is not None]
                if values:
                    key_metrics[key] = {
                        "sum": sum(values),
                        "avg": round(sum(values) / len(values), 2),
                        "max": max(values),
                        "min": min(values)
                    }
            elif any(kw in key.lower() for kw in ["date", "time", "日期", "时间", "created", "updated"]):
                date_cols.append(key)
    
    # 趋势分析
    trends = None
    if date_cols and numeric_cols:
        trends = {
            "trend_direction": "待分析",
            "total_growth_rate": None,
            "description": f"数据包含时间维度 ({', '.join(date_cols[:2])})，建议进行趋势分析"
        }
    
    # 异常检测
    anomalies = []
    for col in numeric_cols[:5]:
        values = [row.get(col, 0) for row in data if row.get(col) is not None]
        if values:
            avg_val = sum(values) / len(values)
            max_val = max(values)
            if avg_val > 0 and max_val > avg_val * 10:
                anomalies.append({
                    "type": "outlier",
                    "column": col,
                    "description": f"{col} 存在极大值 ({max_val})，远超平均值 ({round(avg_val, 2)})",
                    "severity": "medium"
                })
    
    # 基于图谱关系生成关联洞察
    correlations = []
    if relationship_context:
        direct_rels = relationship_context.get("direct_relationships", [])
        for rel in direct_rels[:5]:
            src_table = rel.get("source_table", "")
            tgt_table = rel.get("target_table", "")
            if src_table and tgt_table:
                correlations.append({
                    "type": "cross_table",
                    "tables": [src_table, tgt_table],
                    "relationship": f"{src_table} 与 {tgt_table} 存在外键关联",
                    "insight": f"可分析 {src_table} 和 {tgt_table} 之间的业务关联",
                    "strength": "medium"
                })
    
    # 建议
    recommendations = [
        {"type": "info", "content": f"成功分析 {row_count} 条数据", "priority": "medium"}
    ]
    
    if numeric_cols:
        recommendations.append({
            "type": "optimization",
            "content": f"建议重点关注数值指标: {', '.join(numeric_cols[:3])}",
            "priority": "medium",
            "basis": "数据包含多个数值列"
        })
    
    if correlations:
        recommendations.append({
            "type": "opportunity",
            "content": f"发现 {len(correlations)} 个表间关联，可进行跨表分析",
            "priority": "high",
            "basis": "图谱关系分析"
        })
    
    return {
        "summary": {
            "total_rows": row_count,
            "key_metrics": key_metrics,
            "time_range": "已分析",
            "data_quality": "good" if row_count > 0 else "no_data",
            "description": f"共分析 {row_count} 条数据，包含 {len(numeric_cols)} 个数值列"
        },
        "trends": trends,
        "anomalies": anomalies,
        "correlations": correlations,
        "recommendations": recommendations
    }


async def error_recovery_node(state: DashboardInsightState) -> Dict[str, Any]:
    """错误恢复：复用 error_recovery_agent 的智能恢复能力"""
    logger.info("[Worker] error_recovery 开始执行")
    
    retry_count = state.get("retry_count", 0) + 1
    error_history = state.get("error_history", [])
    
    if not error_history:
        return {"retry_count": retry_count, "current_stage": "recovery_done"}
    
    try:
        from app.agents.agents.error_recovery_agent import error_recovery_agent
        
        adapted_state = _adapt_for_error_recovery(state)
        result = await error_recovery_agent.process(adapted_state)
        
        # 提取恢复结果
        fixed_sql = result.get("generated_sql")
        error_recovery_context = result.get("error_recovery_context")
        
        logger.info(f"[Worker] error_recovery 完成 (第 {retry_count} 次)")
        
        return {
            "generated_sql": fixed_sql,
            "retry_count": retry_count,
            "error_recovery_context": error_recovery_context,
            "current_stage": "recovery_done"
        }
        
    except Exception as e:
        logger.error(f"[Worker] error_recovery 失败: {e}")
        return {"retry_count": retry_count, "current_stage": "recovery_done"}


# ============================================================================
# Supervisor 节点
# ============================================================================

async def supervisor_node(state: DashboardInsightState) -> Dict[str, Any]:
    """Supervisor 中心节点：决策路由和结果汇总"""
    current_stage = state.get("current_stage", "init")
    
    if current_stage in ["completed", "analysis_done"]:
        return _aggregate_final_response(state)
    
    return {}


def _aggregate_final_response(state: DashboardInsightState) -> Dict[str, Any]:
    """汇总最终响应，包含数据溯源信息"""
    execution_result = state.get("execution_result", {})
    lineage = state.get("lineage") or {}
    
    # 补充数据转换步骤描述
    data_transformations = []
    if lineage.get("source_tables"):
        data_transformations.append(f"从 {len(lineage['source_tables'])} 个表获取数据")
    if lineage.get("generated_sql"):
        data_transformations.append("执行SQL查询")
    if execution_result.get("success"):
        data_transformations.append("数据格式化与聚合")
        data_transformations.append("洞察分析与指标提取")
    lineage["data_transformations"] = data_transformations
    
    final_response = {
        "success": execution_result.get("success", False),
        "sql": state.get("generated_sql"),
        "data": execution_result.get("data") if execution_result.get("success") else None,
        "insights": state.get("insights"),
        "enriched_schema": state.get("enriched_schema"),
        "relationship_context": state.get("relationship_context"),
        "lineage": lineage,
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
    
    logger.info("[Supervisor] 结果汇总完成（含溯源信息）")
    return {"final_response": final_response, "current_stage": "completed"}


# ============================================================================
# 路由函数
# ============================================================================

# 阶段路由映射表
STAGE_ROUTES = {
    "init": "schema_enricher",
    "schema_done": "data_sampler",
    "sample_done": "relationship_analyzer",
    "relationship_done": "sql_generator",
    "sql_generated": "sql_validator",
    "validation_done": "sql_executor",
    "execution_done": "insight_analyzer",
}


def supervisor_route(state: DashboardInsightState) -> str:
    """Supervisor 路由决策"""
    current_stage = state.get("current_stage", "init")
    logger.info(f"[Route] 当前阶段: {current_stage}")
    
    # 完成状态
    if current_stage in ["completed", "analysis_done"]:
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
    
    next_agent = STAGE_ROUTES.get(current_stage, "FINISH")
    logger.info(f"[Route] {current_stage} → {next_agent}")
    return next_agent


# ============================================================================
# 图构建
# ============================================================================

def create_dashboard_insight_graph() -> CompiledStateGraph:
    """创建 Hub-and-Spoke 架构的洞察分析图"""
    logger.info("创建 Dashboard Insight 图...")
    
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
    
    # 所有 Worker 返回 Supervisor (Hub-and-Spoke)
    for node in ["schema_enricher", "data_sampler", "relationship_analyzer", 
                 "sql_generator", "sql_validator", "sql_executor", 
                 "insight_analyzer", "error_recovery"]:
        graph.add_edge(node, "supervisor")
    
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
    
    compiled = graph.compile()
    logger.info("Dashboard Insight 图创建完成")
    return compiled


# 全局图实例
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
    """分析 Dashboard 的便捷函数"""
    
    # 动态获取数据库类型
    actual_connection_id = connection_id or aggregated_data.get("connection_id", 1)
    db_type = "mysql"  # 默认值
    try:
        from app.services.db_service import get_db_connection_by_id
        conn = get_db_connection_by_id(actual_connection_id)
        if conn and conn.db_type:
            db_type = conn.db_type.upper()
    except Exception:
        pass
    
    initial_state = DashboardInsightState(
        dashboard=dashboard,
        connection_id=actual_connection_id,
        db_type=db_type,
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
        max_retries=2,
        lineage=None
    )
    
    result = await dashboard_insight_graph.ainvoke(initial_state)
    
    return result.get("final_response", {
        "insights": result.get("insights"),
        "relationship_context": result.get("relationship_context"),
        "lineage": result.get("lineage"),
        "error": result.get("error")
    })


if __name__ == "__main__":
    print("Dashboard Insight 图创建成功")
    print(f"图节点: {list(dashboard_insight_graph.get_graph().nodes.keys())}")
