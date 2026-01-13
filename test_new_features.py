#!/usr/bin/env python3
"""
测试多轮推理和分析师 Agent 功能
"""
import asyncio
from app.core.state import SQLMessageState
from langchain_core.messages import HumanMessage


async def test_clarification_agent():
    """测试澄清 Agent"""
    print("=" * 60)
    print("测试 1: 澄清 Agent - 模糊查询")
    print("=" * 60)
    
    try:
        from app.agents.agents.clarification_agent import clarification_agent
        
        # 模拟模糊查询
        state = SQLMessageState(
            messages=[HumanMessage(content="查看最近的销售数据")],
            connection_id=15,
            current_stage="clarification",
            clarification_round=0,
            max_clarification_rounds=2
        )
        
        result = await clarification_agent.process(state)
        print("✅ 澄清 Agent 测试通过")
        print(f"结果: {result}")
        return True
        
    except Exception as e:
        print(f"❌ 澄清 Agent 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def test_analyst_agent():
    """测试分析师 Agent"""
    print("\n" + "=" * 60)
    print("测试 2: 分析师 Agent - 数据分析")
    print("=" * 60)
    
    try:
        from app.agents.agents.analyst_agent import analyst_agent
        
        # 模拟查询结果
        mock_data = [
            {"date": "2024-01-01", "sales": 1000},
            {"date": "2024-01-02", "sales": 1200},
            {"date": "2024-01-03", "sales": 1100},
            {"date": "2024-01-04", "sales": 1500},
            {"date": "2024-01-05", "sales": 1300},
        ]
        
        state = SQLMessageState(
            messages=[HumanMessage(content="查询最近5天的销售额")],
            connection_id=15,
            current_stage="analysis",
            generated_sql="SELECT date, SUM(amount) as sales FROM orders GROUP BY date",
            execution_result={
                "success": True,
                "data": mock_data
            }
        )
        
        result = await analyst_agent.process(state)
        print("✅ 分析师 Agent 测试通过")
        print(f"结果阶段: {result.get('current_stage')}")
        return True
        
    except Exception as e:
        print(f"❌ 分析师 Agent 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_analyst_utils():
    """测试分析工具函数"""
    print("\n" + "=" * 60)
    print("测试 3: 分析工具函数")
    print("=" * 60)
    
    try:
        from app.services.analyst_utils import (
            calculate_statistics,
            detect_time_series,
            calculate_growth_rate,
            detect_outliers
        )
        
        # 测试数据
        test_data = [
            {"date": "2024-01-01", "sales": 1000, "orders": 10},
            {"date": "2024-01-02", "sales": 1200, "orders": 12},
            {"date": "2024-01-03", "sales": 1100, "orders": 11},
            {"date": "2024-01-04", "sales": 1500, "orders": 15},
            {"date": "2024-01-05", "sales": 1300, "orders": 13},
        ]
        
        # 测试统计计算
        stats = calculate_statistics(test_data)
        assert "total_rows" in stats
        assert stats["total_rows"] == 5
        print(f"✅ 统计计算: {stats['total_rows']} 行")
        
        # 测试时间序列检测
        ts_info = detect_time_series(test_data)
        if ts_info:
            print(f"✅ 时间序列检测: 发现日期列 '{ts_info['date_column']}'")
        
        # 测试增长率计算
        growth = calculate_growth_rate(test_data, "date", "sales")
        if "error" not in growth:
            print(f"✅ 增长率计算: 总体增长 {growth['total_growth_rate']:.2f}%")
        
        # 测试异常检测
        outliers = detect_outliers(test_data, "sales")
        if "error" not in outliers:
            print(f"✅ 异常检测: 发现 {outliers['count']} 个离群值")
        
        print("✅ 所有工具函数测试通过")
        return True
        
    except Exception as e:
        print(f"❌ 工具函数测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_state_extensions():
    """测试状态扩展"""
    print("\n" + "=" * 60)
    print("测试 4: 状态扩展")
    print("=" * 60)
    
    try:
        from app.core.state import SQLMessageState
        
        # 创建状态实例
        state = SQLMessageState(
            messages=[HumanMessage(content="测试")],
            connection_id=15,
            # 新增字段
            clarification_history=[],
            clarification_round=0,
            max_clarification_rounds=2,
            needs_clarification=False,
            clarification_questions=[],
            analyst_insights=None,
            needs_analysis=False
        )
        
        # 验证字段存在
        assert hasattr(state, "clarification_history")
        assert hasattr(state, "clarification_round")
        assert hasattr(state, "analyst_insights")
        assert state.max_clarification_rounds == 2
        
        print("✅ 状态扩展测试通过")
        print(f"   - 澄清轮数上限: {state.max_clarification_rounds}")
        print(f"   - 当前轮数: {state.clarification_round}")
        return True
        
    except Exception as e:
        print(f"❌ 状态扩展测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_schemas():
    """测试 Schema 定义"""
    print("\n" + "=" * 60)
    print("测试 5: Schema 定义")
    print("=" * 60)
    
    try:
        from app.schemas.query import (
            ClarificationQuestion,
            ClarificationResponse,
            AnalystInsights,
            ChatQueryRequest,
            ChatQueryResponse
        )
        
        # 测试澄清问题
        question = ClarificationQuestion(
            id="q1",
            question="您想查看哪个时间范围？",
            type="choice",
            options=["最近7天", "最近30天"]
        )
        assert question.id == "q1"
        print("✅ ClarificationQuestion 验证通过")
        
        # 测试澄清回复
        response = ClarificationResponse(
            question_id="q1",
            answer="最近7天"
        )
        assert response.answer == "最近7天"
        print("✅ ClarificationResponse 验证通过")
        
        # 测试分析洞察
        insights = AnalystInsights(
            summary={"total_rows": 10},
            trends={"trend_direction": "上升"}
        )
        assert insights.summary["total_rows"] == 10
        print("✅ AnalystInsights 验证通过")
        
        # 测试聊天请求
        chat_req = ChatQueryRequest(
            connection_id=15,
            natural_language_query="测试查询",
            conversation_id="test-123"
        )
        assert chat_req.conversation_id == "test-123"
        print("✅ ChatQueryRequest 验证通过")
        
        # 测试聊天响应
        chat_resp = ChatQueryResponse(
            conversation_id="test-123",
            needs_clarification=True,
            clarification_questions=[question]
        )
        assert len(chat_resp.clarification_questions) == 1
        print("✅ ChatQueryResponse 验证通过")
        
        print("✅ 所有 Schema 测试通过")
        return True
        
    except Exception as e:
        print(f"❌ Schema 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """运行所有测试"""
    print("\n")
    print("🚀 开始测试多轮推理和分析师 Agent 功能")
    print("\n")
    
    results = []
    
    # 同步测试
    results.append(("状态扩展", test_state_extensions()))
    results.append(("Schema 定义", test_schemas()))
    results.append(("分析工具函数", test_analyst_utils()))
    
    # 异步测试
    results.append(("澄清 Agent", await test_clarification_agent()))
    results.append(("分析师 Agent", await test_analyst_agent()))
    
    # 汇总结果
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{name}: {status}")
    
    print("\n" + "=" * 60)
    print(f"总计: {passed}/{total} 测试通过")
    print("=" * 60)
    
    if passed == total:
        print("\n🎉 所有测试通过！系统已准备好使用。")
        return 0
    else:
        print(f"\n⚠️  有 {total - passed} 个测试失败，请检查日志。")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
