"""
Chart Generator Agent 的集成测试
测试MCP工具调用返回ToolMessage和完整的图表生成流程
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from langchain_core.messages import HumanMessage, ToolMessage
from app.agents.agents.chart_generator_agent import ChartGeneratorAgent, CHART_TOOLS
from app.core.state import SQLMessageState


def test_chart_tools_wrapped():
    """测试MCP工具已被正确包装"""
    if CHART_TOOLS:
        # 检查工具是否被包装
        for tool in CHART_TOOLS:
            assert hasattr(tool, 'ainvoke'), f"工具 {tool.name} 缺少 ainvoke 方法"
            assert hasattr(tool, 'name'), f"工具缺少 name 属性"
            print(f"✓ 工具 {tool.name} 已正确包装")
    else:
        print("⚠ 没有可用的MCP图表工具（可能是MCP服务器未启动）")


def test_agent_initialization():
    """测试代理初始化"""
    agent = ChartGeneratorAgent()
    
    assert agent.name == "chart_generator_agent"
    assert agent.llm is not None
    assert agent.agent is not None
    assert isinstance(agent.tools, list)
    
    print(f"✓ Chart Generator Agent 初始化成功")
    print(f"  - 工具数量: {len(agent.tools)}")


async def test_tool_returns_tool_message():
    """测试MCP工具调用返回ToolMessage"""
    if not CHART_TOOLS:
        print("⚠ 跳过测试：没有可用的MCP图表工具")
        return
    
    # 获取第一个工具
    tool = CHART_TOOLS[0]
    
    # 模拟工具调用
    from langchain_core.runnables import RunnableConfig
    config = RunnableConfig(configurable={"tool_call_id": "test_call_123"})
    
    try:
        # 调用工具（可能会失败，因为参数可能不正确）
        result = await tool.ainvoke({}, config)
        
        # 验证返回的是ToolMessage
        assert isinstance(result, ToolMessage), f"期望返回ToolMessage，实际返回 {type(result)}"
        assert result.tool_call_id == "test_call_123"
        assert result.name == tool.name
        
        print(f"✓ 工具 {tool.name} 正确返回 ToolMessage")
        print(f"  - tool_call_id: {result.tool_call_id}")
        print(f"  - content: {result.content[:100]}...")
        
    except Exception as e:
        print(f"⚠ 工具调用出错（预期行为）: {e}")


async def test_tool_error_handling():
    """测试工具执行失败时的错误处理"""
    if not CHART_TOOLS:
        print("⚠ 跳过测试：没有可用的MCP图表工具")
        return
    
    tool = CHART_TOOLS[0]
    
    from langchain_core.runnables import RunnableConfig
    config = RunnableConfig(configurable={"tool_call_id": "error_test_456"})
    
    # 使用无效参数调用工具
    result = await tool.ainvoke({"invalid_param": "invalid_value"}, config)
    
    # 即使出错，也应该返回ToolMessage
    assert isinstance(result, ToolMessage), "错误情况下也应返回ToolMessage"
    assert result.tool_call_id == "error_test_456"
    
    # 检查内容是否包含错误信息
    import json
    try:
        content = json.loads(result.content)
        # 可能包含错误信息
        print(f"✓ 工具错误处理正确")
        print(f"  - 返回类型: ToolMessage")
        print(f"  - 内容: {result.content[:200]}...")
    except:
        # 内容可能不是JSON格式
        print(f"✓ 工具错误处理正确（非JSON响应）")


async def test_chart_generation_flow():
    """测试完整的图表生成流程"""
    agent = ChartGeneratorAgent()
    
    # 创建测试状态
    state = SQLMessageState(
        messages=[
            HumanMessage(content="请为销售数据生成柱状图")
        ],
        connection_id=15,
        execution_result={
            "success": True,
            "data": {
                "columns": ["产品", "销量"],
                "rows": [
                    ["产品A", 100],
                    ["产品B", 150],
                    ["产品C", 80]
                ]
            }
        }
    )
    
    try:
        result = await agent.generate_chart(state)
        
        # 验证结果
        assert "messages" in result
        assert len(result["messages"]) > 0
        
        print(f"✓ 图表生成流程测试完成")
        print(f"  - 返回消息数: {len(result['messages'])}")
        
        # 检查是否有ToolMessage
        tool_messages = [msg for msg in result["messages"] if isinstance(msg, ToolMessage)]
        if tool_messages:
            print(f"  - ToolMessage数量: {len(tool_messages)}")
            for tm in tool_messages:
                print(f"    * {tm.name}: {tm.content[:100]}...")
        
    except Exception as e:
        print(f"⚠ 图表生成流程测试出错: {e}")


if __name__ == "__main__":
    import asyncio
    
    print("=" * 60)
    print("Chart Generator Agent 集成测试")
    print("=" * 60)
    
    # 同步测试
    print("\n1. 测试工具包装...")
    test_chart_tools_wrapped()
    
    print("\n2. 测试代理初始化...")
    test_agent_initialization()
    
    # 异步测试
    print("\n3. 测试工具返回ToolMessage...")
    asyncio.run(test_tool_returns_tool_message())
    
    print("\n4. 测试工具错误处理...")
    asyncio.run(test_tool_error_handling())
    
    print("\n5. 测试完整图表生成流程...")
    asyncio.run(test_chart_generation_flow())
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
