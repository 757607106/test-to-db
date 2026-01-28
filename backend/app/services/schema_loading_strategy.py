"""
Schema 加载策略模块

提供多种 Schema 加载策略，确保表的完整性。

策略说明：
1. FULL_LOAD: 全量加载所有表（推荐用于复杂业务场景）
   - 优点：表完整性 100%，SQL 准确性最高
   - 缺点：Token 消耗较大，适合表数量 < 50 的场景

2. SMART_FILTER: 智能过滤（当前默认）
   - 优点：Token 消耗低，响应快
   - 缺点：可能遗漏关键表，导致 SQL 幻觉

3. SKILL_BASED: 基于 Skill 加载（推荐用于大型数据库）
   - 优点：精确控制加载范围，兼顾完整性和效率
   - 缺点：需要预先配置 Skill

使用方式：
    from app.services.schema_loading_strategy import SchemaLoadingStrategy, get_schema_loading_config
    
    strategy = get_schema_loading_config(connection_id)
    if strategy == SchemaLoadingStrategy.FULL_LOAD:
        # 加载所有表
        ...

Phase 1 优化：
- 使用统一的 SchemaContext 格式
- get_full_schema_for_connection 返回 SchemaContext 实例
"""
from enum import Enum
from typing import Dict, Any, Optional, List, Union
import logging

from app.core.config import settings
from app.schemas.schema_context import SchemaContext, TableInfo, ColumnInfo, RelationshipInfo

logger = logging.getLogger(__name__)


class SchemaLoadingStrategy(str, Enum):
    """Schema 加载策略"""
    FULL_LOAD = "full_load"       # 全量加载：加载所有表
    SMART_FILTER = "smart_filter" # 智能过滤：LLM 语义匹配（当前默认）
    SKILL_BASED = "skill_based"   # 基于 Skill：只加载 Skill 关联的表


# 默认策略配置
DEFAULT_STRATEGY = SchemaLoadingStrategy.FULL_LOAD  # 改为全量加载，确保表完整性

# 全量加载的表数量阈值（超过此数量自动降级到智能过滤）
# 从配置文件读取
def _get_full_load_threshold() -> int:
    return getattr(settings, 'SCHEMA_FULL_LOAD_THRESHOLD', 100)

FULL_LOAD_TABLE_THRESHOLD = _get_full_load_threshold()

# 每个连接的策略配置缓存
_connection_strategy_cache: Dict[int, SchemaLoadingStrategy] = {}


def get_schema_loading_strategy(
    connection_id: int,
    table_count: Optional[int] = None,
    skill_mode_enabled: bool = False
) -> SchemaLoadingStrategy:
    """
    获取指定连接的 Schema 加载策略
    
    决策逻辑：
    1. 如果启用了 Skill 模式 → SKILL_BASED
    2. 如果表数量 <= 阈值 → FULL_LOAD（确保完整性）
    3. 如果表数量 > 阈值 → SMART_FILTER（避免 Token 超限）
    
    Args:
        connection_id: 数据库连接 ID
        table_count: 表数量（可选，用于动态决策）
        skill_mode_enabled: 是否启用 Skill 模式
        
    Returns:
        SchemaLoadingStrategy: 加载策略
    """
    # Skill 模式优先
    if skill_mode_enabled:
        logger.info(f"[Schema策略] connection_id={connection_id} → SKILL_BASED (Skill模式启用)")
        return SchemaLoadingStrategy.SKILL_BASED
    
    # 检查环境变量配置（只有明确设置且不是默认值时才覆盖）
    env_strategy = getattr(settings, 'SCHEMA_LOADING_STRATEGY', None)
    # 注意：如果环境变量是默认值 "full_load"，仍然允许基于表数量的动态决策
    # 只有当用户明确设置为 "smart_filter" 或 "skill_based" 时才强制使用
    if env_strategy and env_strategy.lower() != "full_load":
        try:
            strategy = SchemaLoadingStrategy(env_strategy.lower())
            logger.info(f"[Schema策略] connection_id={connection_id} → {strategy.value} (环境变量强制配置)")
            return strategy
        except ValueError:
            logger.warning(f"无效的 SCHEMA_LOADING_STRATEGY: {env_strategy}")
    
    # 基于表数量动态决策
    if table_count is not None:
        if table_count <= FULL_LOAD_TABLE_THRESHOLD:
            logger.info(f"[Schema策略] connection_id={connection_id} → FULL_LOAD (表数量={table_count} <= {FULL_LOAD_TABLE_THRESHOLD})")
            return SchemaLoadingStrategy.FULL_LOAD
        else:
            logger.info(f"[Schema策略] connection_id={connection_id} → SMART_FILTER (表数量={table_count} > {FULL_LOAD_TABLE_THRESHOLD})")
            return SchemaLoadingStrategy.SMART_FILTER
    
    # 默认策略
    logger.info(f"[Schema策略] connection_id={connection_id} → {DEFAULT_STRATEGY.value} (默认)")
    return DEFAULT_STRATEGY


def set_connection_strategy(connection_id: int, strategy: SchemaLoadingStrategy):
    """
    为指定连接设置 Schema 加载策略
    
    Args:
        connection_id: 数据库连接 ID
        strategy: 加载策略
    """
    _connection_strategy_cache[connection_id] = strategy
    logger.info(f"[Schema策略] 已设置 connection_id={connection_id} → {strategy.value}")


def get_full_schema_for_connection(
    db,
    connection_id: int,
    max_tables: int = 9999,  # 默认不限制
    db_type: str = "mysql"
) -> Union[SchemaContext, Dict[str, Any]]:
    """
    获取连接的完整 Schema（全量加载模式）
    
    重要：此函数必须加载所有表，不能有任何限制！
    Schema 的完整性直接影响 SQL 生成的准确性。
    
    Args:
        db: 数据库会话
        connection_id: 数据库连接 ID
        max_tables: 最大表数量限制（默认 9999，即不限制）
        db_type: 数据库类型
        
    Returns:
        SchemaContext: 统一格式的 Schema 上下文
    """
    from app import crud
    
    # 获取所有表 - 不限制数量
    all_tables = crud.schema_table.get_by_connection(db=db, connection_id=connection_id)
    
    # 只在极端情况下（超过 9999 表）才截断，并记录警告
    if len(all_tables) > max_tables:
        logger.warning(f"⚠️ 表数量({len(all_tables)})超过限制({max_tables})，将截断。这可能影响 SQL 准确性！")
        all_tables = all_tables[:max_tables]
    
    # 构建 table_id -> table_name 映射
    table_id_to_name = {table.id: table.table_name for table in all_tables}
    table_ids = set(table_id_to_name.keys())
    
    # 转换为统一格式 - 表信息
    tables = [
        TableInfo(
            table_name=table.table_name,
            description=table.description or "",
            id=table.id
        )
        for table in all_tables
    ]
    
    # 获取所有列并转换为统一格式
    columns = []
    col_id_to_name = {}  # 用于关系查询
    
    for table in all_tables:
        table_columns = crud.schema_column.get_by_table(db=db, table_id=table.id)
        for col in table_columns:
            col_id_to_name[col.id] = col.column_name
            columns.append(ColumnInfo(
                table_name=table.table_name,
                column_name=col.column_name,
                data_type=col.data_type,
                description=col.description or "",
                is_primary_key=col.is_primary_key,
                is_foreign_key=col.is_foreign_key,
                id=col.id,
                table_id=table.id
            ))
    
    # 获取所有关系并转换为统一格式
    relationships = []
    all_relationships = crud.schema_relationship.get_by_connection(db=db, connection_id=connection_id)
    
    for rel in all_relationships:
        if rel.source_table_id in table_ids and rel.target_table_id in table_ids:
            relationships.append(RelationshipInfo(
                source_table=table_id_to_name.get(rel.source_table_id, ""),
                source_column=col_id_to_name.get(rel.source_column_id, ""),
                target_table=table_id_to_name.get(rel.target_table_id, ""),
                target_column=col_id_to_name.get(rel.target_column_id, ""),
                relationship_type=rel.relationship_type or "references",
                id=rel.id
            ))
    
    logger.info(f"[全量加载] 获取完整 Schema: {len(tables)} 表, {len(columns)} 列, {len(relationships)} 关系")
    
    return SchemaContext(
        tables=tables,
        columns=columns,
        relationships=relationships,
        value_mappings={},
        connection_id=connection_id,
        db_type=db_type
    )


__all__ = [
    "SchemaLoadingStrategy",
    "get_schema_loading_strategy",
    "set_connection_strategy",
    "get_full_schema_for_connection",
    "FULL_LOAD_TABLE_THRESHOLD",
    "SchemaContext",
    "TableInfo",
    "ColumnInfo",
    "RelationshipInfo",
]
