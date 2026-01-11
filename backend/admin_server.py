import uvicorn
import logging
import sys
import os
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 加载 .env 文件 (强制覆盖已存在的环境变量)
env_file = Path(__file__).parent / ".env"
if env_file.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(env_file, override=True)
        print(f"✅ Loaded environment from .env (with override)")
    except ImportError:
        print("⚠️ python-dotenv not installed, skipping .env file")

from app.api.api_v1.api import api_router
from app.core.config import settings

# 注释掉过度的日志过滤，保持正常日志显示
# 这样我们可以看到完整的连接信息来诊断问题


app = FastAPI(
    title="ChatDB API",
    description="Text2SQL API for intelligent database querying",
    version="0.1.0",
)

# Set up CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API router
app.include_router(api_router, prefix="/api")


# 强制重新加载 - 修复路由问题

if __name__ == "__main__":
    uvicorn.run("admin_server:app", host="0.0.0.0", port=8000, reload=True, timeout_keep_alive=120)  # 120秒的keep-alive超时
