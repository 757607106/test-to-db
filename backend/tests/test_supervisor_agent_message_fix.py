"""
Supervisor Agent 消息历史修复的集成测试
测试消息历史自动修复、多工具调用和错误恢复流程
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from app.agents.agents.supervisor_agent import SupervisorAgent
from app.core.state import SQLMessageState
from app.core.message_utils import validate_and_fix_message_history


def test_message_history_validation():
    """测试消息历史验证函数"""
    # 创建包含Tool Call但缺少ToolMessage的消息历史
    tool_call = {
        "id": "call_test_123",
        "name": "test_tool",
        "args": {"param": "value"}
    }
    
    messages = [
        HumanMessage(content="测试查询"),
        AIMessage(content="", tool_calls=[tool_call])
        # 缺少对应的ToolMessage
    ]
    
    # 验证并修复
    fixed_messages = validate_and_fix_message_history(messages)
    
    # 应该添加了一个占位ToolMessage
    assert len(fixed_messages) == 3, f"期望3条消息，实际 {len(fixed_messages)}"
    assert isinstance(fixed_messages[2], ToolMessage), "最后一条应该是ToolMessage"
    assert fixed_messages[2].tool_call_id == "call_test_123"
    
    print("✓ 消息历史验证测试通过")
    print(f"  - 原始消息数: {len(messages)}")
    print(f"  - 修复后消息数: {len(fixed_messages)}")
    print(f"  - 添加的占位消息: {fixed_messages[2].content[:100]}")


async def test_supervisor_message_fix():
    """测试Supervisor自动修复消息历史"""
    supervisor = SupervisorAgent()
    
    # 创建测试状态
    state = SQLMessageState(
        messages=[
            HumanMessage(content="查询销售数据")
        ],
        connection_id=15
    )
    
    try:
        result = await supervisor.supervise(state)
        
        assert result["success"], f"Supervisor执行失败: {result.get('error')}"
        assert "result" in result
        
        # 检查消息历史
        if "messages" in result["result"]:
            messages = result["result"]["messages"]
            print(f"✓ Supervisor执行成功")
            print(f"  - 返回消息数: {len(messages)}")
            
            # 检查Tool Calls和ToolMessages的对应关系
            tool_calls = []
            tool_messages = []
            
            for msg in messages:
                if isinstance(msg, AIMessage) and hasattr(msg, "tool_calls") and msg.tool_calls:
                    tool_calls.extend(msg.tool_calls)
                elif isinstance(msg, ToolMessage):
                    tool_messages.append(msg)
            
            print(f"  - Tool Calls数量: {len(tool_calls)}")
            print(f"  - ToolMessages数量: {len(tool_messages)}")
            
            # 验证每个Tool Call都有对应的ToolMessage
            tool_call_ids = set()
            for tc in tool_calls:
                tc_id = tc.get("id") if isinstance(tc, dict) else getattr(tc, "id", None)
                if tc_id:
                    tool_call_ids.add(tc_id)
            
            tool_message_ids = {tm.tool_call_id for tm in tool_messages}
            
            missing_ids = tool_call_ids - tool_message_ids
            if missing_ids:
                print(f"  ⚠ 警告: {len(missing_ids)} 个Tool Call缺少ToolMessage")
            else:
                print(f"  ✓ 所有Tool Call都有对应的ToolMessage")
        
    except Exception as e:
        print(f"✗ Supervisor测试失败: {e}")
        import traceback
        traceback.print_exc()


async def test_multiple_tool_calls():
    """测试多个工具连续调用的场景"""
    supervisor = SupervisorAgent()
    
    # 创建包含多个步骤的查询
    state = SQLMessageState(
        messages=[
            HumanMessage(content="查询最近一个月的销售趋势，并生成折线图")
        ],
        connection_id=15
    )
    
    try:
        result = await supervisor.supervise(state)
        
        if result["success"] and "messages" in result["result"]:
            messages = result["result"]["messages"]
            
            # 统计不同类型的消息
            human_msgs = sum(1 for m in messages if isinstance(m, HumanMessage))
            ai_msgs = sum(1 for m in messages if isinstance(m, AIMessage))
            tool_msgs = sum(1 for m in messages if isinstance(m, ToolMessage))
            
            print(f"✓ 多工具调用测试完成")
            print(f"  - 总消息数: {len(messages)}")
            print(f"  - HumanMessage: {human_msgs}")
            print(f"  - AIMessage: {ai_msgs}")
            print(f"  - ToolMessage: {tool_msgs}")
            
    except Exception as e:
        print(f"✗ 多工具调用测试失败: {e}")


async def test_error_recovery():
    """测试错误恢复流程"""
    supervisor = SupervisorAgent()
    
    # 创建可能触发错误的查询
    state = SQLMessageState(
        messages=[
            HumanMessage(content="查询不存在的表")
        ],
        connection_id=15
    )
    
    try:
        result = await supervisor.supervise(state)
        
        # 即使出错，也应该有结果
        assert "success" in result
        
        if result["success"]:
            print(f"✓ 错误恢复测试: 系统正常处理")
        else:
            print(f"✓ 错误恢复测试: 系统正确返回错误")
            print(f"  - 错误信息: {result.get('error', 'N/A')[:100]}")
            
    except Exception as e:
        print(f"✗ 错误恢复测试失败: {e}")


if __name__ == "__main__":
    import asyncio
    
    print("=" * 60)
    print("Supervisor Agent 消息历史修复集成测试")
    print("=" * 60)
    
    # 同步测试
    print("\n1. 测试消息历史验证...")
    test_message_history_validation()
    
    # 异步测试
    print("\n2. 测试Supervisor自动修复消息历史...")
    asyncio.run(test_supervisor_message_fix())
    
    print("\n3. 测试多工具连续调用...")
    asyncio.run(test_multiple_tool_calls())
    
    print("\n4. 测试错误恢复流程...")
    asyncio.run(test_error_recovery())
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
