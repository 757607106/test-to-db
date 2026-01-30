"""
Skill 服务 (Skill Service)

管理 Skills 的 CRUD 操作，支持 Neo4j 同步。
这是 Skills-SQL-Assistant 架构的核心组件。

核心特性：
1. 零配置可用 - 未配置 Skill 时退化到现有模式
2. 自动发现 - 智能建议 Skill 配置
3. 按需加载 - 只加载查询相关的 Skill 内容
4. Neo4j 同步 - 与现有语义层（Metric）整合
5. Skill-Centric - JOIN 规则内嵌于 Skill，无需独立管理
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging
import fnmatch

from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.core.config import settings
from app.models.skill import Skill as SkillModel
from app.schemas.skill import (
    Skill, SkillCreate, SkillUpdate, SkillLoadResult, SkillSuggestion
)
from app.db.session import get_db_session
from app.services.neo4j_service import neo4j_service

logger = logging.getLogger(__name__)

try:
    from neo4j import GraphDatabase, Driver
except Exception:
    GraphDatabase = None
    Driver = None


class SkillService:
    """
    Skill 服务 - SaaS 多租户支持
    
    核心特性：
    1. 零配置可用 - 未配置 Skill 时自动退化到现有模式
    2. Neo4j 同步 - 与现有语义层整合
    3. 按需加载 - 只加载查询相关的 Skill 内容
    4. Skill-Centric - JOIN 规则内嵌于 Skill
    """
    
    def __init__(self):
        self._neo4j_driver = None
        self._neo4j_initialized = False
    
    # ==================== CRUD ====================
    
    async def create_skill(self, data: SkillCreate, tenant_id: Optional[int] = None) -> Skill:
        """创建 Skill"""
        with get_db_session() as db:
            skill = SkillModel(
                name=data.name,
                display_name=data.display_name,
                description=data.description,
                keywords=data.keywords,
                intent_examples=data.intent_examples,
                table_patterns=data.table_patterns,
                table_names=data.table_names,
                business_rules=data.business_rules,
                common_patterns=data.common_patterns,
                join_rules=data.join_rules,  # 内嵌 JOIN 规则
                priority=data.priority,
                is_active=data.is_active,
                icon=data.icon,
                color=data.color,
                connection_id=data.connection_id,
                tenant_id=tenant_id
            )
            db.add(skill)
            db.commit()
            db.refresh(skill)
            
            # 同步到 Neo4j
            await self._sync_to_neo4j(skill)
            
            logger.info(f"Created skill: {skill.name} (id={skill.id}, connection_id={skill.connection_id})")
            return Skill.model_validate(skill)
    
    async def get_skill(self, skill_id: int) -> Optional[Skill]:
        """根据 ID 获取 Skill"""
        with get_db_session() as db:
            skill = db.query(SkillModel).filter(SkillModel.id == skill_id).first()
            return Skill.model_validate(skill) if skill else None
    
    async def get_skill_by_name(self, name: str, connection_id: int) -> Optional[Skill]:
        """根据名称获取 Skill"""
        with get_db_session() as db:
            skill = db.query(SkillModel).filter(
                SkillModel.name == name,
                SkillModel.connection_id == connection_id
            ).first()
            return Skill.model_validate(skill) if skill else None
    
    async def get_skills_by_connection(
        self, 
        connection_id: int,
        include_inactive: bool = False
    ) -> List[Skill]:
        """获取连接下的所有 Skill"""
        with get_db_session() as db:
            query = db.query(SkillModel).filter(
                SkillModel.connection_id == connection_id
            )
            
            if not include_inactive:
                query = query.filter(SkillModel.is_active == True)
            
            skills = query.order_by(SkillModel.priority.desc()).all()
            return [Skill.model_validate(s) for s in skills]
    
    async def update_skill(self, skill_id: int, data: SkillUpdate) -> Optional[Skill]:
        """更新 Skill"""
        with get_db_session() as db:
            skill = db.query(SkillModel).filter(SkillModel.id == skill_id).first()
            if not skill:
                return None
            
            update_data = data.model_dump(exclude_unset=True)
            for field, value in update_data.items():
                setattr(skill, field, value)
            
            db.commit()
            db.refresh(skill)
            
            # 同步到 Neo4j
            await self._sync_to_neo4j(skill)
            
            logger.info(f"Updated skill: {skill.name} (id={skill.id})")
            return Skill.model_validate(skill)
    
    async def delete_skill(self, skill_id: int) -> bool:
        """删除 Skill"""
        with get_db_session() as db:
            skill = db.query(SkillModel).filter(SkillModel.id == skill_id).first()
            if not skill:
                return False
            
            skill_name = skill.name
            connection_id = skill.connection_id
            
            # 从 Neo4j 删除
            await self._remove_from_neo4j(skill_name, connection_id)
            
            db.delete(skill)
            db.commit()
            
            logger.info(f"Deleted skill: {skill_name} (id={skill_id})")
            return True
    
    # ==================== 核心功能 ====================
    
    async def has_skills_configured(self, connection_id: int) -> bool:
        """
        检查是否配置了 Skill（用于决定是否启用 Skill 模式）
        
        零配置兼容的关键判断点
        """
        skills = await self.get_skills_by_connection(connection_id)
        return len(skills) > 0
    
    async def load_skill(
        self, 
        skill_name: str, 
        connection_id: int
    ) -> SkillLoadResult:
        """
        加载 Skill 完整内容（Progressive Disclosure 核心方法）
        
        返回:
        - Schema 信息（表、列）
        - 指标定义
        - JOIN 规则
        - 业务规则
        """
        # 获取 Skill 配置
        skill = await self.get_skill_by_name(skill_name, connection_id)
        if not skill:
            raise ValueError(f"Skill not found: {skill_name}")
        
        # 获取 Schema（限定在 Skill 关联的表范围内）
        schema_info = await self._get_skill_schema(skill, connection_id)
        
        # 获取关联的指标
        metrics = await self._get_skill_metrics(skill, connection_id)
        
        # 获取关联的 JOIN 规则
        join_rules = await self._get_skill_join_rules(skill, connection_id)
        
        # 获取枚举字段
        enum_columns = await self._get_enum_columns(skill.table_names, connection_id)
        
        # 更新使用计数
        await self._increment_usage(skill.id)
        
        return SkillLoadResult(
            skill_name=skill.name,
            display_name=skill.display_name,
            description=skill.description,
            tables=schema_info.get("tables", []),
            columns=schema_info.get("columns", []),
            relationships=schema_info.get("relationships", []),
            metrics=metrics,
            join_rules=join_rules,
            business_rules=skill.business_rules,
            common_patterns=skill.common_patterns,
            enum_columns=enum_columns
        )
    
    async def get_skill_prompt_section(
        self, 
        connection_id: int
    ) -> Optional[str]:
        """
        生成 Skill 描述段落（注入到 System Prompt）
        
        如果没有配置 Skill，返回 None（使用现有模式）
        """
        skills = await self.get_skills_by_connection(connection_id)
        
        if not skills:
            return None  # 零配置，不注入 Skill 信息
        
        lines = ["## 可用的业务领域 (Skills)\n"]
        lines.append("你可以使用 `load_skill` 工具加载以下领域的详细信息：\n")
        
        for skill in skills:
            keywords_str = ", ".join(skill.keywords[:5]) if skill.keywords else ""
            lines.append(f"- **{skill.name}** ({skill.display_name}): {skill.description or '无描述'}")
            if keywords_str:
                lines.append(f"  关键词: {keywords_str}")
        
        return "\n".join(lines)
    
    # ==================== 私有方法 ====================
    
    async def _get_skill_schema(
        self, 
        skill: Skill, 
        connection_id: int
    ) -> Dict[str, Any]:
        """获取 Skill 关联的 Schema"""
        # 合并精确表名和模式匹配
        target_tables = list(skill.table_names or [])
        
        if skill.table_patterns:
            # 模式匹配扩展表名
            all_tables = await self._get_all_table_names(connection_id)
            for pattern in skill.table_patterns:
                matched = fnmatch.filter(all_tables, pattern)
                target_tables.extend(matched)
        
        target_tables = list(set(target_tables))
        
        if not target_tables:
            return {"tables": [], "columns": [], "relationships": []}
        
        # 从数据库获取 Schema
        from app.models.schema_table import SchemaTable
        from app.models.schema_column import SchemaColumn
        from app.models.schema_relationship import SchemaRelationship
        
        with get_db_session() as db:
            # 获取表
            tables = db.query(SchemaTable).filter(
                SchemaTable.connection_id == connection_id,
                SchemaTable.table_name.in_(target_tables)
            ).all()
            
            table_ids = [t.id for t in tables]
            
            # 获取列
            columns = db.query(SchemaColumn).filter(
                SchemaColumn.table_id.in_(table_ids)
            ).all() if table_ids else []
            
            # 构建 table_id -> table_name 映射
            table_id_to_name = {t.id: t.table_name for t in tables}
            
            # 获取关系
            relationships = db.query(SchemaRelationship).filter(
                SchemaRelationship.connection_id == connection_id,
                or_(
                    SchemaRelationship.source_table_id.in_(table_ids),
                    SchemaRelationship.target_table_id.in_(table_ids)
                )
            ).all() if table_ids else []
            
            return {
                "tables": [
                    {
                        "id": t.id,
                        "table_name": t.table_name,
                        "description": t.description or ""
                    }
                    for t in tables
                ],
                "columns": [
                    {
                        "id": c.id,
                        "column_name": c.column_name,
                        "data_type": c.data_type,
                        "description": c.description or "",
                        "table_id": c.table_id,
                        "table_name": table_id_to_name.get(c.table_id, ""),
                        "is_primary_key": c.is_primary_key,
                        "is_foreign_key": c.is_foreign_key
                    }
                    for c in columns
                ],
                "relationships": [
                    {
                        "source_table_id": r.source_table_id,
                        "source_column_id": r.source_column_id,
                        "target_table_id": r.target_table_id,
                        "target_column_id": r.target_column_id,
                        "relationship_type": r.relationship_type
                    }
                    for r in relationships
                ]
            }
    
    async def _get_skill_metrics(
        self, 
        skill: Skill, 
        connection_id: int
    ) -> List[Dict[str, Any]]:
        """获取 Skill 关联的指标"""
        try:
            driver = self._get_neo4j_driver()
            if not driver:
                return []
            
            with driver.session() as session:
                # 查询 Skill 关联的指标（通过 BELONGS_TO_SKILL 关系）
                result = session.run("""
                    MATCH (s:Skill {name: $skill_name, connection_id: $connection_id})
                    MATCH (m:Metric)-[:BELONGS_TO_SKILL]->(s)
                    RETURN m
                    LIMIT 20
                """, skill_name=skill.name, connection_id=connection_id)
                
                metrics = []
                for record in result:
                    node = record["m"]
                    metrics.append({
                        "name": node.get("name"),
                        "business_name": node.get("business_name"),
                        "formula": node.get("formula"),
                        "description": node.get("description"),
                        "unit": node.get("unit"),
                        "source_table": node.get("source_table"),
                        "source_column": node.get("source_column")
                    })
                
                # 如果没有通过关系找到，尝试通过表名匹配
                if not metrics and skill.table_names:
                    result = session.run("""
                        MATCH (m:Metric {connection_id: $connection_id})
                        WHERE m.source_table IN $table_names
                        RETURN m
                        LIMIT 20
                    """, connection_id=connection_id, table_names=skill.table_names)
                    
                    for record in result:
                        node = record["m"]
                        metrics.append({
                            "name": node.get("name"),
                            "business_name": node.get("business_name"),
                            "formula": node.get("formula"),
                            "description": node.get("description"),
                            "unit": node.get("unit"),
                            "source_table": node.get("source_table"),
                            "source_column": node.get("source_column")
                        })
                
                return metrics
        except Exception as e:
            logger.warning(f"Failed to get skill metrics: {e}")
            return []
    
    async def _get_skill_join_rules(
        self, 
        skill: Skill, 
        connection_id: int
    ) -> List[Dict[str, Any]]:
        """
        获取 Skill 关联的 JOIN 规则
        
        优先使用 Skill 内嵌的 join_rules 字段（Skill-Centric 架构），
        如果为空则回退到 Neo4j 查询（向后兼容）。
        """
        # 优先使用 Skill 内嵌的 join_rules
        if skill.join_rules:
            logger.debug(f"Using embedded join_rules for skill: {skill.name}")
            return skill.join_rules
        
        # 回退：从 Neo4j 查询（向后兼容旧数据）
        try:
            driver = self._get_neo4j_driver()
            if not driver:
                return []
            
            with driver.session() as session:
                # 通过表名查找相关的 JOIN 规则
                if not skill.table_names:
                    return []
                
                result = session.run("""
                    MATCH (j:JoinRule {connection_id: $connection_id})
                    WHERE j.left_table IN $table_names OR j.right_table IN $table_names
                    RETURN j
                    ORDER BY j.priority DESC
                    LIMIT 20
                """, connection_id=connection_id, table_names=skill.table_names)
                
                rules = []
                for record in result:
                    node = record["j"]
                    rules.append({
                        "name": node.get("name"),
                        "left_table": node.get("left_table"),
                        "left_column": node.get("left_column"),
                        "right_table": node.get("right_table"),
                        "right_column": node.get("right_column"),
                        "join_type": node.get("join_type", "INNER"),
                        "description": node.get("description")
                    })
                
                return rules
        except Exception as e:
            logger.warning(f"Failed to get skill join rules from Neo4j: {e}")
            return []
    
    async def _get_enum_columns(
        self, 
        table_names: List[str], 
        connection_id: int
    ) -> List[Dict[str, Any]]:
        """获取枚举字段"""
        try:
            from app.services.value_profiling_service import value_profiling_service
            
            enum_columns = []
            for table_name in (table_names or [])[:5]:  # 限制数量
                try:
                    enums = await value_profiling_service.get_enum_columns(
                        connection_id, table_name
                    )
                    enum_columns.extend(enums)
                except Exception:
                    pass
            
            return enum_columns
        except Exception as e:
            logger.warning(f"Failed to get enum columns: {e}")
            return []
    
    async def _get_all_table_names(self, connection_id: int) -> List[str]:
        """获取所有表名"""
        from app.models.schema_table import SchemaTable
        
        with get_db_session() as db:
            tables = db.query(SchemaTable.table_name).filter(
                SchemaTable.connection_id == connection_id
            ).all()
            return [t[0] for t in tables]
    
    async def _increment_usage(self, skill_id: int):
        """增加使用计数"""
        try:
            with get_db_session() as db:
                db.query(SkillModel).filter(SkillModel.id == skill_id).update(
                    {SkillModel.usage_count: SkillModel.usage_count + 1}
                )
                db.commit()
        except Exception as e:
            logger.warning(f"Failed to increment usage count: {e}")
    
    # ==================== Neo4j 同步 ====================
    
    def _get_neo4j_driver(self):
        if self._neo4j_initialized:
            return self._neo4j_driver
        
        self._neo4j_initialized = True
        
        if not GraphDatabase or not getattr(settings, "NEO4J_URI", None):
            self._neo4j_driver = None
            return None
        
        try:
            self._neo4j_driver = GraphDatabase.driver(
                settings.NEO4J_URI,
                auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
            )
            return self._neo4j_driver
        except Exception as e:
            logger.warning(f"Failed to connect to Neo4j: {e}")
            self._neo4j_driver = None
            return None
    
    async def _sync_to_neo4j(self, skill: SkillModel):
        """同步 Skill 到 Neo4j"""
        try:
            driver = self._get_neo4j_driver()
            if not driver:
                return
            
            with driver.session() as session:
                # 创建/更新 Skill 节点
                session.run("""
                    MERGE (s:Skill {name: $name, connection_id: $connection_id})
                    SET s.display_name = $display_name,
                        s.description = $description,
                        s.keywords = $keywords,
                        s.priority = $priority,
                        s.updated_at = datetime()
                """,
                    name=skill.name,
                    connection_id=skill.connection_id,
                    display_name=skill.display_name,
                    description=skill.description or "",
                    keywords=skill.keywords or [],
                    priority=skill.priority or 0
                )
                
                # 删除旧的 CONTAINS_TABLE 关系
                session.run("""
                    MATCH (s:Skill {name: $name, connection_id: $connection_id})-[r:CONTAINS_TABLE]->()
                    DELETE r
                """, name=skill.name, connection_id=skill.connection_id)
                
                # 建立与 Table 的关系
                for table_name in (skill.table_names or []):
                    session.run("""
                        MATCH (s:Skill {name: $skill_name, connection_id: $connection_id})
                        MATCH (t:Table {name: $table_name, connection_id: $connection_id})
                        MERGE (s)-[:CONTAINS_TABLE]->(t)
                    """,
                        skill_name=skill.name,
                        connection_id=skill.connection_id,
                        table_name=table_name
                    )
                
                # 自动关联 Metric（根据 table_names）
                if skill.table_names:
                    session.run("""
                        MATCH (s:Skill {name: $skill_name, connection_id: $connection_id})
                        MATCH (m:Metric {connection_id: $connection_id})
                        WHERE m.source_table IN $table_names
                        MERGE (m)-[:BELONGS_TO_SKILL]->(s)
                    """,
                        skill_name=skill.name,
                        connection_id=skill.connection_id,
                        table_names=skill.table_names
                    )
                
                logger.info(f"Synced skill to Neo4j: {skill.name}")
        except Exception as e:
            logger.warning(f"Failed to sync skill to Neo4j: {e}")
    
    async def _remove_from_neo4j(self, skill_name: str, connection_id: int):
        """从 Neo4j 删除 Skill"""
        try:
            driver = self._get_neo4j_driver()
            if not driver:
                return
            
            with driver.session() as session:
                session.run("""
                    MATCH (s:Skill {name: $name, connection_id: $connection_id})
                    DETACH DELETE s
                """, name=skill_name, connection_id=connection_id)
                
                logger.info(f"Removed skill from Neo4j: {skill_name}")
        except Exception as e:
            logger.warning(f"Failed to remove skill from Neo4j: {e}")
    
    def close(self):
        """关闭资源（使用公共 Neo4j 服务，此方法保留以保持兼容）"""
        if self._neo4j_driver:
            try:
                self._neo4j_driver.close()
            except Exception:
                pass
        self._neo4j_driver = None
        self._neo4j_initialized = False


# 全局实例
skill_service = SkillService()
