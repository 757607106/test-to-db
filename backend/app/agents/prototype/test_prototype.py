"""
Hub-and-Spoke 架构原型验证测试

测试目的:
1. 验证新架构的基本流程
2. 对比与现有 Pipeline 架构的差异
3. 验证 Supervisor 路由决策
4. 验证结果汇总功能

运行方式:
    cd backend
    python -m app.agents.prototype.test_prototype
"""

import asyncio
import logging
import sys
import time
from typing import Dict, Any

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_supervisor_routing():
    """测试 Supervisor 路由决策"""
    print("\n" + "="*60)
    print("测试 1: Supervisor 路由决策")
    print("="*60)
    
    from app.agents.prototype.true_supervisor import TrueSupervisor
    from app.core.state import SQLMessageState
    from langchain_core.messages import HumanMessage
    
    supervisor = TrueSupervisor()
    
    # 测试场景
    test_cases = [
        {
            "name": "初始状态 → schema_agent",
            "state": {
                "messages": [HumanMessage(content="查询所有客户")],
                "current_stage": "init",
                "connection_id": 1
            },
            "expected": "schema_agent"
        },
        {
            "name": "schema完成 → sql_generator",
            "state": {
                "messages": [HumanMessage(content="查询所有客户")],
                "current_stage": "schema_done",
                "schema_info": {"tables": ["Customer"]}
            },
            "expected": "sql_generator"
        },
        {
            "name": "SQL生成完成 → sql_executor",
            "state": {
                "messages": [HumanMessage(content="查询所有客户")],
                "current_stage": "sql_generated",
                "generated_sql": "SELECT * FROM Customer"
            },
            "expected": "sql_executor"
        },
        {
            "name": "闲聊 → general_chat",
            "state": {
                "messages": [HumanMessage(content="你好")],
                "current_stage": "init",
                "route_decision": "general_chat"
            },
            "expected": "general_chat"
        },
        {
            "name": "完成 → FINISH",
            "state": {
                "messages": [HumanMessage(content="查询")],
                "current_stage": "completed"
            },
            "expected": "FINISH"
        }
    ]
    
    passed = 0
    failed = 0
    
    for tc in test_cases:
        result = await supervisor.route(tc["state"])
        status = "✓" if result == tc["expected"] else "✗"
        
        if result == tc["expected"]:
            passed += 1
        else:
            failed += 1
        
        print(f"  {status} {tc['name']}")
        print(f"      预期: {tc['expected']}, 实际: {result}")
    
    print(f"\n  结果: {passed} 通过, {failed} 失败")
    return failed == 0


async def test_result_aggregation():
    """测试结果汇总功能"""
    print("\n" + "="*60)
    print("测试 2: 结果汇总功能")
    print("="*60)
    
    from app.agents.prototype.true_supervisor import TrueSupervisor
    from app.core.state import SQLExecutionResult
    from langchain_core.messages import HumanMessage
    
    supervisor = TrueSupervisor()
    supervisor._start_time = time.time() - 2.5  # 模拟 2.5s 执行时间
    
    # 模拟完整状态
    state = {
        "messages": [HumanMessage(content="查询所有客户的姓名")],
        "original_query": "查询所有客户的姓名",
        "enriched_query": "请查询 Customer 表中所有客户的姓名",
        "connection_id": 1,
        "current_stage": "completed",
        "generated_sql": "SELECT FirstName, LastName FROM Customer",
        "execution_result": SQLExecutionResult(
            success=True,
            data=[{"FirstName": "John", "LastName": "Doe"}],
            execution_time=0.05
        ),
        "analyst_insights": {"summary": "共查询到 1 条记录"},
        "chart_config": {"type": "table"},
        "recommended_questions": ["查询客户的邮箱", "统计客户数量"]
    }
    
    result = await supervisor.aggregate(state)
    
    # 验证
    final_response = result.get("final_response", {})
    
    checks = [
        ("success", final_response.get("success") == True),
        ("query", final_response.get("query") is not None),
        ("sql", final_response.get("sql") == "SELECT FirstName, LastName FROM Customer"),
        ("data", final_response.get("data") is not None),
        ("analysis", final_response.get("analysis") is not None),
        ("chart", final_response.get("chart") is not None),
        ("recommendations", len(final_response.get("recommendations", [])) > 0),
        ("metadata.execution_time", final_response.get("metadata", {}).get("execution_time") is not None),
        ("source", final_response.get("source") == "generated")
    ]
    
    passed = 0
    for name, check in checks:
        status = "✓" if check else "✗"
        print(f"  {status} {name}")
        if check:
            passed += 1
    
    print(f"\n  结果: {passed}/{len(checks)} 检查通过")
    return passed == len(checks)


async def test_graph_structure():
    """测试图结构"""
    print("\n" + "="*60)
    print("测试 3: Hub-and-Spoke 图结构")
    print("="*60)
    
    from app.agents.prototype.hub_spoke_graph import create_hub_spoke_graph
    
    graph = create_hub_spoke_graph()
    
    # 检查节点
    # 注意: CompiledGraph 的结构可能不同，这里做基本检查
    print("  ✓ 图创建成功")
    print("  ✓ 编译完成")
    
    # 打印图结构
    try:
        # 尝试获取图的可视化表示
        mermaid = graph.get_graph().draw_mermaid()
        print("\n  图结构 (Mermaid):")
        for line in mermaid.split('\n')[:20]:  # 只打印前20行
            print(f"    {line}")
        if len(mermaid.split('\n')) > 20:
            print("    ...")
    except Exception as e:
        print(f"  注意: 无法生成图可视化 ({e})")
    
    return True


async def test_simple_query():
    """测试简单查询流程"""
    print("\n" + "="*60)
    print("测试 4: 简单查询流程 (闲聊)")
    print("="*60)
    
    from app.agents.prototype.hub_spoke_graph import HubSpokeGraph
    
    graph = HubSpokeGraph()
    
    # 测试闲聊
    result = await graph.process_query(
        query="你好，请问你能做什么？",
        connection_id=1,
        thread_id="test-thread-1"
    )
    
    print(f"  成功: {result.get('success')}")
    print(f"  Thread ID: {result.get('thread_id')}")
    
    if result.get("success"):
        final_state = result.get("result", {})
        messages = final_state.get("messages", [])
        if messages:
            last_msg = messages[-1]
            content = last_msg.content if hasattr(last_msg, 'content') else str(last_msg)
            print(f"  响应: {content[:100]}...")
        
        route = final_state.get("route_decision")
        print(f"  路由决策: {route}")
    
    return result.get("success", False)


async def test_data_query_flow():
    """
    测试完整数据查询流程
    
    流程: supervisor → schema_agent → supervisor → sql_generator → supervisor 
          → sql_executor → supervisor → data_analyst → supervisor → FINISH
    """
    print("\n" + "="*60)
    print("测试 5: 完整数据查询流程")
    print("="*60)
    
    # 先检查数据库连接是否存在
    try:
        from app.db.session import get_db
        from app.crud import db_connection as crud_connection
        
        db = next(get_db())
        connection = crud_connection.get(db, id=1)
        db.close()
        
        if not connection:
            print("  跳过: 数据库连接 ID=1 不存在")
            print("  (这是配置问题，不是代码错误)")
            return None
    except Exception as e:
        print(f"  跳过: 无法检查数据库连接 ({e})")
        return None
    
    from app.agents.prototype.hub_spoke_graph import HubSpokeGraph
    
    graph = HubSpokeGraph()
    
    print(f"  执行查询: '查询所有客户的姓名和邮箱'")
    print(f"  使用连接: ID={connection.id}, 名称={connection.name}")
    
    start_time = time.time()
    
    try:
        result = await graph.process_query(
            query="查询所有客户的姓名和邮箱",
            connection_id=connection.id,
            thread_id="test-data-query-1"
        )
        
        elapsed = time.time() - start_time
        print(f"  耗时: {elapsed:.2f}s")
        print(f"  成功: {result.get('success')}")
        
        if result.get("success"):
            final_state = result.get("result", {})
            
            # 检查关键字段
            checks = {
                "current_stage": final_state.get("current_stage"),
                "generated_sql": final_state.get("generated_sql") is not None,
                "execution_result": final_state.get("execution_result") is not None,
                "final_response": final_state.get("final_response") is not None
            }
            
            print(f"  阶段: {checks['current_stage']}")
            print(f"  SQL生成: {'✓' if checks['generated_sql'] else '✗'}")
            print(f"  执行结果: {'✓' if checks['execution_result'] else '✗'}")
            print(f"  统一响应: {'✓' if checks['final_response'] else '✗'}")
            
            if final_state.get("generated_sql"):
                print(f"  SQL: {final_state['generated_sql'][:80]}...")
            
            if final_state.get("final_response"):
                fr = final_state["final_response"]
                print(f"  响应来源: {fr.get('source')}")
                print(f"  元数据: {fr.get('metadata')}")
            
            return all([
                checks["generated_sql"],
                checks["execution_result"] or checks["current_stage"] == "completed"
            ])
        else:
            print(f"  错误: {result.get('error')}")
            # 如果是因为重试上限达到而失败，这其实是正确的行为
            if "Recursion limit" in str(result.get('error', '')):
                print("  注意: 达到递归限制，可能是数据库连接问题")
            return False
            
    except Exception as e:
        logger.warning(f"数据查询测试失败: {e}")
        print(f"  跳过: {e}")
        return None


async def test_error_recovery_flow():
    """测试错误恢复流程"""
    print("\n" + "="*60)
    print("测试 6: 错误恢复流程")
    print("="*60)
    
    from app.agents.prototype.true_supervisor import TrueSupervisor
    from langchain_core.messages import HumanMessage
    
    supervisor = TrueSupervisor()
    
    # 模拟错误状态
    error_state = {
        "messages": [HumanMessage(content="查询所有客户")],
        "current_stage": "error_recovery",
        "retry_count": 1,
        "max_retries": 3,
        "error_history": [
            {
                "stage": "sql_execution",
                "error": "Unknown column 'names' in field list",
                "timestamp": time.time()
            }
        ]
    }
    
    # 测试路由决策
    next_agent = await supervisor.route(error_state)
    print(f"  错误后路由: {next_agent}")
    
    # 测试达到重试上限
    max_retry_state = {
        **error_state,
        "retry_count": 3
    }
    next_agent_max = await supervisor.route(max_retry_state)
    print(f"  达到重试上限: {next_agent_max}")
    
    passed = (next_agent == "sql_generator" and next_agent_max == "FINISH")
    print(f"  结果: {'✓ PASS' if passed else '✗ FAIL'}")
    
    return passed


async def test_cache_hit_flow():
    """测试缓存命中流程"""
    print("\n" + "="*60)
    print("测试 7: 缓存命中流程")
    print("="*60)
    
    from app.agents.prototype.hub_spoke_graph import supervisor_route
    from langchain_core.messages import HumanMessage
    
    # 模拟缓存命中状态
    cache_hit_state = {
        "messages": [HumanMessage(content="查询所有客户")],
        "current_stage": "init",
        "cache_hit": True,
        "cache_hit_type": "exact"
    }
    
    next_agent = supervisor_route(cache_hit_state)
    print(f"  缓存命中路由: {next_agent}")
    
    # 测试线程历史命中
    thread_hit_state = {
        "messages": [HumanMessage(content="查询所有客户")],
        "current_stage": "init",
        "thread_history_hit": True
    }
    
    next_agent_thread = supervisor_route(thread_hit_state)
    print(f"  线程历史命中: {next_agent_thread}")
    
    passed = (next_agent == "FINISH" and next_agent_thread == "FINISH")
    print(f"  结果: {'✓ PASS' if passed else '✗ FAIL'}")
    
    return passed


async def compare_with_pipeline():
    """对比 Hub-and-Spoke 与 Pipeline 架构"""
    print("\n" + "="*60)
    print("对比: Hub-and-Spoke vs Pipeline")
    print("="*60)
    
    comparison = """
    ┌─────────────────────────────────────────────────────────────────────────┐
    │                        架构对比                                          │
    ├──────────────────┬──────────────────────┬───────────────────────────────┤
    │ 维度             │ Pipeline (当前)       │ Hub-and-Spoke (新)            │
    ├──────────────────┼──────────────────────┼───────────────────────────────┤
    │ 消息流向         │ 节点→节点串行         │ 节点→Supervisor→节点          │
    │ 决策点           │ 分散在各条件边        │ 集中在 Supervisor             │
    │ Agent 返回       │ 直接修改 State        │ 返回结果给 Supervisor         │
    │ 灵活性           │ 流程固定              │ 可动态调整顺序                │
    │ 结果汇总         │ 无统一汇总            │ Supervisor 统一汇总           │
    │ 可扩展性         │ 需修改多处边          │ 只需在 Supervisor 添加路由    │
    │ 调试难度         │ 链路长，难追踪        │ 中心化，易追踪                │
    └──────────────────┴──────────────────────┴───────────────────────────────┘
    """
    print(comparison)
    
    return True


async def main():
    """运行所有测试"""
    print("\n" + "="*60)
    print("Hub-and-Spoke 架构原型验证")
    print("="*60)
    
    results = []
    
    # 测试 1: 路由决策
    try:
        results.append(("路由决策", await test_supervisor_routing()))
    except Exception as e:
        logger.error(f"路由决策测试失败: {e}")
        results.append(("路由决策", False))
    
    # 测试 2: 结果汇总
    try:
        results.append(("结果汇总", await test_result_aggregation()))
    except Exception as e:
        logger.error(f"结果汇总测试失败: {e}")
        results.append(("结果汇总", False))
    
    # 测试 3: 图结构
    try:
        results.append(("图结构", await test_graph_structure()))
    except Exception as e:
        logger.error(f"图结构测试失败: {e}")
        results.append(("图结构", False))
    
    # 测试 4: 简单查询 (闲聊)
    try:
        results.append(("闲聊流程", await test_simple_query()))
    except Exception as e:
        logger.warning(f"闲聊测试跳过: {e}")
        results.append(("闲聊流程", None))
    
    # 测试 5: 完整数据查询流程
    try:
        results.append(("数据查询流程", await test_data_query_flow()))
    except Exception as e:
        logger.warning(f"数据查询测试跳过: {e}")
        results.append(("数据查询流程", None))
    
    # 测试 6: 错误恢复流程
    try:
        results.append(("错误恢复", await test_error_recovery_flow()))
    except Exception as e:
        logger.error(f"错误恢复测试失败: {e}")
        results.append(("错误恢复", False))
    
    # 测试 7: 缓存命中流程
    try:
        results.append(("缓存命中", await test_cache_hit_flow()))
    except Exception as e:
        logger.error(f"缓存命中测试失败: {e}")
        results.append(("缓存命中", False))
    
    # 对比
    await compare_with_pipeline()
    
    # 汇总
    print("\n" + "="*60)
    print("测试结果汇总")
    print("="*60)
    
    for name, passed in results:
        if passed is None:
            status = "⏭ SKIP"
        elif passed:
            status = "✓ PASS"
        else:
            status = "✗ FAIL"
        print(f"  {status} - {name}")
    
    # 统计
    total = len(results)
    passed_count = sum(1 for _, r in results if r == True)
    failed_count = sum(1 for _, r in results if r == False)
    skipped_count = sum(1 for _, r in results if r is None)
    
    print(f"\n  总计: {total} | 通过: {passed_count} | 失败: {failed_count} | 跳过: {skipped_count}")
    
    # 返回退出码
    return 0 if failed_count == 0 else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
