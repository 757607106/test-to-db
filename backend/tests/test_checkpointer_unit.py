"""
Checkpointer 单元测试

测试内容：
- Checkpointer 工厂函数
- 配置管理
- 单例模式
- 错误处理
"""
import pytest
import os
from unittest.mock import patch, MagicMock
from app.core.checkpointer import (
    create_checkpointer,
    get_checkpointer,
    reset_checkpointer,
    check_checkpointer_health,
    _mask_password
)


class TestPasswordMasking:
    """测试密码隐藏功能"""
    
    def test_mask_password_standard_uri(self):
        """测试标准 URI 格式"""
        uri = "postgresql://user:secret123@localhost:5432/db"
        masked = _mask_password(uri)
        assert "secret123" not in masked
        assert "user" in masked
        assert "localhost" in masked
        assert "****" in masked
    
    def test_mask_password_no_password(self):
        """测试没有密码的 URI"""
        uri = "postgresql://user@localhost:5432/db"
        masked = _mask_password(uri)
        assert masked == uri or "****" in masked
    
    def test_mask_password_invalid_uri(self):
        """测试无效 URI"""
        uri = "invalid-uri"
        masked = _mask_password(uri)
        assert masked == uri or masked == "****"


class TestCheckpointerCreation:
    """测试 Checkpointer 创建"""
    
    def test_create_checkpointer_disabled(self):
        """测试禁用模式"""
        with patch.dict(os.environ, {"CHECKPOINT_MODE": "none"}):
            # 重新加载配置
            from app.core.config import Settings
            settings = Settings()
            
            with patch("app.core.checkpointer.settings", settings):
                checkpointer = create_checkpointer()
                assert checkpointer is None
    
    def test_create_checkpointer_unsupported_mode(self):
        """测试不支持的模式"""
        with patch.dict(os.environ, {"CHECKPOINT_MODE": "unsupported"}):
            from app.core.config import Settings
            settings = Settings()
            
            with patch("app.core.checkpointer.settings", settings):
                checkpointer = create_checkpointer()
                assert checkpointer is None
    
    def test_create_checkpointer_postgres_no_uri(self):
        """测试 PostgreSQL 模式但未配置 URI"""
        with patch.dict(os.environ, {
            "CHECKPOINT_MODE": "postgres",
            "CHECKPOINT_POSTGRES_URI": ""
        }):
            from app.core.config import Settings
            settings = Settings()
            
            with patch("app.core.checkpointer.settings", settings):
                with pytest.raises(ValueError, match="PostgreSQL URI 是必需的"):
                    create_checkpointer()
    
    @patch("app.core.checkpointer.PostgresSaver")
    def test_create_checkpointer_postgres_success(self, mock_postgres_saver):
        """测试成功创建 PostgreSQL Checkpointer"""
        # Mock PostgresSaver
        mock_instance = MagicMock()
        mock_postgres_saver.from_conn_string.return_value = mock_instance
        
        with patch.dict(os.environ, {
            "CHECKPOINT_MODE": "postgres",
            "CHECKPOINT_POSTGRES_URI": "postgresql://user:pass@localhost:5432/db"
        }):
            from app.core.config import Settings
            settings = Settings()
            
            with patch("app.core.checkpointer.settings", settings):
                checkpointer = create_checkpointer()
                
                assert checkpointer is not None
                mock_postgres_saver.from_conn_string.assert_called_once()
                mock_instance.setup.assert_called_once()


class TestSingletonPattern:
    """测试单例模式"""
    
    def test_get_checkpointer_singleton(self):
        """测试单例模式"""
        # 重置
        reset_checkpointer()
        
        with patch("app.core.checkpointer.create_checkpointer") as mock_create:
            mock_create.return_value = MagicMock()
            
            # 第一次调用
            checkpointer1 = get_checkpointer()
            # 第二次调用
            checkpointer2 = get_checkpointer()
            
            # 应该是同一个实例
            assert checkpointer1 is checkpointer2
            # create_checkpointer 只应该被调用一次
            assert mock_create.call_count == 1
    
    def test_reset_checkpointer(self):
        """测试重置功能"""
        with patch("app.core.checkpointer.create_checkpointer") as mock_create:
            mock_create.return_value = MagicMock()
            
            # 获取实例
            checkpointer1 = get_checkpointer()
            
            # 重置
            reset_checkpointer()
            
            # 再次获取
            checkpointer2 = get_checkpointer()
            
            # 应该是不同的实例
            assert checkpointer1 is not checkpointer2
            # create_checkpointer 应该被调用两次
            assert mock_create.call_count == 2


class TestHealthCheck:
    """测试健康检查"""
    
    def test_health_check_disabled(self):
        """测试禁用时的健康检查"""
        reset_checkpointer()
        
        with patch("app.core.checkpointer.create_checkpointer") as mock_create:
            mock_create.return_value = None
            
            is_healthy = check_checkpointer_health()
            assert is_healthy is False
    
    def test_health_check_enabled(self):
        """测试启用时的健康检查"""
        reset_checkpointer()
        
        with patch("app.core.checkpointer.create_checkpointer") as mock_create:
            mock_create.return_value = MagicMock()
            
            is_healthy = check_checkpointer_health()
            assert is_healthy is True
    
    def test_health_check_exception(self):
        """测试健康检查异常"""
        reset_checkpointer()
        
        with patch("app.core.checkpointer.create_checkpointer") as mock_create:
            mock_create.side_effect = Exception("Connection failed")
            
            is_healthy = check_checkpointer_health()
            assert is_healthy is False


class TestConfiguration:
    """测试配置"""
    
    def test_default_configuration(self):
        """测试默认配置"""
        from app.core.config import Settings
        settings = Settings()
        
        assert settings.CHECKPOINT_MODE == "postgres"
        assert settings.MAX_MESSAGE_HISTORY == 20
        assert settings.ENABLE_MESSAGE_SUMMARY is False
        assert settings.SUMMARY_THRESHOLD == 10
    
    def test_environment_override(self):
        """测试环境变量覆盖"""
        with patch.dict(os.environ, {
            "CHECKPOINT_MODE": "none",
            "MAX_MESSAGE_HISTORY": "50",
            "ENABLE_MESSAGE_SUMMARY": "true",
            "SUMMARY_THRESHOLD": "20"
        }):
            from app.core.config import Settings
            settings = Settings()
            
            assert settings.CHECKPOINT_MODE == "none"
            assert settings.MAX_MESSAGE_HISTORY == 50
            assert settings.ENABLE_MESSAGE_SUMMARY is True
            assert settings.SUMMARY_THRESHOLD == 20


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
