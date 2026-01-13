"""
分析师代理 (Analyst Agent) - 优化版
负责快速分析查询结果，生成关键业务洞察
优化：规则判断 + 单次LLM调用
"""
from typing import Dict, Any, List, Optional
import json

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


# 规则快速判断函数（不调用LLM）
def rule_based_analysis_check(result_data: List[Dict[str, Any]], sql: str = "") -> str:
    """
    规则快速判断是否需要分析及分析级别 - 不调用LLM
    
    Returns:
        "skip": 跳过分析
        "summary_only": 仅摘要
        "full_analysis": 完整分析
    """
    if not result_data:
        return "skip"
    
    row_count = len(result_data)
    
    # 数据量太少不分析
    if row_count < 2:
        return "skip"
    
    # 数据量太大只做摘要
    if row_count > 1000:
        return "summary_only"
    
    # 检查是否有聚合查询
    if sql and any(keyword in sql.upper() for keyword in ["GROUP BY", "SUM(", "AVG(", "COUNT(", "MAX(", "MIN("]):
        return "full_analysis"
    
    # 中等数据量，做完整分析
    if 2 <= row_count <= 1000:
        return "full_analysis"
    
    return "summary_only"


@tool
def intelligent_analysis(
    query: str,
    result_data: List[Dict[str, Any]],
    sql: str,
    analysis_level: str = "full_analysis"
) -> Dict[str, Any]:
    """
    智能一次性分析 - 单次LLM调用包含所有洞察
    
    Args:
        query: 用户原始查询
        result_data: SQL执行结果数据
        sql: 执行的SQL语句
        analysis_level: 分析级别 (skip/summary_only/full_analysis)
        
    Returns:
        综合分析结果
    """
    try:
        if analysis_level == "skip" or not result_data:
            return {
                "success": True,
                "skip_analysis": True,
                "reason": "数据量不足或不需要分析"
            }
        
        # 计算基础统计信息
        stats = calculate_statistics(result_data)
        row_count = len(result_data)
        
        # 构建数据特征描述
        data_characteristics = f"""
数据行数: {row_count}
数值列: {', '.join(stats.get('numeric_columns', [])[:5])}
日期列: {', '.join(stats.get('date_columns', [])[:3])}
"""
        
        # 添加关键指标
        key_metrics = []
        for col in stats.get("numeric_columns", [])[:3]:
            col_stats = stats["summary"].get(col, {})
            if col_stats.get("sum"):
                key_metrics.append(f"{col}总计: {col_stats['sum']:.2f}")
            if col_stats.get("mean"):
                key_metrics.append(f"{col}平均: {col_stats['mean']:.2f}")
        
        metrics_desc = "\n".join(key_metrics) if key_metrics else "无明显数值指标"
        
        # 根据分析级别调整prompt
        if analysis_level == "summary_only":
            analysis_prompt = f"""快速分析以下查询结果，提供简洁摘要（不超过3句话）。

用户查询: {query}
SQL: {sql}

{data_characteristics}
关键指标:
{metrics_desc}

请返回JSON格式：
{{
    "summary": "数据摘要（1-2句话）",
    "key_insight": "关键发现（1句话）"
}}

只返回JSON，不要其他内容。"""
        else:  # full_analysis
            # 检测趋势和异常
            has_time = len(stats.get("date_columns", [])) > 0
            trend_desc = ""
            if has_time and stats.get("numeric_columns"):
                date_col = stats["date_columns"][0]
                value_col = stats["numeric_columns"][0]
                try:
                    growth_analysis = calculate_growth_rate(result_data, date_col, value_col)
                    if "error" not in growth_analysis:
                        trend_desc = f"\n趋势: {growth_analysis.get('trend', '')}方向，增长率{growth_analysis.get('total_growth_rate', 0):.1f}%"
                except:
                    pass
            
            analysis_prompt = f"""分析以下查询结果，提供关键洞察和建议（简洁明了）。

用户查询: {query}
SQL: {sql}

{data_characteristics}
关键指标:
{metrics_desc}{trend_desc}

请分析并返回JSON格式：
{{
    "summary": "数据摘要（2-3句话）",
    "key_insights": ["洞察1", "洞察2"],
    "recommendations": ["建议1"]
}}

只返回JSON，不要其他内容。"""
        
        # 单次LLM调用获取分析结果
        llm = get_default_model()
        response = llm.invoke([HumanMessage(content=analysis_prompt)])
        content = response.content.strip()
        
        # 提取JSON
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        
        result = json.loads(content)
        
        return {
            "success": True,
            "analysis_level": analysis_level,
            "summary": result.get("summary", ""),
            "key_insights": result.get("key_insights", result.get("key_insight", [])),
            "recommendations": result.get("recommendations", []),
            "row_count": row_count,
            "stats": stats
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"分析错误: {str(e)}"
        }


# 保留旧工具作为fallback（已禁用）
# @tool
# def detect_analysis_need(
#     query: str,
#     result_data: List[Dict[str, Any]],
#     sql: str
# ) -> Dict[str, Any]:
#     """已被intelligent_analysis替代"""
#     pass
# 
# 
# # 以下工具已被intelligent_analysis替代（已禁用）
# # @tool
# # def generate_data_summary(result_data: List[Dict[str, Any]]) -> Dict[str, Any]:
# #     """生成数据摘要统计 - 已被intelligent_analysis替代"""
# #     pass
# # 
# # 
# # @tool
# # def analyze_trends(result_data: List[Dict[str, Any]], query: str) -> Dict[str, Any]:
# #     """分析时间序列趋势 - 已被intelligent_analysis替代"""
# #     pass
# # 
# # 
# # @tool
# # def detect_data_anomalies(result_data: List[Dict[str, Any]]) -> Dict[str, Any]:
# #     """检测数据异常 - 已被intelligent_analysis替代"""
# #     pass
# # 
# # 
# # @tool
# # def generate_business_recommendations(...) -> Dict[str, Any]:
# #     """基于分析结果生成业务建议 - 已被intelligent_analysis替代"""
# #     pass


class AnalystAgent:
    """分析师代理 - 优化版（规则判断 + 单次LLM调用）"""

    def __init__(self):
        self.name = "analyst_agent"
        self.llm = get_default_model()
        # 简化：只使用一个智能分析工具
        self.tools = [
            intelligent_analysis
        ]

        # 创建ReAct代理（保留以兼容supervisor）
        self.agent = create_react_agent(
            self.llm,
            self.tools,
            prompt=self._create_system_prompt,
            name=self.name,
        )
    
    def _create_system_prompt(self, state: SQLMessageState, config: RunnableConfig) -> list[AnyMessage]:
        """创建系统提示 - 简化版"""
        connection_id = extract_connection_id(state)
        
        system_msg = f"""你是一个高效的数据分析师。
**重要：当前数据库connection_id是 {connection_id}**

你的任务是快速分析查询结果并提供关键洞察：

工作流程（简化）：
1. 使用 intelligent_analysis 工具进行一次性综合分析
2. 工具会自动判断分析级别并返回结果

分析原则：
- 简洁明了，直奔主题
- 关注用户真正关心的业务问题
- 提供可操作的洞察，避免空泛描述
- 根据数据量自动调整分析深度

输出要求：
- 2-3句话的摘要
- 1-2个关键洞察
- 1个可选建议（如果适用）

请快速提供有价值的分析。"""

        return [{"role": "system", "content": system_msg}] + state["messages"]

    async def process(self, state: SQLMessageState) -> Dict[str, Any]:
        """处理分析任务 - 优化版"""
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
            
            # 获取用户查询和SQL
            user_query = state.get("original_query") or state.get("enriched_query", "")
            if not user_query and state.get("messages"):
                first_message = state["messages"][0]
                user_query = first_message.content if hasattr(first_message, 'content') else ""
            
            generated_sql = state.get("generated_sql", "")
            
            # 快速规则判断（不调用LLM）
            analysis_level = rule_based_analysis_check(result_data, generated_sql)
            
            if analysis_level == "skip":
                return {
                    "messages": [AIMessage(content="查询结果无需分析")],
                    "current_stage": "chart_generation",
                    "needs_analysis": False
                }

            # 准备输入消息
            messages = [
                HumanMessage(content=f"""请使用intelligent_analysis工具分析以下查询结果：

用户查询: {user_query}
SQL: {generated_sql}
结果行数: {len(result_data)}
分析级别: {analysis_level}

请快速分析并返回结果。""")
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
