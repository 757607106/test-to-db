"""
消息历史管理测试

测试消息修剪、统计和管理功能

运行方式:
    python test_message_history.py
"""
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from app.core.message_history import (
    trim_message_history,
    count_message_tokens,
    should_trim_messages,
    get_message_stats,
    auto_trim_messages
)


def test_basic_trim():
    """测试基本的消息修剪功能"""
    print("\n=== 测试基本消息修剪 ===")
    
    # 创建测试消息
    messages = [
        SystemMessage(content="你是一个SQL助手"),
        HumanMessage(content="查询所有客户"),
        AIMessage(content="SELECT * FROM customers"),
        HumanMessage(content="只要前10个"),
        AIMessage(content="SELECT * FROM customers LIMIT 10"),
        HumanMessage(content="按名字排序"),
        AIMessage(content="SELECT * FROM customers ORDER BY name LIMIT 10"),
    ]
    
    print(f"原始消息数量: {len(messages)}")
    
    # 修剪到5条
    trimmed = trim_message_history(messages, max_messages=5)
    
    print(f"修剪后消息数量: {len(trimmed)}")
    print(f"保留的系统消息数: {sum(1 for m in trimmed if isinstance(m, SystemMessage))}")
    
    # 验证
    assert len(trimmed) == 5, "应该保留5条消息"
    assert any(isinstance(m, SystemMessage) for m in trimmed), "应该保留系统消息"
    
    print("✓ 基本修剪测试通过")


def test_preserve_system_messages():
    """测试保留系统消息功能"""
    print("\n=== 测试保留系统消息 ===")
    
    messages = [
        SystemMessage(content="系统提示1"),
        SystemMessage(content="系统提示2"),
        HumanMessage(content="问题1"),
        AIMessage(content="回答1"),
        HumanMessage(content="问题2"),
        AIMessage(content="回答2"),
    ]
    
    print(f"原始消息: {len(messages)} 条 (2条系统消息)")
    
    # 修剪到4条，应该保留所有系统消息
    trimmed = trim_message_history(messages, max_messages=4, preserve_system=True)
    
    system_count = sum(1 for m in trimmed if isinstance(m, SystemMessage))
    print(f"修剪后: {len(trimmed)} 条 ({system_count}条系统消息)")
    
    # 验证
    assert system_count == 2, "应该保留所有系统消息"
    assert len(trimmed) == 4, "总共应该是4条消息"
    
    print("✓ 保留系统消息测试通过")


def test_token_counting():
    """测试token计数功能"""
    print("\n=== 测试Token计数 ===")
    
    messages = [
        HumanMessage(content="这是一个测试消息"),
        AIMessage(content="这是另一个测试消息，内容稍微长一点"),
    ]
    
    tokens = count_message_tokens(messages)
    print(f"估算token数: {tokens}")
    
    # 验证（粗略估算）
    assert tokens > 0, "Token数应该大于0"
    
    print("✓ Token计数测试通过")


def test_should_trim():
    """测试是否需要修剪的判断"""
    print("\n=== 测试修剪判断 ===")
    
    # 创建少量消息
    few_messages = [HumanMessage(content=f"消息{i}") for i in range(5)]
    
    # 创建大量消息
    many_messages = [HumanMessage(content=f"消息{i}") for i in range(25)]
    
    print(f"少量消息({len(few_messages)}条): 需要修剪? {should_trim_messages(few_messages)}")
    print(f"大量消息({len(many_messages)}条): 需要修剪? {should_trim_messages(many_messages)}")
    
    # 验证
    assert not should_trim_messages(few_messages), "少量消息不应该修剪"
    assert should_trim_messages(many_messages), "大量消息应该修剪"
    
    print("✓ 修剪判断测试通过")


def test_message_stats():
    """测试消息统计功能"""
    print("\n=== 测试消息统计 ===")
    
    messages = [
        SystemMessage(content="系统提示"),
        HumanMessage(content="用户问题1"),
        AIMessage(content="AI回答1"),
        HumanMessage(content="用户问题2"),
        AIMessage(content="AI回答2"),
    ]
    
    stats = get_message_stats(messages)
    
    print(f"统计信息:")
    print(f"  总数: {stats['total']}")
    print(f"  系统消息: {stats['system']}")
    print(f"  用户消息: {stats['human']}")
    print(f"  AI消息: {stats['ai']}")
    print(f"  其他消息: {stats['other']}")
    print(f"  估算token: {stats['estimated_tokens']}")
    
    # 验证
    assert stats['total'] == 5, "总数应该是5"
    assert stats['system'] == 1, "系统消息应该是1"
    assert stats['human'] == 2, "用户消息应该是2"
    assert stats['ai'] == 2, "AI消息应该是2"
    
    print("✓ 消息统计测试通过")


def test_auto_trim():
    """测试自动修剪功能"""
    print("\n=== 测试自动修剪 ===")
    
    # 创建少量消息（不需要修剪）
    few_messages = [HumanMessage(content=f"消息{i}") for i in range(5)]
    result1 = auto_trim_messages(few_messages)
    
    print(f"少量消息: {len(few_messages)} -> {len(result1)}")
    assert len(result1) == len(few_messages), "少量消息不应该被修剪"
    
    # 创建大量消息（需要修剪）
    many_messages = [
        SystemMessage(content="系统提示")
    ] + [HumanMessage(content=f"消息{i}") for i in range(25)]
    
    result2 = auto_trim_messages(many_messages)
    
    print(f"大量消息: {len(many_messages)} -> {len(result2)}")
    assert len(result2) < len(many_messages), "大量消息应该被修剪"
    assert len(result2) <= 20, "修剪后应该不超过20条"
    
    print("✓ 自动修剪测试通过")


def test_long_conversation():
    """测试长对话场景"""
    print("\n=== 测试长对话场景 ===")
    
    # 模拟一个长对话
    messages = [SystemMessage(content="你是一个SQL助手")]
    
    # 添加10轮对话
    for i in range(10):
        messages.append(HumanMessage(content=f"查询{i+1}"))
        messages.append(AIMessage(content=f"SELECT * FROM table{i+1}"))
    
    print(f"长对话消息数: {len(messages)}")
    
    # 获取统计
    stats_before = get_message_stats(messages)
    print(f"修剪前统计: {stats_before}")
    
    # 自动修剪
    trimmed = auto_trim_messages(messages)
    
    # 获取修剪后统计
    stats_after = get_message_stats(trimmed)
    print(f"修剪后统计: {stats_after}")
    
    # 验证
    assert len(trimmed) <= 20, "修剪后应该不超过20条"
    assert stats_after['system'] >= 1, "应该保留系统消息"
    
    print("✓ 长对话场景测试通过")


def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("消息历史管理测试")
    print("=" * 60)
    
    try:
        test_basic_trim()
        test_preserve_system_messages()
        test_token_counting()
        test_should_trim()
        test_message_stats()
        test_auto_trim()
        test_long_conversation()
        
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
    run_all_tests()
