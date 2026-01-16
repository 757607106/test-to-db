"""
消息工具模块的单元测试
测试validate_and_fix_message_history和MCPToolWrapper的功能
"""
import pytest
import json
from unittest.mock import AsyncMock, Mock
from langchain_core.messages import AIMessage, ToolMessage, HumanMessage
from langchain_core.runnables import RunnableConfig

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.message_utils import validate_and_fix_message_history, MCPToolWrapper


class TestValidateAndFixMessageHistory:
    """测试validate_and_fix_message_history函数"""
    
    def test_empty_message_list(self):
        """测试空消息列表"""
        result = validate_and_fix_message_history([])
        assert result == []
    
    def test_no_tool_calls(self):
        """测试没有Tool Calls的消息历史"""
        messages = [
            HumanMessage(content="Hello"),
            AIMessage(content="Hi there!")
        ]
        result = validate_and_fix_message_history(messages)
        assert len(result) == 2
        assert result == messages
    
    def test_tool_call_with_matching_tool_message(self):
        """测试Tool Call有对应的ToolMessage"""
        tool_call = {
            "id": "call_123",
            "name": "test_tool",
            "args": {"param": "value"}
        }
        
        messages = [
            AIMessage(content="", tool_calls=[tool_call]),
            ToolMessage(
                content="Tool result",
                tool_call_id="call_123",
                name="test_tool"
            )
        ]
        
        result = validate_and_fix_message_history(messages)
        # 应该保持原样，不添加额外消息
        assert len(result) == 2
        assert isinstance(result[0], AIMessage)
        assert isinstance(result[1], ToolMessage)
    
    def test_tool_call_without_tool_message(self):
        """测试Tool Call缺少对应的ToolMessage"""
        tool_call = {
            "id": "call_456",
            "name": "missing_tool",
            "args": {"param": "value"}
        }
        
        messages = [
            AIMessage(content="", tool_calls=[tool_call])
        ]
        
        result = validate_and_fix_message_history(messages)
        # 应该添加一个占位ToolMessage
        assert len(result) == 2
        assert isinstance(result[0], AIMessage)
        assert isinstance(result[1], ToolMessage)
        assert result[1].tool_call_id == "call_456"
        assert result[1].name == "missing_tool"
        
        # 验证占位消息内容
        content = json.loads(result[1].content)
        assert content["status"] == "pending"
        assert "not yet available" in content["message"]
    
    def test_multiple_tool_calls_mixed(self):
        """测试多个Tool Calls，部分有ToolMessage，部分没有"""
        tool_call_1 = {
            "id": "call_1",
            "name": "tool_1",
            "args": {}
        }
        tool_call_2 = {
            "id": "call_2",
            "name": "tool_2",
            "args": {}
        }
        
        messages = [
            AIMessage(content="", tool_calls=[tool_call_1, tool_call_2]),
            ToolMessage(
                content="Result 1",
                tool_call_id="call_1",
                name="tool_1"
            )
            # call_2 没有对应的ToolMessage
        ]
        
        result = validate_and_fix_message_history(messages)
        # 应该添加一个占位ToolMessage给call_2
        assert len(result) == 3
        
        # 找到新添加的ToolMessage
        added_message = result[2]
        assert isinstance(added_message, ToolMessage)
        assert added_message.tool_call_id == "call_2"
        assert added_message.name == "tool_2"


class TestMCPToolWrapper:
    """测试MCPToolWrapper类"""
    
    @pytest.mark.asyncio
    async def test_successful_tool_execution(self):
        """测试工具成功执行"""
        # 创建模拟的MCP工具
        mock_tool = AsyncMock()
        mock_tool.ainvoke = AsyncMock(return_value={"result": "success", "data": 123})
        mock_tool.description = "Test tool"
        
        wrapper = MCPToolWrapper(mock_tool, "test_tool")
        
        # 执行工具
        config = RunnableConfig(configurable={"tool_call_id": "call_789"})
        result = await wrapper.ainvoke({"input": "test"}, config)
        
        # 验证返回的是ToolMessage
        assert isinstance(result, ToolMessage)
        assert result.tool_call_id == "call_789"
        assert result.name == "test_tool"
        
        # 验证内容
        content = json.loads(result.content)
        assert content["result"] == "success"
        assert content["data"] == 123
    
    @pytest.mark.asyncio
    async def test_tool_execution_with_string_result(self):
        """测试工具返回字符串结果"""
        mock_tool = AsyncMock()
        mock_tool.ainvoke = AsyncMock(return_value="Simple string result")
        
        wrapper = MCPToolWrapper(mock_tool, "string_tool")
        
        config = RunnableConfig(configurable={"tool_call_id": "call_str"})
        result = await wrapper.ainvoke({}, config)
        
        assert isinstance(result, ToolMessage)
        assert result.content == "Simple string result"
        assert result.name == "string_tool"
    
    @pytest.mark.asyncio
    async def test_tool_execution_error(self):
        """测试工具执行失败"""
        mock_tool = AsyncMock()
        mock_tool.ainvoke = AsyncMock(side_effect=Exception("Tool execution failed"))
        
        wrapper = MCPToolWrapper(mock_tool, "error_tool")
        
        config = RunnableConfig(configurable={"tool_call_id": "call_error"})
        result = await wrapper.ainvoke({}, config)
        
        # 即使出错也应该返回ToolMessage
        assert isinstance(result, ToolMessage)
        assert result.tool_call_id == "call_error"
        assert result.name == "error_tool"
        
        # 验证错误内容
        content = json.loads(result.content)
        assert content["status"] == "error"
        assert "Tool execution failed" in content["error"]
        assert content["tool_name"] == "error_tool"
    
    @pytest.mark.asyncio
    async def test_tool_without_config(self):
        """测试没有config的工具调用"""
        mock_tool = AsyncMock()
        mock_tool.ainvoke = AsyncMock(return_value={"status": "ok"})
        
        wrapper = MCPToolWrapper(mock_tool, "no_config_tool")
        
        # 不传config
        result = await wrapper.ainvoke({})
        
        assert isinstance(result, ToolMessage)
        assert result.tool_call_id == "unknown"  # 默认值
        assert result.name == "no_config_tool"
    
    def test_wrapper_preserves_tool_attributes(self):
        """测试包装器保留原始工具的属性"""
        mock_tool = Mock()
        mock_tool.name = "original_name"
        mock_tool.description = "Original description"
        mock_tool.args_schema = {"type": "object"}
        
        wrapper = MCPToolWrapper(mock_tool, "wrapped_tool")
        
        assert wrapper.name == "wrapped_tool"
        assert wrapper.description == "Original description"
        assert wrapper.args_schema == {"type": "object"}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
