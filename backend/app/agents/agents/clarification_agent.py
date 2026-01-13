"""
澄清代理 (Clarification Agent) - 优化版
负责快速检测用户查询是否需要澄清，并生成澄清问题
优化：合并检测和问题生成为单次LLM调用
"""
from typing import Dict, Any, List
from uuid import uuid4
import json

from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, AIMessage, AnyMessage
from langchain_core.runnables import RunnableConfig
from langgraph.prebuilt import create_react_agent

from app.core.state import SQLMessageState, extract_connection_id
from app.core.llms import get_default_model
from app.db.session import SessionLocal
from app import crud


@tool
def quick_clarification_check(query: str, connection_id: int) -> Dict[str, Any]:
    """
    一次性检测并生成澄清问题 - 优化为单次LLM调用
    
    Args:
        query: 用户的自然语言查询
        connection_id: 数据库连接ID
        
    Returns:
        检测结果和澄清问题（如果需要）
    """
    try:
        # 快速规则过滤：明确的查询直接跳过
        clear_indicators = ["SELECT", "WHERE", "FROM", "具体的", "明确的"]
        ambiguous_keywords = ["最近", "近期", "一些", "某些", "大概", "可能"]
        
        # 如果查询包含SQL关键词或非常明确，直接跳过
        query_upper = query.upper()
        if any(keyword in query_upper for keyword in clear_indicators[:3]):
            return {
                "success": True,
                "needs_clarification": False,
                "reason": "查询包含明确的SQL语句或结构化查询",
                "questions": []
            }
        
        # 获取数据库schema信息用于辅助判断
        db = SessionLocal()
        try:
            tables = crud.schema_table.get_by_connection(db, connection_id=connection_id, limit=100)
            tables_info = [{"table_name": t.table_name} for t in tables]
        finally:
            db.close()
        
        # 使用LLM一次性完成检测和问题生成
        llm = get_default_model()
        
        combined_prompt = f"""分析用户查询，判断是否需要澄清，如需澄清则直接生成问题。

用户查询: {query}

可用的数据库表: {', '.join([t.get('table_name', '') for t in tables_info[:10]])}

请快速判断以下方面：
1. 时间范围是否模糊（"最近"、"近期"等）
2. 字段选择是否不明确
3. 是否有多义词
4. 是否缺少关键过滤条件
5. 表名是否不明确

如果查询足够明确，直接返回 needs_clarification: false
如果需要澄清，直接生成1-2个简洁的澄清问题（不要超过2个）

返回JSON格式：
{{
    "needs_clarification": true/false,
    "reason": "简要说明",
    "questions": [
        {{
            "id": "q1",
            "question": "问题内容（简洁明了）",
            "type": "choice",  // 或 "text"
            "options": ["选项1", "选项2", "选项3"]  // type为choice时提供
        }}
    ]
}}

只返回JSON，不要其他内容。"""

        response = llm.invoke([HumanMessage(content=combined_prompt)])
        content = response.content.strip()
        
        # 提取JSON
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        
        result = json.loads(content)
        
        # 确保每个问题都有ID
        questions = result.get("questions", [])
        for i, q in enumerate(questions):
            if "id" not in q:
                q["id"] = f"q{i+1}"
        
        return {
            "success": True,
            "needs_clarification": result.get("needs_clarification", False),
            "reason": result.get("reason", ""),
            "questions": questions[:2],  # 最多2个问题
            "confidence": 0.8
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "needs_clarification": False,
            "questions": []
        }


# 保留原detect_ambiguity作为fallback（已禁用）
# @tool
# def detect_ambiguity(query: str, connection_id: int) -> Dict[str, Any]:
#     """
#     检测用户查询是否存在模糊或需要澄清的地方 - 已被quick_clarification_check替代
#     """
#     pass
# 
# 
# # @tool
# # def generate_clarification_questions(
# #     query: str,
# #     ambiguity_points: List[Dict[str, Any]],
# #     connection_id: int
# # ) -> Dict[str, Any]:
# #     """
# #     根据检测到的模糊点生成澄清问题 - 已被quick_clarification_check替代
# #     """
# #     pass


# 保留process_user_clarification用于处理澄清回复（简化版）
@tool
def process_user_clarification(
    original_query: str,
    clarification_qa: List[Dict[str, Any]],
    connection_id: int
) -> Dict[str, Any]:
    """
    处理用户的澄清回复，生成增强后的查询（简化版 - 直接合并）
    
    Args:
        original_query: 用户原始查询
        clarification_qa: 澄清问答对列表 [{"question": "...", "answer": "..."}]
        connection_id: 数据库连接ID
        
    Returns:
        处理结果，包括增强后的查询
    """
    try:
        # 简化：直接将澄清信息附加到原查询，不再调用LLM
        if not clarification_qa:
            return {
                "success": True,
                "enriched_query": original_query,
                "needs_more_clarification": False
            }
        
        # 构建增强查询
        clarifications = ", ".join([
            f"{qa.get('answer', '')}"
            for qa in clarification_qa
            if qa.get('answer')
        ])
        
        enriched_query = f"{original_query} ({clarifications})"
        
        return {
            "success": True,
            "enriched_query": enriched_query,
            "needs_more_clarification": False,
            "confidence": 0.9
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "enriched_query": original_query,
            "needs_more_clarification": False
        }


class ClarificationAgent:
    """澄清代理 - 优化版（单次LLM调用）"""

    def __init__(self):
        self.name = "clarification_agent"
        self.llm = get_default_model()
        # 简化：只使用两个工具
        self.tools = [
            quick_clarification_check,
            process_user_clarification
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
        clarification_round = state.get("clarification_round", 0)
        max_rounds = state.get("max_clarification_rounds", 2)
        
        system_msg = f"""你是一个高效的查询澄清专家。
**重要：当前数据库connection_id是 {connection_id}**
**当前澄清轮次: {clarification_round}/{max_rounds}**

你的任务是快速判断查询是否需要澄清：

工作流程（简化）：
1. 如果是首次查询，使用 quick_clarification_check 一次性完成检测和问题生成
2. 如果用户已提供澄清回复，使用 process_user_clarification 处理

工作原则：
- 只在真正需要时才要求澄清
- 最多生成1-2个问题（不要过度澄清）
- 优先使用选择题
- 如果查询足够明确，直接跳过

明确查询示例：
- "查询2023年1月的销售数据"
- "显示用户表中的所有记录"
- "统计订单总数"

需要澄清的示例：
- "最近的销售情况" (时间不明确)
- "查询一些用户信息" (字段不明确)

请快速判断并执行。"""

        return [{"role": "system", "content": system_msg}] + state["messages"]

    async def process(self, state: SQLMessageState) -> Dict[str, Any]:
        """处理澄清任务"""
        try:
            # 获取用户查询
            user_query = state["messages"][-1].content
            if isinstance(user_query, list):
                user_query = user_query[0]["text"]
            
            # 获取connection_id
            connection_id = state.get("connection_id", 15)
            clarification_round = state.get("clarification_round", 0)
            max_rounds = state.get("max_clarification_rounds", 2)

            # 检查是否已达到最大澄清轮次
            if clarification_round >= max_rounds:
                return {
                    "messages": [AIMessage(content="已达到最大澄清轮次，将基于现有信息继续处理。")],
                    "current_stage": "schema_analysis",
                    "needs_clarification": False
                }

            # 准备输入消息
            messages = [
                HumanMessage(content=f"""请分析以下用户查询是否需要澄清：

查询: {user_query}
连接ID: {connection_id}
当前澄清轮次: {clarification_round}/{max_rounds}

请使用提供的工具进行分析和处理。""")
            ]

            # 调用代理
            result = await self.agent.ainvoke({
                "messages": messages
            })
            
            # 更新状态
            state["agent_messages"]["clarification_agent"] = result
            
            return {
                "messages": result["messages"],
                "current_stage": "schema_analysis"  # 默认进入下一阶段
            }
            
        except Exception as e:
            # 记录错误，但不阻塞流程
            print(f"澄清代理错误: {str(e)}")
            return {
                "messages": [AIMessage(content=f"澄清检测时出现问题，将直接处理查询: {str(e)}")],
                "current_stage": "schema_analysis",
                "needs_clarification": False
            }


# 创建全局实例
clarification_agent = ClarificationAgent()
