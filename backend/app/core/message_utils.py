"""
消息工具模块
提供消息历史验证和修复功能，以及MCP工具包装类
"""
import json
from typing import List, Dict, Any, Optional, Type
from langchain_core.messages import BaseMessage, AIMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field


def validate_and_fix_message_history(messages: List[BaseMessage]) -> List[BaseMessage]:
    """
    验证并修复消息历史，确保所有Tool Call都有对应的ToolMessage
    
    Args:
        messages: 消息历史列表
        
    Returns:
        修复后的消息历史列表
        
    Validates: Requirements 2.5, 4.4
    """
    if not messages:
        return messages
    
    fixed_messages = []
    pending_tool_calls = {}
    
    for message in messages:
        fixed_messages.append(message)
        
        # 收集Tool Calls
        if isinstance(message, AIMessage) and hasattr(message, "tool_calls") and message.tool_calls:
            for tool_call in message.tool_calls:
                # 使用tool_call的id作为键
                tool_call_id = tool_call.get("id") if isinstance(tool_call, dict) else getattr(tool_call, "id", None)
                if tool_call_id:
                    pending_tool_calls[tool_call_id] = tool_call
        
        # 匹配ToolMessages
        if isinstance(message, ToolMessage):
            tool_call_id = message.tool_call_id
            if tool_call_id in pending_tool_calls:
                del pending_tool_calls[tool_call_id]
    
    # 为未匹配的Tool Calls创建占位ToolMessage
    for tool_call_id, tool_call in pending_tool_calls.items():
        tool_name = tool_call.get("name") if isinstance(tool_call, dict) else getattr(tool_call, "name", "unknown_tool")
        
        placeholder_message = ToolMessage(
            content=json.dumps({
                "status": "pending",
                "message": "Tool call result not yet available"
            }),
            tool_call_id=tool_call_id,
            name=tool_name
        )
        fixed_messages.append(placeholder_message)
    
    return fixed_messages


class MCPToolWrapper(BaseTool):
    """
    MCP工具包装类，确保所有MCP工具调用都返回ToolMessage
    
    Validates: Requirements 3.2, 3.3
    """
    
    name: str = Field(description="工具名称")
    description: str = Field(default="", description="工具描述")
    mcp_tool: Any = Field(description="原始MCP工具对象")
    
    class Config:
        arbitrary_types_allowed = True
    
    def __init__(self, mcp_tool: Any, tool_name: str, **kwargs):
        """
        初始化MCP工具包装器
        
        Args:
            mcp_tool: 原始MCP工具对象
            tool_name: 工具名称
        """
        description = getattr(mcp_tool, "description", "")
        super().__init__(
            name=tool_name,
            description=description,
            mcp_tool=mcp_tool,
            **kwargs
        )
    
    def _run(self, *args, **kwargs) -> str:
        """同步运行（不支持，抛出错误）"""
        raise NotImplementedError("MCPToolWrapper 只支持异步调用，请使用 _arun")
    
    async def _arun(self, *args, **kwargs) -> str:
        """
        异步执行MCP工具
        
        Args:
            *args: 位置参数
            **kwargs: 关键字参数
            
        Returns:
            工具执行结果的字符串表示
            
        Validates: Requirements 3.2, 3.3
        """
        try:
            # 执行MCP工具
            result = await self.mcp_tool.ainvoke(kwargs if kwargs else {})
            
            # 返回字符串结果
            return result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)
        except Exception as e:
            # 错误也要返回结果字符串
            error_result = {
                "error": str(e),
                "status": "error",
                "tool_name": self.name
            }
            return json.dumps(error_result, ensure_ascii=False)
    
    def invoke(self, input: Dict[str, Any], config: Optional[RunnableConfig] = None) -> ToolMessage:
        """
        同步执行MCP工具并返回ToolMessage（用于兼容性）
        
        Args:
            input: 工具输入参数
            config: 运行配置
            
        Returns:
            包含工具执行结果的ToolMessage
        """
        import asyncio
        
        # 如果在异步上下文中，直接调用ainvoke
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 在已运行的事件循环中，创建任务
                return asyncio.create_task(self.ainvoke(input, config))
            else:
                # 没有运行的事件循环，创建新的
                return loop.run_until_complete(self.ainvoke(input, config))
        except RuntimeError:
            # 没有事件循环，创建新的
            return asyncio.run(self.ainvoke(input, config))
    
    async def ainvoke(self, input: Dict[str, Any], config: Optional[RunnableConfig] = None) -> ToolMessage:
        """
        异步执行MCP工具并返回ToolMessage
        
        Args:
            input: 工具输入参数
            config: 运行配置
            
        Returns:
            包含工具执行结果的ToolMessage
            
        Validates: Requirements 3.2, 3.3
        """
        config = config or {}
        tool_call_id = config.get("configurable", {}).get("tool_call_id", "unknown")
        
        try:
            # 执行MCP工具
            result = await self.mcp_tool.ainvoke(input, config)
            
            # 将结果包装成ToolMessage
            content = result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)
            
            return ToolMessage(
                content=content,
                tool_call_id=tool_call_id,
                name=self.name
            )
        except Exception as e:
            # 错误也要返回ToolMessage
            error_content = json.dumps({
                "error": str(e),
                "status": "error",
                "tool_name": self.name
            }, ensure_ascii=False)
            
            return ToolMessage(
                content=error_content,
                tool_call_id=tool_call_id,
                name=self.name
            )

