"""
Text-to-SQL 系统场景测试（简化版，无需 pytest）

运行方式: python3 tests/test_scenarios_simple.py
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from langchain_core.messages import HumanMessage
from app.agents.chat_graph import get_global_graph_async
from app.core.state import create_initial_state


class Colors:
    """终端颜色"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'
    BOLD = '\033[1m'


def print_header(text: str):
    """打印测试标题"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*80}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*80}{Colors.END}\n")


def print_success(text: str):
    """打印成功消息"""
    print(f"{Colors.GREEN}✅ {text}{Colors.END}")


def print_error(text: str):
    """打印错误消息"""
    print(f"{Colors.RED}❌ {text}{Colors.END}")


def print_warning(text: str):
    """打印警告消息"""
    print(f"{Colors.YELLOW}⚠️  {text}{Colors.END}")


def print_info(text: str, indent=0):
    """打印信息"""
    prefix = "   " * indent
    print(f"{prefix}{text}")


async def test_1_1_simple_query_fast_mode():
    """
    测试 1.1: 简单查询（快速模式）
    """
    print_header("测试 1.1: 简单查询（快速模式）")
    
    try:
        graph = await get_global_graph_async()
        
        initial_state = create_initial_state(connection_id=7)
        initial_state["messages"] = [HumanMessage(content="查询产品数量")]
        
        config = {"configurable": {"thread_id": "test-fast-mode"}}
        
        print_info("执行查询: '查询产品数量'")
        result = await graph.graph.ainvoke(initial_state, config=config)
        
        # 验证
        fast_mode = result.get("fast_mode")
        skip_chart = result.get("skip_chart_generation")
        current_stage = result.get("current_stage")
        
        print_info(f"fast_mode: {fast_mode}", 1)
        print_info(f"skip_chart_generation: {skip_chart}", 1)
        print_info(f"current_stage: {current_stage}", 1)
        
        if fast_mode and skip_chart and current_stage == "completed":
            print_success("快速模式测试通过")
            return True
        else:
            print_error("快速模式测试失败")
            return False
            
    except Exception as e:
        print_error(f"测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def test_1_2_complex_query_full_mode():
    """
    测试 1.2: 复杂查询（完整模式）
    """
    print_header("测试 1.2: 复杂查询（完整模式）")
    
    try:
        graph = await get_global_graph_async()
        
        initial_state = create_initial_state(connection_id=7)
        initial_state["messages"] = [
            HumanMessage(content="分析最近的库存分布情况")
        ]
        
        config = {"configurable": {"thread_id": "test-full-mode"}}
        
        print_info("执行查询: '分析最近的库存分布情况'")
        result = await graph.graph.ainvoke(initial_state, config=config)
        
        # 验证
        fast_mode = result.get("fast_mode")
        current_stage = result.get("current_stage")
        execution_result = result.get("execution_result")
        
        print_info(f"fast_mode: {fast_mode}", 1)
        print_info(f"current_stage: {current_stage}", 1)
        print_info(f"has_execution_result: {execution_result is not None}", 1)
        
        # 检查是否有分析内容
        messages = result.get("messages", [])
        analysis_count = 0
        for msg in messages:
            if hasattr(msg, 'type') and msg.type == 'ai':
                content = msg.content
                if isinstance(content, str) and len(content) > 100:
                    analysis_count += 1
        
        print_info(f"analysis_messages_count: {analysis_count}", 1)
        
        if fast_mode == False and current_stage == "completed" and analysis_count > 0:
            print_success("完整模式测试通过")
            return True
        else:
            print_error("完整模式测试失败")
            return False
            
    except Exception as e:
        print_error(f"测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def test_3_1_clear_query_skip_clarification():
    """
    测试 3.1: 明确查询（跳过澄清）
    """
    print_header("测试 3.1: 明确查询（跳过澄清）")
    
    try:
        graph = await get_global_graph_async()
        
        initial_state = create_initial_state(connection_id=7)
        initial_state["messages"] = [
            HumanMessage(content="SELECT * FROM inventory LIMIT 10")
        ]
        
        config = {"configurable": {"thread_id": "test-skip-clarification"}}
        
        print_info("执行查询: 'SELECT * FROM inventory LIMIT 10'")
        result = await graph.graph.ainvoke(initial_state, config=config)
        
        # 验证
        has_clarification = bool(result.get("clarification_responses"))
        current_stage = result.get("current_stage")
        
        print_info(f"has_clarification_responses: {has_clarification}", 1)
        print_info(f"current_stage: {current_stage}", 1)
        
        if not has_clarification and current_stage == "completed":
            print_success("跳过澄清测试通过")
            return True
        else:
            print_error("跳过澄清测试失败")
            return False
            
    except Exception as e:
        print_error(f"测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def test_5_1_schema_info_passing():
    """
    测试 5.1: Schema 信息正确传递
    """
    print_header("测试 5.1: Schema 信息正确传递")
    
    try:
        graph = await get_global_graph_async()
        
        initial_state = create_initial_state(connection_id=7)
        initial_state["messages"] = [
            HumanMessage(content="查询库存中产品名称的记录")
        ]
        
        config = {"configurable": {"thread_id": "test-schema-passing"}}
        
        print_info("执行查询: '查询库存中产品名称的记录'")
        result = await graph.graph.ainvoke(initial_state, config=config)
        
        # 验证
        schema_info = result.get("schema_info")
        has_schema = schema_info is not None
        
        if has_schema:
            tables_count = len(schema_info.get("tables", {}))
            connection_id = schema_info.get("connection_id")
            
            print_info(f"has_schema_info: {has_schema}", 1)
            print_info(f"tables_count: {tables_count}", 1)
            print_info(f"connection_id: {connection_id}", 1)
            
            # 验证 SQL
            generated_sql = result.get("generated_sql", "")
            has_correct_table = "inventory" in generated_sql.lower()
            
            print_info(f"sql_contains_inventory: {has_correct_table}", 1)
            
            if has_schema and tables_count > 0 and has_correct_table:
                print_success("Schema 信息传递测试通过")
                return True
        
        print_error("Schema 信息传递测试失败")
        return False
            
    except Exception as e:
        print_error(f"测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def run_all_tests():
    """运行所有测试"""
    print(f"\n{Colors.BOLD}{'='*80}{Colors.END}")
    print(f"{Colors.BOLD}Text-to-SQL 系统场景测试{Colors.END}")
    print(f"{Colors.BOLD}{'='*80}{Colors.END}")
    
    tests = [
        ("简单查询（快速模式）", test_1_1_simple_query_fast_mode),
        ("复杂查询（完整模式）", test_1_2_complex_query_full_mode),
        ("明确查询（跳过澄清）", test_3_1_clear_query_skip_clarification),
        ("Schema 信息传递", test_5_1_schema_info_passing),
    ]
    
    results = []
    
    for name, test_func in tests:
        try:
            result = await test_func()
            results.append((name, result))
        except Exception as e:
            print_error(f"{name} - 异常: {str(e)}")
            results.append((name, False))
        
        # 测试之间等待一下
        await asyncio.sleep(1)
    
    # 打印总结
    print(f"\n{Colors.BOLD}{'='*80}{Colors.END}")
    print(f"{Colors.BOLD}测试总结{Colors.END}")
    print(f"{Colors.BOLD}{'='*80}{Colors.END}\n")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        if result:
            print_success(f"{name}")
        else:
            print_error(f"{name}")
    
    print(f"\n{Colors.BOLD}通过: {passed}/{total}{Colors.END}")
    
    if passed == total:
        print(f"\n{Colors.GREEN}{Colors.BOLD}🎉 所有测试通过！{Colors.END}")
        return 0
    else:
        print(f"\n{Colors.RED}{Colors.BOLD}⚠️  有 {total - passed} 个测试失败{Colors.END}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(run_all_tests())
    sys.exit(exit_code)
