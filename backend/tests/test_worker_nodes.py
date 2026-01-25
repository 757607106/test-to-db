"""
Worker 节点单元测试

测试 worker_nodes.py 中的统一节点和 streaming_node 装饰器。

测试覆盖:
1. streaming_node 装饰器 - 流式事件发送、错误处理
2. 节点基础函数 - extract_user_query, get_custom_agent
3. Worker 节点 - 各节点的基本逻辑

运行方式:
    pytest tests/test_worker_nodes.py -v
"""
import asyncio
import pytest
import sys
import time
from pathlib import Path
from typing import Dict, Any
from unittest.mock import AsyncMock, MagicMock, patch

# 配置 pytest-asyncio
pytest_plugins = ('pytest_asyncio',)

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from langchain_core.messages import HumanMessage, AIMessage

from app.core.state import SQLMessageState
from app.agents.utils.node_wrapper import streaming_node, safe_node
from app.agents.nodes.base import (
    extract_user_query,
    extract_last_human_message,
    get_custom_agent,
    build_error_record,
)


# ============================================================================
# streaming_node 装饰器测试
# ============================================================================

class TestStreamingNodeDecorator:
    """streaming_node 装饰器测试"""
    
    @pytest.mark.asyncio
    async def test_streaming_node_sends_running_event(self):
        """测试装饰器发送 running 事件"""
        events = []
        
        @streaming_node(step_name="test_step")
        async def test_node(state: Dict, writer=None):
            return {"current_stage": "done"}
        
        def mock_writer(event):
            events.append(event)
        
        state = {"messages": []}
        await test_node(state, mock_writer)
        
        # 验证发送了 running 事件
        running_events = [e for e in events if e.get("status") == "running"]
        assert len(running_events) == 1
        assert running_events[0]["step"] == "test_step"
    
    @pytest.mark.asyncio
    async def test_streaming_node_sends_completed_event(self):
        """测试装饰器发送 completed 事件"""
        events = []
        
        @streaming_node(step_name="test_step")
        async def test_node(state: Dict, writer=None):
            return {"current_stage": "done"}
        
        def mock_writer(event):
            events.append(event)
        
        state = {"messages": []}
        await test_node(state, mock_writer)
        
        # 验证发送了 completed 事件
        completed_events = [e for e in events if e.get("status") == "completed"]
        assert len(completed_events) == 1
        assert completed_events[0]["step"] == "test_step"
        assert "time_ms" in completed_events[0]
    
    @pytest.mark.asyncio
    async def test_streaming_node_handles_exception(self):
        """测试装饰器处理异常"""
        events = []
        
        @streaming_node(step_name="failing_step", fallback_stage="error_recovery")
        async def failing_node(state: Dict, writer=None):
            raise ValueError("测试错误")
        
        def mock_writer(event):
            events.append(event)
        
        state = {"messages": [], "error_history": []}
        result = await failing_node(state, mock_writer)
        
        # 验证返回错误状态
        assert result["current_stage"] == "error_recovery"
        assert len(result["error_history"]) == 1
        assert "测试错误" in result["error_history"][0]["error"]
        
        # 验证发送了 error 事件
        error_events = [e for e in events if e.get("status") == "error"]
        assert len(error_events) == 1
    
    @pytest.mark.asyncio
    async def test_streaming_node_works_without_writer(self):
        """测试装饰器在无 writer 时正常工作"""
        @streaming_node(step_name="test_step")
        async def test_node(state: Dict, writer=None):
            return {"current_stage": "done", "value": 42}
        
        state = {"messages": []}
        result = await test_node(state)  # 不传 writer
        
        assert result["current_stage"] == "done"
        assert result["value"] == 42
    
    @pytest.mark.asyncio
    async def test_streaming_node_time_tracking(self):
        """测试装饰器时间跟踪"""
        events = []
        
        @streaming_node(step_name="slow_step")
        async def slow_node(state: Dict, writer=None):
            await asyncio.sleep(0.1)  # 100ms
            return {"current_stage": "done"}
        
        def mock_writer(event):
            events.append(event)
        
        state = {"messages": []}
        await slow_node(state, mock_writer)
        
        # 验证 time_ms 大于 100
        completed_events = [e for e in events if e.get("status") == "completed"]
        assert len(completed_events) == 1
        assert completed_events[0]["time_ms"] >= 100


# ============================================================================
# 节点基础函数测试
# ============================================================================

class TestNodeBaseUtils:
    """节点基础工具函数测试"""
    
    def test_extract_user_query_from_human_message(self):
        """测试从 HumanMessage 提取查询"""
        messages = [
            AIMessage(content="你好"),
            HumanMessage(content="查询产品数量"),
        ]
        query = extract_user_query(messages)
        assert query == "查询产品数量"
    
    def test_extract_user_query_from_dict(self):
        """测试从字典消息提取查询"""
        messages = [
            {"type": "ai", "content": "你好"},
            {"type": "human", "content": "统计销售额"},
        ]
        query = extract_user_query(messages)
        assert query == "统计销售额"
    
    def test_extract_user_query_empty_list(self):
        """测试空列表返回 None"""
        messages = []
        query = extract_user_query(messages)
        assert query is None
    
    def test_extract_user_query_no_human_message(self):
        """测试无用户消息返回 None"""
        messages = [
            AIMessage(content="你好"),
            AIMessage(content="再见"),
        ]
        query = extract_user_query(messages)
        assert query is None
    
    def test_extract_user_query_multimodal_content(self):
        """测试多模态消息内容提取"""
        messages = [
            HumanMessage(content=[
                {"type": "text", "text": "查询产品"},
                {"type": "image", "url": "http://example.com/img.png"}
            ]),
        ]
        query = extract_user_query(messages)
        assert query == "查询产品"
    
    def test_extract_last_human_message(self):
        """测试从状态提取用户消息"""
        state = {
            "messages": [
                HumanMessage(content="第一条"),
                AIMessage(content="回复"),
                HumanMessage(content="第二条"),
            ]
        }
        query = extract_last_human_message(state)
        assert query == "第二条"
    
    def test_get_custom_agent_from_custom_agents(self):
        """测试从 custom_agents 获取自定义 Agent"""
        mock_agent = MagicMock()
        mock_agent.name = "custom"
        default_agent = MagicMock()
        default_agent.name = "default"
        
        state = {
            "custom_agents": {"test_agent": mock_agent}
        }
        
        agent = get_custom_agent(state, "test_agent", default_agent)
        assert agent.name == "custom"
    
    def test_get_custom_agent_returns_default(self):
        """测试无自定义时返回默认 Agent"""
        default_agent = MagicMock()
        default_agent.name = "default"
        
        state = {}
        
        agent = get_custom_agent(state, "test_agent", default_agent)
        assert agent.name == "default"
    
    def test_build_error_record(self):
        """测试构建错误记录"""
        record = build_error_record("sql_execution", "表不存在")
        
        assert record["stage"] == "sql_execution"
        assert record["error"] == "表不存在"
        assert "timestamp" in record
        assert isinstance(record["timestamp"], float)


# ============================================================================
# safe_node 装饰器测试
# ============================================================================

class TestSafeNodeDecorator:
    """safe_node 装饰器测试"""
    
    @pytest.mark.asyncio
    async def test_safe_node_passes_through_success(self):
        """测试 safe_node 成功时正常返回"""
        @safe_node()
        async def test_node(state: Dict):
            return {"current_stage": "done", "value": 123}
        
        result = await test_node({})
        assert result["current_stage"] == "done"
        assert result["value"] == 123
    
    @pytest.mark.asyncio
    async def test_safe_node_catches_exception(self):
        """测试 safe_node 捕获异常"""
        @safe_node(default_stage="error_recovery")
        async def failing_node(state: Dict):
            raise RuntimeError("测试异常")
        
        state = {"error_history": []}
        result = await failing_node(state)
        
        assert result["current_stage"] == "error_recovery"
        assert len(result["error_history"]) == 1
        assert "测试异常" in result["error_history"][0]["error"]


# ============================================================================
# Worker 节点集成测试
# ============================================================================

class TestWorkerNodesIntegration:
    """Worker 节点集成测试"""
    
    @pytest.mark.asyncio
    async def test_schema_agent_node_with_mock(self):
        """测试 schema_agent_node 使用 mock agent"""
        from app.agents.nodes.worker_nodes import schema_agent_node
        
        mock_agent = AsyncMock()
        mock_agent.process = AsyncMock(return_value={
            "schema_info": {"tables": ["products"]},
            "current_stage": "schema_done"
        })
        
        state = {
            "messages": [HumanMessage(content="查询产品")],
            "custom_agents": {"schema_agent": mock_agent}
        }
        
        result = await schema_agent_node(state, None)
        
        assert result["current_stage"] == "schema_done"
        assert "schema_info" in result
        mock_agent.process.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_sql_generator_node_with_mock(self):
        """测试 sql_generator_node 使用 mock agent"""
        from app.agents.nodes.worker_nodes import sql_generator_node
        
        mock_agent = AsyncMock()
        mock_agent.process = AsyncMock(return_value={
            "generated_sql": "SELECT * FROM products",
            "current_stage": "sql_generated"
        })
        
        state = {
            "messages": [HumanMessage(content="查询产品")],
            "schema_info": {"tables": ["products"]},
            "custom_agents": {"sql_generator": mock_agent}
        }
        
        result = await sql_generator_node(state, None)
        
        assert result["current_stage"] == "sql_generated"
        assert result["generated_sql"] == "SELECT * FROM products"
        mock_agent.process.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_general_chat_node(self):
        """测试 general_chat_node 闲聊处理"""
        from app.agents.nodes.worker_nodes import general_chat_node
        
        with patch('app.core.llms.get_default_model') as mock_get_model:
            mock_llm = AsyncMock()
            mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="你好！有什么可以帮助你的？"))
            mock_get_model.return_value = mock_llm
            
            events = []
            def mock_writer(event):
                events.append(event)
            
            state = {
                "messages": [HumanMessage(content="你好")]
            }
            
            result = await general_chat_node(state, mock_writer)
            
            assert result["current_stage"] == "completed"
            assert result["route_decision"] == "general_chat"
            assert len(result["messages"]) == 1


# ============================================================================
# 子图测试
# ============================================================================

class TestSupervisorSubgraph:
    """Supervisor 子图测试"""
    
    def test_subgraph_creation(self):
        """测试子图创建"""
        from app.agents.agents.supervisor_subgraph import create_supervisor_subgraph
        
        graph = create_supervisor_subgraph()
        
        # 验证图已编译
        assert graph is not None
        assert hasattr(graph, 'ainvoke')
    
    def test_subgraph_singleton(self):
        """测试子图单例模式"""
        from app.agents.agents.supervisor_subgraph import get_supervisor_subgraph
        
        graph1 = get_supervisor_subgraph()
        graph2 = get_supervisor_subgraph()
        
        assert graph1 is graph2


# ============================================================================
# 主图测试
# ============================================================================

class TestChatGraph:
    """主图测试"""
    
    def test_hub_spoke_graph_creation(self):
        """测试 Hub-and-Spoke 图创建"""
        from app.agents.chat_graph import create_hub_spoke_graph
        
        graph = create_hub_spoke_graph()
        
        # 验证图已编译
        assert graph is not None
        assert hasattr(graph, 'ainvoke')
    
    def test_intelligent_sql_graph_creation(self):
        """测试 IntelligentSQLGraph 创建"""
        from app.agents.chat_graph import IntelligentSQLGraph
        
        sql_graph = IntelligentSQLGraph()
        
        assert sql_graph.graph is not None
        assert sql_graph._initialized is True


# ============================================================================
# 运行入口
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
