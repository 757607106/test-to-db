"""
错误恢复代理 - LLM 驱动版本
负责分析错误、提供恢复策略和自动修复能力

设计原则：
- 使用 LLM 智能分析错误，而非硬编码规则
- 让 LLM 决定修复策略
- 避免误判
"""
import logging
from typing import Dict, Any, List, Annotated
from langchain_core.tools import tool, InjectedToolCallId
from langchain_core.messages import HumanMessage, ToolMessage
from langgraph.prebuilt import create_react_agent, InjectedState
from langgraph.types import Command

from app.core.state import SQLMessageState
from app.core.agent_config import get_agent_llm, CORE_AGENT_SQL_GENERATOR

logger = logging.getLogger(__name__)


@tool
def analyze_and_fix_sql_error(
    state: Annotated[dict, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId]
) -> Command:
    """
    分析 SQL 错误并尝试修复。使用 LLM 智能分析错误类型和修复策略。
    
    从状态中获取：SQL、错误历史、Schema 信息
    
    Returns:
        Command: 更新状态的命令
    """
    # 获取当前消息历史（包含 LLM 生成的 AIMessage）
    # 修复：Command.PARENT 需要包含完整消息历史，否则子 Agent 的 AIMessage 会丢失
    current_messages = list(state.get("messages", []))
    
    try:
        # 从状态获取必要信息
        sql_query = state.get("generated_sql", "")
        error_history = state.get("error_history", [])
        schema_info = state.get("schema_info", {})
        retry_count = state.get("retry_count", 0)
        max_retries = state.get("max_retries", 3)
        db_type = state.get("db_type", "mysql")
        
        if not sql_query:
            error_msg = ToolMessage(
                content="恢复失败：没有找到需要修复的 SQL 语句",
                tool_call_id=tool_call_id
            )
            return Command(
                graph=Command.PARENT,
                update={
                    "current_stage": "terminated",
                    "messages": current_messages + [error_msg]
                }
            )
        
        # 获取最新错误消息
        error_message = ""
        if error_history:
            latest_error = error_history[-1]
            error_message = latest_error.get("error", "")
        
        if not error_message:
            tool_msg = ToolMessage(
                content="没有发现错误，继续验证",
                tool_call_id=tool_call_id
            )
            return Command(
                graph=Command.PARENT,
                update={
                    "current_stage": "sql_validation",
                    "messages": current_messages + [tool_msg]
                }
            )
        
        # 使用 LLM 分析错误并生成修复后的 SQL
        llm = get_agent_llm(CORE_AGENT_SQL_GENERATOR, use_wrapper=True)
        
        # 构建 Schema 上下文
        schema_context = ""
        if schema_info:
            tables = schema_info.get("schema_context", {})
            if isinstance(tables, dict):
                schema_context = f"可用的表和字段: {list(tables.keys())}"
        
        prompt = f"""你是 SQL 错误修复专家。请分析以下错误并修复 SQL。

**原始 SQL**:
```sql
{sql_query}
```

**错误信息**:
{error_message}

**数据库类型**: {db_type}

**Schema 信息**: {schema_context}

**重试次数**: {retry_count}/{max_retries}

**请分析错误原因并直接输出修复后的 SQL。如果无法修复，请说明原因。**

注意：
1. 只输出修复后的 SQL 语句，不要添加解释
2. 如果错误是由于表或字段不存在，请根据 Schema 信息修正
3. 如果是语法错误，请修正语法
4. 如果无法确定如何修复，输出 "CANNOT_FIX: " 后面跟原因
5. 确保 SQL 以分号结尾
"""
        
        response = llm.invoke([HumanMessage(content=prompt)])
        llm_response = response.content.strip()
        
        # 解析 LLM 响应
        if llm_response.startswith("CANNOT_FIX:"):
            # 无法修复
            reason = llm_response.replace("CANNOT_FIX:", "").strip()
            new_retry_count = retry_count + 1
            
            if new_retry_count >= max_retries:
                next_stage = "terminated"
                message = f"SQL 修复失败: {reason}。已达最大重试次数。"
            else:
                next_stage = "sql_generation"
                message = f"SQL 修复失败: {reason}。将重新生成 (重试 {new_retry_count}/{max_retries})"
            
            logger.warning(f"[ErrorRecovery] {message}")
            
            tool_msg = ToolMessage(content=message, tool_call_id=tool_call_id)
            return Command(
                graph=Command.PARENT,
                update={
                    "current_stage": next_stage,
                    "retry_count": new_retry_count,
                    "messages": current_messages + [tool_msg]
                }
            )
        else:
            # 提取 SQL（移除可能的 markdown 代码块）
            fixed_sql = llm_response
            if "```sql" in fixed_sql:
                fixed_sql = fixed_sql.split("```sql")[1].split("```")[0].strip()
            elif "```" in fixed_sql:
                fixed_sql = fixed_sql.split("```")[1].split("```")[0].strip()
            
            # 确保以分号结尾
            if fixed_sql and not fixed_sql.rstrip().endswith(';'):
                fixed_sql = fixed_sql.rstrip() + ';'
            
            message = "SQL 已通过 LLM 智能修复"
            logger.info(f"[ErrorRecovery] {message}")
            
            tool_msg = ToolMessage(content=message, tool_call_id=tool_call_id)
            return Command(
                graph=Command.PARENT,
                update={
                    "current_stage": "sql_validation",
                    "generated_sql": fixed_sql,
                    "retry_count": 0,
                    "messages": current_messages + [tool_msg]
                }
            )
        
    except Exception as e:
        logger.error(f"[ErrorRecovery] 修复异常: {e}")
        error_msg = ToolMessage(
            content=f"SQL 修复失败: {str(e)}",
            tool_call_id=tool_call_id
        )
        return Command(
            graph=Command.PARENT,
            update={
                "current_stage": "terminated",
                "messages": current_messages + [error_msg]
            }
        )


class ErrorRecoveryAgent:
    """错误恢复代理 - LLM 驱动"""

    def __init__(self):
        self.name = "error_recovery_agent"
        self.llm = get_agent_llm(CORE_AGENT_SQL_GENERATOR)
        self.tools = [analyze_and_fix_sql_error]
        
        # 创建 ReAct 代理
        self.agent = create_react_agent(
            self.llm,
            self.tools,
            prompt=self._create_system_prompt(),
            name=self.name,
            state_schema=SQLMessageState,
        )
    
    def _create_system_prompt(self) -> str:
        """创建系统提示"""
        return """你是一个专业的 SQL 错误恢复专家。

你的任务是分析 SQL 错误并尝试修复。使用 analyze_and_fix_sql_error 工具来分析错误并生成修复后的 SQL。

工作流程：
1. 调用 analyze_and_fix_sql_error 工具
2. 工具会使用 LLM 智能分析错误并生成修复后的 SQL
3. 返回修复结果

只需要调用一次工具即可完成任务。"""

    async def recover(self, state: SQLMessageState) -> Dict[str, Any]:
        """执行错误恢复"""
        try:
            error_history = state.get("error_history", [])
            current_sql = state.get("generated_sql", "")
            
            # 获取最新错误
            latest_error = error_history[-1] if error_history else {}
            
            # 准备输入消息
            messages = [
                HumanMessage(content=f"""
请分析以下错误并尝试修复：

当前 SQL: {current_sql}
最新错误: {latest_error.get('error', '未知错误')}

请使用 analyze_and_fix_sql_error 工具进行修复。
""")
            ]
            
            # 调用恢复代理
            result = await self.agent.ainvoke({
                "messages": messages
            })
            
            return {
                "success": True,
                "messages": result.get("messages", [])
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }


# 创建全局实例
error_recovery_agent = ErrorRecoveryAgent()
