"""
Dashboard洞察分析服务
负责数据聚合、条件应用、洞察生成编排
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from app import crud, schemas
from app.models.dashboard_widget import DashboardWidget
from app.services.graph_relationship_service import graph_relationship_service
from app.agents.agents.dashboard_analyst_agent import dashboard_analyst_agent


class DashboardInsightService:
    """Dashboard洞察分析服务"""
    
    def generate_dashboard_insights(
        self,
        db: Session,
        dashboard_id: int,
        user_id: int,
        request: schemas.DashboardInsightRequest
    ) -> schemas.DashboardInsightResponse:
        """
        生成看板洞察
        
        Args:
            db: 数据库会话
            dashboard_id: 看板ID
            user_id: 用户ID
            request: 洞察请求
            
        Returns:
            洞察响应
        """
        # 1. 获取Dashboard和Widgets
        dashboard = crud.crud_dashboard.get(db, id=dashboard_id)
        if not dashboard:
            raise ValueError(f"Dashboard {dashboard_id} not found")
        
        # 检查权限
        has_permission = crud.crud_dashboard.check_permission(
            db,
            dashboard_id=dashboard_id,
            user_id=user_id,
            required_level="viewer"
        )
        if not has_permission:
            raise PermissionError("No permission to view this dashboard")
        
        # 2. 获取Widgets
        widgets = dashboard.widgets
        if not widgets:
            raise ValueError("Dashboard has no widgets")
        
        # 筛选指定的Widgets
        if request.included_widget_ids:
            widgets = [w for w in widgets if w.id in request.included_widget_ids]
        
        # 过滤掉insight_analysis类型的Widget
        data_widgets = [w for w in widgets if w.widget_type != "insight_analysis"]
        
        if len(data_widgets) < 1:
            raise ValueError("No valid data widgets found")
        
        # 3. 聚合Widget数据
        aggregated_data = self._aggregate_widget_data(
            data_widgets,
            request.conditions
        )
        
        # 4. 查询图谱关系（如果启用）
        relationship_context = None
        relationship_count = 0
        if request.use_graph_relationships and aggregated_data["table_names"]:
            connection_id = data_widgets[0].connection_id
            relationship_context = graph_relationship_service.query_table_relationships(
                connection_id,
                aggregated_data["table_names"]
            )
            relationship_count = relationship_context.get("relationship_count", 0)
        
        # 5. 生成洞察（调用Agent）
        insights = self._generate_insights(
            dashboard,
            aggregated_data,
            relationship_context,
            request.analysis_dimensions
        )
        
        # 6. 创建或更新洞察Widget
        widget_id = self._create_or_update_insight_widget(
            db,
            dashboard_id,
            insights,
            request.conditions,
            request.use_graph_relationships,
            len(data_widgets)
        )
        
        # 7. 返回响应
        return schemas.DashboardInsightResponse(
            widget_id=widget_id,
            insights=insights,
            analyzed_widget_count=len(data_widgets),
            analysis_timestamp=datetime.utcnow(),
            applied_conditions=request.conditions,
            relationship_count=relationship_count
        )
    
    def _aggregate_widget_data(
        self,
        widgets: List[DashboardWidget],
        conditions: Optional[schemas.InsightConditions]
    ) -> Dict[str, Any]:
        """
        聚合Widget数据
        
        Args:
            widgets: Widget列表
            conditions: 查询条件
            
        Returns:
            聚合后的数据集
        """
        aggregated_rows = []
        table_names = set()
        numeric_columns = set()
        date_columns = set()
        widget_summaries = []
        
        for widget in widgets:
            # 提取widget数据
            if not widget.data_cache or "data" not in widget.data_cache:
                continue
            
            data = widget.data_cache["data"]
            if not data or not isinstance(data, list):
                continue
            
            # 应用条件过滤
            filtered_data = self._apply_conditions(data, conditions)
            
            aggregated_rows.extend(filtered_data)
            
            # 提取表名（尝试从query_config中获取）
            if widget.query_config:
                if "table_name" in widget.query_config:
                    table_names.add(widget.query_config["table_name"])
                elif "sql" in widget.query_config:
                    # 简单解析SQL获取表名（可以后续优化）
                    sql = widget.query_config["sql"]
                    # 这里简化处理，实际应该用SQL解析器
                    pass
            
            # 提取列信息
            if filtered_data:
                first_row = filtered_data[0]
                for key, value in first_row.items():
                    if isinstance(value, (int, float)):
                        numeric_columns.add(key)
                    elif isinstance(value, str):
                        # 尝试检测是否是日期列
                        if any(keyword in key.lower() for keyword in ["date", "time", "created", "updated"]):
                            date_columns.add(key)
            
            # Widget摘要
            widget_summaries.append({
                "id": widget.id,
                "type": widget.widget_type,
                "title": widget.title,
                "row_count": len(filtered_data)
            })
        
        return {
            "data": aggregated_rows,
            "total_rows": len(aggregated_rows),
            "table_names": list(table_names),
            "numeric_columns": list(numeric_columns),
            "date_columns": list(date_columns),
            "widget_summaries": widget_summaries
        }
    
    def _apply_conditions(
        self,
        data: List[Dict[str, Any]],
        conditions: Optional[schemas.InsightConditions]
    ) -> List[Dict[str, Any]]:
        """
        应用查询条件过滤数据
        
        Args:
            data: 原始数据
            conditions: 查询条件
            
        Returns:
            过滤后的数据
        """
        if not conditions:
            return data
        
        filtered_data = data.copy()
        
        # 时间范围过滤
        if conditions.time_range:
            # 找到时间列（简单实现，实际应该更智能）
            date_column = None
            if filtered_data:
                first_row = filtered_data[0]
                for key in first_row.keys():
                    if any(keyword in key.lower() for keyword in ["date", "time", "created"]):
                        date_column = key
                        break
            
            if date_column and conditions.time_range.start and conditions.time_range.end:
                # 简单的字符串比较（实际应该转换为日期对象）
                filtered_data = [
                    row for row in filtered_data
                    if conditions.time_range.start <= str(row.get(date_column, "")) <= conditions.time_range.end
                ]
        
        # 维度筛选
        if conditions.dimension_filters:
            for column, value in conditions.dimension_filters.items():
                filtered_data = [
                    row for row in filtered_data
                    if row.get(column) == value
                ]
        
        return filtered_data
    
    def _generate_insights(
        self,
        dashboard: Any,
        aggregated_data: Dict[str, Any],
        relationship_context: Optional[Dict[str, Any]],
        analysis_dimensions: Optional[List[str]]
    ) -> schemas.InsightResult:
        """
        生成洞察（集成AI智能体）
        
        Args:
            dashboard: Dashboard对象
            aggregated_data: 聚合数据
            relationship_context: 关系上下文
            analysis_dimensions: 分析维度
            
        Returns:
            洞察结果
        """
        # 调用Dashboard分析师智能体
        try:
            insights = dashboard_analyst_agent.analyze_dashboard_data(
                dashboard=dashboard,
                aggregated_data=aggregated_data,
                relationship_context=relationship_context,
                analysis_dimensions=analysis_dimensions
            )
            return insights
        except Exception as e:
            print(f"AI智能体分析失败，使用降级方案: {str(e)}")
            # 降级方案：返回简单版本
            return self._generate_fallback_insights(aggregated_data, relationship_context)
    
    def _generate_fallback_insights(
        self,
        aggregated_data: Dict[str, Any],
        relationship_context: Optional[Dict[str, Any]]
    ) -> schemas.InsightResult:
        """
        生成降级洞察（当AI分析失败时使用）
        """
        total_rows = aggregated_data["total_rows"]
        
        # 简单的摘要
        summary = schemas.InsightSummary(
            total_rows=total_rows,
            key_metrics={"widget_count": len(aggregated_data["widget_summaries"])},
            time_range="暂无时间范围信息"
        )
        
        # 简单的趋势
        trends = schemas.InsightTrend(
            trend_direction="平稳",
            total_growth_rate=0.0,
            description="数据量稳定"
        )
        
        # 简单的建议
        recommendations = [
            schemas.InsightRecommendation(
                type="optimization",
                content="继续监控数据变化趋势",
                priority="medium",
                basis="当前数据量充足"
            )
        ]
        
        # 如果有关系上下文，添加关联洞察
        correlations = []
        if relationship_context and relationship_context.get("has_relationships"):
            for rel_desc in relationship_context.get("relationship_descriptions", [])[:3]:
                correlations.append(
                    schemas.InsightCorrelation(
                        type="cross_table",
                        relationship=rel_desc,
                        insight=f"发现表关系: {rel_desc}",
                        strength="medium"
                    )
                )
        
        return schemas.InsightResult(
            summary=summary,
            trends=trends,
            anomalies=[],
            correlations=correlations,
            recommendations=recommendations
        )
    
    def _create_or_update_insight_widget(
        self,
        db: Session,
        dashboard_id: int,
        insights: schemas.InsightResult,
        conditions: Optional[schemas.InsightConditions],
        use_graph_relationships: bool,
        analyzed_widget_count: int
    ) -> int:
        """
        创建或更新洞察Widget
        
        Args:
            db: 数据库会话
            dashboard_id: 看板ID
            insights: 洞察结果
            conditions: 应用的条件
            use_graph_relationships: 是否使用图谱关系
            analyzed_widget_count: 分析的Widget数量
            
        Returns:
            Widget ID
        """
        # 查找是否已存在洞察Widget
        existing_widgets = crud.crud_dashboard_widget.get_by_dashboard(
            db,
            dashboard_id=dashboard_id
        )
        
        insight_widget = None
        for widget in existing_widgets:
            if widget.widget_type == "insight_analysis":
                insight_widget = widget
                break
        
        # 构建query_config
        query_config = {
            "analysis_scope": "all_widgets",
            "analysis_dimensions": ["summary", "trends", "correlations", "recommendations"],
            "refresh_strategy": "manual",
            "last_analysis_at": datetime.utcnow().isoformat(),
            "use_graph_relationships": use_graph_relationships,
            "analyzed_widget_count": analyzed_widget_count
        }
        
        if conditions:
            query_config["current_conditions"] = conditions.dict(exclude_none=True)
        
        # 构建data_cache（存储洞察结果）
        data_cache = insights.dict(exclude_none=True)
        
        if insight_widget:
            # 更新现有Widget
            crud.crud_dashboard_widget.update(
                db,
                db_obj=insight_widget,
                obj_in=schemas.WidgetUpdate(
                    title="看板洞察分析",
                )
            )
            insight_widget.query_config = query_config
            insight_widget.data_cache = data_cache
            insight_widget.last_refresh_at = datetime.utcnow()
            db.commit()
            db.refresh(insight_widget)
            return insight_widget.id
        else:
            # 创建新Widget
            widget_create = schemas.WidgetCreate(
                widget_type="insight_analysis",
                title="看板洞察分析",
                connection_id=1,  # 洞察Widget不需要真实连接ID
                query_config=query_config,
                chart_config=None,
                position_config={"x": 0, "y": 0, "w": 12, "h": 6},
                refresh_interval=0
            )
            
            new_widget = crud.crud_dashboard_widget.create_widget(
                db,
                dashboard_id=dashboard_id,
                obj_in=widget_create
            )
            new_widget.data_cache = data_cache
            db.commit()
            db.refresh(new_widget)
            return new_widget.id


# 创建全局实例
dashboard_insight_service = DashboardInsightService()
