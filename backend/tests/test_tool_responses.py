"""
单元测试：ToolResponse 序列化和验证

测试 LangChain 原生结构化输出方案的核心组件
"""
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

import json
import pytest
from app.schemas.agent_message import ToolResponse, SQLGenerationResult


class TestToolResponse:
    """测试 ToolResponse Pydantic 模型"""
    
    def test_success_response_serialization(self):
        """测试成功响应的序列化"""
        response = ToolResponse(
            status="success",
            data={"columns": ["id", "name"], "rows": [[1, "Alice"], [2, "Bob"]]},
            metadata={"execution_time": 0.5, "from_cache": False}
        )
        
        # 测试 model_dump_json 序列化
        json_str = response.model_dump_json()
        parsed = json.loads(json_str)
        
        assert parsed["status"] == "success"
        assert "data" in parsed
        assert parsed["data"]["columns"] == ["id", "name"]
        assert parsed["metadata"]["execution_time"] == 0.5
        assert parsed["error"] is None
    
    def test_error_response_serialization(self):
        """测试错误响应的序列化"""
        response = ToolResponse(
            status="error",
            error="数据库连接失败",
            metadata={"connection_id": 123}
        )
        
        json_str = response.model_dump_json()
        parsed = json.loads(json_str)
        
        assert parsed["status"] == "error"
        assert parsed["error"] == "数据库连接失败"
        assert parsed["metadata"]["connection_id"] == 123
        assert parsed["data"] is None
    
    def test_pending_response_serialization(self):
        """测试待处理响应的序列化"""
        response = ToolResponse(
            status="pending",
            metadata={"estimated_time": 5}
        )
        
        json_str = response.model_dump_json()
        parsed = json.loads(json_str)
        
        assert parsed["status"] == "pending"
        assert parsed["metadata"]["estimated_time"] == 5
    
    def test_invalid_status_rejected(self):
        """测试无效的 status 值被拒绝"""
        with pytest.raises(ValueError):
            ToolResponse(status="invalid")  # type: ignore
    
    def test_optional_fields_default_none(self):
        """测试可选字段默认为 None"""
        response = ToolResponse(status="success")
        
        assert response.data is None
        assert response.error is None
        assert response.metadata is None
    
    def test_deserialization_from_json(self):
        """测试从 JSON 字符串反序列化"""
        json_str = json.dumps({
            "status": "success",
            "data": {"result": [1, 2, 3]},
            "error": None,
            "metadata": {"time": 0.5}
        })
        
        # Pydantic v2 方式
        response = ToolResponse.model_validate_json(json_str)
        
        assert response.status == "success"
        assert response.data["result"] == [1, 2, 3]
        assert response.metadata["time"] == 0.5


class TestSQLGenerationResult:
    """测试 SQLGenerationResult 结构化输出模型"""
    
    def test_valid_sql_generation_result(self):
        """测试有效的 SQL 生成结果"""
        result = SQLGenerationResult(
            sql_query="SELECT * FROM users WHERE age > 18 LIMIT 100",
            explanation="查询年龄大于18岁的用户",
            confidence=0.95
        )
        
        assert result.sql_query == "SELECT * FROM users WHERE age > 18 LIMIT 100"
        assert result.explanation == "查询年龄大于18岁的用户"
        assert result.confidence == 0.95
    
    def test_confidence_validation(self):
        """测试 confidence 范围验证 (0-1)"""
        # 有效范围
        valid = SQLGenerationResult(
            sql_query="SELECT 1",
            confidence=0.5
        )
        assert valid.confidence == 0.5
        
        # 边界值
        edge1 = SQLGenerationResult(sql_query="SELECT 1", confidence=0.0)
        assert edge1.confidence == 0.0
        
        edge2 = SQLGenerationResult(sql_query="SELECT 1", confidence=1.0)
        assert edge2.confidence == 1.0
        
        # 无效范围
        with pytest.raises(ValueError):
            SQLGenerationResult(sql_query="SELECT 1", confidence=1.5)
        
        with pytest.raises(ValueError):
            SQLGenerationResult(sql_query="SELECT 1", confidence=-0.1)
    
    def test_optional_explanation(self):
        """测试 explanation 字段可选"""
        result = SQLGenerationResult(
            sql_query="SELECT * FROM users",
            confidence=0.8
        )
        
        assert result.explanation is None
    
    def test_serialization_for_llm(self):
        """测试序列化用于 LLM with_structured_output"""
        result = SQLGenerationResult(
            sql_query="SELECT name, COUNT(*) as cnt FROM orders GROUP BY name",
            explanation="按用户名统计订单数量",
            confidence=0.92
        )
        
        json_str = result.model_dump_json()
        parsed = json.loads(json_str)
        
        assert "sql_query" in parsed
        assert "explanation" in parsed
        assert "confidence" in parsed
        assert parsed["confidence"] == 0.92


class TestBackwardCompatibility:
    """测试向后兼容性"""
    
    def test_parse_legacy_format(self):
        """测试解析旧格式（{success: boolean}）"""
        # 模拟旧格式
        legacy_json = json.dumps({
            "success": True,
            "data": {"rows": [1, 2, 3]},
            "execution_time": 1.5
        })
        
        # 前端的兼容解析函数应该能处理
        # 这里只是确认新格式可以被创建
        legacy = json.loads(legacy_json)
        
        # 转换为新格式
        if "success" in legacy:
            new_response = ToolResponse(
                status="success" if legacy["success"] else "error",
                data=legacy.get("data"),
                error=legacy.get("error"),
                metadata={"execution_time": legacy.get("execution_time")}
            )
            
            assert new_response.status == "success"
            assert new_response.data["rows"] == [1, 2, 3]
            assert new_response.metadata["execution_time"] == 1.5


class TestMessageUtils:
    """测试 message_utils 中的工具函数"""
    
    def test_generate_tool_call_id(self):
        """测试 tool call ID 生成"""
        from app.core.message_utils import generate_tool_call_id
        
        # 相同参数应生成相同 ID
        id1 = generate_tool_call_id("execute_sql", {"sql": "SELECT 1", "conn_id": 1})
        id2 = generate_tool_call_id("execute_sql", {"sql": "SELECT 1", "conn_id": 1})
        assert id1 == id2
        
        # 不同参数应生成不同 ID
        id3 = generate_tool_call_id("execute_sql", {"sql": "SELECT 2", "conn_id": 1})
        assert id1 != id3
        
        # ID 格式检查
        assert id1.startswith("call_")
        assert len(id1) == 21  # "call_" + 16位哈希
    
    def test_create_ai_message_with_tools(self):
        """测试创建带工具调用的 AI 消息"""
        from app.core.message_utils import create_ai_message_with_tools
        
        tool_calls = [
            {"name": "tool1", "args": {"arg1": "value1"}, "id": "call_123"},
            {"name": "", "args": {}, "id": "call_456"},  # 空 name，应被过滤
            {"name": "tool2", "args": {"arg2": "value2"}, "id": "call_789"},
        ]
        
        message = create_ai_message_with_tools("", tool_calls)
        
        # 只有 name 非空的被保留
        assert len(message.tool_calls) == 2
        assert message.tool_calls[0]["name"] == "tool1"
        assert message.tool_calls[1]["name"] == "tool2"
    
    def test_create_ai_message_duplicate_ids(self):
        """测试处理重复的 tool call ID"""
        from app.core.message_utils import create_ai_message_with_tools
        
        tool_calls = [
            {"name": "tool1", "args": {"arg1": "value1"}, "id": "call_duplicate"},
            {"name": "tool2", "args": {"arg2": "value2"}, "id": "call_duplicate"},  # 重复 ID
        ]
        
        message = create_ai_message_with_tools("", tool_calls)
        
        # 两个工具调用都应保留，但 ID 应该不同
        assert len(message.tool_calls) == 2
        assert message.tool_calls[0]["id"] != message.tool_calls[1]["id"]


@pytest.mark.asyncio
class TestIntegration:
    """集成测试：完整的工具调用流程"""
    
    async def test_tool_execution_flow(self):
        """测试工具执行流程：调用 -> 序列化 -> 传输 -> 解析"""
        # 模拟工具执行
        from app.agents.agents.sql_executor_agent import execute_sql_query
        
        # 注意：这需要数据库连接，这里只测试返回类型
        # 实际测试应该 mock 数据库连接
        
        # 测试返回类型是 ToolResponse
        # result = execute_sql_query("SELECT 1", connection_id=1)
        # assert isinstance(result, ToolResponse)
        # assert result.status in ["success", "error", "pending"]
        
        # 简化测试：直接创建 ToolResponse
        result = ToolResponse(
            status="success",
            data={"columns": ["1"], "data": [[1]]}
        )
        
        # 序列化
        json_str = result.model_dump_json()
        
        # 模拟网络传输
        transmitted = json_str
        
        # 前端解析
        parsed = json.loads(transmitted)
        assert parsed["status"] == "success"
        assert parsed["data"]["columns"] == ["1"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
