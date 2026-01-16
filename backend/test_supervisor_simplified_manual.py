"""
SupervisorAgent手动测试 - 简化流程验证
不依赖pytest，直接运行验证
"""
from app.agents.agents.supervisor_agent import SupervisorAgent, create_intelligent_sql_supervisor


def test_worker_agents_count():
    """测试工作代理数量为5"""
    print("\n测试1: 工作代理数量")
    supervisor = SupervisorAgent()
    count = len(supervisor.worker_agents)
    expected = 5
    
    if count == expected:
        print(f"  ✅ 通过: 工作代理数量为{count}")
        return True
    else:
        print(f"  ❌ 失败: 期望{expected}个，实际{count}个")
        return False


def test_no_validator_agent():
    """测试不包含SQL Validator Agent"""
    print("\n测试2: 不包含SQL Validator")
    supervisor = SupervisorAgent()
    
    # 检查代理名称
    agent_names = []
    for agent in supervisor.worker_agents:
        if hasattr(agent, 'name'):
            agent_names.append(agent.name)
        elif hasattr(agent, '__class__'):
            agent_names.append(agent.__class__.__name__)
    
    # 验证不包含validator
    has_validator = any("validator" in name.lower() for name in agent_names)
    
    if not has_validator:
        print(f"  ✅ 通过: 不包含validator代理")
        print(f"  代理列表: {agent_names}")
        return True
    else:
        print(f"  ❌ 失败: 发现validator代理")
        print(f"  代理列表: {agent_names}")
        return False


def test_system_prompt_no_validation():
    """测试系统提示词不包含验证相关内容"""
    print("\n测试3: 系统提示词不包含验证")
    supervisor = SupervisorAgent()
    prompt = supervisor._get_supervisor_prompt()
    
    prompt_lower = prompt.lower()
    
    issues = []
    if "validator" in prompt_lower:
        issues.append("包含'validator'")
    if "validation" in prompt_lower:
        issues.append("包含'validation'")
    if "验证sql" in prompt:
        issues.append("包含'验证SQL'")
    if "sql_validator_agent" in prompt:
        issues.append("包含'sql_validator_agent'")
    
    if not issues:
        print(f"  ✅ 通过: 系统提示词不包含验证相关内容")
        return True
    else:
        print(f"  ❌ 失败: {', '.join(issues)}")
        return False


def test_system_prompt_has_simplified_flow():
    """测试系统提示词包含简化后的流程"""
    print("\n测试4: 系统提示词包含简化流程")
    supervisor = SupervisorAgent()
    prompt = supervisor._get_supervisor_prompt()
    
    required_agents = [
        "schema_agent",
        "sql_generator_agent",
        "sql_executor_agent",
        "chart_generator_agent",
        "error_recovery_agent"
    ]
    
    missing = []
    for agent in required_agents:
        if agent not in prompt:
            missing.append(agent)
    
    # 检查流程描述
    has_correct_flow = "sql_generator_agent → sql_executor_agent" in prompt
    
    if not missing and has_correct_flow:
        print(f"  ✅ 通过: 包含所有必需代理和正确流程")
        return True
    else:
        if missing:
            print(f"  ❌ 失败: 缺少代理 {missing}")
        if not has_correct_flow:
            print(f"  ❌ 失败: 流程描述不正确")
        return False


def test_create_intelligent_sql_supervisor():
    """测试便捷函数"""
    print("\n测试5: 便捷函数创建supervisor")
    supervisor = create_intelligent_sql_supervisor()
    
    if isinstance(supervisor, SupervisorAgent) and len(supervisor.worker_agents) == 5:
        print(f"  ✅ 通过: 便捷函数正常工作")
        return True
    else:
        print(f"  ❌ 失败: 便捷函数创建失败")
        return False


def main():
    print("=" * 60)
    print("SupervisorAgent简化流程测试")
    print("=" * 60)
    
    tests = [
        test_worker_agents_count,
        test_no_validator_agent,
        test_system_prompt_no_validation,
        test_system_prompt_has_simplified_flow,
        test_create_intelligent_sql_supervisor
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
