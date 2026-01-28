"""
统一的 Schema 上下文模型

Phase 1 优化：解决 Schema 信息在各模块间传递时格式不一致的问题。

使用场景：
- schema_agent.py: 输出统一格式
- sql_generator_agent.py: 输入解析
- dashboard_insight_graph.py: Schema 增强
- text2sql_utils.py: Schema 检索

设计原则：
1. 扁平化结构，避免嵌套
2. 字段命名统一（使用 table_name 而非 name）
3. 提供便捷的转换方法
4. 支持序列化和反序列化
"""
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class TableInfo(BaseModel):
    """表信息 - 统一格式"""
    table_name: str = Field(..., description="表名")
    description: str = Field(default="", description="表描述")
    id: Optional[int] = Field(default=None, description="表ID（可选）")
    
    class Config:
        extra = "ignore"  # 忽略额外字段，兼容旧格式


class ColumnInfo(BaseModel):
    """列信息 - 统一格式"""
    table_name: str = Field(..., description="所属表名")
    column_name: str = Field(..., description="列名")
    data_type: str = Field(..., description="数据类型")
    description: str = Field(default="", description="列描述")
    is_primary_key: bool = Field(default=False, description="是否主键")
    is_foreign_key: bool = Field(default=False, description="是否外键")
    id: Optional[int] = Field(default=None, description="列ID（可选）")
    table_id: Optional[int] = Field(default=None, description="表ID（可选）")
    
    class Config:
        extra = "ignore"


class RelationshipInfo(BaseModel):
    """关系信息 - 统一格式"""
    source_table: str = Field(..., description="源表名")
    source_column: str = Field(..., description="源列名")
    target_table: str = Field(..., description="目标表名")
    target_column: str = Field(..., description="目标列名")
    relationship_type: str = Field(default="references", description="关系类型")
    id: Optional[int] = Field(default=None, description="关系ID（可选）")
    
    class Config:
        extra = "ignore"


class SchemaContext(BaseModel):
    """
    统一的 Schema 上下文
    
    所有模块间传递 Schema 信息时使用此格式。
    """
    tables: List[TableInfo] = Field(default_factory=list, description="表列表")
    columns: List[ColumnInfo] = Field(default_factory=list, description="列列表")
    relationships: List[RelationshipInfo] = Field(default_factory=list, description="关系列表")
    value_mappings: Dict[str, List[str]] = Field(default_factory=dict, description="值映射")
    connection_id: int = Field(..., description="数据库连接ID")
    db_type: str = Field(default="mysql", description="数据库类型")
    
    # ========================================
    # 便捷属性
    # ========================================
    
    @property
    def table_names(self) -> List[str]:
        """获取所有表名"""
        return [t.table_name for t in self.tables]
    
    @property
    def table_count(self) -> int:
        """表数量"""
        return len(self.tables)
    
    @property
    def column_count(self) -> int:
        """列数量"""
        return len(self.columns)
    
    def get_columns_for_table(self, table_name: str) -> List[ColumnInfo]:
        """获取指定表的所有列"""
        return [c for c in self.columns if c.table_name == table_name]
    
    def get_table_info(self, table_name: str) -> Optional[TableInfo]:
        """获取指定表的信息"""
        for t in self.tables:
            if t.table_name == table_name:
                return t
        return None
    
    # ========================================
    # 格式转换方法
    # ========================================
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式（用于 JSON 序列化）"""
        return {
            "tables": [t.model_dump() for t in self.tables],
            "columns": [c.model_dump() for c in self.columns],
            "relationships": [r.model_dump() for r in self.relationships],
            "value_mappings": self.value_mappings,
            "connection_id": self.connection_id,
            "db_type": self.db_type,
        }
    
    def to_prompt_format(self) -> str:
        """
        转换为 LLM Prompt 友好的格式
        
        格式示例:
        表: orders (订单表)
          - id: INT (主键)
          - customer_id: INT (外键, 关联 customers.id)
          - total_amount: DECIMAL (订单总金额)
        """
        lines = []
        
        # 按表组织
        for table in self.tables:
            table_desc = f" ({table.description})" if table.description else ""
            lines.append(f"表: {table.table_name}{table_desc}")
            
            # 该表的列
            table_columns = self.get_columns_for_table(table.table_name)
            for col in table_columns:
                col_attrs = []
                if col.is_primary_key:
                    col_attrs.append("主键")
                if col.is_foreign_key:
                    col_attrs.append("外键")
                if col.description:
                    col_attrs.append(col.description)
                
                attrs_str = f" ({', '.join(col_attrs)})" if col_attrs else ""
                lines.append(f"  - {col.column_name}: {col.data_type}{attrs_str}")
            
            lines.append("")  # 空行分隔
        
        # 关系信息
        if self.relationships:
            lines.append("表关系:")
            for rel in self.relationships:
                lines.append(
                    f"  - {rel.source_table}.{rel.source_column} → "
                    f"{rel.target_table}.{rel.target_column} ({rel.relationship_type})"
                )
        
        return "\n".join(lines)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any], connection_id: int = 0, db_type: str = "mysql") -> "SchemaContext":
        """
        从字典创建 SchemaContext
        
        支持多种输入格式的兼容转换：
        1. 标准格式: {"tables": [...], "columns": [...], ...}
        2. 嵌套格式: {"tables": {"tables": [...], "columns": [...]}}
        3. 旧格式: {"tables": [{"name": "xxx", ...}]}
        """
        import logging
        logger = logging.getLogger(__name__)
        
        # 处理嵌套格式
        if "tables" in data and isinstance(data["tables"], dict):
            # 嵌套格式: schema_info.tables.tables
            logger.debug("[from_dict] 检测到嵌套格式")
            nested = data["tables"]
            tables_raw = nested.get("tables", [])
            columns_raw = nested.get("columns", [])
            relationships_raw = nested.get("relationships", [])
        else:
            # 标准格式
            logger.debug("[from_dict] 使用标准格式")
            tables_raw = data.get("tables", [])
            columns_raw = data.get("columns", [])
            relationships_raw = data.get("relationships", [])
        
        logger.debug(f"[from_dict] tables_raw 数量: {len(tables_raw)}, columns_raw 数量: {len(columns_raw)}")
        
        # 转换表信息
        tables = []
        for t in tables_raw:
            if isinstance(t, dict):
                table_name = t.get("table_name") or t.get("name", "")
                if table_name:
                    tables.append(TableInfo(
                        table_name=table_name,
                        description=t.get("description", ""),
                        id=t.get("id"),
                    ))
        
        logger.debug(f"[from_dict] 转换后的表数量: {len(tables)}")
        
        # 转换列信息
        columns = []
        for c in columns_raw:
            if isinstance(c, dict):
                columns.append(ColumnInfo(
                    table_name=c.get("table_name", ""),
                    column_name=c.get("column_name") or c.get("name", ""),
                    data_type=c.get("data_type") or c.get("type", ""),
                    description=c.get("description", ""),
                    is_primary_key=c.get("is_primary_key", False),
                    is_foreign_key=c.get("is_foreign_key", False),
                    id=c.get("id"),
                    table_id=c.get("table_id"),
                ))
        
        # 转换列信息
        columns = []
        for c in columns_raw:
            if isinstance(c, dict):
                columns.append(ColumnInfo(
                    table_name=c.get("table_name", ""),
                    column_name=c.get("column_name") or c.get("name", ""),
                    data_type=c.get("data_type") or c.get("type", ""),
                    description=c.get("description", ""),
                    is_primary_key=c.get("is_primary_key", False),
                    is_foreign_key=c.get("is_foreign_key", False),
                    id=c.get("id"),
                    table_id=c.get("table_id"),
                ))
        
        # 转换关系信息
        relationships = []
        for r in relationships_raw:
            if isinstance(r, dict):
                relationships.append(RelationshipInfo(
                    source_table=r.get("source_table", ""),
                    source_column=r.get("source_column", ""),
                    target_table=r.get("target_table", ""),
                    target_column=r.get("target_column", ""),
                    relationship_type=r.get("relationship_type", "references"),
                    id=r.get("id"),
                ))
        
        return cls(
            tables=tables,
            columns=columns,
            relationships=relationships,
            value_mappings=data.get("value_mappings", {}),
            connection_id=data.get("connection_id", connection_id),
            db_type=data.get("db_type", db_type),
        )


# ========================================
# 辅助函数
# ========================================

def normalize_schema_info(schema_info: Any, connection_id: int = 0, db_type: str = "mysql") -> SchemaContext:
    """
    将任意格式的 schema_info 规范化为 SchemaContext
    
    支持的输入格式：
    1. SchemaContext 实例 - 直接返回
    2. Dict - 调用 from_dict 转换
    3. None - 返回空的 SchemaContext
    
    Args:
        schema_info: 任意格式的 schema 信息
        connection_id: 数据库连接ID
        db_type: 数据库类型
        
    Returns:
        SchemaContext: 规范化后的 Schema 上下文
    """
    if schema_info is None:
        return SchemaContext(connection_id=connection_id, db_type=db_type)
    
    if isinstance(schema_info, SchemaContext):
        return schema_info
    
    if isinstance(schema_info, dict):
        return SchemaContext.from_dict(schema_info, connection_id, db_type)
    
    # 尝试转换为字典
    if hasattr(schema_info, "model_dump"):
        return SchemaContext.from_dict(schema_info.model_dump(), connection_id, db_type)
    
    if hasattr(schema_info, "__dict__"):
        return SchemaContext.from_dict(schema_info.__dict__, connection_id, db_type)
    
    # 无法转换，返回空
    return SchemaContext(connection_id=connection_id, db_type=db_type)


def extract_table_names(schema_info: Any) -> List[str]:
    """
    从任意格式的 schema_info 中提取表名列表
    
    这是一个便捷函数，用于快速获取表名而不需要完整转换。
    """
    if schema_info is None:
        return []
    
    if isinstance(schema_info, SchemaContext):
        return schema_info.table_names
    
    if isinstance(schema_info, dict):
        # 处理嵌套格式
        tables_data = schema_info.get("tables", [])
        if isinstance(tables_data, dict):
            tables_data = tables_data.get("tables", [])
        
        names = []
        for t in tables_data:
            if isinstance(t, dict):
                name = t.get("table_name") or t.get("name", "")
                if name:
                    names.append(name)
        return names
    
    return []


__all__ = [
    "TableInfo",
    "ColumnInfo", 
    "RelationshipInfo",
    "SchemaContext",
    "normalize_schema_info",
    "extract_table_names",
]
