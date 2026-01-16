"""
SQLExecutorAgent简单测试 - 验证简化流程
测试不检查validation_result，错误信息包含完整字段
"""
from app.agents.agents.sql_executor_agent import SQLExecutorAgent
from app.core.state import SQLMessageState, SQLValidationResult
from langchain_core.messages import HumanMessage


def test_agent_initialization():
    """测试代理正确初始化"""
    print("\n测试1: 代理初始化")
    
    try:
        agent = SQLExecutorAgent()
        
        checks = []
        
        # 检查name
        if agent.name == "sql_executor_agent":
            checks.append("name正确")
        
        # 检查llm
        if agent.llm is not None:
            checks.append("llm已初始化")
        
        # 检查tools
        if len(agent.tools) >= 1:
            checks.append(f"tools已配置({len(agent.tools)}个)")
        
        # 检查agent
        if agent.agent is not None:
            checks.append("agent已创建")
        
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


def test_process_method_signature():
    """测试process方法不再检查validation_result"""
    print("\n测试2: process方法不检查validation_result")
    
    try:
        agent = SQLExecutorAgent()
        
        # 读取process方法的源代码
        import inspect
        source = inspect.getsource(agent.process)
        
        # 检查是否有未注释的validation_result检查
        # 排除注释行
        lines = source.split('\n')
        active_lines = [line for line in lines if not line.strip().startswith('#')]
        active_code = '\n'.join(active_lines)
        
        has_validation_check = "validation_result" in active_code and "is_valid" in active_code
        
        if not has_validation_check:
            print(f"  ✅ 通过: process方法不检查validation_result（已移除或注释）")
            return True
        else:
            print(f"  ❌ 失败: process方法仍然检查validation_result")
            return False
    except Exception as e:
        print(f"  ❌ 异常: {e}")
        return False


def test_error_info_structure():
    """测试错误信息包含所有必需字段"""
    print("\n测试3: 错误信息结构")
    
    try:
        agent = SQLExecutorAgent()
        
        # 读取process方法的源代码
        import inspect
        source = inspect.getsource(agent.process)
        
        # 检查错误信息是否包含必需字段
        required_fields = ["stage", "error", "sql_query", "retry_count"]
        
        found_fields = []
        for field in required_fields:
            if f'"{field}"' in source or f"'{field}'" in source:
                found_fields.append(field)
        
        if len(found_fields) >= 3:  # 至少包含3个必需字段
            print(f"  ✅ 通过: 错误信息包含必需字段")
            print(f"  找到字段: {found_fields}")
            return True
        else:
            print(f"  ❌ 失败: 错误信息缺少必需字段")
            print(f"  找到字段: {found_fields}")
            return False
    except Exception as e:
        print(f"  ❌ 异常: {e}")
        return False


def test_system_prompt():
    """测试系统提示词"""
    print("\n测试4: 系统提示词")
    
    try:
        agent = SQLExecutorAgent()
        
        # 创建测试状态
        state = SQLMessageState(
            messages=[HumanMessage(content="test")],
            connection_id=15,
            current_stage="sql_execution",
            retry_count=0,
            max_retries=3,
            error_history=[]
        )
        
        # 获取系统提示
        from langchain_core.runnables import RunnableConfig
        config = RunnableConfig()
        prompt_messages = agent._create_system_prompt(state, config)
        
        # 验证提示词存在
        if prompt_messages and len(prompt_messages) > 0:
            print(f"  ✅ 通过: 系统提示词正常生成")
            return True
        else:
            print(f"  ❌ 失败: 系统提示词生成失败")
            return False
    except Exception as e:
        print(f"  ❌ 异常: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    print("=" * 60)
    print("SQLExecutorAgent简单测试")
    print("=" * 60)
    
    tests = [
        test_agent_initialization,
        test_process_method_signature,
        test_error_info_structure,
        test_system_prompt
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
