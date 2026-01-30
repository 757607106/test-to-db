"""
图谱关系服务
查询Neo4j中的表关系，为洞察分析提供关系上下文
"""
from typing import List, Dict, Any, Optional
from neo4j import GraphDatabase

from app.core.config import settings


class GraphRelationshipService:
    """图谱关系查询服务"""
    
    def __init__(self):
        self.driver = None
    
    def _get_driver(self):
        """获取Neo4j驱动"""
        if not self.driver:
            self.driver = GraphDatabase.driver(
                settings.NEO4J_URI,
                auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
            )
        return self.driver
    
    def query_table_relationships(
        self,
        connection_id: int,
        table_names: List[str]
    ) -> Dict[str, Any]:
        """
        查询指定表的关系信息
        
        Args:
            connection_id: 数据库连接ID
            table_names: 要查询的表名列表
            
        Returns:
            关系上下文字典
        """
        if not table_names:
            return {
                "tables": [],
                "source_tables": [],
                "direct_relationships": [],
                "indirect_relationships": [],
                "relationship_count": 0,
                "relationship_descriptions": [],
                "relationship_types": {},
                "has_relationships": False
            }
        
        try:
            driver = self._get_driver()
            
            with driver.session() as session:
                # 查询直接关联关系
                direct_relationships = self._query_direct_relationships(
                    session, connection_id, table_names
                )
                
                # 查询二度关联（可选，用于发现更深层次的关系）
                indirect_relationships = self._query_indirect_relationships(
                    session, connection_id, table_names
                )
                
                # 构建关系上下文
                relationship_context = self._build_relationship_context(
                    table_names,
                    direct_relationships,
                    indirect_relationships
                )
                
                return relationship_context
                
        except Exception as e:
            print(f"查询图谱关系失败: {str(e)}")
            return {
                "tables": table_names,
                "source_tables": table_names,
                "direct_relationships": [],
                "indirect_relationships": [],
                "relationship_count": 0,
                "relationship_descriptions": [],
                "relationship_types": {},
                "has_relationships": False,
                "error": str(e)
            }
    
    def _query_direct_relationships(
        self,
        session,
        connection_id: int,
        table_names: List[str]
    ) -> List[Dict[str, Any]]:
        """查询直接关联关系"""
        query = """
        MATCH (source:Table {connection_id: $connection_id})-[:HAS_COLUMN]->(sc:Column)-[r:REFERENCES]->(tc:Column)<-[:HAS_COLUMN]-(target:Table {connection_id: $connection_id})
        WHERE source.name IN $table_names OR target.name IN $table_names
        RETURN 
          source.name AS source_table,
          sc.name AS source_column,
          r.type AS relationship_type,
          tc.name AS target_column,
          target.name AS target_table,
          target.description AS target_description
        ORDER BY source_table, target_table
        """
        
        result = session.run(query, connection_id=connection_id, table_names=table_names)
        
        relationships = []
        for record in result:
            relationships.append({
                "source_table": record["source_table"],
                "source_column": record["source_column"],
                "relationship_type": record["relationship_type"] or "references",
                "target_column": record["target_column"],
                "target_table": record["target_table"],
                "target_description": record["target_description"] or "",
                "depth": 1
            })
        
        return relationships
    
    def _query_indirect_relationships(
        self,
        session,
        connection_id: int,
        table_names: List[str]
    ) -> List[Dict[str, Any]]:
        """查询二度关联关系（通过中间表连接）"""
        query = """
        MATCH path = (source:Table {connection_id: $connection_id})-[:HAS_COLUMN]->(:Column)-[:REFERENCES*1..2]-(:Column)<-[:HAS_COLUMN]-(target:Table {connection_id: $connection_id})
        WHERE source.name IN $table_names
          AND source <> target
          AND NOT target.name IN $table_names
        RETURN DISTINCT
          source.name AS source_table,
          target.name AS related_table,
          target.description AS related_description,
          length(path) AS relationship_depth
        ORDER BY relationship_depth, source_table
        LIMIT 10
        """
        
        result = session.run(query, connection_id=connection_id, table_names=table_names)
        
        relationships = []
        for record in result:
            relationships.append({
                "source_table": record["source_table"],
                "target_table": record["related_table"],
                "target_description": record["related_description"] or "",
                "depth": record["relationship_depth"],
                "type": "indirect"
            })
        
        return relationships
    
    def _build_relationship_context(
        self,
        table_names: List[str],
        direct_relationships: List[Dict[str, Any]],
        indirect_relationships: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """构建关系上下文"""
        
        # 合并所有涉及的表
        all_tables = set(table_names)
        for rel in direct_relationships:
            all_tables.add(rel["target_table"])
        for rel in indirect_relationships:
            all_tables.add(rel["target_table"])
        
        # 构建关系描述文本（用于LLM Prompt）
        relationship_descriptions = []
        
        for rel in direct_relationships:
            desc = f"{rel['source_table']}.{rel['source_column']} -> {rel['target_table']}.{rel['target_column']}"
            if rel.get("target_description"):
                desc += f" ({rel['target_description']})"
            relationship_descriptions.append(desc)
        
        # 统计关系类型
        relationship_types = {}
        for rel in direct_relationships:
            rel_type = rel.get("relationship_type", "references")
            relationship_types[rel_type] = relationship_types.get(rel_type, 0) + 1
        
        return {
            "tables": list(all_tables),
            "source_tables": table_names,
            "direct_relationships": direct_relationships,
            "indirect_relationships": indirect_relationships,
            "relationship_count": len(direct_relationships),
            "relationship_descriptions": relationship_descriptions,
            "relationship_types": relationship_types,
            "has_relationships": len(direct_relationships) > 0
        }
    
    def close(self):
        """关闭Neo4j连接"""
        if self.driver:
            self.driver.close()
            self.driver = None


# 创建全局实例
graph_relationship_service = GraphRelationshipService()
