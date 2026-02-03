#!/usr/bin/env python3
"""
Simple LangGraph API Server

A minimal script to start the LangGraph API server directly using uvicorn.
pip install --upgrade "langgraph-cli[inmem]"
"""


import os
import sys
import json
from pathlib import Path

def setup_environment():
    """Setup required environment variables"""
    # Add src to Python path
    src_path = Path(__file__).parent / "src"
    sys.path.insert(0, str(src_path))
    
    # 优先加载 .env 文件，以便后续读取 SERVICE_HOST 等配置
    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        try:
            from dotenv import load_dotenv
            load_dotenv(env_file, override=False)  # 不覆盖已存在的环境变量
            print(f"✅ Loaded environment from .env")
        except ImportError:
            print("⚠️  python-dotenv not installed, skipping .env file")
    
    # Load graphs from langgraph.json
    config_path = Path(__file__).parent / "langgraph.json"
    graphs = {}

    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
            graphs = config.get("graphs", {})
    
    # 从环境变量获取主机地址配置，支持 localhost 和局域网 IP 访问
    # 优先使用环境变量 SERVICE_HOST，默认为 localhost
    service_host = os.getenv("SERVICE_HOST", "localhost")
    
    # PostgreSQL checkpointer URI - 支持通过环境变量完全自定义或使用 SERVICE_HOST
    default_postgres_uri = f"postgresql://langgraph:langgraph_password_2026@{service_host}:5433/langgraph_checkpoints"
    postgres_uri = os.getenv("CHECKPOINT_POSTGRES_URI", default_postgres_uri)
    
    # LangGraph API URL - 支持通过环境变量完全自定义或使用 SERVICE_HOST
    default_langgraph_url = f"http://{service_host}:2024"
    langgraph_api_url = os.getenv("LANGGRAPH_API_URL", default_langgraph_url)
    
    # Set environment variables
    os.environ.update({
        # Database and storage - 使用自定义 PostgreSQL checkpointer
        "POSTGRES_URI": postgres_uri,
        # "REDIS_URI": "redis://localhost:6379",
        "DATABASE_URI": ":memory:",
        "REDIS_URI": "fake",
        # "MIGRATIONS_PATH": "/storage/migrations",
        "MIGRATIONS_PATH": "__inmem",
        # Server configuration
        "ALLOW_PRIVATE_NETWORK": "true",
        "LANGGRAPH_UI_BUNDLER": "true",
        "LANGGRAPH_RUNTIME_EDITION": "inmem",
        "LANGSMITH_LANGGRAPH_API_VARIANT": "local_dev",
        "LANGGRAPH_DISABLE_FILE_PERSISTENCE": "false",
        "LANGGRAPH_ALLOW_BLOCKING": "true",
        "LANGGRAPH_API_URL": langgraph_api_url,

        "LANGGRAPH_DEFAULT_RECURSION_LIMIT": "200",
        
        # Graphs configuration
        "LANGSERVE_GRAPHS": json.dumps(graphs) if graphs else "{}",
        
        # Worker configuration
        "N_JOBS_PER_WORKER": "1",
    })

def main():
    """Start the server"""
    print("🚀 Starting Simple LangGraph API Server...")
    
    # Setup environment
    setup_environment()
    
    # 获取实际配置的地址用于显示
    service_host = os.getenv("SERVICE_HOST", "localhost")
    
    # Print server information
    print("\n" + "="*60)
    print(f"📍 Server URL: http://{service_host}:2024")
    print(f"   (监听 0.0.0.0:2024, 同时支持 localhost 和 {service_host} 访问)")
    print(f"📚 API Documentation: http://{service_host}:2024/docs")
    print(f"🎨 Studio UI: http://{service_host}:2024/ui")
    print(f"💚 Health Check: http://{service_host}:2024/ok")
    print("="*60)
    
    try:
        # Import uvicorn after environment setup
        import uvicorn
        
        # Start the server directly
        uvicorn.run(
            "langgraph_api.server:app",
            host="0.0.0.0",
            port=2024,
            reload=True,
            access_log=False,
            log_config={
                "version": 1,
                "disable_existing_loggers": False,
                "formatters": {
                    "default": {
                        "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                    }
                },
                "handlers": {
                    "default": {
                        "formatter": "default",
                        "class": "logging.StreamHandler",
                        "stream": "ext://sys.stdout",
                    }
                },
                "root": {
                    "level": "INFO",
                    "handlers": ["default"],
                },
                "loggers": {
                    "uvicorn": {"level": "INFO"},
                    "uvicorn.error": {"level": "INFO"},
                    "uvicorn.access": {"level": "WARNING"},
                }
            }
        )
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user")
    except Exception as e:
        print(f"❌ Server failed to start: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
