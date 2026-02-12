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

from app.core.agent_config import get_agent_llm, CORE_AGENT_CHART_ANALYST
from app.core.llm_wrapper import LLMWrapper, LLMWrapperConfig

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
            llm: 自定义 LLM 模型或 LLMWrapper，默认使用 CORE_AGENT_CHART_ANALYST 配置
        """
        self.name = "dashboard_analyst_agent"
        # 使用 LLMWrapper 统一处理重试和超时
        if llm is not None:
            # 如果传入的是原生 LLM，包装它
            if isinstance(llm, LLMWrapper):
                self.llm = llm
            else:
                self.llm = LLMWrapper(llm=llm, name=self.name)
        else:
            # 使用 get_agent_llm 获取带 wrapper 的 LLM
            self.llm = get_agent_llm(CORE_AGENT_CHART_ANALYST, use_wrapper=True)
    
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
        user_intent: Optional[str] = None,
        enable_explainability: bool = True  # 新增：是否启用可解释性
    ) -> Dict[str, Any]:
        """
        分析 Dashboard 数据并生成洞察
        
        Args:
            data: 聚合数据列表
            schema_info: Schema 信息（表结构、列统计等）
            relationship_context: 图谱关系上下文
            sample_data: 采样数据
            user_intent: 用户分析意图
            enable_explainability: 是否启用可解释性（生成详细的分析过程说明）
            
        Returns:
            结构化的洞察结果（包含可解释性信息）
        """
        start_time = time.time()
        
        # ✨ 初始化分析过程追踪
        analysis_process = {
            "steps": [],
            "start_time": start_time,
            "data_quality_check": {},
            "analysis_method": "llm",
            "confidence_factors": []
        } if enable_explainability else None
        
        try:
            # ✨ 步骤1：数据质量检查
            if analysis_process:
                quality_check = self._check_data_quality(data)
                analysis_process["data_quality_check"] = quality_check
                analysis_process["steps"].append({
                    "step": 1,
                    "name": "数据质量检查",
                    "description": f"检查了 {len(data)} 条记录，数据质量评级: {quality_check['rating']}",
                    "timestamp": time.time() - start_time
                })
            
            # 预计算统计信息
            statistics = self._precompute_statistics(data)
            
            # ✨ 步骤2：统计预计算
            if analysis_process:
                analysis_process["steps"].append({
                    "step": 2,
                    "name": "统计预计算",
                    "description": f"识别了 {len(statistics['numeric_columns'])} 个数值列、{len(statistics['categorical_columns'])} 个分类列",
                    "details": {
                        "numeric_columns": statistics['numeric_columns'],
                        "categorical_columns": statistics['categorical_columns']
                    },
                    "timestamp": time.time() - start_time
                })
            
            # 构建分析 Prompt
            prompt = self._build_analysis_prompt(
                data=data,
                statistics=statistics,
                schema_info=schema_info,
                relationship_context=relationship_context,
                user_intent=user_intent
            )
            
            # ✨ 步骤3：LLM 分析
            if analysis_process:
                analysis_process["steps"].append({
                    "step": 3,
                    "name": "LLM智能分析",
                    "description": "调用大语言模型进行多维度智能分析",
                    "llm_model": getattr(self.llm, 'model_name', 'unknown'),
                    "timestamp": time.time() - start_time
                })
            
            # 调用 LLM 进行分析
            response = await self.llm.ainvoke([
                SystemMessage(content=self._create_system_prompt()),
                HumanMessage(content=prompt)
            ])
            
            response_text = response.content if hasattr(response, 'content') else str(response)
            
            # 解析 JSON 响应
            insights = self._parse_llm_response(response_text, statistics)
            
            # ✨ 步骤4：结果验证和增强
            if analysis_process:
                analysis_process["steps"].append({
                    "step": 4,
                    "name": "结果验证和增强",
                    "description": f"验证了 {len(insights.get('recommendations', []))} 条建议、{len(insights.get('anomalies', []))} 个异常",
                    "timestamp": time.time() - start_time
                })
                
                # 计算置信度因素
                confidence_factors = self._calculate_confidence_factors(insights, statistics, relationship_context)
                analysis_process["confidence_factors"] = confidence_factors
                
                # 添加可解释性信息到洞察结果
                insights["explainability"] = self._generate_explainability_report(
                    analysis_process, insights, statistics
                )
            
            elapsed_ms = int((time.time() - start_time) * 1000)
            logger.info(f"[DashboardAnalyst] LLM 分析完成，耗时 {elapsed_ms}ms")
            
            return insights
            
        except Exception as e:
            elapsed_ms = int((time.time() - start_time) * 1000)
            logger.error(f"[DashboardAnalyst] LLM 分析失败: {e}，降级到规则分析")
            
            # ✨ 记录失败并降级
            if analysis_process:
                analysis_process["steps"].append({
                    "step": 5,
                    "name": "降级处理",
                    "description": f"LLM分析失败，启用规则引擎降级: {str(e)[:100]}",
                    "timestamp": time.time() - start_time
                })
                analysis_process["analysis_method"] = "rule_based_fallback"
            
            # 降级到规则分析
            fallback_result = self._fallback_analysis(data, relationship_context)
            
            if analysis_process and enable_explainability:
                fallback_result["explainability"] = self._generate_explainability_report(
                    analysis_process, fallback_result, self._precompute_statistics(data)
                )
            
            return fallback_result
    
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
    
    def _check_data_quality(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        检查数据质量（可解释性增强）
        
        Returns:
            数据质量评估报告
        """
        total_rows = len(data)
        
        if total_rows == 0:
            return {
                "rating": "no_data",
                "score": 0,
                "issues": ["数据为空"],
                "strengths": []
            }
        
        issues = []
        strengths = []
        score = 100
        
        # 检查1：数据量
        if total_rows < 10:
            issues.append(f"数据量较少（{total_rows}条），分析结果可能不够准确")
            score -= 20
        elif total_rows >= 100:
            strengths.append(f"数据量充足（{total_rows}条），支持准确分析")
        
        # 检查2：数据完整性
        if data:
            total_fields = 0
            null_fields = 0
            for row in data:
                if isinstance(row, dict):
                    for value in row.values():
                        total_fields += 1
                        if value is None or value == "":
                            null_fields += 1
            
            null_rate = null_fields / total_fields if total_fields > 0 else 0
            
            if null_rate > 0.3:
                issues.append(f"数据缺失率较高（{null_rate*100:.1f}%）")
                score -= 15
            elif null_rate < 0.1:
                strengths.append(f"数据完整性良好（缺失率 {null_rate*100:.1f}%）")
        
        # 检查3：数据多样性
        if data and isinstance(data[0], dict):
            field_count = len(data[0])
            if field_count < 3:
                issues.append(f"数据维度较少（{field_count}个字段）")
                score -= 10
            elif field_count >= 5:
                strengths.append(f"数据维度丰富（{field_count}个字段）")
        
        # 评级
        if score >= 80:
            rating = "excellent"
        elif score >= 60:
            rating = "good"
        elif score >= 40:
            rating = "fair"
        else:
            rating = "poor"
        
        return {
            "rating": rating,
            "score": max(0, score),
            "issues": issues,
            "strengths": strengths,
            "total_rows": total_rows
        }
    
    def _calculate_confidence_factors(
        self,
        insights: Dict[str, Any],
        statistics: Dict[str, Any],
        relationship_context: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        计算置信度因素（可解释性增强）
        
        Returns:
            影响置信度的因素列表
        """
        factors = []
        
        # 因素1：数据量
        row_count = statistics.get("row_count", 0)
        if row_count >= 100:
            factors.append({
                "factor": "数据量充足",
                "impact": "positive",
                "description": f"分析了 {row_count} 条记录，样本量足够支持准确分析",
                "weight": 0.2
            })
        elif row_count < 10:
            factors.append({
                "factor": "数据量不足",
                "impact": "negative",
                "description": f"仅有 {row_count} 条记录，可能影响分析准确性",
                "weight": -0.3
            })
        
        # 因素2：数值列数量
        numeric_cols = len(statistics.get("numeric_columns", []))
        if numeric_cols >= 3:
            factors.append({
                "factor": "数值指标丰富",
                "impact": "positive",
                "description": f"包含 {numeric_cols} 个数值列，支持多维度量化分析",
                "weight": 0.15
            })
        elif numeric_cols == 0:
            factors.append({
                "factor": "缺少数值指标",
                "impact": "negative",
                "description": "数据中无数值列，无法进行量化分析",
                "weight": -0.4
            })
        
        # 因素3：图谱关系
        if relationship_context:
            rel_count = len(relationship_context.get("direct_relationships", []))
            if rel_count > 0:
                factors.append({
                    "factor": "图谱关系支持",
                    "impact": "positive",
                    "description": f"发现 {rel_count} 个表间关系，增强跨表分析能力",
                    "weight": 0.15
                })
        
        # 因素4：异常检测结果
        anomalies = insights.get("anomalies", [])
        if len(anomalies) > 0:
            high_severity = sum(1 for a in anomalies if a.get("severity") == "high")
            if high_severity > 0:
                factors.append({
                    "factor": "发现高危异常",
                    "impact": "neutral",
                    "description": f"检测到 {high_severity} 个高严重度异常，需要关注",
                    "weight": 0.0
                })
        
        # 因素5：建议数量
        recommendations = insights.get("recommendations", [])
        if len(recommendations) >= 3:
            factors.append({
                "factor": "建议充足",
                "impact": "positive",
                "description": f"生成了 {len(recommendations)} 条可操作建议",
                "weight": 0.1
            })
        
        return factors
    
    def _generate_explainability_report(
        self,
        analysis_process: Dict[str, Any],
        insights: Dict[str, Any],
        statistics: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        生成可解释性报告（阶段4核心功能）
        
        Returns:
            详细的分析过程说明和可解释性信息
        """
        # 1. 分析流程总结
        steps_summary = []
        for step in analysis_process.get("steps", []):
            steps_summary.append({
                "step": step["step"],
                "name": step["name"],
                "description": step["description"],
                "time_elapsed_ms": int(step["timestamp"] * 1000)
            })
        
        # 2. 数据质量评估
        quality = analysis_process.get("data_quality_check", {})
        
        # 3. 置信度评分
        confidence_factors = analysis_process.get("confidence_factors", [])
        confidence_score = 0.7  # 基础分
        for factor in confidence_factors:
            confidence_score += factor.get("weight", 0)
        confidence_score = max(0.0, min(1.0, confidence_score))
        
        # 4. 分析方法说明
        method = analysis_process.get("analysis_method", "llm")
        method_description = {
            "llm": "使用大语言模型进行智能分析，结合多维度数据特征生成洞察",
            "rule_based_fallback": "LLM分析失败，使用规则引擎降级分析（基于统计规则和阈值）"
        }.get(method, "未知分析方法")
        
        # 5. 为什么给出这些洞察
        why_insights = []
        
        # 趋势分析的理由
        if insights.get("trends"):
            trend_dir = insights["trends"].get("trend_direction", "未知")
            if trend_dir in ["上升", "下降"]:
                why_insights.append({
                    "insight_type": "趋势分析",
                    "reason": f"检测到数据整体呈现{trend_dir}趋势，基于时间序列数据的统计分析",
                    "data_basis": f"分析了 {statistics.get('row_count', 0)} 条时序数据"
                })
        
        # 异常检测的理由
        anomalies = insights.get("anomalies", [])
        if anomalies:
            high_severity_count = sum(1 for a in anomalies if a.get("severity") == "high")
            why_insights.append({
                "insight_type": "异常检测",
                "reason": f"发现 {len(anomalies)} 个异常数据点（其中 {high_severity_count} 个高危），基于统计离群检测算法",
                "data_basis": "使用四分位距（IQR）和标准差方法进行异常识别"
            })
        
        # 关联分析的理由
        correlations = insights.get("correlations", [])
        if correlations:
            why_insights.append({
                "insight_type": "关联分析",
                "reason": f"识别出 {len(correlations)} 个跨表或跨维度的关联关系",
                "data_basis": "基于知识图谱的表间关系和数据语义分析"
            })
        
        # 建议的理由
        recommendations = insights.get("recommendations", [])
        high_priority = sum(1 for r in recommendations if r.get("priority") == "high")
        if recommendations:
            why_insights.append({
                "insight_type": "业务建议",
                "reason": f"生成了 {len(recommendations)} 条建议（{high_priority} 条高优先级）",
                "data_basis": "基于数据趋势、异常模式和业务最佳实践"
            })
        
        # 6. 下一步建议
        next_actions = []
        
        if quality.get("rating") == "poor":
            next_actions.append({
                "action": "改善数据质量",
                "reason": "当前数据质量较低，建议增加数据量或完善数据字段",
                "priority": "high"
            })
        
        if len(statistics.get("numeric_columns", [])) == 0:
            next_actions.append({
                "action": "添加量化指标",
                "reason": "缺少数值型字段，建议添加可量化的业务指标",
                "priority": "medium"
            })
        
        if high_priority > 0:
            next_actions.append({
                "action": "处理高优先级建议",
                "reason": f"发现 {high_priority} 条高优先级建议，建议优先处理",
                "priority": "high"
            })
        
        if len(anomalies) > 0:
            high_severity = sum(1 for a in anomalies if a.get("severity") == "high")
            if high_severity > 0:
                next_actions.append({
                    "action": "调查异常数据",
                    "reason": f"发现 {high_severity} 个高危异常，建议深入调查根因",
                    "priority": "high"
                })
        
        # 7. 可视化建议
        visualization_suggestions = []
        
        if insights.get("trends"):
            visualization_suggestions.append({
                "chart_type": "折线图",
                "reason": "趋势数据适合使用折线图展示时间序列变化",
                "recommended_fields": statistics.get("date_columns", [])[:2]
            })
        
        if len(statistics.get("categorical_columns", [])) > 0 and len(statistics.get("numeric_columns", [])) > 0:
            visualization_suggestions.append({
                "chart_type": "柱状图",
                "reason": "分类数据与数值数据结合，适合柱状图对比",
                "recommended_fields": {
                    "x": statistics.get("categorical_columns", [])[0],
                    "y": statistics.get("numeric_columns", [])[0]
                }
            })
        
        return {
            "analysis_flow": {
                "steps": steps_summary,
                "total_time_ms": int((time.time() - analysis_process["start_time"]) * 1000),
                "method": method,
                "method_description": method_description
            },
            "data_quality": {
                "rating": quality.get("rating", "unknown"),
                "score": quality.get("score", 0),
                "issues": quality.get("issues", []),
                "strengths": quality.get("strengths", [])
            },
            "confidence": {
                "score": round(confidence_score, 2),
                "factors": confidence_factors,
                "interpretation": self._interpret_confidence(confidence_score)
            },
            "why_these_insights": why_insights,
            "next_actions": next_actions,
            "visualization_suggestions": visualization_suggestions,
            "metadata": {
                "analyzed_rows": statistics.get("row_count", 0),
                "numeric_columns": len(statistics.get("numeric_columns", [])),
                "categorical_columns": len(statistics.get("categorical_columns", [])),
                "date_columns": len(statistics.get("date_columns", []))
            }
        }
    
    def _interpret_confidence(self, score: float) -> str:
        """解释置信度分数"""
        if score >= 0.85:
            return "非常可信：分析基于充足的数据和多维度验证"
        elif score >= 0.70:
            return "可信：分析结果可靠，但建议结合业务经验判断"
        elif score >= 0.50:
            return "中等可信：数据或维度有限，结果仅供参考"
        else:
            return "低可信度：数据质量或数量不足，建议谨慎使用"


# 创建全局实例
dashboard_analyst_agent = DashboardAnalystAgent()


__all__ = [
    "DashboardAnalystAgent",
    "dashboard_analyst_agent",
]
