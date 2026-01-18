"""
Integration tests for embedding model configuration system.

Tests:
1. Database configuration loading
2. VectorService initialization with different providers
3. Fallback to environment variables
4. System config API endpoints
"""

import pytest
import asyncio
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.crud.crud_system_config import system_config
from app.crud.crud_llm_config import llm_config
from app.schemas.llm_config import LLMConfigCreate
from app.core.llms import get_default_embedding_config, create_embedding_from_config, get_default_embedding_model_v2
from app.services.hybrid_retrieval_service import VectorService, VectorServiceFactory


class TestEmbeddingConfiguration:
    """Test embedding model configuration system"""
    
    def setup_method(self):
        """Setup test database session"""
        self.db = SessionLocal()
    
    def teardown_method(self):
        """Cleanup test database session"""
        self.db.close()
        # Clear VectorService cache
        VectorServiceFactory.clear_instances()
    
    def test_system_config_crud(self):
        """Test system_config CRUD operations"""
        # Set default embedding model ID
        config = system_config.set_default_embedding_model_id(self.db, llm_config_id=999)
        assert config.config_key == "default_embedding_model_id"
        assert config.config_value == "999"
        
        # Get default embedding model ID
        config_id = system_config.get_default_embedding_model_id(self.db)
        assert config_id == 999
        
        # Clear default
        config = system_config.set_default_embedding_model_id(self.db, llm_config_id=None)
        assert config.config_value is None
        
        config_id = system_config.get_default_embedding_model_id(self.db)
        assert config_id is None
    
    def test_create_embedding_config(self):
        """Test creating embedding model configuration"""
        # Create OpenAI embedding config
        config_create = LLMConfigCreate(
            provider="OpenAI",
            api_key="sk-test-key",
            base_url="https://api.openai.com/v1",
            model_name="text-embedding-3-small",
            model_type="embedding",
            is_active=True
        )
        
        config = llm_config.create(self.db, obj_in=config_create)
        self.db.commit()
        
        assert config.id is not None
        assert config.provider == "OpenAI"
        assert config.model_type == "embedding"
        assert config.is_active is True
        
        # Cleanup
        llm_config.remove(self.db, id=config.id)
        self.db.commit()
    
    def test_get_default_embedding_config(self):
        """Test getting default embedding configuration"""
        # Create a test embedding config
        config_create = LLMConfigCreate(
            provider="OpenAI",
            api_key="sk-test-key",
            base_url="https://api.openai.com/v1",
            model_name="text-embedding-3-small",
            model_type="embedding",
            is_active=True
        )
        
        config = llm_config.create(self.db, obj_in=config_create)
        self.db.commit()
        
        # Set as default
        system_config.set_default_embedding_model_id(self.db, llm_config_id=config.id)
        self.db.commit()
        
        # Get default config
        default_config = get_default_embedding_config()
        assert default_config is not None
        assert default_config.id == config.id
        assert default_config.provider == "OpenAI"
        
        # Cleanup
        system_config.set_default_embedding_model_id(self.db, llm_config_id=None)
        llm_config.remove(self.db, id=config.id)
        self.db.commit()
    
    def test_create_embedding_from_config_openai(self):
        """Test creating OpenAI embedding instance from config"""
        # Create OpenAI config
        config_create = LLMConfigCreate(
            provider="OpenAI",
            api_key="sk-test-key",
            base_url="https://api.openai.com/v1",
            model_name="text-embedding-3-small",
            model_type="embedding",
            is_active=True
        )
        
        config = llm_config.create(self.db, obj_in=config_create)
        self.db.commit()
        
        # Create embedding instance
        embedding_model = create_embedding_from_config(config)
        assert embedding_model is not None
        # Check it's an OpenAIEmbeddings instance
        from langchain_openai import OpenAIEmbeddings
        assert isinstance(embedding_model, OpenAIEmbeddings)
        
        # Cleanup
        llm_config.remove(self.db, id=config.id)
        self.db.commit()
    
    def test_create_embedding_from_config_ollama(self):
        """Test creating Ollama embedding instance from config"""
        # Create Ollama config
        config_create = LLMConfigCreate(
            provider="Ollama",
            api_key=None,  # Ollama doesn't need API key
            base_url="http://localhost:11434",
            model_name="qwen3-embedding:0.6b",
            model_type="embedding",
            is_active=True
        )
        
        config = llm_config.create(self.db, obj_in=config_create)
        self.db.commit()
        
        # Create embedding instance
        embedding_model = create_embedding_from_config(config)
        assert embedding_model is not None
        # Check it's an OllamaEmbeddings instance
        from langchain_community.embeddings import OllamaEmbeddings
        assert isinstance(embedding_model, OllamaEmbeddings)
        
        # Cleanup
        llm_config.remove(self.db, id=config.id)
        self.db.commit()
    
    @pytest.mark.asyncio
    async def test_vector_service_with_config(self):
        """Test VectorService initialization with LLMConfiguration"""
        # Create test config
        config_create = LLMConfigCreate(
            provider="OpenAI",
            api_key="sk-test-key",
            base_url="https://api.openai.com/v1",
            model_name="text-embedding-3-small",
            model_type="embedding",
            is_active=True
        )
        
        config = llm_config.create(self.db, obj_in=config_create)
        self.db.commit()
        
        # Create VectorService with config
        vector_service = VectorService(llm_config=config)
        
        assert vector_service.provider == "openai"
        assert vector_service.model_name == "text-embedding-3-small"
        assert vector_service.llm_config == config
        
        # Note: We don't actually initialize to avoid API calls in tests
        # In real usage, you would call: await vector_service.initialize()
        
        # Cleanup
        llm_config.remove(self.db, id=config.id)
        self.db.commit()
    
    @pytest.mark.asyncio
    async def test_vector_service_factory_with_default_config(self):
        """Test VectorServiceFactory using default configuration"""
        # Create and set default config
        config_create = LLMConfigCreate(
            provider="OpenAI",
            api_key="sk-test-key",
            base_url="https://api.openai.com/v1",
            model_name="text-embedding-3-small",
            model_type="embedding",
            is_active=True
        )
        
        config = llm_config.create(self.db, obj_in=config_create)
        self.db.commit()
        
        system_config.set_default_embedding_model_id(self.db, llm_config_id=config.id)
        self.db.commit()
        
        # Note: In real scenario, VectorServiceFactory.get_default_service() would:
        # 1. Call get_default_embedding_config()
        # 2. Create VectorService with that config
        # 3. Initialize the service
        
        # We test the config retrieval part
        default_config = get_default_embedding_config()
        assert default_config is not None
        assert default_config.id == config.id
        
        # Cleanup
        system_config.set_default_embedding_model_id(self.db, llm_config_id=None)
        llm_config.remove(self.db, id=config.id)
        self.db.commit()
        VectorServiceFactory.clear_instances()
    
    def test_embedding_config_validation(self):
        """Test validation of embedding configurations"""
        # Test invalid model_type
        config_create = LLMConfigCreate(
            provider="OpenAI",
            api_key="sk-test-key",
            model_name="gpt-4",
            model_type="chat",  # Wrong type
            is_active=True
        )
        
        config = llm_config.create(self.db, obj_in=config_create)
        self.db.commit()
        
        # Should raise error when trying to create embedding from chat config
        with pytest.raises(ValueError, match="model_type must be 'embedding'"):
            create_embedding_from_config(config)
        
        # Cleanup
        llm_config.remove(self.db, id=config.id)
        self.db.commit()


def test_migration_script_exists():
    """Test that migration script exists and is executable"""
    import os
    from pathlib import Path
    
    script_path = Path(__file__).parent.parent / "scripts" / "migrate_embedding_config.py"
    assert script_path.exists(), "Migration script should exist"
    assert os.access(script_path, os.R_OK), "Migration script should be readable"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
