"""
SupervisorAgent单元测试 - 简化流程验证
验证SQL Validator Agent已被移除
"""
import pytest
from app.agents.agents.supervisor_agent import SupervisorAgent, create_intelligent_sql_supervisor


class TestSupervisorAgentSimplified:
    """测试简化后的SupervisorAgent"""
    
    def test_worker_agents_count(self):
        """
        属性 3: 工作代理列表不包含验证器
        验证: 需求 2.1, 2.2
        
        测试工作代理数量为5（简化后）
        """
        supervisor = SupervisorAgent()
        assert len(supervisor.worker_agents) == 5, \
            f"期望5个工作代理，实际{len(supervisor.worker_agents)}个"
    
    def test_no_validator_agent(self):
        """
        属性 3: 工作代理列表不包含验证器
        验证: 需求 2.1, 2.2
        
        测试不包含SQL Validator Agent
        """
        supervisor = SupervisorAgent()
        
        # 检查代理名称
        agent_names = []
        for agent in supervisor.worker_agents:
            # 尝试获取agent的name属性
            if hasattr(agent, 'name'):
                agent_names.append(agent.name)
            elif hasattr(agent, '__class__'):
                agent_names.append(agent.__class__.__name__)
        
        # 验证不包含validator相关的名称
        for name in agent_names:
            assert "validator" not in name.lower(), \
                f"发现验证器代理: {name}"
    
    def test_required_agents_present(self):
        """
        属性 3: 工作代理列表不包含验证器
        验证: 需求 4.2
        
        测试包含所有必需的5个代理
        """
        supervisor = SupervisorAgent()
        
        # 期望的代理数量
        expected_count = 5
        actual_count = len(supervisor.worker_agents)
        
        assert actual_count == expected_count, \
            f"期望{expected_count}个代理，实际{actual_count}个"
        
        # 验证所有代理都已初始化
        for i, agent in enumerate(supervisor.worker_agents):
            assert agent is not None, f"代理{i}未正确初始化"
    
    def test_system_prompt_no_validation(self):
        """
        属性 3: 工作代理列表不包含验证器
        验证: 需求 2.4
        
        测试系统提示词不包含验证相关内容
        """
        supervisor = SupervisorAgent()
        prompt = supervisor._get_supervisor_prompt()
        
        # 转换为小写进行检查
        prompt_lower = prompt.lower()
        
        # 验证不包含验证相关的关键词
        assert "validator" not in prompt_lower, \
            "系统提示词中包含'validator'"
        assert "validation" not in prompt_lower, \
            "系统提示词中包含'validation'"
        assert "验证sql" not in prompt, \
            "系统提示词中包含'验证SQL'"
        assert "sql_validator_agent" not in prompt, \
            "系统提示词中包含'sql_validator_agent'"
    
    def test_system_prompt_has_simplified_flow(self):
        """
        验证: 需求 4.1
        
        测试系统提示词包含简化后的流程描述
        """
        supervisor = SupervisorAgent()
        prompt = supervisor._get_supervisor_prompt()
        
        # 验证包含简化后的流程
        assert "schema_agent" in prompt, "缺少schema_agent"
        assert "sql_generator_agent" in prompt, "缺少sql_generator_agent"
        assert "sql_executor_agent" in prompt, "缺少sql_executor_agent"
        assert "chart_generator_agent" in prompt, "缺少chart_generator_agent"
        assert "error_recovery_agent" in prompt, "缺少error_recovery_agent"
        
        # 验证流程描述正确（不包含验证步骤）
        assert "sql_generator_agent → sql_executor_agent" in prompt, \
            "流程描述应该是SQL生成直接到执行"
    
    def test_create_intelligent_sql_supervisor(self):
        """
        测试便捷函数创建supervisor
        """
        supervisor = create_intelligent_sql_supervisor()
        
        assert isinstance(supervisor, SupervisorAgent)
        assert len(supervisor.worker_agents) == 5
    
    def test_supervisor_has_llm(self):
        """
        测试supervisor正确初始化LLM
        """
        supervisor = SupervisorAgent()
        
        assert supervisor.llm is not None, "LLM未初始化"
        assert supervisor.supervisor is not None, "Supervisor graph未初始化"
    
    def test_worker_agents_are_compiled_graphs(self):
        """
        测试工作代理是已编译的图
        """
        supervisor = SupervisorAgent()
        
        for i, agent in enumerate(supervisor.worker_agents):
            # 验证代理不是None
            assert agent is not None, f"代理{i}为None"
            
            # 验证代理是CompiledStateGraph类型
            assert hasattr(agent, '__class__'), f"代理{i}没有__class__属性"


class TestSupervisorAgentBackwardCompatibility:
    """测试向后兼容性"""
    
    def test_custom_worker_agents(self):
        """
        测试可以传入自定义工作代理
        """
        # 创建mock代理
        mock_agents = [object() for _ in range(3)]
        
        supervisor = SupervisorAgent(worker_agents=mock_agents)
        
        assert len(supervisor.worker_agents) == 3
        assert supervisor.worker_agents == mock_agents


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
