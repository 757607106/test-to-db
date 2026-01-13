"""
分析师代理 (Analyst Agent)
负责分析查询结果，生成业务洞察、趋势分析和建议
"""
from typing import Dict, Any, List, Optional

from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, AIMessage, AnyMessage
from langchain_core.runnables import RunnableConfig
from langgraph.prebuilt import create_react_agent

from app.core.state import SQLMessageState, extract_connection_id
from app.core.llms import get_default_model
from app.services.analyst_utils import (
    calculate_statistics,
    detect_time_series,
    calculate_growth_rate,
    detect_outliers,
    analyze_distribution,
    find_correlations
)


@tool
def detect_analysis_need(
    query: str,
    result_data: List[Dict[str, Any]],
    sql: str
) -> Dict[str, Any]:
    """
    智能判断是否需要进行数据分析
    
    Args:
        query: 用户原始查询
        result_data: SQL执行结果数据
        sql: 执行的SQL语句
        
    Returns:
        判断结果和建议的分析类型
    """
    try:
        # 规则判断（快速过滤）
        if not result_data:
            return {
                "success": True,
                "needs_analysis": False,
                "reason": "结果为空"
            }
        
        row_count = len(result_data)
        
        # 数据量太少不分析
        if row_count < 2:
            return {
                "success": True,
                "needs_analysis": False,
                "reason": "数据量太少（少于2行）"
            }
        
        # 数据量太大只做摘要
        analysis_types = []
        if row_count > 1000:
            analysis_types = ["summary"]
            return {
                "success": True,
                "needs_analysis": True,
                "analysis_types": analysis_types,
                "reason": "数据量大，提供摘要分析"
            }
        
        # 检查数据结构
        stats = calculate_statistics(result_data)
        has_numeric = len(stats.get("numeric_columns", [])) > 0
        has_time = len(stats.get("date_columns", [])) > 0
        
        # 判断分析类型
        if has_time and has_numeric:
            analysis_types = ["summary", "trends", "anomalies"]
        elif has_numeric:
            analysis_types = ["summary", "distribution", "anomalies"]
        else:
            analysis_types = ["summary"]
        
        # 如果有聚合查询，增加深度分析
        if any(keyword in sql.upper() for keyword in ["GROUP BY", "SUM(", "AVG(", "COUNT("]):
            analysis_types.append("aggregation_insights")
        
        # 使用LLM判断用户意图
        llm = get_default_model()
        intent_prompt = f"""分析用户查询意图，判断是否需要数据分析。

用户查询: {query}
数据行数: {row_count}
包含数值列: {has_numeric}
包含时间列: {has_time}

请判断：
1. 用户是否想要数据分析（不仅仅是原始数据）
2. 是否适合进行趋势分析
3. 是否需要异常检测

返回JSON格式：
{{
    "user_wants_analysis": true/false,
    "confidence": 0.0-1.0,
    "suggested_types": ["summary", "trends", "anomalies", "recommendations"]
}}

只返回JSON。"""

        try:
            response = llm.invoke([HumanMessage(content=intent_prompt)])
            content = response.content.strip()
            
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            import json
            llm_result = json.loads(content)
            
            user_wants = llm_result.get("user_wants_analysis", True)
            suggested = llm_result.get("suggested_types", [])
            
            # 合并规则判断和LLM判断
            if user_wants:
                analysis_types.extend([t for t in suggested if t not in analysis_types])
            
        except:
            pass  # LLM判断失败，使用规则判断结果
        
        needs_analysis = len(analysis_types) > 0 and row_count >= 2
        
        return {
            "success": True,
            "needs_analysis": needs_analysis,
            "analysis_types": analysis_types[:4],  # 最多4种分析类型
            "reason": f"数据量适中（{row_count}行），适合分析",
            "data_characteristics": {
                "has_numeric": has_numeric,
                "has_time": has_time,
                "row_count": row_count
            }
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "needs_analysis": False
        }


@tool
def generate_data_summary(result_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    生成数据摘要统计
    
    Args:
        result_data: 查询结果数据
        
    Returns:
        摘要统计信息
    """
    try:
        stats = calculate_statistics(result_data)
        
        if "error" in stats:
            return {"success": False, "error": stats["error"]}
        
        # 提取关键指标
        key_metrics = {}
        for col in stats.get("numeric_columns", []):
            col_stats = stats["summary"].get(col, {})
            if col_stats.get("sum"):
                key_metrics[f"{col}_总计"] = col_stats["sum"]
            if col_stats.get("mean"):
                key_metrics[f"{col}_平均"] = round(col_stats["mean"], 2)
        
        return {
            "success": True,
            "total_rows": stats["total_rows"],
            "numeric_columns": stats["numeric_columns"],
            "key_metrics": key_metrics,
            "column_summary": stats["summary"]
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"摘要生成错误: {str(e)}"
        }


@tool
def analyze_trends(result_data: List[Dict[str, Any]], query: str) -> Dict[str, Any]:
    """
    分析时间序列趋势
    
    Args:
        result_data: 查询结果数据
        query: 用户查询（用于理解上下文）
        
    Returns:
        趋势分析结果
    """
    try:
        # 检测时间序列
        ts_info = detect_time_series(result_data)
        
        if not ts_info or not ts_info.get("has_time_series"):
            return {
                "success": False,
                "error": "数据不包含时间序列"
            }
        
        date_col = ts_info["date_column"]
        
        # 查找数值列
        stats = calculate_statistics(result_data)
        numeric_cols = stats.get("numeric_columns", [])
        
        if not numeric_cols:
            return {
                "success": False,
                "error": "没有数值列可用于趋势分析"
            }
        
        # 对第一个数值列进行趋势分析
        value_col = numeric_cols[0]
        growth_analysis = calculate_growth_rate(result_data, date_col, value_col)
        
        if "error" in growth_analysis:
            return {
                "success": False,
                "error": growth_analysis["error"]
            }
        
        # 生成趋势描述
        trend_desc = f"{value_col}在时间段内呈{growth_analysis['trend']}趋势"
        if growth_analysis['total_growth_rate'] != 0:
            trend_desc += f"，总体变化{growth_analysis['total_growth_rate']:.2f}%"
        
        return {
            "success": True,
            "date_column": date_col,
            "value_column": value_col,
            "trend_direction": growth_analysis["trend"],
            "total_growth_rate": growth_analysis["total_growth_rate"],
            "average_growth_rate": growth_analysis["average_growth_rate"],
            "description": trend_desc,
            "date_range": ts_info["date_range"]
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"趋势分析错误: {str(e)}"
        }


@tool
def detect_data_anomalies(result_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    检测数据异常
    
    Args:
        result_data: 查询结果数据
        
    Returns:
        异常检测结果
    """
    try:
        stats = calculate_statistics(result_data)
        numeric_cols = stats.get("numeric_columns", [])
        
        if not numeric_cols:
            return {
                "success": False,
                "error": "没有数值列可进行异常检测"
            }
        
        anomalies = []
        
        # 对每个数值列检测异常
        for col in numeric_cols[:3]:  # 最多检测3个列
            outlier_result = detect_outliers(result_data, col, method="iqr")
            
            if "error" not in outlier_result and outlier_result.get("count", 0) > 0:
                anomalies.append({
                    "column": col,
                    "type": "离群值",
                    "count": outlier_result["count"],
                    "percentage": round(outlier_result["percentage"], 2),
                    "values": outlier_result["outliers"][:5],  # 最多显示5个
                    "description": f"{col}列发现{outlier_result['count']}个离群值（占{outlier_result['percentage']:.1f}%）"
                })
        
        return {
            "success": True,
            "anomalies": anomalies,
            "total_anomalies": len(anomalies)
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"异常检测错误: {str(e)}"
        }


@tool
def generate_business_recommendations(
    query: str,
    summary: Dict[str, Any],
    trends: Optional[Dict[str, Any]] = None,
    anomalies: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    基于分析结果生成业务建议
    
    Args:
        query: 用户查询
        summary: 数据摘要
        trends: 趋势分析结果
        anomalies: 异常检测结果
        
    Returns:
        业务建议
    """
    try:
        llm = get_default_model()
        
        # 构建分析结果描述
        analysis_context = f"用户查询: {query}\n\n"
        analysis_context += f"数据摘要:\n- 总行数: {summary.get('total_rows', 0)}\n"
        
        if summary.get("key_metrics"):
            analysis_context += "关键指标:\n"
            for metric, value in list(summary["key_metrics"].items())[:5]:
                analysis_context += f"  - {metric}: {value}\n"
        
        if trends and trends.get("success"):
            analysis_context += f"\n趋势分析:\n- {trends.get('description', '')}\n"
        
        if anomalies and anomalies.get("success") and anomalies.get("anomalies"):
            analysis_context += f"\n异常情况:\n"
            for anom in anomalies["anomalies"][:2]:
                analysis_context += f"  - {anom.get('description', '')}\n"
        
        recommendation_prompt = f"""作为业务分析师，基于以下数据分析结果，提供3-5条简洁的业务建议。

{analysis_context}

请提供：
1. 基于数据的洞察
2. 可操作的建议
3. 需要关注的风险点

返回JSON格式：
{{
    "recommendations": [
        {{"type": "洞察/建议/风险", "content": "具体内容"}},
        ...
    ]
}}

只返回JSON。"""

        response = llm.invoke([HumanMessage(content=recommendation_prompt)])
        content = response.content.strip()
        
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        
        import json
        result = json.loads(content)
        
        recommendations = result.get("recommendations", [])
        
        return {
            "success": True,
            "recommendations": recommendations[:5]  # 最多5条建议
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"建议生成错误: {str(e)}",
            "recommendations": []
        }


class AnalystAgent:
    """分析师代理"""

    def __init__(self):
        self.name = "analyst_agent"
        self.llm = get_default_model()
        self.tools = [
            detect_analysis_need,
            generate_data_summary,
            analyze_trends,
            detect_data_anomalies,
            generate_business_recommendations
        ]

        # 创建ReAct代理
        self.agent = create_react_agent(
            self.llm,
            self.tools,
            prompt=self._create_system_prompt,
            name=self.name,
        )
    
    def _create_system_prompt(self, state: SQLMessageState, config: RunnableConfig) -> list[AnyMessage]:
        """创建系统提示"""
        connection_id = extract_connection_id(state)
        
        system_msg = f"""你是一个专业的数据分析师。
        **重要：当前数据库connection_id是 {connection_id}**

你的任务是：
1. 智能判断查询结果是否需要深度分析
2. 生成数据摘要和统计信息
3. 分析趋势和模式（如果有时间序列数据）
4. 检测数据异常和离群值
5. 提供业务洞察和可行建议

工作流程：
1. 首先使用 detect_analysis_need 判断是否需要分析
2. 如果需要分析，根据建议的分析类型执行相应工具：
   - summary: 使用 generate_data_summary
   - trends: 使用 analyze_trends
   - anomalies: 使用 detect_data_anomalies
3. 最后使用 generate_business_recommendations 生成建议

分析原则：
- 不要过度分析简单查询
- 关注用户真正关心的业务问题
- 提供可操作的建议，而非空泛的描述
- 数据量大时只做摘要分析
- 发现异常时给出可能的原因

输出要求：
- 简洁明了，避免术语堆砌
- 突出关键发现
- 建议具体可行

请智能判断并提供有价值的分析洞察。"""

        return [{"role": "system", "content": system_msg}] + state["messages"]

    async def process(self, state: SQLMessageState) -> Dict[str, Any]:
        """处理分析任务"""
        try:
            # 获取查询结果
            execution_result = state.get("execution_result")
            
            if not execution_result or not execution_result.get("success"):
                return {
                    "messages": [AIMessage(content="没有可分析的执行结果")],
                    "current_stage": "chart_generation",
                    "needs_analysis": False
                }
            
            result_data = execution_result.get("data", [])
            
            if not result_data:
                return {
                    "messages": [AIMessage(content="查询结果为空，无需分析")],
                    "current_stage": "chart_generation",
                    "needs_analysis": False
                }
            
            # 获取用户查询和SQL
            user_query = state.get("original_query") or state.get("enriched_query", "")
            if not user_query and state.get("messages"):
                first_message = state["messages"][0]
                user_query = first_message.content if hasattr(first_message, 'content') else ""
            
            generated_sql = state.get("generated_sql", "")

            # 准备输入消息
            messages = [
                HumanMessage(content=f"""请分析以下查询结果：

用户查询: {user_query}
SQL: {generated_sql}
结果行数: {len(result_data)}

请使用提供的工具进行智能分析。""")
            ]

            # 调用代理
            result = await self.agent.ainvoke({
                "messages": messages
            })
            
            # 更新状态
            state["agent_messages"]["analyst_agent"] = result
            state["current_stage"] = "chart_generation"
            
            return {
                "messages": result["messages"],
                "current_stage": "chart_generation"
            }
            
        except Exception as e:
            # 记录错误但不阻塞流程
            print(f"分析代理错误: {str(e)}")
            return {
                "messages": [AIMessage(content=f"分析过程出现问题: {str(e)}")],
                "current_stage": "chart_generation",
                "needs_analysis": False
            }


# 创建全局实例
analyst_agent = AnalystAgent()
