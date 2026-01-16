"""
SQLGeneratorAgent简单测试 - 不涉及异步调用
只测试配置和提示词
"""
from app.agents.agents.sql_generator_agent import SQLGeneratorAgent


def test_system_prompt_emphasizes_quality():
    """测试系统提示词强调SQL质量"""
    print("\n测试1: 系统提示词强调质量")
    
    agent = SQLGeneratorAgent()
    prompt = agent._create_system_prompt()
    
    # 检查是否强调质量和安全性
    quality_keywords = [
        "确保",
        "正确性",
        "安全性",
        "不再有验证",
        "直接执行"
    ]
    
    found_keywords = []
    for keyword in quality_keywords:
        if keyword in prompt:
            found_keywords.append(keyword)
    
    if len(found_keywords) >= 3:
        print(f"  ✅ 通过: 系统提示词强调质量（找到{len(found_keywords)}个关键词）")
        print(f"  关键词: {found_keywords}")
        return True
    else:
        print(f"  ❌ 失败: 系统提示词未充分强调质量（只找到{len(found_keywords)}个关键词）")
        return False


def test_agent_initialization():
    """测试代理正确初始化"""
    print("\n测试2: 代理初始化")
    
    try:
        agent = SQLGeneratorAgent()
        
        checks = []
        
        # 检查name
        if agent.name == "sql_generator_agent":
            checks.append("name正确")
        else:
            print(f"  ⚠️  name不正确: {agent.name}")
        
        # 检查llm
        if agent.llm is not None:
            checks.append("llm已初始化")
        else:
            print(f"  ⚠️  llm未初始化")
        
        # 检查tools
        if len(agent.tools) >= 2:
            checks.append(f"tools已配置({len(agent.tools)}个)")
        else:
            print(f"  ⚠️  tools数量不足: {len(agent.tools)}")
        
        # 检查agent
        if agent.agent is not None:
            checks.append("agent已创建")
        else:
            print(f"  ⚠️  agent未创建")
        
        if len(checks) >= 3:
            print(f"  ✅ 通过: 代理初始化正常")
            print(f"  检查项: {checks}")
            return True
        else:
            print(f"  ❌ 失败: 部分初始化失败")
            return False
    except Exception as e:
        print(f"  ❌ 异常: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_prompt_no_validation_mention():
    """测试提示词不提及旧的验证流程"""
    print("\n测试3: 提示词不提及旧验证流程")
    
    agent = SQLGeneratorAgent()
    prompt = agent._create_system_prompt()
    
    # 检查不应该出现的内容
    bad_keywords = [
        "analyze_sql_optimization_need",
        "optimize_sql_query"
    ]
    
    found_bad = []
    for keyword in bad_keywords:
        if keyword in prompt:
            found_bad.append(keyword)
    
    if not found_bad:
        print(f"  ✅ 通过: 提示词不包含旧的优化工具引用")
        return True
    else:
        print(f"  ❌ 失败: 提示词包含旧工具引用: {found_bad}")
        return False


def main():
    print("=" * 60)
    print("SQLGeneratorAgent简单测试")
    print("=" * 60)
    
    tests = [
        test_system_prompt_emphasizes_quality,
        test_agent_initialization,
        test_prompt_no_validation_mention
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"  ❌ 异常: {e}")
            import traceback
            traceback.print_exc()
            results.append(False)
    
    print("\n" + "=" * 60)
    print(f"测试结果: {sum(results)}/{len(results)} 通过")
    print("=" * 60)
    
    if all(results):
        print("✅ 所有测试通过!")
        return 0
    else:
        print("❌ 部分测试失败")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
