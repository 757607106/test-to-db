"""
Dashboard洞察分析服务
负责数据聚合、条件应用、洞察生成编排
优化：支持异步后台处理
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
import asyncio
from sqlalchemy.orm import Session

from app import crud, schemas
from app.models.dashboard_widget import DashboardWidget
from app.services.graph_relationship_service import graph_relationship_service
from app.db.session import SessionLocal
from app.services.text2sql_utils import retrieve_relevant_schema, format_schema_for_prompt
from app.core.llms import get_default_model
from langchain_core.messages import SystemMessage, HumanMessage

class DashboardInsightService:
    """Dashboard洞察分析服务"""
    
    async def generate_mining_suggestions(self, db: Session, request: schemas.MiningRequest) -> schemas.MiningResponse:
        """生成智能挖掘建议"""
        # 1. 获取上下文
        if request.intent:
            # 如果有明确意图，使用检索增强
            schema_context = retrieve_relevant_schema(db, request.connection_id, request.intent)
        else:
            # 如果没有意图，获取所有表（或者前N个表）
            # 尝试从数据库缓存获取 Schema
            tables = crud.schema_table.get_by_connection(db=db, connection_id=request.connection_id)
            
            # 构建一个简化的 schema_context
            schema_context = {"tables": [], "relationships": []}
            for table in tables[:10]: # 限制前10个表以防 Prompt 过长
                 columns = crud.schema_column.get_by_table(db=db, table_id=table.id)
                 schema_context["tables"].append({
                     "table_name": table.table_name,
                     "columns": [{"column_name": c.column_name, "data_type": c.data_type} for c in columns]
                 })

        # 2. 格式化 Schema
        schema_str = format_schema_for_prompt(schema_context)
        
        # 3. 构建 Prompt
        prompt = f"""
        你是一个智能数据分析师。请基于以下数据库结构，推荐 {request.limit} 个有价值的数据分析视角（图表）。
        
        用户意图：{request.intent or "自动发现关键业务指标和趋势"}
        
        数据库结构：
        {schema_str}
        
        要求：
        1. 推荐的 SQL 必须是合法的 SELECT 语句。
        2. 图表类型从以下选择：bar, line, pie, scatter, table。
        3. 每个推荐都要有明确的业务价值。
        4. SQL 尽量包含聚合分析（SUM, COUNT, AVG, GROUP BY）。
        5. 不要使用未知的表或列。
        """
        
        # 4. 调用 LLM
        try:
            llm = get_default_model().with_structured_output(schemas.MiningResponse)
            response = await llm.ainvoke([
                SystemMessage(content="你是一个专业的数据分析师。"),
                HumanMessage(content=prompt)
            ])
            return response
        except Exception as e:
            print(f"Mining suggestion generation failed: {e}")
            # Fallback empty response
            return schemas.MiningResponse(suggestions=[])

    def trigger_dashboard_insights(
        self,
        db: Session,
        dashboard_id: int,
        user_id: int,
        request: schemas.DashboardInsightRequest
    ) -> schemas.DashboardInsightResponse:
        """
        触发看板洞察生成（创建占位Widget，后续由后台任务处理）
        """
        # 1. 检查权限
        self._check_permission(db, dashboard_id, user_id)
        
        # 2. 获取Dashboard
        dashboard = crud.crud_dashboard.get(db, id=dashboard_id)
        if not dashboard:
            raise ValueError(f"Dashboard {dashboard_id} not found")
            
        # 3. 创建或更新Widget为"分析中"状态
        # 创建初始的空结果
        initial_result = schemas.InsightResult(
            summary=schemas.InsightSummary(total_rows=0, key_metrics={}, time_range="分析中..."),
            trends=None, anomalies=[], correlations=[], recommendations=[]
        )
        
        # 创建或更新 Widget (同步)
        widget_id = self._create_or_update_insight_widget(
            db,
            dashboard_id,
            initial_result,
            request.conditions,
            request.use_graph_relationships,
            analyzed_widget_count=0,
            status="processing" # 标记为处理中
        )
        
        return schemas.DashboardInsightResponse(
            widget_id=widget_id,
            insights=initial_result,
            analyzed_widget_count=0,
            analysis_timestamp=datetime.utcnow(),
            applied_conditions=request.conditions,
            relationship_count=0,
            status="processing" # 新增状态字段
        )

    async def process_dashboard_insights_task(
        self,
        dashboard_id: int,
        user_id: int,
        request: schemas.DashboardInsightRequest,
        widget_id: int
    ):
        """
        后台任务：执行实际的洞察分析逻辑
        """
        db = SessionLocal()
        try:
            print(f"🚀 开始后台洞察分析 Task (Dashboard: {dashboard_id})")
            
            # 1. 获取数据
            dashboard = crud.crud_dashboard.get(db, id=dashboard_id)
            widgets = dashboard.widgets
            
            # 筛选Widgets
            if request.included_widget_ids:
                widgets = [w for w in widgets if w.id in request.included_widget_ids]
            
            data_widgets = [w for w in widgets if w.widget_type != "insight_analysis"]
            
            if not data_widgets:
                print("⚠️ 无有效数据组件，跳过分析")
                return

            # 2. 聚合数据
            aggregated_data = self._aggregate_widget_data(data_widgets, request.conditions)
            
            # 3. 图谱查询
            relationship_context = None
            relationship_count = 0
            if request.use_graph_relationships and aggregated_data["table_names"]:
                try:
                    connection_id = data_widgets[0].connection_id
                    relationship_context = graph_relationship_service.query_table_relationships(
                        connection_id,
                        aggregated_data["table_names"]
                    )
                    relationship_count = relationship_context.get("relationship_count", 0)
                except Exception as e:
                    print(f"⚠️ 图谱关系查询失败: {e}")

            # 4. 简化的洞察分析（不使用dashboard_analyst_agent）
            insights = schemas.InsightResult(
                summary=schemas.InsightSummary(
                    total_rows=aggregated_data["total_rows"],
                    key_metrics={},
                    time_range="已分析"
                ),
                trends=None,
                anomalies=[],
                correlations=[],
                recommendations=[
                    schemas.InsightRecommendation(
                        type="info",
                        content=f"已分析 {len(data_widgets)} 个数据组件",
                        priority="medium"
                    )
                ]
            )
            
            # 5. 更新 Widget 状态为完成
            self._update_insight_widget_result(
                db, 
                widget_id, 
                insights, 
                len(data_widgets),
                status="completed"
            )
            
            print(f"✅ 后台洞察分析完成 (Widget: {widget_id})")
            
        except Exception as e:
            print(f"❌ 后台洞察分析失败: {str(e)}")
            # 更新状态为失败
            self._update_widget_status(db, widget_id, "failed", str(e))
        finally:
            db.close()

    def _check_permission(self, db: Session, dashboard_id: int, user_id: int):
        has_permission = crud.crud_dashboard.check_permission(
            db, dashboard_id=dashboard_id, user_id=user_id, required_level="viewer"
        )
        if not has_permission:
            raise PermissionError("No permission to view this dashboard")

    def _aggregate_widget_data(
        self,
        widgets: List[DashboardWidget],
        conditions: Optional[schemas.InsightConditions]
    ) -> Dict[str, Any]:
        """聚合Widget数据"""
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
            
            # 提取表名
            if widget.query_config:
                if "table_name" in widget.query_config:
                    table_names.add(widget.query_config["table_name"])
            
            # 提取列信息
            if filtered_data:
                first_row = filtered_data[0]
                for key, value in first_row.items():
                    if isinstance(value, (int, float)):
                        numeric_columns.add(key)
                    elif isinstance(value, str):
                        if any(keyword in key.lower() for keyword in ["date", "time", "created", "updated"]):
                            date_columns.add(key)
            
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
        """应用查询条件过滤数据"""
        if not conditions:
            return data
        
        filtered_data = data.copy()
        
        # 时间范围过滤
        if conditions.time_range:
            date_column = None
            if filtered_data:
                first_row = filtered_data[0]
                for key in first_row.keys():
                    if any(keyword in key.lower() for keyword in ["date", "time", "created"]):
                        date_column = key
                        break
            
            if date_column and conditions.time_range.start and conditions.time_range.end:
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
    
    def _create_or_update_insight_widget(
        self,
        db: Session,
        dashboard_id: int,
        insights: schemas.InsightResult,
        conditions: Optional[schemas.InsightConditions],
        use_graph_relationships: bool,
        analyzed_widget_count: int,
        status: str = "completed"
    ) -> int:
        """创建或更新洞察Widget"""
        existing_widgets = crud.crud_dashboard_widget.get_by_dashboard(db, dashboard_id=dashboard_id)
        
        insight_widget = None
        for widget in existing_widgets:
            if widget.widget_type == "insight_analysis":
                insight_widget = widget
                break
        
        query_config = {
            "analysis_scope": "all_widgets",
            "analysis_dimensions": ["summary", "trends", "correlations", "recommendations"],
            "refresh_strategy": "manual",
            "last_analysis_at": datetime.utcnow().isoformat(),
            "use_graph_relationships": use_graph_relationships,
            "analyzed_widget_count": analyzed_widget_count,
            "status": status # 状态
        }
        
        if conditions:
            query_config["current_conditions"] = conditions.dict(exclude_none=True)
        
        data_cache = insights.dict(exclude_none=True)
        
        if insight_widget:
            crud.crud_dashboard_widget.update(
                db,
                db_obj=insight_widget,
                obj_in=schemas.WidgetUpdate(title="看板洞察分析")
            )
            insight_widget.query_config = query_config
            insight_widget.data_cache = data_cache
            insight_widget.last_refresh_at = datetime.utcnow()
            db.commit()
            db.refresh(insight_widget)
            return insight_widget.id
        else:
            widget_create = schemas.WidgetCreate(
                widget_type="insight_analysis",
                title="看板洞察分析",
                connection_id=1,
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

    def _update_insight_widget_result(self, db: Session, widget_id: int, insights: schemas.InsightResult, count: int, status: str):
        widget = crud.crud_dashboard_widget.get(db, id=widget_id)
        if widget:
            query_config = widget.query_config or {}
            query_config["status"] = status
            query_config["analyzed_widget_count"] = count
            query_config["last_analysis_at"] = datetime.utcnow().isoformat()
            
            widget.query_config = query_config
            widget.data_cache = insights.dict(exclude_none=True)
            widget.last_refresh_at = datetime.utcnow()
            db.commit()

    def _update_widget_status(self, db: Session, widget_id: int, status: str, error: str = None):
        widget = crud.crud_dashboard_widget.get(db, id=widget_id)
        if widget:
            query_config = widget.query_config or {}
            query_config["status"] = status
            if error:
                query_config["error"] = error
            widget.query_config = query_config
            db.commit()

# 创建全局实例
dashboard_insight_service = DashboardInsightService()
