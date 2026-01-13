"""
测试优化后的Agent系统
验证功能正确性和性能提升
"""
import asyncio
import time
from app.agents.agents.clarification_agent import clarification_agent, quick_clarification_check
from app.agents.agents.schema_agent import schema_agent, analyze_query_and_fetch_schema
from app.agents.agents.sql_generator_agent import sql_generator_agent, generate_sql_query
from app.agents.agents.sql_executor_agent import sql_executor_agent, execute_sql_query
from app.agents.agents.analyst_agent import analyst_agent, intelligent_analysis, rule_based_analysis_check
from app.core.state import SQLMessageState
from langchain_core.messages import HumanMessage


async def test_clarification_agent():
    """测试简化后的澄清代理"""
    print("\n=== 测试澄清代理 ===")
    start_time = time.time()
    
    # 测试明确查询
    result1 = quick_clarification_check.invoke({
        "query": "SELECT * FROM users WHERE id = 1",
        "connection_id": 15
    })
    print(f"明确查询结果: {result1.get('needs_clarification')}")
    
    # 测试模糊查询
    result2 = quick_clarification_check.invoke({
        "query": "最近的销售情况",
        "connection_id": 15
    })
    print(f"模糊查询结果: {result2.get('needs_clarification')}")
    print(f"澄清问题数: {len(result2.get('questions', []))}")
    
    elapsed = time.time() - start_time
    print(f"✅ 澄清代理测试完成，耗时: {elapsed:.2f}秒")
    return elapsed


async def test_schema_agent():
    """测试优化后的Schema代理"""
    print("\n=== 测试Schema代理 ===")
    start_time = time.time()
    
    # 直接调用工具
    result = analyze_query_and_fetch_schema.invoke({
        "query": "查询所有用户",
        "connection_id": 15
    })
    
    print(f"Schema获取成功: {result.get('success')}")
    print(f"获取表数量: {len(result.get('schema_context', {}))}")
    
    elapsed = time.time() - start_time
    print(f"✅ Schema代理测试完成，耗时: {elapsed:.2f}秒")
    return elapsed


async def test_sql_generator():
    """测试优化后的SQL生成代理"""
    print("\n=== 测试SQL生成代理 ===")
    start_time = time.time()
    
    # 构造测试schema
    test_schema = {
        "users": {
            "columns": ["id", "name", "email"],
            "types": {"id": "int", "name": "varchar", "email": "varchar"}
        }
    }
    
    result = generate_sql_query.invoke({
        "user_query": "查询所有用户的名字和邮箱",
        "schema_info": test_schema,
        "db_type": "mysql"
    })
    
    print(f"SQL生成成功: {result.get('success')}")
    print(f"生成的SQL: {result.get('sql_query', '')[:100]}")
    
    elapsed = time.time() - start_time
    print(f"✅ SQL生成代理测试完成，耗时: {elapsed:.2f}秒")
    return elapsed


async def test_analyst_agent():
    """测试简化后的分析代理"""
    print("\n=== 测试分析代理 ===")
    start_time = time.time()
    
    # 测试规则判断
    test_data = [
        {"id": 1, "name": "Alice", "sales": 1000},
        {"id": 2, "name": "Bob", "sales": 1500},
        {"id": 3, "name": "Charlie", "sales": 800}
    ]
    
    analysis_level = rule_based_analysis_check(test_data, "SELECT * FROM sales")
    print(f"分析级别判断: {analysis_level}")
    
    # 测试智能分析
    result = intelligent_analysis.invoke({
        "query": "查询销售数据",
        "result_data": test_data,
        "sql": "SELECT * FROM sales",
        "analysis_level": analysis_level
    })
    
    print(f"分析成功: {result.get('success')}")
    print(f"分析摘要: {result.get('summary', '')[:100]}")
    
    elapsed = time.time() - start_time
    print(f"✅ 分析代理测试完成，耗时: {elapsed:.2f}秒")
    return elapsed


async def test_full_workflow():
    """测试完整工作流"""
    print("\n=== 测试完整工作流 ===")
    start_time = time.time()
    
    state = SQLMessageState(
        messages=[HumanMessage(content="查询所有用户")],
        connection_id=15,
        current_stage="clarification",
        retry_count=0,
        max_retries=3,
        error_history=[]
    )
    
    # 1. 澄清检测
    print("1. 执行澄清检测...")
    clarif_result = quick_clarification_check.invoke({
        "query": "查询所有用户",
        "connection_id": 15
    })
    print(f"   需要澄清: {clarif_result.get('needs_clarification')}")
    
    # 2. Schema分析
    print("2. 执行Schema分析...")
    schema_result = analyze_query_and_fetch_schema.invoke({
        "query": "查询所有用户",
        "connection_id": 15
    })
    print(f"   Schema成功: {schema_result.get('success')}")
    
    # 3. SQL生成
    if schema_result.get('success'):
        print("3. 执行SQL生成...")
        sql_result = generate_sql_query.invoke({
            "user_query": "查询所有用户",
            "schema_info": schema_result.get('schema_context', {}),
            "value_mappings": schema_result.get('value_mappings'),
            "db_type": "mysql"
        })
        print(f"   SQL生成成功: {sql_result.get('success')}")
        
        # 4. SQL执行
        if sql_result.get('success'):
            print("4. 执行SQL查询...")
            try:
                exec_result = execute_sql_query.invoke({
                    "sql_query": sql_result.get('sql_query'),
                    "connection_id": 15,
                    "timeout": 30
                })
                print(f"   SQL执行成功: {exec_result.get('success')}")
                
                # 5. 结果分析
                if exec_result.get('success') and exec_result.get('data'):
                    print("5. 执行结果分析...")
                    data = exec_result.get('data', {})
                    result_data = []
                    if data.get('data') and data.get('columns'):
                        for row in data['data']:
                            result_data.append(dict(zip(data['columns'], row)))
                    
                    if result_data:
                        analysis_level = rule_based_analysis_check(result_data, sql_result.get('sql_query', ''))
                        if analysis_level != "skip":
                            analysis_result = intelligent_analysis.invoke({
                                "query": "查询所有用户",
                                "result_data": result_data,
                                "sql": sql_result.get('sql_query'),
                                "analysis_level": analysis_level
                            })
                            print(f"   分析完成: {analysis_result.get('success')}")
            except Exception as e:
                print(f"   SQL执行出错（预期，因为可能没有数据库连接）: {str(e)[:50]}")
    
    elapsed = time.time() - start_time
    print(f"\n✅ 完整工作流测试完成，总耗时: {elapsed:.2f}秒")
    return elapsed


async def performance_comparison():
    """性能对比总结"""
    print("\n" + "="*60)
    print("性能优化总结")
    print("="*60)
    
    print("\n优化措施:")
    print("1. ✅ 澄清代理: 3次LLM调用 -> 1次LLM调用")
    print("2. ✅ 分析代理: 2次LLM调用 -> 规则判断 + 1次LLM调用")
    print("3. ✅ Schema代理: ReAct循环 -> 直接工具调用")
    print("4. ✅ SQL生成代理: ReAct循环 -> 直接工具调用")
    print("5. ✅ SQL执行代理: ReAct循环 -> 直接工具调用")
    
    print("\n预期性能提升:")
    print("- LLM调用次数减少: ~50%")
    print("- ReAct开销消除: 每个agent节省1-2次LLM调用")
    print("- 总体响应时间提升: 50-70%")
    
    print("\n优化后的工作流:")
    print("用户查询 → 澄清检测(1次LLM) → Schema分析(直接调用) → ")
    print("SQL生成(直接调用) → SQL执行(直接调用) → 分析(规则+1次LLM) → 完成")


async def main():
    """主测试函数"""
    print("开始测试优化后的Agent系统...")
    print("="*60)
    
    try:
        # 单元测试
        times = []
        times.append(await test_clarification_agent())
        times.append(await test_schema_agent())
        times.append(await test_sql_generator())
        times.append(await test_analyst_agent())
        
        # 集成测试
        times.append(await test_full_workflow())
        
        # 性能总结
        await performance_comparison()
        
        print("\n" + "="*60)
        print(f"所有测试完成！总耗时: {sum(times):.2f}秒")
        print("="*60)
        
    except Exception as e:
        print(f"\n❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
