from typing import Optional, Dict, Any, Union
from sqlalchemy.orm import Session

from app.crud.base import CRUDBase
from app.models.system_config import SystemConfig
from app.schemas.system_config import SystemConfigCreate, SystemConfigUpdate


class CRUDSystemConfig(CRUDBase[SystemConfig, SystemConfigCreate, SystemConfigUpdate]):
    def get_by_key(self, db: Session, *, config_key: str) -> Optional[SystemConfig]:
        """Get system configuration by key"""
        return db.query(self.model).filter(self.model.config_key == config_key).first()

    def get_value(self, db: Session, *, config_key: str) -> Optional[str]:
        """Get configuration value by key"""
        config = self.get_by_key(db, config_key=config_key)
        return config.config_value if config else None

    def set_value(
        self, 
        db: Session, 
        *, 
        config_key: str, 
        config_value: str,
        description: Optional[str] = None
    ) -> SystemConfig:
        """Set configuration value. Create if not exists, update if exists."""
        config = self.get_by_key(db, config_key=config_key)
        if config:
            # Update existing
            update_data = {"config_value": config_value}
            if description is not None:
                update_data["description"] = description
            return self.update(db, db_obj=config, obj_in=update_data)
        else:
            # Create new
            obj_in = SystemConfigCreate(
                config_key=config_key,
                config_value=config_value,
                description=description
            )
            return self.create(db, obj_in=obj_in)

    def get_default_embedding_model_id(self, db: Session) -> Optional[int]:
        """Get the default embedding model ID"""
        value = self.get_value(db, config_key="default_embedding_model_id")
        if value and value.strip():
            try:
                return int(value)
            except ValueError:
                return None
        return None

    def set_default_embedding_model_id(self, db: Session, *, llm_config_id: Optional[int]) -> SystemConfig:
        """Set the default embedding model ID"""
        value = str(llm_config_id) if llm_config_id is not None else None
        return self.set_value(
            db,
            config_key="default_embedding_model_id",
            config_value=value,
            description="默认Embedding模型的LLM配置ID"
        )

    # ===== QA 样本检索配置 =====
    
    def get_qa_sample_config(self, db: Session) -> Dict[str, Any]:
        """获取 QA 样本检索配置"""
        import json
        value = self.get_value(db, config_key="qa_sample_retrieval_config")
        if value:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                pass
        # 返回默认配置
        return {
            "enabled": True,
            "top_k": 3,
            "min_similarity": 0.6,
            "timeout_seconds": 5
        }
    
    def set_qa_sample_config(
        self, 
        db: Session, 
        *, 
        config: Dict[str, Any]
    ) -> SystemConfig:
        """设置 QA 样本检索配置"""
        import json
        return self.set_value(
            db,
            config_key="qa_sample_retrieval_config",
            config_value=json.dumps(config),
            description="QA样本检索配置（enabled/top_k/min_similarity/timeout_seconds）"
        )
    
    def is_qa_sample_enabled(self, db: Session) -> bool:
        """检查 QA 样本检索是否启用"""
        config = self.get_qa_sample_config(db)
        return config.get("enabled", True)
    
    def set_qa_sample_enabled(self, db: Session, *, enabled: bool) -> SystemConfig:
        """设置 QA 样本检索启用状态"""
        config = self.get_qa_sample_config(db)
        config["enabled"] = enabled
        return self.set_qa_sample_config(db, config=config)


system_config = CRUDSystemConfig(SystemConfig)
