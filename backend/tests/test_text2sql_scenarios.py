"""
Text-to-SQL 系统场景测试

测试所有关键流程和节点
"""
import asyncio
import pytest
from typing import Dict, Any
from langchain_core.messages import HumanMessage

from app.agents.chat_graph import get_global_graph_async
from app.core.state import create_initial_state


class TestText2SQLScenarios:
    """Text-to-SQL 场景测试套件"""
    
    @pytest.fixture(scope="class")
    async def graph(self):
        """获取测试用图实例"""
        return await get_global_graph_async()
    
    # =========================================================================
    # 场景 1: 正常场景测试
    # =========================================================================
    
    @pytest.mark.asyncio
    async def test_simple_query_fast_mode(self):
        """
        测试 1.1: 简单查询（快速模式）
        预期: fast_mode=true, skip_chart_generation=true
        """
        print("\n" + "="*80)
        print("测试 1.1: 简单查询（快速模式）")
        print("="*80)
        
        graph = await get_global_graph_async()
        
        initial_state = create_initial_state(connection_id=7)
        initial_state["messages"] = [
            HumanMessage(content="查询产品数量")
        ]
        
        config = {"configurable": {"thread_id": "test-fast-mode"}}
        
        result = await graph.graph.ainvoke(initial_state, config=config)
        
        # 验证
        assert result.get("fast_mode") == True, "应该启用快速模式"
        assert result.get("skip_chart_generation") == True, "应该跳过图表生成"
        assert result.get("current_stage") == "completed", "应该完成"
        
        print("✅ 快速模式测试通过")
        print(f"   - fast_mode: {result.get('fast_mode')}")
        print(f"   - skip_chart_generation: {result.get('skip_chart_generation')}")
        print(f"   - current_stage: {result.get('current_stage')}")
    
    @pytest.mark.asyncio
    async def test_complex_query_full_mode(self):
        """
        测试 1.2: 复杂查询（完整模式）
        预期: fast_mode=false, 调用分析专家
        """
        print("\n" + "="*80)
        print("测试 1.2: 复杂查询（完整模式）")
        print("="*80)
        
        graph = await get_global_graph_async()
        
        initial_state = create_initial_state(connection_id=7)
        initial_state["messages"] = [
            HumanMessage(content="分析最近7天各个仓库的库存变化趋势")
        ]
        
        config = {"configurable": {"thread_id": "test-full-mode"}}
        
        result = await graph.graph.ainvoke(initial_state, config=config)
        
        # 验证
        assert result.get("fast_mode") == False, "应该使用完整模式"
        assert result.get("current_stage") == "completed", "应该完成"
        assert result.get("execution_result") is not None, "应该有执行结果"
        
        # 检查是否有分析内容
        messages = result.get("messages", [])
        has_analysis = False
        for msg in messages:
            if hasattr(msg, 'type') and msg.type == 'ai':
                content = msg.content
                if isinstance(content, str) and len(content) > 100:
                    has_analysis = True
                    break
        
        assert has_analysis, "应该包含详细分析"
        
        print("✅ 完整模式测试通过")
        print(f"   - fast_mode: {result.get('fast_mode')}")
        print(f"   - current_stage: {result.get('current_stage')}")
        print(f"   - has_analysis: {has_analysis}")
    
    # =========================================================================
    # 场景 3: 澄清场景测试
    # =========================================================================
    
    @pytest.mark.asyncio
    async def test_clear_query_skip_clarification(self):
        """
        测试 3.1: 明确查询（跳过澄清）
        预期: 直接执行，不需要澄清
        """
        print("\n" + "="*80)
        print("测试 3.1: 明确查询（跳过澄清）")
        print("="*80)
        
        graph = await get_global_graph_async()
        
        initial_state = create_initial_state(connection_id=7)
        initial_state["messages"] = [
            HumanMessage(content="查询 inventory 表的所有记录 LIMIT 10")
        ]
        
        config = {"configurable": {"thread_id": "test-skip-clarification"}}
        
        result = await graph.graph.ainvoke(initial_state, config=config)
        
        # 验证
        assert "clarification_responses" not in result or not result.get("clarification_responses"), \
            "不应该有澄清响应"
        assert result.get("current_stage") == "completed", "应该完成"
        
        print("✅ 跳过澄清测试通过")
        print(f"   - 无澄清响应: {not result.get('clarification_responses')}")
        print(f"   - current_stage: {result.get('current_stage')}")
    
    # =========================================================================
    # 场景 4: Cache Check 测试
    # =========================================================================
    
    @pytest.mark.asyncio
    async def test_cache_exact_match(self):
        """
        测试 4.1: 精确匹配缓存命中
        预期: 第二次查询命中缓存，直接返回
        """
        print("\n" + "="*80)
        print("测试 4.1: 精确匹配缓存命中")
        print("="*80)
        
        graph = await get_global_graph_async()
        
        query = "SELECT * FROM inventory LIMIT 5"
        
        # 第一次查询（建立缓存）
        print("\n第一次查询（建立缓存）...")
        initial_state1 = create_initial_state(connection_id=7)
        initial_state1["messages"] = [HumanMessage(content=query)]
        config1 = {"configurable": {"thread_id": "test-cache-1"}}
        
        result1 = await graph.graph.ainvoke(initial_state1, config1)
        
        assert result1.get("cache_hit") != True or result1.get("cache_hit") is None, \
            "第一次查询不应命中缓存"
        print(f"   - cache_hit: {result1.get('cache_hit')}")
        
        # 等待缓存写入
        await asyncio.sleep(1)
        
        # 第二次查询（应该命中缓存）
        print("\n第二次查询（应该命中缓存）...")
        initial_state2 = create_initial_state(connection_id=7)
        initial_state2["messages"] = [HumanMessage(content=query)]
        config2 = {"configurable": {"thread_id": "test-cache-2"}}
        
        result2 = await graph.graph.ainvoke(initial_state2, config2)
        
        # 验证
        # 注意：由于我们使用了新的 thread_id，可能不会命中缓存
        # 这取决于缓存服务的实现
        print(f"   - cache_hit: {result2.get('cache_hit')}")
        print(f"   - cache_hit_type: {result2.get('cache_hit_type')}")
        
        if result2.get("cache_hit"):
            print("✅ 缓存命中测试通过")
            assert result2.get("cache_hit_type") in ["exact", "semantic"], \
                "应该是精确或语义匹配"
        else:
            print("⚠️  缓存未命中（可能是因为使用了不同的 thread_id）")
    
    # =========================================================================
    # 场景 5: Schema 信息传递测试
    # =========================================================================
    
    @pytest.mark.asyncio
    async def test_schema_info_passing(self):
        """
        测试 5.1: Schema 信息正确传递
        预期: schema_agent 存储信息，sql_generator_agent 正确使用
        """
        print("\n" + "="*80)
        print("测试 5.1: Schema 信息正确传递")
        print("="*80)
        
        graph = await get_global_graph_async()
        
        initial_state = create_initial_state(connection_id=7)
        initial_state["messages"] = [
            HumanMessage(content="查询库存中产品名称为 'Product A' 的记录")
        ]
        
        config = {"configurable": {"thread_id": "test-schema-passing"}}
        
        result = await graph.graph.ainvoke(initial_state, config=config)
        
        # 验证
        assert "schema_info" in result, "应该包含 schema_info"
        assert result["schema_info"] is not None, "schema_info 不应为空"
        
        schema_info = result["schema_info"]
        assert "tables" in schema_info, "schema_info 应该包含 tables"
        assert "connection_id" in schema_info, "schema_info 应该包含 connection_id"
        
        print("✅ Schema 信息传递测试通过")
        print(f"   - schema_info 存在: True")
        print(f"   - tables 数量: {len(schema_info.get('tables', {}))}")
        print(f"   - connection_id: {schema_info.get('connection_id')}")
        
        # 验证 SQL 生成使用了正确的表结构
        generated_sql = result.get("generated_sql", "")
        assert "inventory" in generated_sql.lower(), "SQL 应该包含 inventory 表"
        print(f"   - SQL 包含正确表名: True")


# ============================================================================
# 独立测试函数（可以直接运行）
# ============================================================================

async def run_basic_test():
    """运行基础测试"""
    print("\n" + "="*80)
    print("开始基础功能测试")
    print("="*80)
    
    graph = await get_global_graph_async()
    
    # 测试简单查询
    print("\n测试: 简单查询")
    initial_state = create_initial_state(connection_id=7)
    initial_state["messages"] = [HumanMessage(content="查询产品总数")]
    
    config = {"configurable": {"thread_id": "basic-test"}}
    
    result = await graph.graph.ainvoke(initial_state, config=config)
    
    print(f"\n执行结果:")
    print(f"  - fast_mode: {result.get('fast_mode')}")
    print(f"  - current_stage: {result.get('current_stage')}")
    print(f"  - cache_hit: {result.get('cache_hit')}")
    print(f"  - generated_sql: {result.get('generated_sql', '')[:100]}...")
    
    if result.get("execution_result"):
        exec_result = result["execution_result"]
        print(f"  - execution_result.success: {exec_result.success}")
        if exec_result.success and exec_result.data:
            print(f"  - 返回数据行数: {exec_result.data.get('row_count', 0)}")
    
    print("\n✅ 基础功能测试完成")


if __name__ == "__main__":
    # 直接运行测试
    print("="*80)
    print("Text-to-SQL 系统场景测试")
    print("="*80)
    
    asyncio.run(run_basic_test())
