"""
Phase 2 API集成测试
测试多轮对话和会话管理功能

运行方式:
    python test_phase2_api_integration.py
"""
import asyncio
from uuid import uuid4


async def test_single_turn_conversation():
    """测试单轮对话（向后兼容）"""
    from app.agents.chat_graph import IntelligentSQLGraph
    
    print("\n=== 测试单轮对话 ===")
    
    graph = IntelligentSQLGraph()
    
    # 不提供thread_id，应该自动生成
    result = await graph.process_query(
        query="查询所有客户",
        connection_id=15
    )
    
    print(f"成功: {result.get('success')}")
    print(f"Thread ID: {result.get('thread_id')}")
    print(f"最终阶段: {result.get('final_stage')}")
    
    assert result.get("success") is not None
    assert result.get("thread_id") is not None
    assert len(result.get("thread_id")) == 36  # UUID长度
    
    print("✓ 单轮对话测试通过")


async def test_multi_turn_conversation():
    """测试多轮对话"""
    from app.agents.chat_graph import IntelligentSQLGraph
    
    print("\n=== 测试多轮对话 ===")
    
    graph = IntelligentSQLGraph()
    
    # 第一轮对话
    print("\n第一轮: 查询2024年的销售数据")
    result1 = await graph.process_query(
        query="查询2024年的销售数据",
        connection_id=15
    )
    
    thread_id = result1.get("thread_id")
    print(f"Thread ID: {thread_id}")
    print(f"成功: {result1.get('success')}")
    
    assert thread_id is not None
    
    # 第二轮对话 - 使用相同的thread_id
    print("\n第二轮: 按月份分组（使用相同thread_id）")
    result2 = await graph.process_query(
        query="按月份分组",
        connection_id=15,
        thread_id=thread_id  # 使用相同的thread_id
    )
    
    print(f"Thread ID: {result2.get('thread_id')}")
    print(f"成功: {result2.get('success')}")
    
    # 验证thread_id保持一致
    assert result2.get("thread_id") == thread_id
    
    print("✓ 多轮对话测试通过")


async def test_thread_id_persistence():
    """测试thread_id持久化"""
    from app.agents.chat_graph import IntelligentSQLGraph
    from app.core.checkpointer import get_checkpointer
    
    print("\n=== 测试thread_id持久化 ===")
    
    checkpointer = get_checkpointer()
    
    if checkpointer is None:
        print("⚠ Checkpointer未启用，跳过持久化测试")
        return
    
    print(f"Checkpointer类型: {type(checkpointer).__name__}")
    
    graph = IntelligentSQLGraph()
    
    # 创建一个会话
    custom_thread_id = f"test-{uuid4()}"
    print(f"\n使用自定义thread_id: {custom_thread_id}")
    
    result = await graph.process_query(
        query="测试查询",
        connection_id=15,
        thread_id=custom_thread_id
    )
    
    print(f"查询结果: {result.get('success')}")
    print(f"返回的thread_id: {result.get('thread_id')}")
    
    # 验证thread_id正确返回
    assert result.get("thread_id") == custom_thread_id
    
    print("✓ thread_id持久化测试通过")


async def test_conversation_isolation():
    """测试会话隔离"""
    from app.agents.chat_graph import IntelligentSQLGraph
    
    print("\n=== 测试会话隔离 ===")
    
    graph = IntelligentSQLGraph()
    
    # 创建两个独立的会话
    print("\n会话1: 查询客户")
    result1 = await graph.process_query(
        query="查询所有客户",
        connection_id=15
    )
    thread_id1 = result1.get("thread_id")
    print(f"会话1 Thread ID: {thread_id1}")
    
    print("\n会话2: 查询订单")
    result2 = await graph.process_query(
        query="查询所有订单",
        connection_id=15
    )
    thread_id2 = result2.get("thread_id")
    print(f"会话2 Thread ID: {thread_id2}")
    
    # 验证两个会话有不同的thread_id
    assert thread_id1 != thread_id2
    
    print("✓ 会话隔离测试通过")


async def test_error_handling_with_thread_id():
    """测试错误处理（带thread_id）"""
    from app.agents.chat_graph import IntelligentSQLGraph
    
    print("\n=== 测试错误处理 ===")
    
    graph = IntelligentSQLGraph()
    
    # 使用无效的connection_id
    result = await graph.process_query(
        query="测试查询",
        connection_id=99999  # 不存在的连接
    )
    
    print(f"成功: {result.get('success')}")
    print(f"Thread ID: {result.get('thread_id')}")
    print(f"错误: {result.get('error', 'N/A')[:100]}")
    
    # 即使失败，也应该返回thread_id
    assert result.get("thread_id") is not None
    
    print("✓ 错误处理测试通过")


def test_checkpointer_health():
    """测试Checkpointer健康状态"""
    from app.core.checkpointer import check_checkpointer_health, get_checkpointer
    
    print("\n=== 测试Checkpointer健康状态 ===")
    
    checkpointer = get_checkpointer()
    
    if checkpointer is None:
        print("⚠ Checkpointer未启用")
        health = check_checkpointer_health()
        assert health is False
        print("✓ 健康检查正确返回False")
    else:
        print(f"Checkpointer类型: {type(checkpointer).__name__}")
        health = check_checkpointer_health()
        print(f"健康状态: {health}")
        assert health is True
        print("✓ 健康检查通过")


async def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("Phase 2 API集成测试")
    print("=" * 60)
    
    try:
        # 同步测试
        test_checkpointer_health()
        
        # 异步测试
        await test_single_turn_conversation()
        await test_multi_turn_conversation()
        await test_thread_id_persistence()
        await test_conversation_isolation()
        await test_error_handling_with_thread_id()
        
        print("\n" + "=" * 60)
        print("✓ 所有测试通过！")
        print("=" * 60)
        
    except Exception as e:
        print("\n" + "=" * 60)
        print(f"✗ 测试失败: {str(e)}")
        print("=" * 60)
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    # 直接运行
    asyncio.run(run_all_tests())
