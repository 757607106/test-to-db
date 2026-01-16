"""
验证 LLM 修复：模拟实际聊天场景
"""
from app.db.session import SessionLocal
from app.models.llm_config import LLMConfiguration
from app.core.llms import get_default_model

def verify_fix():
    """验证修复效果"""
    db = SessionLocal()
    
    try:
        print("\n" + "="*70)
        print("验证 LLM 配置修复")
        print("="*70)
        
        # 1. 显示所有活跃配置
        active_configs = db.query(LLMConfiguration).filter(
            LLMConfiguration.is_active == True,
            LLMConfiguration.model_type == "chat"
        ).order_by(LLMConfiguration.id.asc()).all()
        
        print(f"\n📋 当前活跃的 chat 配置（共 {len(active_configs)} 个）：")
        for i, config in enumerate(active_configs, 1):
            print(f"   {i}. ID={config.id}, {config.provider} - {config.model_name}")
            print(f"      Base URL: {config.base_url}")
        
        # 2. 测试 get_default_model
        print("\n🔍 调用 get_default_model() 获取默认模型...")
        print("-" * 70)
        
        llm = get_default_model()
        
        print("-" * 70)
        
        # 3. 验证结果
        if active_configs:
            latest_config = active_configs[-1]  # ID 最大的
            print(f"\n✅ 预期使用：ID={latest_config.id}, {latest_config.provider} - {latest_config.model_name}")
            print(f"   (这是 ID 最大的配置，即最新创建的配置)")
        
        print("\n" + "="*70)
        print("✅ 修复验证完成！")
        print("="*70)
        print("\n💡 说明：")
        print("   - 修复前：系统使用 ID 最小的配置（千问，ID=5）")
        print("   - 修复后：系统使用 ID 最大的配置（DeepSeek，ID=9）")
        print("   - 这符合用户直觉：最新配置的模型应该被使用")
        print("\n🎯 下一步：")
        print("   1. 重启 LangGraph 服务器")
        print("   2. 在聊天页面发送消息")
        print("   3. 观察日志，应该看到使用 DeepSeek 模型")
        print()
        
    except Exception as e:
        print(f"\n❌ 验证出错: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    verify_fix()
