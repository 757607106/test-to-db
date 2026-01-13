"""
Dashboard分析师代理
扩展现有AnalystAgent，支持多Widget分析和图谱关系增强
"""
from typing import Dict, Any, List, Optional
import json

from langchain_core.messages import HumanMessage
from app.core.llms import get_default_model
from app.services.analyst_utils import calculate_statistics, detect_time_series, calculate_growth_rate
from app import schemas


class DashboardAnalystAgent:
    """Dashboard分析师代理"""
    
    def __init__(self):
        self.llm = get_default_model()
    
    def analyze_dashboard_data(
        self,
        dashboard: Any,
        aggregated_data: Dict[str, Any],
        relationship_context: Optional[Dict[str, Any]] = None,
        analysis_dimensions: Optional[List[str]] = None
    ) -> schemas.InsightResult:
        """
        分析看板数据，生成综合洞察
        
        Args:
            dashboard: Dashboard对象
            aggregated_data: 聚合后的数据
            relationship_context: 图谱关系上下文
            analysis_dimensions: 分析维度
            
        Returns:
            洞察结果
        """
        data = aggregated_data.get("data", [])
        total_rows = aggregated_data.get("total_rows", 0)
        
        # 规则判断分析级别
        analysis_level = self._determine_analysis_level(aggregated_data)
        
        if analysis_level == "skip":
            return self._create_minimal_insights(total_rows)
        
        # 计算统计信息
        stats = calculate_statistics(data) if data else {}
        
        # 检测时间序列
        time_series_info = detect_time_series(data) if data else None
        
        # 构建Prompt并调用LLM
        insights_dict = self._generate_insights_with_llm(
            dashboard,
            aggregated_data,
            stats,
            time_series_info,
            relationship_context,
            analysis_level
        )
        
        # 转换为Schema对象
        return self._convert_to_insight_result(insights_dict)
    
    def _determine_analysis_level(self, aggregated_data: Dict[str, Any]) -> str:
        """确定分析级别"""
        total_rows = aggregated_data.get("total_rows", 0)
        widget_count = len(aggregated_data.get("widget_summaries", []))
        
        if total_rows < 2 or widget_count == 0:
            return "skip"
        
        if total_rows > 1000:
            return "summary_only"
        
        if widget_count >= 2:
            return "full_analysis"
        
        return "basic_analysis"
    
    def _generate_insights_with_llm(
        self,
        dashboard: Any,
        aggregated_data: Dict[str, Any],
        stats: Dict[str, Any],
        time_series_info: Optional[Dict[str, Any]],
        relationship_context: Optional[Dict[str, Any]],
        analysis_level: str
    ) -> Dict[str, Any]:
        """使用LLM生成洞察"""
        
        # 构建数据特征描述
        data_characteristics = self._build_data_characteristics(aggregated_data, stats)
        
        # 构建关系上下文描述
        relationship_desc = self._build_relationship_description(relationship_context)
        
        # 构建Widget摘要
        widget_summaries = self._build_widget_summaries(aggregated_data)
        
        # 构建Prompt
        prompt = self._build_llm_prompt(
            dashboard,
            data_characteristics,
            widget_summaries,
            relationship_desc,
            time_series_info,
            analysis_level
        )
        
        # 调用LLM
        try:
            response = self.llm.invoke([HumanMessage(content=prompt)])
            content = response.content.strip()
            
            # 提取JSON
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            result = json.loads(content)
            return result
            
        except Exception as e:
            print(f"LLM生成洞察失败: {str(e)}")
            return self._create_fallback_insights(aggregated_data, stats)
    
    def _build_data_characteristics(
        self,
        aggregated_data: Dict[str, Any],
        stats: Dict[str, Any]
    ) -> str:
        """构建数据特征描述"""
        total_rows = aggregated_data.get("total_rows", 0)
        numeric_cols = ', '.join(stats.get('numeric_columns', [])[:5]) or "无"
        date_cols = ', '.join(stats.get('date_columns', [])[:3]) or "无"
        
        return f"""- 总数据量: {total_rows}
- 数值列: {numeric_cols}
- 日期列: {date_cols}"""
    
    def _build_widget_summaries(self, aggregated_data: Dict[str, Any]) -> str:
        """构建Widget摘要"""
        summaries = aggregated_data.get("widget_summaries", [])
        if not summaries:
            return "无组件信息"
        
        lines = []
        for idx, summary in enumerate(summaries, 1):
            lines.append(
                f"- Widget {idx}: {summary['title']} ({summary['type']}) - {summary['row_count']}行"
            )
        
        return "\n".join(lines)
    
    def _build_relationship_description(
        self,
        relationship_context: Optional[Dict[str, Any]]
    ) -> str:
        """构建关系描述"""
        if not relationship_context or not relationship_context.get("has_relationships"):
            return "暂无表关系信息"
        
        rel_count = relationship_context.get("relationship_count", 0)
        rel_descs = relationship_context.get("relationship_descriptions", [])
        
        lines = [f"发现 {rel_count} 个表关系:"]
        for rel_desc in rel_descs[:5]:  # 最多显示5个
            lines.append(f"- {rel_desc}")
        
        return "\n".join(lines)
    
    def _build_llm_prompt(
        self,
        dashboard: Any,
        data_characteristics: str,
        widget_summaries: str,
        relationship_desc: str,
        time_series_info: Optional[Dict[str, Any]],
        analysis_level: str
    ) -> str:
        """构建LLM Prompt"""
        
        dashboard_name = getattr(dashboard, 'name', '未命名看板')
        dashboard_desc = getattr(dashboard, 'description', '无描述')
        
        time_info = ""
        if time_series_info and time_series_info.get("has_time_series"):
            date_range = time_series_info.get("date_range", {})
            time_info = f"\n- 时间范围: {date_range.get('start', '')} 至 {date_range.get('end', '')}"
        
        prompt = f"""你是一个专业的BI数据洞察分析师，正在分析一个业务看板。

看板信息：
- 看板名称：{dashboard_name}
- 看板描述：{dashboard_desc}

组件数据摘要：
{widget_summaries}

聚合数据特征：
{data_characteristics}{time_info}

数据库表关系信息：
{relationship_desc}

请基于以上信息，生成综合的业务洞察分析，包括：
1. 数据摘要（重点指标汇总，2-3句话）
2. 趋势分析（如有时间序列数据，描述趋势方向）
3. 异常检测（识别数据中的异常模式，如果有）
4. 关联洞察（利用表关系信息，发现跨表业务关联）
5. 业务建议（3-5条可执行建议，优先级从高到低）

输出JSON格式：
{{
  "summary": {{
    "total_rows": 数值,
    "key_metrics": {{"指标名": 值}},
    "time_range": "范围描述"
  }},
  "trends": {{
    "trend_direction": "上升/下降/平稳",
    "total_growth_rate": 数值,
    "description": "趋势描述"
  }},
  "anomalies": [
    {{
      "type": "异常类型",
      "column": "列名",
      "description": "异常描述",
      "severity": "high/medium/low"
    }}
  ],
  "correlations": [
    {{
      "type": "cross_table",
      "tables": ["table1", "table2"],
      "relationship": "关系描述",
      "insight": "关联洞察描述",
      "strength": "strong/medium/weak"
    }}
  ],
  "recommendations": [
    {{
      "type": "optimization/warning/opportunity",
      "content": "建议内容",
      "priority": "high/medium/low",
      "basis": "建议依据"
    }}
  ]
}}

只返回JSON，不要其他内容。"""
        
        return prompt
    
    def _create_fallback_insights(
        self,
        aggregated_data: Dict[str, Any],
        stats: Dict[str, Any]
    ) -> Dict[str, Any]:
        """创建降级洞察（LLM失败时使用）"""
        total_rows = aggregated_data.get("total_rows", 0)
        widget_count = len(aggregated_data.get("widget_summaries", []))
        
        return {
            "summary": {
                "total_rows": total_rows,
                "key_metrics": {"widget_count": widget_count},
                "time_range": "暂无时间信息"
            },
            "trends": {
                "trend_direction": "平稳",
                "total_growth_rate": 0.0,
                "description": "数据量稳定"
            },
            "anomalies": [],
            "correlations": [],
            "recommendations": [
                {
                    "type": "optimization",
                    "content": "继续监控数据变化趋势",
                    "priority": "medium",
                    "basis": "当前数据分析基于规则生成"
                }
            ]
        }
    
    def _create_minimal_insights(self, total_rows: int) -> schemas.InsightResult:
        """创建最小洞察"""
        return schemas.InsightResult(
            summary=schemas.InsightSummary(
                total_rows=total_rows,
                key_metrics={},
                time_range="数据不足"
            ),
            trends=None,
            anomalies=[],
            correlations=[],
            recommendations=[
                schemas.InsightRecommendation(
                    type="optimization",
                    content="需要更多数据才能生成有效洞察",
                    priority="low"
                )
            ]
        )
    
    def _convert_to_insight_result(self, insights_dict: Dict[str, Any]) -> schemas.InsightResult:
        """将字典转换为InsightResult Schema"""
        
        # 转换summary
        summary_data = insights_dict.get("summary", {})
        summary = schemas.InsightSummary(
            total_rows=summary_data.get("total_rows"),
            key_metrics=summary_data.get("key_metrics"),
            time_range=summary_data.get("time_range")
        )
        
        # 转换trends
        trends_data = insights_dict.get("trends")
        trends = None
        if trends_data:
            trends = schemas.InsightTrend(
                trend_direction=trends_data.get("trend_direction"),
                total_growth_rate=trends_data.get("total_growth_rate"),
                description=trends_data.get("description")
            )
        
        # 转换anomalies
        anomalies = []
        for anomaly_data in insights_dict.get("anomalies", []):
            anomalies.append(schemas.InsightAnomaly(
                type=anomaly_data.get("type", "unknown"),
                column=anomaly_data.get("column"),
                description=anomaly_data.get("description", ""),
                severity=anomaly_data.get("severity")
            ))
        
        # 转换correlations
        correlations = []
        for corr_data in insights_dict.get("correlations", []):
            correlations.append(schemas.InsightCorrelation(
                type=corr_data.get("type", "cross_widget"),
                tables=corr_data.get("tables"),
                relationship=corr_data.get("relationship"),
                insight=corr_data.get("insight", ""),
                strength=corr_data.get("strength")
            ))
        
        # 转换recommendations
        recommendations = []
        for rec_data in insights_dict.get("recommendations", []):
            recommendations.append(schemas.InsightRecommendation(
                type=rec_data.get("type", "optimization"),
                content=rec_data.get("content", ""),
                priority=rec_data.get("priority"),
                basis=rec_data.get("basis")
            ))
        
        return schemas.InsightResult(
            summary=summary,
            trends=trends,
            anomalies=anomalies,
            correlations=correlations,
            recommendations=recommendations
        )


# 创建全局实例
dashboard_analyst_agent = DashboardAnalystAgent()
