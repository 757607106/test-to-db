"""
Supervisor 全场景集成测试 - 深度 Mock 版
"""
import pytest
import logging
import json
from unittest.mock import patch, MagicMock, AsyncMock

# 必须在导入 agent 之前 mock
with patch("app.core.agent_config.get_agent_llm") as mock_get_llm:
    pass

from app.agents.chat_graph import create_intelligent_sql_graph
from langgraph.errors import GraphInterrupt
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import AIMessage, HumanMessage

logger = logging.getLogger(__name__)
TEST_CONNECTION_ID = 15

@pytest.fixture
def mock_checkpointer():
    return MemorySaver()

@pytest.fixture
def mock_deep_env():
    """全面 Mock 所有 LLM 和 Agent 相关的入口"""
    # LLM Mock - 使用 MagicMock 模拟模型对象，但 ainvoke 是异步的
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock()
    mock_llm.bind_tools = MagicMock(return_value=mock_llm) # 重要：支持 bind_tools
    
    # Mock 意图识别结果
    mock_intent = MagicMock()
    mock_intent.query_type.value = "data_query"
    mock_intent.route = "sql_supervisor"
    mock_intent.complexity = "simple"
    mock_intent.needs_clarification = False
    mock_intent.sub_queries = []
    
    # Mock Skill 路由结果
    mock_skill = MagicMock()
    mock_skill.enabled = False
    mock_skill.matched_skills = []
    mock_skill.schema_info = {"tables": [], "columns": []}
    mock_skill.business_rules = []
    mock_skill.join_rules = []
    mock_skill.primary_skill_name = None
    mock_skill.reasoning = "Mocked skill routing"
    mock_skill.strategy_used = "full_schema"

    patches = [
        patch("app.agents.agents.supervisor_agent.get_agent_llm", return_value=mock_llm),
        patch("app.agents.agents.schema_agent.get_agent_llm", return_value=mock_llm),
        patch("app.agents.agents.clarification_agent.get_agent_llm", return_value=mock_llm),
        patch("app.agents.agents.sql_generator_agent.get_agent_llm", return_value=mock_llm),
        patch("app.core.agent_config.get_agent_llm", return_value=mock_llm),
        patch("app.core.llms.get_default_model", return_value=mock_llm),
        patch("app.core.llms.create_chat_model", return_value=mock_llm),
    ]
    
    agent_patches = [
        patch("app.agents.agents.schema_agent.schema_agent.agent", new_callable=AsyncMock),
        patch("app.agents.agents.clarification_agent.clarification_agent.agent", new_callable=AsyncMock),
        patch("app.agents.agents.sql_generator_agent.sql_generator_agent.agent", new_callable=AsyncMock),
        patch("app.agents.agents.sql_executor_agent.sql_executor_agent.agent", new_callable=AsyncMock),
        patch("app.agents.agents.error_recovery_agent.error_recovery_agent.agent", new_callable=AsyncMock),
        patch("app.agents.agents.data_analyst_agent.data_analyst_agent.agent", new_callable=AsyncMock),
        patch("app.agents.agents.sql_validator_agent.sql_validator_agent.agent", new_callable=AsyncMock),
    ]
    
    service_patches = [
        patch("app.services.text2sql_utils.retrieve_relevant_schema", return_value={"tables":[]}),
        patch("app.agents.chat_graph.perform_skill_routing", return_value=mock_skill),
        patch("app.agents.chat_graph.detect_intent", return_value=mock_intent),
        patch("app.agents.chat_graph.get_qa_sample_config", return_value={"enabled": False}),
        patch("app.agents.chat_graph.format_skill_context_for_prompt", return_value=""),
        patch("app.agents.chat_graph.detect_intent_fast", return_value=mock_intent),
        patch("app.db.session.SessionLocal"),
    ]
    
    # 开始所有 patch 并收集 mock 对象
    agent_mocks = []
    for p in agent_patches:
        agent_mocks.append(p.start())
        
    for p in patches + service_patches:
        p.start()
    
    m_schema = agent_mocks[0]
    m_clarif = agent_mocks[1]
    m_gen = agent_mocks[2]
    m_exec = agent_mocks[3]
    m_err = agent_mocks[4]
    m_ana = agent_mocks[5]
    m_val = agent_mocks[6]
    
    for m, n in zip(agent_mocks, 
                    ["schema_agent", "clarification_agent", "sql_generator_agent", "sql_executor_agent", "error_recovery_agent", "data_analyst_agent", "sql_validator_agent"]):
        m.name = n

    yield {
        "llm": mock_llm,
        "agents": {
            "schema": m_schema,
            "clarification": m_clarif,
            "generator": m_gen,
            "executor": m_exec,
            "error": m_err,
            "analyst": m_ana,
            "validator": m_val
        }
    }
    
    # 停止所有 patch
    for p in patches + agent_patches + service_patches:
        try:
            p.stop()
        except:
            pass

@pytest.mark.asyncio
class TestSupervisorFullScenarios:

    async def test_scenario_1_standard_flow(self, mock_checkpointer, mock_deep_env):
        """场景1: 标准流程"""
        query = "查询销售订单"
        thread_id = "test_s1"
        mock_llm = mock_deep_env["llm"]
        agents = mock_deep_env["agents"]
        
        mock_llm.ainvoke.side_effect = [
            AIMessage(content="", tool_calls=[{"name": "transfer_to_schema_agent", "args": {"query": query}, "id": "c1", "type": "tool_call"}], name="supervisor"),
            AIMessage(content="", tool_calls=[{"name": "transfer_to_sql_generator_agent", "args": {"query": query}, "id": "c2", "type": "tool_call"}], name="supervisor"),
            AIMessage(content="完成", name="supervisor"),
        ]
        
        agents["schema"].ainvoke.return_value = {"messages": [AIMessage(content="Found schema", name="schema_agent")]}
        agents["generator"].ainvoke.return_value = {"messages": [AIMessage(content="Generated SQL", name="sql_generator_agent")]}
        
        with patch("app.core.checkpointer.get_checkpointer", return_value=mock_checkpointer):
            graph = create_intelligent_sql_graph(enable_clarification=True)
            result = await graph.process_query(query, connection_id=TEST_CONNECTION_ID, thread_id=thread_id)
            
            assert result["success"] is True
            names = [m.name for m in result["result"]["messages"] if hasattr(m, 'name') and m.name]
            assert "sql_generator_agent" in names
            logger.info("✓ 场景1通过")

    async def test_scenario_2_vague_time_clarification(self, mock_checkpointer, mock_deep_env):
        """场景2: 模糊时间澄清"""
        query = "最近的订单"
        thread_id = "test_s2"
        mock_llm = mock_deep_env["llm"]
        agents = mock_deep_env["agents"]
        
        mock_llm.ainvoke.side_effect = [
            AIMessage(content="", tool_calls=[{"name": "transfer_to_schema_agent", "args": {"query": query}, "id": "c1", "type": "tool_call"}], name="supervisor"),
            AIMessage(content="", tool_calls=[{"name": "transfer_to_clarification_agent", "args": {"query": query}, "id": "c2", "type": "tool_call"}], name="supervisor"),
        ]
        
        agents["schema"].ainvoke.return_value = {"messages": [AIMessage(content="Found schema", name="schema_agent")]}
        agents["clarification"].ainvoke.side_effect = GraphInterrupt([{"value": "clarify"}])
        
        with patch("app.core.checkpointer.get_checkpointer", return_value=mock_checkpointer):
            graph = create_intelligent_sql_graph(enable_clarification=True)
            try:
                await graph.process_query(query, connection_id=TEST_CONNECTION_ID, thread_id=thread_id)
                pytest.fail("应该中断")
            except GraphInterrupt:
                logger.info("✓ 场景2通过")

    async def test_scenario_3_error_recovery(self, mock_checkpointer, mock_deep_env):
        """场景3: 错误恢复"""
        query = "坏查询"
        thread_id = "test_s3"
        mock_llm = mock_deep_env["llm"]
        agents = mock_deep_env["agents"]
        
        mock_llm.ainvoke.side_effect = [
            AIMessage(content="", tool_calls=[{"name": "transfer_to_schema_agent", "args": {"query": query}, "id": "c1", "type": "tool_call"}], name="supervisor"),
            AIMessage(content="", tool_calls=[{"name": "transfer_to_sql_generator_agent", "args": {"query": query}, "id": "c2", "type": "tool_call"}], name="supervisor"),
            AIMessage(content="", tool_calls=[{"name": "transfer_to_error_recovery_agent", "args": {"error": "..."}, "id": "c3", "type": "tool_call"}], name="supervisor"),
            AIMessage(content="结束", name="supervisor"),
        ]
        
        agents["schema"].ainvoke.return_value = {"messages": [AIMessage(content="Found schema", name="schema_agent")]}
        agents["generator"].ainvoke.return_value = {"messages": [AIMessage(content="Generated SQL", name="sql_generator_agent")]}
        agents["error"].ainvoke.return_value = {"messages": [AIMessage(content="Fixed", name="error_recovery_agent")]}
        
        with patch("app.core.checkpointer.get_checkpointer", return_value=mock_checkpointer):
            graph = create_intelligent_sql_graph(enable_clarification=True)
            result = await graph.process_query(query, connection_id=TEST_CONNECTION_ID, thread_id=thread_id)
            
            assert result["success"] is True
            names = [m.name for m in result["result"]["messages"] if hasattr(m, 'name') and m.name]
            assert "error_recovery_agent" in names
            logger.info("✓ 场景3通过")

    async def test_scenario_4_prohibit_auto_decision(self, mock_checkpointer, mock_deep_env):
        """场景4: 禁止自动决策"""
        query = "优质客户"
        thread_id = "test_s4"
        mock_llm = mock_deep_env["llm"]
        agents = mock_deep_env["agents"]
        
        mock_llm.ainvoke.side_effect = [
            AIMessage(content="", tool_calls=[{"name": "transfer_to_schema_agent", "args": {"query": query}, "id": "c1", "type": "tool_call"}], name="supervisor"),
            AIMessage(content="", tool_calls=[{"name": "transfer_to_clarification_agent", "args": {"query": query}, "id": "c2", "type": "tool_call"}], name="supervisor"),
        ]
        
        agents["schema"].ainvoke.return_value = {"messages": [AIMessage(content="Found schema", name="schema_agent")]}
        agents["clarification"].ainvoke.side_effect = GraphInterrupt([{"value": "clarify"}])
        
        with patch("app.core.checkpointer.get_checkpointer", return_value=mock_checkpointer):
            graph = create_intelligent_sql_graph(enable_clarification=True)
            try:
                await graph.process_query(query, connection_id=TEST_CONNECTION_ID, thread_id=thread_id)
                pytest.fail("应该中断")
            except GraphInterrupt:
                logger.info("✓ 场景4通过")
