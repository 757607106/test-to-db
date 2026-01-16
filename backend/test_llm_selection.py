"""
测试 LLM 配置选择逻辑
验证系统是否使用最新的活跃配置
"""
from app.db.session import SessionLocal
from app.models.llm_config import LLMConfiguration
from app.core.llms import get_active_llm_config

def test_llm_selection():
    """测试 LLM 配置选择"""
    db = SessionLocal()
    
    try:
        print("\n" + "="*60)
        print("测试 LLM 配置选择逻辑")
        print("="*60)
        
        # 1. 查询所有活跃的 chat 类型配置
        active_configs = db.query(LLMConfiguration).filter(
            LLMConfiguration.is_active == True,
            LLMConfiguration.model_type == "chat"
        ).order_by(LLMConfiguration.id.asc()).all()
        
        print(f"\n找到 {len(active_configs)} 个活跃的 chat 配置：")
        for config in active_configs:
            print(f"  ID: {config.id}, 提供商: {config.provider}, 模型: {config.model_name}")
        
        # 2. 测试 get_active_llm_config
        print("\n调用 get_active_llm_config()...")
        selected_config = get_active_llm_config(model_type="chat")
        
        if selected_config:
            print(f"\n✅ 选中的配置：")
            print(f"   ID: {selected_config.id}")
            print(f"   提供商: {selected_config.provider}")
            print(f"   模型: {selected_config.model_name}")
            print(f"   Base URL: {selected_config.base_url}")
            
            # 验证是否选择了 ID 最大的（最新的）
            if active_configs:
                max_id = max(c.id for c in active_configs)
                if selected_config.id == max_id:
                    print(f"\n✅ 验证通过：选择了 ID 最大的配置（最新配置）")
                else:
                    print(f"\n❌ 验证失败：应该选择 ID={max_id}，但实际选择了 ID={selected_config.id}")
        else:
            print("\n❌ 未找到活跃配置")
        
        print("\n" + "="*60)
        
    except Exception as e:
        print(f"\n❌ 测试出错: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    test_llm_selection()
