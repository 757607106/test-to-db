"""
Migration script to migrate embedding configuration from environment variables to database.

This script:
1. Checks if there's a default embedding model configured in system_config
2. If not, checks environment variables for embedding configuration
3. Creates a corresponding llm_configuration record
4. Sets it as the default embedding model in system_config

Usage:
    python backend/scripts/migrate_embedding_config.py
"""

import os
import sys
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.core.config import settings
from app.crud.crud_system_config import system_config
from app.crud.crud_llm_config import llm_config
from app.schemas.llm_config import LLMConfigCreate


def migrate_embedding_config():
    """Migrate embedding configuration from environment variables to database"""
    
    db: Session = SessionLocal()
    
    try:
        print("=" * 60)
        print("Embedding Configuration Migration")
        print("=" * 60)
        
        # Check if default embedding model is already configured
        default_id = system_config.get_default_embedding_model_id(db)
        
        if default_id:
            existing_config = llm_config.get(db, id=default_id)
            if existing_config and existing_config.is_active:
                print(f"\n✓ Default embedding model already configured:")
                print(f"  ID: {existing_config.id}")
                print(f"  Provider: {existing_config.provider}")
                print(f"  Model: {existing_config.model_name}")
                print(f"  Base URL: {existing_config.base_url or 'Default'}")
                print("\nNo migration needed.")
                return
            else:
                print(f"\n⚠ Default embedding ID ({default_id}) points to inactive/missing config")
                print("  Will create new configuration from environment variables...")
        else:
            print("\n→ No default embedding model configured in database")
            print("  Checking environment variables...")
        
        # Determine provider and configuration from environment variables
        vector_service_type = settings.VECTOR_SERVICE_TYPE
        
        if vector_service_type == "aliyun":
            provider = "Aliyun"
            api_key = settings.DASHSCOPE_API_KEY
            base_url = settings.DASHSCOPE_BASE_URL
            model_name = settings.DASHSCOPE_EMBEDDING_MODEL
        elif vector_service_type == "ollama":
            provider = "Ollama"
            api_key = None  # Ollama doesn't require API key
            base_url = settings.OLLAMA_BASE_URL
            model_name = settings.OLLAMA_EMBEDDING_MODEL
        else:
            # Default to OpenAI
            provider = "OpenAI"
            api_key = settings.OPENAI_API_KEY
            base_url = settings.OPENAI_API_BASE
            model_name = getattr(settings, 'EMBEDDING_MODEL', 'text-embedding-3-small')
        
        print(f"\n→ Environment configuration detected:")
        print(f"  Service Type: {vector_service_type}")
        print(f"  Provider: {provider}")
        print(f"  Model: {model_name}")
        print(f"  Base URL: {base_url or 'Default'}")
        print(f"  API Key: {'***' + api_key[-8:] if api_key and len(api_key) > 8 else 'Not set'}")
        
        # Validate configuration
        if not model_name:
            print("\n✗ Error: Model name not found in environment variables")
            print("  Please configure DASHSCOPE_EMBEDDING_MODEL, OLLAMA_EMBEDDING_MODEL, or EMBEDDING_MODEL")
            return
        
        if provider != "Ollama" and not api_key:
            print(f"\n✗ Error: API key required for provider '{provider}' but not found")
            print("  Please configure DASHSCOPE_API_KEY or OPENAI_API_KEY")
            return
        
        # Create LLM configuration
        print("\n→ Creating embedding model configuration in database...")
        
        config_create = LLMConfigCreate(
            provider=provider,
            api_key=api_key,
            base_url=base_url,
            model_name=model_name,
            model_type="embedding",
            is_active=True
        )
        
        new_config = llm_config.create(db, obj_in=config_create)
        db.commit()
        
        print(f"✓ Created LLM configuration (ID: {new_config.id})")
        
        # Set as default
        print("\n→ Setting as default embedding model...")
        system_config.set_default_embedding_model_id(db, llm_config_id=new_config.id)
        db.commit()
        
        print("✓ Set as default embedding model")
        
        print("\n" + "=" * 60)
        print("Migration completed successfully!")
        print("=" * 60)
        print(f"\nDefault Embedding Model:")
        print(f"  ID: {new_config.id}")
        print(f"  Provider: {new_config.provider}")
        print(f"  Model: {new_config.model_name}")
        print(f"  Base URL: {new_config.base_url or 'Default'}")
        print("\nYou can now manage embedding models through the Admin UI.")
        
    except Exception as e:
        db.rollback()
        print(f"\n✗ Error during migration: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    migrate_embedding_config()
