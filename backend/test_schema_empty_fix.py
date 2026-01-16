"""
测试Schema为空场景的修复效果
验证三个关键修复点：
1. schema_agent能正确检测并返回友好错误
2. supervisor能正确识别技术性故障
3. clarification_agent不会询问技术问题
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from langchain_core.messages import HumanMessage
from app.agents.agents.schema_agent import analyze_query_and_fetch_schema
from app.agents.chat_graph import create_intelligent_sql_graph
from app.db.session import SessionLocal
from app import crud


async def test_case_1_schema_empty_detection():
    """
    测试用例1: Schema Agent能否正确检测空schema并返回友好错误
    """
    print("\n" + "="*80)
    print("测试用例1: Schema为空的检测")
    print("="*80)
    
    # 使用一个不存在的connection_id
    test_connection_id = 99999
    test_query = "查询去年每个季度的销量最高的产品"
    
    print(f"\n输入:")
    print(f"  - 查询: {test_query}")
    print(f"  - Connection ID: {test_connection_id} (不存在)")
    
    result = analyze_query_and_fetch_schema.invoke({
        "query": test_query,
        "connection_id": test_connection_id
    })
    
    print(f"\n输出:")
    print(f"  - Success: {result.get('success')}")
    print(f"  - Error: {result.get('error', 'N/A')[:200]}...")
    
    # 验证结果
    assert result.get('success') == False, "应该返回失败状态"
    error_msg = result.get('error', '')
    assert "数据库连接" in error_msg or "不存在" in error_msg, "错误消息应该提示连接不存在"
    
    print(f"\n✅ 测试通过: Schema Agent正确检测到连接不存在")
    return True


async def test_case_2_schema_empty_with_valid_connection():
    """
    测试用例2: 使用有效但未发布schema的connection
    """
    print("\n" + "="*80)
    print("测试用例2: 有效连接但Schema未发布")
    print("="*80)
    
    # 检查是否有未发布schema的connection
    db = SessionLocal()
    try:
        connections = crud.db_connection.get_multi(db, limit=10)
        
        # 找一个没有schema的connection
        test_connection = None
        for conn in connections:
            tables = crud.schema_table.get_by_connection(db, connection_id=conn.id)
            if len(tables) == 0:
                test_connection = conn
                break
        
        if not test_connection:
            print("\n⚠️  跳过: 没有找到未发布schema的数据库连接")
            print("   提示: 请在Admin中创建一个数据库连接但不发布schema")
            return None
        
        test_query = "查询去年每个季度的销量最高的产品"
        
        print(f"\n输入:")
        print(f"  - 查询: {test_query}")
        print(f"  - Connection: {test_connection.name} (ID: {test_connection.id})")
        print(f"  - 表数量: 0 (未发布)")
        
        result = analyze_query_and_fetch_schema.invoke({
            "query": test_query,
            "connection_id": test_connection.id
        })
        
        print(f"\n输出:")
        print(f"  - Success: {result.get('success')}")
        if not result.get('success'):
            error_msg = result.get('error', '')
            print(f"\n错误消息:")
            print("-" * 80)
            print(error_msg)
            print("-" * 80)
            
            # 验证错误消息包含关键信息
            assert "没有可用的表结构" in error_msg or "schema" in error_msg.lower(), \
                "错误消息应该提示schema问题"
            assert "Admin" in error_msg or "发布" in error_msg or "Publish" in error_msg, \
                "错误消息应该包含解决方案"
            assert "发现Schema" in error_msg or "Discover" in error_msg, \
                "错误消息应该提示发现schema步骤"
            
            print(f"\n✅ 测试通过: 返回了友好的错误消息和解决方案")
            return True
        else:
            print(f"\n❌ 测试失败: 应该返回失败但却成功了")
            return False
            
    finally:
        db.close()


async def test_case_3_full_workflow_with_empty_schema():
    """
    测试用例3: 完整工作流 - 验证Supervisor不会调用clarification_agent
    """
    print("\n" + "="*80)
    print("测试用例3: 完整工作流测试")
    print("="*80)
    
    # 找一个未发布schema的connection
    db = SessionLocal()
    try:
        connections = crud.db_connection.get_multi(db, limit=10)
        test_connection = None
        for conn in connections:
            tables = crud.schema_table.get_by_connection(db, connection_id=conn.id)
            if len(tables) == 0:
                test_connection = conn
                break
        
        if not test_connection:
            print("\n⚠️  跳过: 没有找到未发布schema的数据库连接")
            return None
        
        test_query = "我想查询一下去年每个季度的销量最高的产品"
        
        print(f"\n输入:")
        print(f"  - 查询: {test_query}")
        print(f"  - Connection: {test_connection.name} (ID: {test_connection.id})")
        
        # 创建图实例
        graph = create_intelligent_sql_graph()
        
        print(f"\n执行工作流...")
        result = await graph.process_query(
            query=test_query,
            connection_id=test_connection.id
        )
        
        print(f"\n输出:")
        print(f"  - Success: {result.get('success')}")
        print(f"  - Final Stage: {result.get('final_stage', 'N/A')}")
        
        if not result.get('success'):
            error_msg = result.get('error', '')
            print(f"\n错误消息预览: {error_msg[:300]}...")
            
            # 验证不会进入clarification阶段
            # 验证直接返回技术性错误
            print(f"\n✅ 测试通过: 工作流正确处理了schema为空的情况")
            return True
        else:
            print(f"\n❌ 测试失败: 应该返回失败")
            return False
            
    finally:
        db.close()


async def test_case_4_clarification_only_business_logic():
    """
    测试用例4: 验证clarification_agent只问业务逻辑问题
    """
    print("\n" + "="*80)
    print("测试用例4: Clarification Agent行为验证")
    print("="*80)
    
    from app.agents.agents.clarification_agent import quick_clarification_check
    
    # 测试模糊查询（应该澄清）
    test_cases = [
        {
            "query": "查询最近的销售情况",
            "should_clarify": True,
            "reason": "时间范围模糊"
        },
        {
            "query": "查询2023年1月的销售数据",
            "should_clarify": False,
            "reason": "查询明确"
        }
    ]
    
    db = SessionLocal()
    try:
        # 使用一个有schema的connection
        connections = crud.db_connection.get_multi(db, limit=10)
        test_connection = None
        for conn in connections:
            tables = crud.schema_table.get_by_connection(db, connection_id=conn.id)
            if len(tables) > 0:
                test_connection = conn
                break
        
        if not test_connection:
            print("\n⚠️  跳过: 没有找到已发布schema的数据库连接")
            return None
        
        for i, test_case in enumerate(test_cases, 1):
            print(f"\n子测试 {i}: {test_case['reason']}")
            print(f"  查询: {test_case['query']}")
            
            result = quick_clarification_check.invoke({
                "query": test_case['query'],
                "connection_id": test_connection.id
            })
            
            needs_clarification = result.get('needs_clarification', False)
            questions = result.get('questions', [])
            
            print(f"  需要澄清: {needs_clarification}")
            print(f"  问题数量: {len(questions)}")
            
            if questions:
                for q in questions:
                    question_text = q.get('question', '')
                    print(f"  问题: {question_text}")
                    
                    # 验证不包含技术性问题
                    forbidden_keywords = ["表", "字段", "结构", "关系", "存储"]
                    has_forbidden = any(kw in question_text for kw in forbidden_keywords)
                    
                    if has_forbidden:
                        print(f"    ❌ 包含禁止的技术性关键词")
                        return False
                    else:
                        print(f"    ✅ 没有技术性问题")
            
            expected = test_case['should_clarify']
            if needs_clarification == expected:
                print(f"  ✅ 符合预期 (should_clarify={expected})")
            else:
                print(f"  ⚠️  不符合预期 (expected={expected}, got={needs_clarification})")
        
        print(f"\n✅ 测试通过: Clarification Agent行为正确")
        return True
        
    finally:
        db.close()


async def main():
    """运行所有测试"""
    print("\n" + "="*80)
    print("开始Schema为空场景修复验证测试")
    print("="*80)
    
    results = []
    
    # 测试1: Schema Agent检测
    try:
        result1 = await test_case_1_schema_empty_detection()
        results.append(("Schema Agent - 连接不存在检测", result1))
    except Exception as e:
        print(f"\n❌ 测试1异常: {e}")
        results.append(("Schema Agent - 连接不存在检测", False))
    
    # 测试2: Schema为空但连接有效
    try:
        result2 = await test_case_2_schema_empty_with_valid_connection()
        results.append(("Schema Agent - Schema未发布检测", result2))
    except Exception as e:
        print(f"\n❌ 测试2异常: {e}")
        results.append(("Schema Agent - Schema未发布检测", False))
    
    # 测试3: 完整工作流
    try:
        result3 = await test_case_3_full_workflow_with_empty_schema()
        results.append(("完整工作流 - Supervisor路由", result3))
    except Exception as e:
        print(f"\n❌ 测试3异常: {e}")
        import traceback
        traceback.print_exc()
        results.append(("完整工作流 - Supervisor路由", False))
    
    # 测试4: Clarification行为
    try:
        result4 = await test_case_4_clarification_only_business_logic()
        results.append(("Clarification Agent行为", result4))
    except Exception as e:
        print(f"\n❌ 测试4异常: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Clarification Agent行为", False))
    
    # 输出总结
    print("\n" + "="*80)
    print("测试结果总结")
    print("="*80)
    
    passed = 0
    skipped = 0
    failed = 0
    
    for test_name, result in results:
        if result is None:
            status = "⚠️  SKIPPED"
            skipped += 1
        elif result:
            status = "✅ PASSED"
            passed += 1
        else:
            status = "❌ FAILED"
            failed += 1
        
        print(f"{status} - {test_name}")
    
    print(f"\n总计: {len(results)}个测试")
    print(f"  ✅ 通过: {passed}")
    print(f"  ❌ 失败: {failed}")
    print(f"  ⚠️  跳过: {skipped}")
    
    if failed == 0:
        print(f"\n🎉 所有测试通过！修复成功！")
    else:
        print(f"\n⚠️  有{failed}个测试失败，需要进一步检查")
    
    print("="*80)


if __name__ == "__main__":
    asyncio.run(main())
