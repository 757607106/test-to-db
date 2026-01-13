"""
澄清代理 (Clarification Agent)
负责检测用户查询是否需要澄清，并生成澄清问题
"""
from typing import Dict, Any, List
from uuid import uuid4

from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, AIMessage, AnyMessage
from langchain_core.runnables import RunnableConfig
from langgraph.prebuilt import create_react_agent

from app.core.state import SQLMessageState, extract_connection_id
from app.core.llms import get_default_model
from app.db.session import SessionLocal
from app import crud


@tool
def detect_ambiguity(query: str, connection_id: int) -> Dict[str, Any]:
    """
    检测用户查询是否存在模糊或需要澄清的地方
    
    Args:
        query: 用户的自然语言查询
        connection_id: 数据库连接ID
        
    Returns:
        检测结果，包括是否需要澄清、模糊点列表等
    """
    try:
        # 获取数据库schema信息用于辅助判断
        db = SessionLocal()
        try:
            tables = crud.schema_table.get_by_connection(db, connection_id=connection_id, limit=100)
            tables_info = [{"table_name": t.table_name} for t in tables]
        finally:
            db.close()
        
        # 使用LLM分析查询是否需要澄清
        llm = get_default_model()
        
        analysis_prompt = f"""分析以下用户查询，判断是否需要向用户澄清信息。

用户查询: {query}

可用的数据库表: {', '.join([t.get('table_name', '') for t in tables_info[:10]])}

请判断以下方面是否存在模糊：
1. **时间范围模糊**: 查询提到"最近"、"近期"等但未指定具体时间
2. **字段选择模糊**: 查询想要的数据字段不明确
3. **多义词**: 查询中的词可能有多种理解（如"销售额"可能指交易金额或订单数）
4. **缺少过滤条件**: 查询可能返回大量数据，但未指定筛选条件
5. **表名不明确**: 查询涉及的业务实体可能对应多个表

请以JSON格式返回：
{{
    "needs_clarification": true/false,
    "ambiguity_points": [
        {{"type": "时间范围模糊", "description": "...", "severity": "high/medium/low"}}
    ],
    "confidence": 0.0-1.0,
    "reason": "简要说明"
}}

只返回JSON，不要其他内容。"""

        response = llm.invoke([HumanMessage(content=analysis_prompt)])
        content = response.content.strip()
        
        # 提取JSON
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        
        import json
        result = json.loads(content)
        
        return {
            "success": True,
            "needs_clarification": result.get("needs_clarification", False),
            "ambiguity_points": result.get("ambiguity_points", []),
            "confidence": result.get("confidence", 0.5),
            "reason": result.get("reason", "")
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "needs_clarification": False
        }


@tool
def generate_clarification_questions(
    query: str,
    ambiguity_points: List[Dict[str, Any]],
    connection_id: int
) -> Dict[str, Any]:
    """
    根据检测到的模糊点生成澄清问题
    
    Args:
        query: 用户原始查询
        ambiguity_points: 检测到的模糊点列表
        connection_id: 数据库连接ID
        
    Returns:
        生成的澄清问题列表
    """
    try:
        if not ambiguity_points:
            return {
                "success": True,
                "questions": []
            }
        
        # 获取数据库信息辅助生成问题
        db = SessionLocal()
        try:
            tables = crud.schema_table.get_by_connection(db, connection_id=connection_id, limit=100)
            tables_info = [{"table_name": t.table_name} for t in tables]
        finally:
            db.close()
        
        llm = get_default_model()
        
        # 构建提示
        ambiguity_desc = "\n".join([
            f"- {point.get('type', '')}: {point.get('description', '')}"
            for point in ambiguity_points[:3]  # 最多处理3个模糊点
        ])
        
        question_prompt = f"""基于以下模糊点，生成简洁明了的澄清问题（最多3个）。

原始查询: {query}

模糊点:
{ambiguity_desc}

数据库表信息: {', '.join([t.get('table_name', '') for t in tables_info[:10]])}

请生成澄清问题，每个问题应该：
1. 简洁明了，易于回答
2. 提供选项（如果适用）
3. 帮助明确用户意图

返回JSON格式：
{{
    "questions": [
        {{
            "id": "q1",
            "question": "问题内容",
            "type": "choice",  // 或 "text"
            "options": ["选项1", "选项2", "选项3"],  // type为choice时提供
            "related_ambiguity": "时间范围模糊"
        }}
    ]
}}

只返回JSON，不要其他内容。"""

        response = llm.invoke([HumanMessage(content=question_prompt)])
        content = response.content.strip()
        
        # 提取JSON
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        
        import json
        result = json.loads(content)
        
        questions = result.get("questions", [])
        
        # 确保每个问题都有ID
        for i, q in enumerate(questions):
            if "id" not in q:
                q["id"] = f"q{i+1}"
        
        return {
            "success": True,
            "questions": questions[:3]  # 最多3个问题
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "questions": []
        }


@tool
def process_user_clarification(
    original_query: str,
    clarification_qa: List[Dict[str, Any]],
    connection_id: int
) -> Dict[str, Any]:
    """
    处理用户的澄清回复，生成增强后的查询
    
    Args:
        original_query: 用户原始查询
        clarification_qa: 澄清问答对列表 [{"question": "...", "answer": "..."}]
        connection_id: 数据库连接ID
        
    Returns:
        处理结果，包括增强后的查询和是否需要继续澄清
    """
    try:
        llm = get_default_model()
        
        # 构建澄清信息
        clarifications = "\n".join([
            f"Q: {qa.get('question', '')}\nA: {qa.get('answer', '')}"
            for qa in clarification_qa
        ])
        
        enhancement_prompt = f"""基于用户的澄清回复，增强原始查询。

原始查询: {original_query}

澄清信息:
{clarifications}

请：
1. 将澄清信息整合到查询中
2. 生成一个更明确、更完整的查询描述
3. 判断是否还需要进一步澄清

返回JSON格式：
{{
    "enriched_query": "增强后的完整查询描述",
    "needs_more_clarification": true/false,
    "reason": "是否需要继续澄清的原因",
    "confidence": 0.0-1.0
}}

只返回JSON，不要其他内容。"""

        response = llm.invoke([HumanMessage(content=enhancement_prompt)])
        content = response.content.strip()
        
        # 提取JSON
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        
        import json
        result = json.loads(content)
        
        return {
            "success": True,
            "enriched_query": result.get("enriched_query", original_query),
            "needs_more_clarification": result.get("needs_more_clarification", False),
            "confidence": result.get("confidence", 0.8),
            "reason": result.get("reason", "")
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "enriched_query": original_query,
            "needs_more_clarification": False
        }


class ClarificationAgent:
    """澄清代理"""

    def __init__(self):
        self.name = "clarification_agent"
        self.llm = get_default_model()
        self.tools = [
            detect_ambiguity,
            generate_clarification_questions,
            process_user_clarification
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
        clarification_round = state.get("clarification_round", 0)
        max_rounds = state.get("max_clarification_rounds", 2)
        
        system_msg = f"""你是一个专业的查询澄清专家。
        **重要：当前数据库connection_id是 {connection_id}**
        **当前澄清轮次: {clarification_round}/{max_rounds}**

你的任务是：
1. 检测用户查询是否存在模糊或不明确之处
2. 如需澄清，生成简洁明了的澄清问题
3. 处理用户的澄清回复，生成增强后的查询

工作原则：
- 只在真正需要时才要求澄清（不要过度澄清）
- 问题要简洁、易于回答
- 优先使用选择题而非开放式问题
- 最多生成3个澄清问题
- 考虑已经进行的澄清轮次，避免重复询问

澄清场景：
1. **时间范围不明确**: "最近"、"近期"等模糊时间词
2. **字段选择不清**: 不清楚用户想看哪些数据字段
3. **多义词**: 可能有多种理解的业务术语
4. **缺少关键过滤条件**: 查询可能返回过多数据
5. **表名模糊**: 业务实体可能对应多个数据库表

当前状态：
- 如果这是首次查询，使用 detect_ambiguity 检测是否需要澄清
- 如果用户已提供澄清回复，使用 process_user_clarification 处理

请智能判断并采取适当行动。"""

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
