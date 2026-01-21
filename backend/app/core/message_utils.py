"""
消息工具模块
提供消息历史验证和修复功能，以及MCP工具包装类
"""
import json
import hashlib
from typing import List, Dict, Any, Optional, Type
from langchain_core.messages import BaseMessage, AIMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from app.schemas.agent_message import ToolResponse


def generate_tool_call_id(tool_name: str, args: Dict[str, Any]) -> str:
    """
    生成稳定且唯一的 tool call ID
    
    使用工具名称和参数生成一个稳定的哈希ID，确保：
    1. 相同的工具调用生成相同的ID（可用于缓存/去重）
    2. 不同的工具调用生成不同的ID
    3. ID格式符合 LangChain 约定（call_前缀）
    4. 不会出现重复ID的问题（如 "call_xxxcall_xxx"）
    
    Args:
        tool_name: 工具名称
        args: 工具参数字典
        
    Returns:
        str: 格式为 "call_{16位哈希}" 的唯一ID
        
    Examples:
        >>> generate_tool_call_id("execute_sql_query", {"sql": "SELECT * FROM users", "conn_id": 1})
        'call_a1b2c3d4e5f6g7h8'
        
        >>> generate_tool_call_id("execute_sql_query", {"sql": "SELECT * FROM users", "conn_id": 1})
        'call_a1b2c3d4e5f6g7h8'  # 相同参数生成相同ID
    """
    # 将参数按键排序后转为JSON字符串，确保参数顺序不影响哈希结果
    content = f"{tool_name}:{json.dumps(args, sort_keys=True, ensure_ascii=False)}"
    
    # 使用 MD5 生成哈希（足够用于此场景，且速度快）
    hash_id = hashlib.md5(content.encode('utf-8')).hexdigest()[:16]
    
    return f"call_{hash_id}"


def create_ai_message_with_tools(content: str, tool_calls: List[Dict[str, Any]]) -> AIMessage:
    """
    创建包含工具调用的 AIMessage，并验证工具调用的完整性
    
    确保：
    1. 所有 tool call 都有非空的 name
    2. 所有 tool call 都有唯一的 id
    3. 过滤掉无效的 tool call
    
    Args:
        content: AI消息内容
        tool_calls: 工具调用列表
        
    Returns:
        AIMessage: 包含验证后的工具调用的消息
        
    Examples:
        >>> create_ai_message_with_tools(
        ...     "",
        ...     [{"name": "execute_sql", "args": {"sql": "..."}, "id": "call_123"}]
        ... )
        AIMessage(content='', tool_calls=[...])
    """
    import logging
    logger = logging.getLogger(__name__)
    
    validated_calls = []
    seen_ids = set()
    
    for tc in tool_calls:
        # 检查 name 是否有效
        tool_name = tc.get("name", "").strip()
        if not tool_name:
            logger.warning(f"跳过空 name 的 tool call: {tc}")
            continue
        
        # 检查或生成 ID
        tool_id = tc.get("id")
        if not tool_id:
            # 如果没有ID，自动生成一个
            tool_id = generate_tool_call_id(tool_name, tc.get("args", {}))
            tc["id"] = tool_id
        
        # 检查 ID 是否重复
        if tool_id in seen_ids:
            logger.warning(f"检测到重复的 tool call ID: {tool_id}，重新生成")
            tool_id = generate_tool_call_id(
                tool_name, 
                {**tc.get("args", {}), "_unique": len(validated_calls)}
            )
            tc["id"] = tool_id
        
        seen_ids.add(tool_id)
        validated_calls.append(tc)
    
    return AIMessage(content=content, tool_calls=validated_calls)


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
            工具执行结果的字符串表示（JSON格式的ToolResponse）
            
        Validates: Requirements 3.2, 3.3
        """
        try:
            # 执行MCP工具
            result = await self.mcp_tool.ainvoke(kwargs if kwargs else {})
            
            # 包装为 ToolResponse 以确保格式统一
            if isinstance(result, ToolResponse):
                # 已经是 ToolResponse，直接序列化
                return result.model_dump_json()
            elif isinstance(result, str):
                # 字符串结果，包装为 ToolResponse
                response = ToolResponse(status="success", data={"result": result})
                return response.model_dump_json()
            else:
                # 其他类型（Dict等），包装为 ToolResponse
                response = ToolResponse(status="success", data=result)
                return response.model_dump_json()
        except Exception as e:
            # 错误也要返回 ToolResponse 格式
            error_response = ToolResponse(
                status="error",
                error=str(e),
                metadata={"tool_name": self.name}
            )
            return error_response.model_dump_json()
    
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
            包含工具执行结果的ToolMessage（内容为ToolResponse格式）
            
        Validates: Requirements 3.2, 3.3
        """
        config = config or {}
        tool_call_id = config.get("configurable", {}).get("tool_call_id", "unknown")
        
        try:
            # 执行MCP工具
            result = await self.mcp_tool.ainvoke(input, config)
            
            # 包装为 ToolResponse 确保格式统一
            if isinstance(result, ToolResponse):
                response = result
            elif isinstance(result, str):
                response = ToolResponse(status="success", data={"result": result})
            else:
                response = ToolResponse(status="success", data=result)
            
            return ToolMessage(
                content=response.model_dump_json(),  # ✅ 使用 Pydantic 标准序列化
                tool_call_id=tool_call_id,
                name=self.name
            )
        except Exception as e:
            # 错误也要返回 ToolResponse 格式的 ToolMessage
            error_response = ToolResponse(
                status="error",
                error=str(e),
                metadata={"tool_name": self.name}
            )
            
            return ToolMessage(
                content=error_response.model_dump_json(),  # ✅ 使用 Pydantic 标准序列化
                tool_call_id=tool_call_id,
                name=self.name
            )

