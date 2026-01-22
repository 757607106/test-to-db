"""
基础功能测试 - 单个测试
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from langchain_core.messages import HumanMessage
from app.agents.chat_graph import get_global_graph_async
from app.core.state import create_initial_state


async def test_simple_query():
    """测试简单查询"""
    print("\n" + "="*80)
    print("测试: 简单查询（快速模式）")
    print("="*80)
    
    try:
        print("\n1. 获取图实例...")
        graph = await get_global_graph_async()
        print("   ✓ 图实例获取成功")
        
        print("\n2. 准备初始状态...")
        initial_state = create_initial_state(connection_id=7)
        initial_state["messages"] = [HumanMessage(content="查询产品数量")]
        print("   ✓ 状态准备完成")
        
        config = {"configurable": {"thread_id": "test-simple-query"}}
        
        print("\n3. 执行查询...")
        print("   查询内容: '查询产品数量'")
        print("   connection_id: 7")
        
        result = await graph.graph.ainvoke(initial_state, config=config)
        
        print("\n4. 查看结果...")
        print(f"   - current_stage: {result.get('current_stage')}")
        print(f"   - fast_mode: {result.get('fast_mode')}")
        print(f"   - skip_chart_generation: {result.get('skip_chart_generation')}")
        print(f"   - cache_hit: {result.get('cache_hit')}")
        print(f"   - has_schema_info: {result.get('schema_info') is not None}")
        print(f"   - has_generated_sql: {bool(result.get('generated_sql'))}")
        
        if result.get("generated_sql"):
            sql = result.get("generated_sql", "")
            print(f"   - generated_sql: {sql[:100]}...")
        
        if result.get("execution_result"):
            exec_result = result.get("execution_result")
            print(f"   - execution_success: {exec_result.success if hasattr(exec_result, 'success') else 'N/A'}")
            if hasattr(exec_result, 'data') and exec_result.data:
                row_count = exec_result.data.get('row_count', 0) if isinstance(exec_result.data, dict) else 0
                print(f"   - result_row_count: {row_count}")
        
        # 检查消息
        messages = result.get("messages", [])
        print(f"   - message_count: {len(messages)}")
        
        # 统计不同类型的消息
        human_msgs = sum(1 for m in messages if hasattr(m, 'type') and m.type == 'human')
        ai_msgs = sum(1 for m in messages if hasattr(m, 'type') and m.type == 'ai')
        tool_msgs = sum(1 for m in messages if hasattr(m, 'type') and m.type == 'tool')
        
        print(f"   - human_messages: {human_msgs}")
        print(f"   - ai_messages: {ai_msgs}")
        print(f"   - tool_messages: {tool_msgs}")
        
        # 验证
        print("\n5. 验证结果...")
        checks = []
        
        # 检查是否完成
        if result.get("current_stage") == "completed":
            print("   ✓ 流程已完成")
            checks.append(True)
        else:
            print(f"   ✗ 流程未完成，当前阶段: {result.get('current_stage')}")
            checks.append(False)
        
        # 检查是否有 SQL
        if result.get("generated_sql"):
            print("   ✓ SQL 已生成")
            checks.append(True)
        else:
            print("   ✗ SQL 未生成")
            checks.append(False)
        
        # 检查是否有执行结果
        if result.get("execution_result"):
            print("   ✓ SQL 已执行")
            checks.append(True)
        else:
            print("   ✗ SQL 未执行")
            checks.append(False)
        
        # 总结
        print("\n" + "="*80)
        if all(checks):
            print("✅ 测试通过")
            return 0
        else:
            print(f"⚠️  测试部分失败 ({sum(checks)}/{len(checks)} 通过)")
            return 1
            
    except Exception as e:
        print(f"\n❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(test_simple_query())
    sys.exit(exit_code)
