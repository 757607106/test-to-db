import sys
import os
from pathlib import Path

# 添加 backend 目录到路径
sys.path.append(str(Path(__file__).parent))

from app.core.llms import get_default_model
from langchain_core.messages import HumanMessage

def check():
    print("🔍 正在检查 LLM 连接...")
    try:
        # 获取配置的模型
        llm = get_default_model()
        print(f"🤖 模型: {llm.model_name}")
        print(f"📦 类型: {type(llm).__name__}")
        
        # 打印连接地址信息
        if hasattr(llm, "base_url"):
             print(f"🌐 Base URL: {llm.base_url}")
        elif hasattr(llm, "api_base"):
             print(f"🌐 API Base: {llm.api_base}")
        
        print("📨 发送测试消息...")
        response = llm.invoke([HumanMessage(content="Hello, return 'OK' if you see this.")])
        
        print("-" * 30)
        print(f"✅ 连接成功! 回复: {response.content}")
        print("-" * 30)
        
    except Exception as e:
        print("\n❌ 连接失败!")
        print(f"错误类型: {type(e).__name__}")
        print(f"错误详情: {e}")
        print("\n建议:")
        print("1. 检查 .env 中的 OPENAI_API_KEY 和 OPENAI_API_BASE")
        print("2. 确保网络可以访问该 API 地址")
        print("3. 如果使用 DeepSeek，尝试将 LLM_PROVIDER 设置为 openai 并使用 DeepSeek 的 URL")

if __name__ == "__main__":
    check()
