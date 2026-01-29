"""
Dashboard 洞察分析智能体 (Dashboard Analyst Agent)

专门用于分析 Dashboard 聚合数据，生成智能洞察报告。

职责：
1. 分析聚合数据，提取关键业务指标
2. 识别趋势、异常和模式
3. 利用图谱关系生成跨表关联洞察
4. 提供可操作的业务建议

架构位置：
- 被 dashboard_insight_graph.py 中的 insight_analyzer_node 调用
- 支持降级机制：LLM失败时使用规则分析
"""
import json
import logging
import re
import time
from typing import Dict, Any, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage

from app.core.llms import get_default_model
from app.core.agent_config import get_agent_llm, CORE_AGENT_CHART_ANALYST

logger = logging.getLogger(__name__)


class DashboardAnalystAgent:
    """
    Dashboard 洞察分析智能体
    
    职责：
    - 分析 Dashboard 聚合数据
    - 结合图谱关系生成跨表洞察
    - 输出结构化的洞察报告
    """
    
    def __init__(self, llm=None):
        """
        初始化 Dashboard 分析专家
        
        Args:
            llm: 自定义 LLM 模型，默认使用 CORE_AGENT_CHART_ANALYST 配置
        """
        self.name = "dashboard_analyst_agent"
        self.llm = llm or get_agent_llm(CORE_AGENT_CHART_ANALYST)
    
    def _create_system_prompt(self) -> str:
        """创建系统提示词"""
        return """你是一位专业的商业智能分析师，负责分析 Dashboard 数据并生成有价值的业务洞察。

**分析维度** (必须输出以下所有维度):

1. **数据摘要 (Summary)**: 
   - 数据总量和关键指标概览
   - 数据质量评估
   - 时间范围说明

2. **趋势分析 (Trends)**:
   - 识别增长/下降趋势
   - 计算增长率
   - 识别关键拐点或周期性变化

3. **异常检测 (Anomalies)**:
   - 识别离群值和异常数据点
   - 描述异常模式
   - 评估异常严重程度 (high/medium/low)

4. **关联洞察 (Correlations)**:
   - 分析不同维度之间的关联
   - 识别跨表数据的业务关联
   - 评估关联强度 (strong/medium/weak)

5. **业务建议 (Recommendations)**:
   - 基于数据的优化建议
   - 风险预警
   - 机会识别
   - 优先级排序 (high/medium/low)

**输出格式** (必须严格遵守 JSON 格式):

```json
{
  "summary": {
    "total_rows": 数值,
    "key_metrics": {"指标名": {"sum": 值, "avg": 值, "max": 值, "min": 值}},
    "time_range": "描述",
    "data_quality": "good/fair/poor",
    "description": "一句话概述"
  },
  "trends": {
    "trend_direction": "上升/下降/平稳",
    "total_growth_rate": 数值或null,
    "description": "趋势描述"
  },
  "anomalies": [
    {"type": "异常类型", "column": "列名", "description": "描述", "severity": "high/medium/low"}
  ],
  "correlations": [
    {"type": "cross_table/cross_widget", "tables": ["表1", "表2"], "relationship": "关系描述", "insight": "洞察内容", "strength": "strong/medium/weak"}
  ],
  "recommendations": [
    {"type": "optimization/warning/opportunity", "content": "建议内容", "priority": "high/medium/low", "basis": "建议依据"}
  ]
}
```

**注意事项**:
- 洞察必须基于数据事实，不要臆测
- 如果某个维度无法分析，返回空数组或null
- 保持简洁专业，每个洞察点控制在 1-2 句话
- 优先分析业务价值高的指标"""

    async def analyze(
        self,
        data: List[Dict[str, Any]],
        schema_info: Optional[Dict[str, Any]] = None,
        relationship_context: Optional[Dict[str, Any]] = None,
        sample_data: Optional[Dict[str, List]] = None,
        user_intent: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        分析 Dashboard 数据并生成洞察
        
        Args:
            data: 聚合数据列表
            schema_info: Schema 信息（表结构、列统计等）
            relationship_context: 图谱关系上下文
            sample_data: 采样数据
            user_intent: 用户分析意图
            
        Returns:
            结构化的洞察结果
        """
        start_time = time.time()
        
        try:
            # 预计算统计信息
            statistics = self._precompute_statistics(data)
            
            # 构建分析 Prompt
            prompt = self._build_analysis_prompt(
                data=data,
                statistics=statistics,
                schema_info=schema_info,
                relationship_context=relationship_context,
                user_intent=user_intent
            )
            
            # 调用 LLM 进行分析
            response = await self.llm.ainvoke([
                SystemMessage(content=self._create_system_prompt()),
                HumanMessage(content=prompt)
            ])
            
            response_text = response.content if hasattr(response, 'content') else str(response)
            
            # 解析 JSON 响应
            insights = self._parse_llm_response(response_text, statistics)
            
            elapsed_ms = int((time.time() - start_time) * 1000)
            logger.info(f"[DashboardAnalyst] LLM 分析完成，耗时 {elapsed_ms}ms")
            
            return insights
            
        except Exception as e:
            elapsed_ms = int((time.time() - start_time) * 1000)
            logger.error(f"[DashboardAnalyst] LLM 分析失败: {e}，降级到规则分析")
            
            # 降级到规则分析
            return self._fallback_analysis(data, relationship_context)
    
    def _precompute_statistics(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        预计算统计指标
        
        Args:
            data: 数据列表
            
        Returns:
            统计信息字典
        """
        stats = {
            "row_count": len(data),
            "numeric_columns": [],
            "categorical_columns": [],
            "date_columns": [],
            "column_stats": {}
        }
        
        if not data:
            return stats
        
        # 获取所有列名
        all_columns = set()
        for row in data:
            if isinstance(row, dict):
                all_columns.update(row.keys())
        
        for col in all_columns:
            values = [row.get(col) for row in data if row.get(col) is not None]
            if not values:
                continue
            
            # 检测数值列
            numeric_values = []
            for v in values:
                try:
                    if isinstance(v, (int, float)):
                        numeric_values.append(float(v))
                    elif isinstance(v, str):
                        cleaned = v.replace(',', '').replace('%', '')
                        if cleaned.replace('.', '').replace('-', '').isdigit():
                            numeric_values.append(float(cleaned))
                except (ValueError, TypeError):
                    pass
            
            if len(numeric_values) > len(values) * 0.7:  # 70%+ 是数值
                stats["numeric_columns"].append(col)
                if numeric_values:
                    stats["column_stats"][col] = {
                        "type": "numeric",
                        "min": min(numeric_values),
                        "max": max(numeric_values),
                        "avg": round(sum(numeric_values) / len(numeric_values), 2),
                        "sum": sum(numeric_values),
                        "count": len(numeric_values)
                    }
            else:
                # 检测日期列
                date_keywords = ["date", "time", "日期", "时间", "created", "updated", "at"]
                if any(kw in col.lower() for kw in date_keywords):
                    stats["date_columns"].append(col)
                else:
                    stats["categorical_columns"].append(col)
                    # 统计分类值分布
                    value_counts = {}
                    for v in values:
                        v_str = str(v)[:50]  # 截断过长的值
                        value_counts[v_str] = value_counts.get(v_str, 0) + 1
                    stats["column_stats"][col] = {
                        "type": "categorical",
                        "unique_count": len(value_counts),
                        "top_values": sorted(value_counts.items(), key=lambda x: -x[1])[:5]
                    }
        
        return stats
    
    def _build_analysis_prompt(
        self,
        data: List[Dict[str, Any]],
        statistics: Dict[str, Any],
        schema_info: Optional[Dict[str, Any]] = None,
        relationship_context: Optional[Dict[str, Any]] = None,
        user_intent: Optional[str] = None
    ) -> str:
        """构建分析 Prompt"""
        
        # 限制数据量
        data_preview = data[:30] if len(data) > 30 else data
        data_str = json.dumps(data_preview, ensure_ascii=False, default=str, indent=2)
        
        # 格式化统计信息
        stats_str = f"""
数据统计:
- 总行数: {statistics['row_count']}
- 数值列: {', '.join(statistics['numeric_columns']) or '无'}
- 分类列: {', '.join(statistics['categorical_columns']) or '无'}
- 日期列: {', '.join(statistics['date_columns']) or '无'}
"""
        
        # 格式化列统计详情
        if statistics.get("column_stats"):
            stats_str += "\n列统计详情:\n"
            for col, stat in statistics["column_stats"].items():
                if stat.get("type") == "numeric":
                    stats_str += f"  - {col}: 最小={stat['min']}, 最大={stat['max']}, 平均={stat['avg']}, 总和={stat['sum']}\n"
                elif stat.get("type") == "categorical":
                    top_vals = ", ".join([f"{v[0]}({v[1]}次)" for v in stat.get("top_values", [])[:3]])
                    stats_str += f"  - {col}: {stat['unique_count']}个唯一值, TOP3: {top_vals}\n"
        
        # 格式化图谱关系
        relationship_str = ""
        if relationship_context:
            direct_rels = relationship_context.get("direct_relationships", [])
            if direct_rels:
                relationship_str = "\n表间关系（来自知识图谱）:\n"
                for rel in direct_rels[:10]:  # 最多显示10个关系
                    src_table = rel.get("source_table", "")
                    src_col = rel.get("source_column", "")
                    tgt_table = rel.get("target_table", "")
                    tgt_col = rel.get("target_column", "")
                    relationship_str += f"  - {src_table}.{src_col} -> {tgt_table}.{tgt_col}\n"
        
        # 格式化 Schema 信息
        schema_str = ""
        if schema_info:
            tables = schema_info.get("tables", [])
            if tables:
                schema_str = "\nSchema 信息:\n"
                for t in tables[:5]:  # 最多显示5个表
                    table_name = t.get("name", t.get("table_name", ""))
                    desc = t.get("description", "")
                    schema_str += f"  - {table_name}: {desc}\n"
        
        # 用户意图
        intent_str = f"\n分析意图: {user_intent}" if user_intent else "\n分析意图: 自动发现关键业务指标和趋势"
        
        return f"""请分析以下 Dashboard 数据并生成洞察报告。
{intent_str}
{stats_str}
{schema_str}
{relationship_str}

数据内容（最多30行）:
{data_str}

请严格按照 JSON 格式输出分析结果。"""

    def _parse_llm_response(
        self,
        response_text: str,
        statistics: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        解析 LLM 响应
        
        Args:
            response_text: LLM 返回的文本
            statistics: 预计算的统计信息
            
        Returns:
            结构化的洞察结果
        """
        # 清理 markdown 代码块
        cleaned = response_text.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()
        
        try:
            # 尝试直接解析 JSON
            parsed = json.loads(cleaned)
            
            # 验证并补充必要字段
            insights = {
                "summary": parsed.get("summary") or self._create_default_summary(statistics),
                "trends": parsed.get("trends"),
                "anomalies": parsed.get("anomalies", []),
                "correlations": parsed.get("correlations", []),
                "recommendations": parsed.get("recommendations", [])
            }
            
            return insights
            
        except json.JSONDecodeError as e:
            logger.warning(f"JSON 解析失败: {e}，尝试提取 JSON 块")
            
            # 尝试从文本中提取 JSON 块
            json_match = re.search(r'\{[\s\S]*\}', cleaned)
            if json_match:
                try:
                    parsed = json.loads(json_match.group(0))
                    return {
                        "summary": parsed.get("summary") or self._create_default_summary(statistics),
                        "trends": parsed.get("trends"),
                        "anomalies": parsed.get("anomalies", []),
                        "correlations": parsed.get("correlations", []),
                        "recommendations": parsed.get("recommendations", [])
                    }
                except json.JSONDecodeError:
                    pass
            
            # 解析失败，使用降级方案
            logger.warning("LLM 响应解析失败，使用降级方案")
            return self._create_default_summary(statistics)
    
    def _create_default_summary(self, statistics: Dict[str, Any]) -> Dict[str, Any]:
        """创建默认的摘要信息"""
        key_metrics = {}
        for col, stat in statistics.get("column_stats", {}).items():
            if stat.get("type") == "numeric":
                key_metrics[col] = {
                    "sum": stat.get("sum", 0),
                    "avg": stat.get("avg", 0),
                    "max": stat.get("max", 0),
                    "min": stat.get("min", 0)
                }
        
        return {
            "summary": {
                "total_rows": statistics.get("row_count", 0),
                "key_metrics": key_metrics,
                "time_range": "已分析",
                "data_quality": "good" if statistics.get("row_count", 0) > 0 else "no_data",
                "description": f"共分析 {statistics.get('row_count', 0)} 条数据"
            },
            "trends": None,
            "anomalies": [],
            "correlations": [],
            "recommendations": [
                {
                    "type": "info",
                    "content": f"成功分析 {statistics.get('row_count', 0)} 条数据",
                    "priority": "medium"
                }
            ]
        }
    
    def _fallback_analysis(
        self,
        data: List[Dict[str, Any]],
        relationship_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        降级分析：LLM 失败时使用规则分析
        
        Args:
            data: 数据列表
            relationship_context: 图谱关系上下文
            
        Returns:
            基于规则的洞察结果
        """
        statistics = self._precompute_statistics(data)
        row_count = len(data)
        
        # 构建 key_metrics
        key_metrics = {}
        for col, stat in statistics.get("column_stats", {}).items():
            if stat.get("type") == "numeric":
                key_metrics[col] = {
                    "sum": stat.get("sum", 0),
                    "avg": stat.get("avg", 0),
                    "max": stat.get("max", 0),
                    "min": stat.get("min", 0)
                }
        
        # 构建摘要
        summary = {
            "total_rows": row_count,
            "key_metrics": key_metrics,
            "time_range": "已分析",
            "data_quality": "good" if row_count > 0 else "no_data",
            "description": f"共分析 {row_count} 条数据，包含 {len(statistics.get('numeric_columns', []))} 个数值列"
        }
        
        # 简单趋势检测（如果有日期列和数值列）
        trends = None
        if statistics.get("date_columns") and statistics.get("numeric_columns"):
            trends = {
                "trend_direction": "待分析",
                "total_growth_rate": None,
                "description": f"数据包含时间维度 ({', '.join(statistics['date_columns'][:2])})，可进行趋势分析"
            }
        
        # 异常检测（基于简单规则）
        anomalies = []
        for col, stat in statistics.get("column_stats", {}).items():
            if stat.get("type") == "numeric":
                # 检测极值差异
                if stat.get("max", 0) > stat.get("avg", 1) * 10:
                    anomalies.append({
                        "type": "outlier",
                        "column": col,
                        "description": f"{col} 存在极大值 ({stat['max']})，远超平均值 ({stat['avg']})",
                        "severity": "medium"
                    })
        
        # 基于图谱关系生成关联洞察
        correlations = []
        if relationship_context:
            direct_rels = relationship_context.get("direct_relationships", [])
            for rel in direct_rels[:5]:  # 最多5个关联洞察
                src_table = rel.get("source_table", "")
                tgt_table = rel.get("target_table", "")
                if src_table and tgt_table:
                    correlations.append({
                        "type": "cross_table",
                        "tables": [src_table, tgt_table],
                        "relationship": f"{src_table} 与 {tgt_table} 存在外键关联",
                        "insight": f"可分析 {src_table} 和 {tgt_table} 之间的业务关联",
                        "strength": "medium"
                    })
        
        # 建议
        recommendations = []
        if row_count > 0:
            recommendations.append({
                "type": "info",
                "content": f"成功分析 {row_count} 条数据",
                "priority": "medium",
                "basis": "数据分析完成"
            })
        
        if statistics.get("numeric_columns"):
            recommendations.append({
                "type": "optimization",
                "content": f"建议重点关注数值指标: {', '.join(statistics['numeric_columns'][:3])}",
                "priority": "medium",
                "basis": "数据包含多个数值列"
            })
        
        if correlations:
            recommendations.append({
                "type": "opportunity",
                "content": f"发现 {len(correlations)} 个表间关联，可进行跨表分析",
                "priority": "high",
                "basis": "图谱关系分析"
            })
        
        return {
            "summary": summary,
            "trends": trends,
            "anomalies": anomalies,
            "correlations": correlations,
            "recommendations": recommendations
        }


# 创建全局实例
dashboard_analyst_agent = DashboardAnalystAgent()


__all__ = [
    "DashboardAnalystAgent",
    "dashboard_analyst_agent",
]
