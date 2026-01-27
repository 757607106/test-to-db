"""
Neo4j JoinRule 到 Skill.join_rules 数据迁移脚本

用法:
    python scripts/migrate_join_rules_to_skills.py

功能:
    1. 从 Neo4j 读取所有 JoinRule 节点
    2. 根据 table_names 匹配关联到对应的 Skill
    3. 将 JoinRule 数据写入 Skill.join_rules 字段
    4. 可选：清理 Neo4j 中的 JoinRule 节点

注意:
    - 此脚本是幂等的，可以多次运行
    - 现有 Skill.join_rules 不会被覆盖（除非 --force）
"""
import os
import sys
import json
import logging
import argparse
from typing import List, Dict, Any

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from neo4j import GraphDatabase
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.skill import Skill

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_neo4j_driver():
    """获取 Neo4j 驱动"""
    try:
        driver = GraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
        )
        return driver
    except Exception as e:
        logger.error(f"Failed to connect to Neo4j: {e}")
        return None


def get_all_join_rules(driver) -> List[Dict[str, Any]]:
    """从 Neo4j 获取所有 JoinRule"""
    rules = []
    
    with driver.session() as session:
        result = session.run("""
            MATCH (j:JoinRule)
            RETURN j.id AS id,
                   j.name AS name,
                   j.description AS description,
                   j.left_table AS left_table,
                   j.left_column AS left_column,
                   j.right_table AS right_table,
                   j.right_column AS right_column,
                   j.join_type AS join_type,
                   j.priority AS priority,
                   j.extra_conditions AS extra_conditions,
                   j.connection_id AS connection_id,
                   j.is_active AS is_active
            ORDER BY j.connection_id, j.priority DESC
        """)
        
        for record in result:
            rules.append({
                "id": record["id"],
                "name": record["name"],
                "description": record["description"],
                "left_table": record["left_table"],
                "left_column": record["left_column"],
                "right_table": record["right_table"],
                "right_column": record["right_column"],
                "join_type": record["join_type"] or "INNER",
                "priority": record["priority"] or 1,
                "extra_conditions": record["extra_conditions"],
                "connection_id": record["connection_id"],
                "is_active": record["is_active"] if record["is_active"] is not None else True
            })
    
    logger.info(f"Found {len(rules)} JoinRule(s) in Neo4j")
    return rules


def migrate_rules_to_skills(db: Session, rules: List[Dict[str, Any]], force: bool = False) -> Dict[str, int]:
    """将 JoinRule 迁移到对应的 Skill"""
    stats = {
        "migrated": 0,
        "skipped": 0,
        "no_match": 0
    }
    
    # 按 connection_id 分组
    rules_by_connection = {}
    for rule in rules:
        conn_id = rule["connection_id"]
        if conn_id not in rules_by_connection:
            rules_by_connection[conn_id] = []
        rules_by_connection[conn_id].append(rule)
    
    # 获取所有 Skills
    all_skills = db.query(Skill).all()
    logger.info(f"Found {len(all_skills)} Skill(s) in database")
    
    for skill in all_skills:
        # 跳过已有 join_rules 的 Skill（除非 force）
        if skill.join_rules and not force:
            logger.debug(f"Skipping skill '{skill.name}' - already has join_rules")
            stats["skipped"] += 1
            continue
        
        # 获取此连接的 JoinRule
        conn_rules = rules_by_connection.get(skill.connection_id, [])
        if not conn_rules:
            continue
        
        # 匹配与此 Skill 相关的 JoinRule
        skill_tables = set(skill.table_names or [])
        matched_rules = []
        
        for rule in conn_rules:
            # 如果 rule 的 left_table 或 right_table 在 skill 的 table_names 中
            if rule["left_table"] in skill_tables or rule["right_table"] in skill_tables:
                # 转换为内嵌格式
                matched_rules.append({
                    "name": rule["name"],
                    "description": rule["description"],
                    "left_table": rule["left_table"],
                    "left_column": rule["left_column"],
                    "right_table": rule["right_table"],
                    "right_column": rule["right_column"],
                    "join_type": rule["join_type"],
                    "extra_conditions": rule["extra_conditions"]
                })
        
        if matched_rules:
            skill.join_rules = matched_rules
            logger.info(f"Migrated {len(matched_rules)} rule(s) to skill '{skill.name}'")
            stats["migrated"] += len(matched_rules)
        else:
            stats["no_match"] += 1
    
    db.commit()
    return stats


def cleanup_neo4j_join_rules(driver, dry_run: bool = True):
    """清理 Neo4j 中的 JoinRule 节点"""
    with driver.session() as session:
        if dry_run:
            result = session.run("MATCH (j:JoinRule) RETURN count(j) AS count")
            count = result.single()["count"]
            logger.info(f"[DRY RUN] Would delete {count} JoinRule node(s)")
        else:
            result = session.run("MATCH (j:JoinRule) DETACH DELETE j RETURN count(j) AS count")
            count = result.single()["count"]
            logger.info(f"Deleted {count} JoinRule node(s) from Neo4j")


def main():
    parser = argparse.ArgumentParser(description="Migrate JoinRule from Neo4j to Skill.join_rules")
    parser.add_argument("--force", action="store_true", help="Overwrite existing join_rules")
    parser.add_argument("--cleanup", action="store_true", help="Delete JoinRule nodes from Neo4j after migration")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without making changes")
    args = parser.parse_args()
    
    logger.info("=== JoinRule Migration Script ===")
    logger.info(f"Options: force={args.force}, cleanup={args.cleanup}, dry_run={args.dry_run}")
    
    # 连接 Neo4j
    driver = get_neo4j_driver()
    if not driver:
        logger.error("Cannot connect to Neo4j, exiting")
        sys.exit(1)
    
    try:
        # 获取所有 JoinRule
        rules = get_all_join_rules(driver)
        
        if not rules:
            logger.info("No JoinRule found in Neo4j, nothing to migrate")
            return
        
        # 迁移到 Skill
        if not args.dry_run:
            db = SessionLocal()
            try:
                stats = migrate_rules_to_skills(db, rules, args.force)
                logger.info(f"Migration complete: {stats}")
            finally:
                db.close()
        else:
            logger.info(f"[DRY RUN] Would migrate {len(rules)} rule(s)")
        
        # 清理 Neo4j
        if args.cleanup:
            cleanup_neo4j_join_rules(driver, dry_run=args.dry_run)
    
    finally:
        driver.close()
    
    logger.info("=== Migration Complete ===")


if __name__ == "__main__":
    main()
