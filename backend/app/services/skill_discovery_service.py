"""
Skill 自动发现服务 (Skill Discovery Service)

基于数据库 Schema 自动发现和建议 Skill 配置。

核心功能：
1. 分析表结构，识别业务领域
2. 根据表名前缀、关联关系分组
3. 使用 LLM 生成 Skill 建议
4. 支持增量发现（新表加入时）

发现策略：
- 表名前缀分组（如 order_*, inventory_*）
- 外键关联分析（强关联的表归为同一领域）
- 表注释语义分析
- LLM 辅助命名和描述生成
"""
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, field
import logging
import re
from collections import defaultdict

from app.schemas.skill import SkillSuggestion, SkillCreate
from app.db.session import get_db_session
from app.models.schema_table import SchemaTable
from app.models.schema_relationship import SchemaRelationship

logger = logging.getLogger(__name__)


@dataclass
class TableGroup:
    """表分组"""
    name: str
    tables: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    confidence: float = 0.0
    grouping_reason: str = ""


@dataclass
class DiscoveryResult:
    """发现结果"""
    suggestions: List[SkillSuggestion]
    analyzed_tables: int
    grouped_tables: int
    ungrouped_tables: List[str]


class SkillDiscoveryService:
    """
    Skill 自动发现服务
    
    分析数据库 Schema，智能建议 Skill 配置
    """
    
    # 常见业务领域前缀映射
    DOMAIN_PREFIXES = {
        "order": ["订单", "销售", "交易"],
        "sale": ["销售", "营销"],
        "purchase": ["采购", "进货"],
        "inventory": ["库存", "仓储"],
        "stock": ["库存", "存货"],
        "product": ["产品", "商品"],
        "goods": ["商品", "货物"],
        "customer": ["客户", "会员"],
        "user": ["用户", "账户"],
        "finance": ["财务", "资金"],
        "payment": ["支付", "收款"],
        "account": ["账户", "账目"],
        "employee": ["员工", "人事"],
        "staff": ["员工", "人员"],
        "department": ["部门", "组织"],
        "report": ["报表", "统计"],
        "log": ["日志", "记录"],
        "config": ["配置", "设置"],
        "system": ["系统", "管理"],
    }
    
    # 忽略的系统表前缀
    IGNORE_PREFIXES = ["sys_", "log_", "tmp_", "temp_", "bak_", "backup_"]
    
    def __init__(self):
        pass
    
    async def discover(
        self, 
        connection_id: int,
        use_llm: bool = False
    ) -> DiscoveryResult:
        """
        执行 Skill 自动发现
        
        Args:
            connection_id: 数据库连接 ID
            use_llm: 是否使用 LLM 增强分析
            
        Returns:
            DiscoveryResult: 发现结果
        """
        # 获取所有表
        tables = await self._get_tables(connection_id)
        
        if not tables:
            return DiscoveryResult(
                suggestions=[],
                analyzed_tables=0,
                grouped_tables=0,
                ungrouped_tables=[]
            )
        
        # 获取表关系
        relationships = await self._get_relationships(connection_id)
        
        # 步骤1: 基于前缀分组
        prefix_groups = self._group_by_prefix(tables)
        
        # 步骤2: 基于关系优化分组
        refined_groups = self._refine_by_relationships(prefix_groups, relationships)
        
        # 步骤3: 生成 Skill 建议
        if use_llm:
            suggestions = await self._generate_suggestions_with_llm(refined_groups, tables)
        else:
            suggestions = self._generate_suggestions(refined_groups, tables)
        
        # 统计未分组的表
        grouped_tables = set()
        for group in refined_groups:
            grouped_tables.update(group.tables)
        
        ungrouped = [t["table_name"] for t in tables if t["table_name"] not in grouped_tables]
        
        return DiscoveryResult(
            suggestions=suggestions,
            analyzed_tables=len(tables),
            grouped_tables=len(grouped_tables),
            ungrouped_tables=ungrouped
        )
    
    async def _get_tables(self, connection_id: int) -> List[Dict[str, Any]]:
        """获取所有表"""
        with get_db_session() as db:
            tables = db.query(SchemaTable).filter(
                SchemaTable.connection_id == connection_id
            ).all()
            
            return [
                {
                    "table_name": t.table_name,
                    "description": t.description or "",
                    "id": t.id
                }
                for t in tables
                if not any(t.table_name.lower().startswith(p) for p in self.IGNORE_PREFIXES)
            ]
    
    async def _get_relationships(self, connection_id: int) -> List[Dict[str, Any]]:
        """获取表关系"""
        with get_db_session() as db:
            # 获取表名映射
            tables = db.query(SchemaTable).filter(
                SchemaTable.connection_id == connection_id
            ).all()
            table_id_to_name = {t.id: t.table_name for t in tables}
            
            # 获取关系
            relationships = db.query(SchemaRelationship).filter(
                SchemaRelationship.connection_id == connection_id
            ).all()
            
            return [
                {
                    "source_table": table_id_to_name.get(r.source_table_id, ""),
                    "target_table": table_id_to_name.get(r.target_table_id, ""),
                    "relationship_type": r.relationship_type
                }
                for r in relationships
                if r.source_table_id in table_id_to_name and r.target_table_id in table_id_to_name
            ]
    
    def _group_by_prefix(self, tables: List[Dict[str, Any]]) -> List[TableGroup]:
        """基于前缀分组"""
        prefix_tables: Dict[str, List[str]] = defaultdict(list)
        
        for table in tables:
            table_name = table["table_name"].lower()
            
            # 提取前缀
            prefix = self._extract_prefix(table_name)
            if prefix:
                prefix_tables[prefix].append(table["table_name"])
        
        # 转换为 TableGroup
        groups = []
        for prefix, table_list in prefix_tables.items():
            if len(table_list) >= 2:  # 至少2个表才成组
                keywords = self.DOMAIN_PREFIXES.get(prefix, [prefix])
                groups.append(TableGroup(
                    name=prefix,
                    tables=table_list,
                    keywords=keywords,
                    confidence=0.7 if prefix in self.DOMAIN_PREFIXES else 0.5,
                    grouping_reason=f"表名前缀 '{prefix}'"
                ))
        
        return groups
    
    def _extract_prefix(self, table_name: str) -> Optional[str]:
        """提取表名前缀"""
        # 移除常见前缀
        for prefix in ["t_", "tb_", "tbl_"]:
            if table_name.startswith(prefix):
                table_name = table_name[len(prefix):]
                break
        
        # 提取第一个下划线前的部分
        parts = table_name.split("_")
        if len(parts) >= 2:
            prefix = parts[0]
            # 检查是否为已知领域
            if prefix in self.DOMAIN_PREFIXES or len(prefix) >= 3:
                return prefix
        
        return None
    
    def _refine_by_relationships(
        self, 
        groups: List[TableGroup], 
        relationships: List[Dict[str, Any]]
    ) -> List[TableGroup]:
        """基于关系优化分组"""
        if not relationships:
            return groups
        
        # 构建关系图
        relation_graph: Dict[str, Set[str]] = defaultdict(set)
        for rel in relationships:
            source = rel["source_table"]
            target = rel["target_table"]
            relation_graph[source].add(target)
            relation_graph[target].add(source)
        
        # 检查是否需要合并组
        refined = []
        merged_indices = set()
        
        for i, group in enumerate(groups):
            if i in merged_indices:
                continue
            
            # 检查与其他组的关联度
            group_tables = set(group.tables)
            
            for j, other_group in enumerate(groups):
                if i >= j or j in merged_indices:
                    continue
                
                other_tables = set(other_group.tables)
                
                # 计算组间关联数
                cross_relations = 0
                for t1 in group_tables:
                    for t2 in relation_graph.get(t1, set()):
                        if t2 in other_tables:
                            cross_relations += 1
                
                # 高关联度则合并
                min_size = min(len(group_tables), len(other_tables))
                if min_size > 0 and cross_relations / min_size > 0.5:
                    # 合并组
                    merged_tables = list(group_tables | other_tables)
                    merged_keywords = list(set(group.keywords + other_group.keywords))
                    
                    group = TableGroup(
                        name=f"{group.name}_{other_group.name}",
                        tables=merged_tables,
                        keywords=merged_keywords,
                        confidence=max(group.confidence, other_group.confidence),
                        grouping_reason=f"合并高关联组: {group.name} + {other_group.name}"
                    )
                    merged_indices.add(j)
            
            refined.append(group)
        
        return refined
    
    def _generate_suggestions(
        self, 
        groups: List[TableGroup],
        all_tables: List[Dict[str, Any]]
    ) -> List[SkillSuggestion]:
        """生成 Skill 建议"""
        suggestions = []
        
        for group in groups:
            # 生成 Skill 名称
            skill_name = self._generate_skill_name(group.name)
            
            # 生成显示名称
            display_name = self._generate_display_name(group.name, group.keywords)
            
            # 生成描述
            description = self._generate_description(group)
            
            suggestions.append(SkillSuggestion(
                name=skill_name,
                display_name=display_name,
                description=description,
                keywords=group.keywords[:10],
                table_names=group.tables,
                confidence=group.confidence,
                reasoning=group.grouping_reason
            ))
        
        # 按置信度排序
        suggestions.sort(key=lambda x: x.confidence, reverse=True)
        
        return suggestions
    
    async def _generate_suggestions_with_llm(
        self, 
        groups: List[TableGroup],
        all_tables: List[Dict[str, Any]]
    ) -> List[SkillSuggestion]:
        """使用 LLM 增强的 Skill 建议生成"""
        try:
            from app.core.llms import get_default_model
            
            suggestions = []
            llm = get_default_model(caller="skill_discovery")
            
            for group in groups:
                # 构建表信息
                table_info = []
                for table_name in group.tables[:10]:
                    table_data = next(
                        (t for t in all_tables if t["table_name"] == table_name), 
                        None
                    )
                    if table_data:
                        desc = table_data.get("description", "")
                        table_info.append(f"- {table_name}: {desc or '无描述'}")
                
                prompt = f"""分析以下数据库表，生成业务领域的名称和描述。

表列表:
{chr(10).join(table_info)}

请返回以下格式（JSON）:
{{
  "name": "英文标识（小写+下划线，如 sales_order）",
  "display_name": "中文显示名称",
  "description": "领域描述（一句话说明处理什么查询）",
  "keywords": ["关键词1", "关键词2", "关键词3"]
}}"""

                response = await llm.ainvoke(prompt)
                
                # 解析响应
                try:
                    import json
                    # 提取 JSON
                    content = response.content
                    json_match = re.search(r'\{[^{}]+\}', content, re.DOTALL)
                    if json_match:
                        data = json.loads(json_match.group())
                        
                        suggestions.append(SkillSuggestion(
                            name=data.get("name", self._generate_skill_name(group.name)),
                            display_name=data.get("display_name", group.name),
                            description=data.get("description", ""),
                            keywords=data.get("keywords", group.keywords)[:10],
                            table_names=group.tables,
                            confidence=min(group.confidence + 0.1, 1.0),
                            reasoning=f"LLM 增强: {group.grouping_reason}"
                        ))
                        continue
                except (json.JSONDecodeError, KeyError) as e:
                    logger.warning(f"LLM 响应解析失败: {e}")
                
                # 解析失败，使用基础方法
                suggestions.append(SkillSuggestion(
                    name=self._generate_skill_name(group.name),
                    display_name=self._generate_display_name(group.name, group.keywords),
                    description=self._generate_description(group),
                    keywords=group.keywords[:10],
                    table_names=group.tables,
                    confidence=group.confidence,
                    reasoning=group.grouping_reason
                ))
            
            return suggestions
            
        except Exception as e:
            logger.warning(f"LLM 建议生成失败: {e}，使用基础方法")
            return self._generate_suggestions(groups, all_tables)
    
    def _generate_skill_name(self, prefix: str) -> str:
        """生成 Skill 名称"""
        # 确保符合命名规范
        name = re.sub(r'[^a-z0-9_]', '_', prefix.lower())
        name = re.sub(r'_+', '_', name).strip('_')
        
        if not name or not name[0].isalpha():
            name = 'skill_' + name
        
        return name[:50]
    
    def _generate_display_name(self, prefix: str, keywords: List[str]) -> str:
        """生成显示名称"""
        if keywords and keywords[0]:
            return f"{keywords[0]}管理"
        
        return f"{prefix.title()} 业务"
    
    def _generate_description(self, group: TableGroup) -> str:
        """生成描述"""
        tables_str = ", ".join(group.tables[:3])
        if len(group.tables) > 3:
            tables_str += f" 等 {len(group.tables)} 个表"
        
        keywords_str = ", ".join(group.keywords[:3]) if group.keywords else group.name
        
        return f"处理与 {keywords_str} 相关的数据查询，包含 {tables_str}"
    
    async def apply_suggestions(
        self, 
        connection_id: int,
        suggestions: List[SkillSuggestion],
        tenant_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        应用建议，创建 Skills
        
        Args:
            connection_id: 数据库连接 ID
            suggestions: 要应用的建议列表
            tenant_id: 租户 ID
            
        Returns:
            创建结果列表
        """
        from app.services.skill_service import skill_service
        
        results = []
        
        for suggestion in suggestions:
            try:
                # 创建 Skill
                skill_data = SkillCreate(
                    name=suggestion.name,
                    display_name=suggestion.display_name,
                    description=suggestion.description,
                    keywords=suggestion.keywords,
                    table_names=suggestion.table_names,
                    connection_id=connection_id
                )
                
                skill = await skill_service.create_skill(skill_data, tenant_id)
                
                results.append({
                    "name": suggestion.name,
                    "success": True,
                    "skill_id": skill.id
                })
                
            except Exception as e:
                results.append({
                    "name": suggestion.name,
                    "success": False,
                    "error": str(e)
                })
        
        return results


# 全局实例
skill_discovery_service = SkillDiscoveryService()
