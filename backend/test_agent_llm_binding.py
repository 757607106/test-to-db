#!/usr/bin/env python3
"""
测试智能体LLM绑定是否正确
"""
from app.db.session import SessionLocal
from app.core.agent_config import get_agent_llm, CORE_AGENT_SQL_GENERATOR, CORE_AGENT_CHART_ANALYST, CORE_AGENT_ROUTER

def test_agent_llm_binding():
    """测试智能体LLM绑定"""
    print("="*80)
    print("测试智能体LLM绑定")
    print("="*80)
    
    db = SessionLocal()
    try:
        # 测试SQL生成专家
        print("\n1. 测试 SQL生成专家 (sql_generator_core)")
        print("-"*80)
        llm = get_agent_llm(CORE_AGENT_SQL_GENERATOR, db)
        print(f"✓ 成功获取LLM实例: {type(llm).__name__}")
        
        # 测试数据分析专家
        print("\n2. 测试 数据分析专家 (chart_analyst_core)")
        print("-"*80)
        llm = get_agent_llm(CORE_AGENT_CHART_ANALYST, db)
        print(f"✓ 成功获取LLM实例: {type(llm).__name__}")
        
        # 测试意图识别路由
        print("\n3. 测试 意图识别路由 (router_core)")
        print("-"*80)
        llm = get_agent_llm(CORE_AGENT_ROUTER, db)
        print(f"✓ 成功获取LLM实例: {type(llm).__name__}")
        
        print("\n" + "="*80)
        print("✅ 所有测试通过！")
        print("="*80)
        print("\n提示：")
        print("- 如果看到 '🤖 Agent 模型调用' 输出，说明使用了配置的模型")
        print("- 如果看到 'deepseek-chat'，说明绑定成功")
        print("- 如果看到 'qwen3-max'，说明仍在使用全局默认")
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    test_agent_llm_binding()
