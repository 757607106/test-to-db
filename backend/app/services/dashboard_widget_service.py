"""Dashboard Widget业务服务"""
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from decimal import Decimal
from datetime import datetime, date
import time

from app import crud
from app.schemas.dashboard_widget import (
    WidgetCreate, WidgetUpdate,
    WidgetResponse, WidgetRefreshResponse
)
from app.models.dashboard_widget import DashboardWidget


def convert_to_json_serializable(obj):
    """
    将数据库返回的对象转换为JSON可序列化的格式
    处理Decimal、datetime、date等特殊类型
    """
    if isinstance(obj, Decimal):
        # 将Decimal转换为float，保持精度
        return float(obj)
    elif isinstance(obj, (datetime, date)):
        # 将日期时间转换为ISO格式字符串
        return obj.isoformat()
    elif isinstance(obj, bytes):
        # 将bytes转换为字符串
        try:
            return obj.decode('utf-8')
        except:
            return str(obj)
    elif obj is None:
        return None
    else:
        return obj


class DashboardWidgetService:
    """Dashboard Widget业务服务类"""

    def create_widget(
        self,
        db: Session,
        *,
        dashboard_id: int,
        obj_in: WidgetCreate,
        user_id: int
    ) -> Optional[DashboardWidget]:
        """创建Widget"""
        # 检查权限
        if not crud.crud_dashboard.check_permission(
            db,
            dashboard_id=dashboard_id,
            user_id=user_id,
            required_level="editor"
        ):
            return None
        
        return crud.crud_dashboard_widget.create_widget(
            db,
            obj_in=obj_in,
            dashboard_id=dashboard_id
        )

    def update_widget(
        self,
        db: Session,
        *,
        widget_id: int,
        obj_in: WidgetUpdate,
        user_id: int
    ) -> Optional[DashboardWidget]:
        """更新Widget"""
        widget = crud.crud_dashboard_widget.get(db, id=widget_id)
        if not widget:
            return None
        
        # 检查权限
        if not crud.crud_dashboard.check_permission(
            db,
            dashboard_id=widget.dashboard_id,
            user_id=user_id,
            required_level="editor"
        ):
            return None
        
        return crud.crud_dashboard_widget.update(db, db_obj=widget, obj_in=obj_in)

    def delete_widget(
        self,
        db: Session,
        *,
        widget_id: int,
        user_id: int
    ) -> bool:
        """删除Widget"""
        widget = crud.crud_dashboard_widget.get(db, id=widget_id)
        if not widget:
            return False
        
        # 检查权限
        if not crud.crud_dashboard.check_permission(
            db,
            dashboard_id=widget.dashboard_id,
            user_id=user_id,
            required_level="editor"
        ):
            return False
        
        crud.crud_dashboard_widget.remove(db, id=widget_id)
        return True

    def refresh_widget(
        self,
        db: Session,
        *,
        widget_id: int,
        user_id: int
    ) -> Optional[WidgetRefreshResponse]:
        """手动刷新Widget数据"""
        widget = crud.crud_dashboard_widget.get(db, id=widget_id)
        if not widget:
            return None
        
        # 检查权限(viewer也可以刷新)
        if not crud.crud_dashboard.check_permission(
            db,
            dashboard_id=widget.dashboard_id,
            user_id=user_id,
            required_level="viewer"
        ):
            return None
        
        # 实际执行SQL查询获取数据
        from app.services.db_service import get_db_connection_by_id, execute_query
        
        start_time = time.time()
        
        try:
            # 获取数据库连接
            connection = get_db_connection_by_id(widget.connection_id)
            if not connection:
                raise Exception(f"数据库连接 {widget.connection_id} 不存在")
            
            # 从query_config中获取SQL
            generated_sql = widget.query_config.get("generated_sql", "")
            if not generated_sql:
                raise Exception("Widget没有有效的SQL查询")
            
            # 执行查询
            result_data = execute_query(connection, generated_sql)
            
            # P0-FIX: 统一数据格式为 {"columns": [...], "data": [...], "row_count": ...}
            if result_data:
                columns = list(result_data[0].keys()) if result_data else []
                # 转换每个值为JSON可序列化格式，使用字典格式
                formatted_data = [
                    {col: convert_to_json_serializable(row[col]) for col in columns}
                    for row in result_data
                ]
                data_cache = {
                    "columns": columns,
                    "data": formatted_data,
                    "row_count": len(formatted_data),
                    "refreshed_at": datetime.utcnow().isoformat()
                }
            else:
                data_cache = {
                    "columns": [],
                    "data": [],
                    "row_count": 0,
                    "refreshed_at": datetime.utcnow().isoformat()
                }
            
        except Exception as e:
            print(f"刷新Widget数据失败: {str(e)}")
            # P0-FIX: 统一错误时的数据格式
            data_cache = {
                "columns": [],
                "data": [],
                "row_count": 0,
                "error": str(e),
                "refreshed_at": datetime.utcnow().isoformat()
            }
        
        updated_widget, duration_ms = crud.crud_dashboard_widget.refresh_data(
            db,
            widget_id=widget_id,
            data_cache=data_cache
        )
        
        if not updated_widget:
            return None
        
        return WidgetRefreshResponse(
            id=updated_widget.id,
            data_cache=updated_widget.data_cache,
            last_refresh_at=updated_widget.last_refresh_at,
            refresh_duration_ms=duration_ms
        )

    def regenerate_widget_query(
        self,
        db: Session,
        *,
        widget_id: int,
        mode: str,
        updated_query: Optional[str],
        parameters: Optional[Dict[str, Any]],
        user_id: int
    ) -> Optional[DashboardWidget]:
        """重新生成Widget查询
        
        Args:
            db: 数据库会话
            widget_id: Widget ID
            mode: 模式 - 'params'只更新参数, 'full'完全重新生成SQL
            updated_query: 更新后的自然语言查询
            parameters: 更新后的参数
            user_id: 用户ID
            
        Returns:
            更新后的Widget对象
        """
        widget = crud.crud_dashboard_widget.get(db, id=widget_id)
        if not widget:
            return None
        
        # 检查权限
        if not crud.crud_dashboard.check_permission(
            db,
            dashboard_id=widget.dashboard_id,
            user_id=user_id,
            required_level="editor"
        ):
            return None
        
        # 构建新的query_config
        new_query_config = widget.query_config.copy() if widget.query_config else {}
        
        if mode == "params":
            # 只更新参数
            if parameters:
                new_query_config["parameters"] = parameters
        elif mode == "full":
            # P1-FIX: 完全重新生成SQL
            if updated_query:
                new_query_config["original_query"] = updated_query
            if parameters:
                new_query_config["parameters"] = parameters
            
            # 调用SQL Generator重新生成SQL
            generated_sql = self._regenerate_sql(
                db=db,
                connection_id=widget.connection_id,
                query=updated_query or new_query_config.get("original_query", ""),
                parameters=parameters
            )
            
            if generated_sql:
                new_query_config["generated_sql"] = generated_sql
                new_query_config["regenerated_at"] = datetime.utcnow().isoformat()
        
        return crud.crud_dashboard_widget.update_query_config(
            db,
            widget_id=widget_id,
            query_config=new_query_config
        )

    def _regenerate_sql(
        self,
        db: Session,
        connection_id: int,
        query: str,
        parameters: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """
        P1-FIX: 调用SQL Generator重新生成SQL
        
        Args:
            db: 数据库会话
            connection_id: 数据库连接ID
            query: 自然语言查询
            parameters: 可选参数
            
        Returns:
            生成的SQL语句，失败返回None
        """
        import asyncio
        import logging
        
        logger = logging.getLogger(__name__)
        
        if not query:
            logger.warning("[_regenerate_sql] 没有提供查询语句")
            return None
        
        try:
            from app.agents.agents.sql_generator_agent import sql_generator_agent
            from app.services.text2sql_utils import retrieve_relevant_schema
            from app.models.db_connection import DBConnection
            from langchain_core.messages import HumanMessage
            
            # 获取数据库类型
            connection = db.query(DBConnection).filter(DBConnection.id == connection_id).first()
            db_type = connection.db_type.lower() if connection else "mysql"
            
            # 获取相关的schema信息
            schema_context = retrieve_relevant_schema(db, connection_id, query)
            
            # 构建state
            state = {
                "messages": [HumanMessage(content=query)],
                "schema_info": schema_context,
                "connection_id": connection_id,
                "db_type": db_type,
                "skip_sample_retrieval": False,
                "error_recovery_context": None,
                "current_stage": "sql_generation",
            }
            
            # 尝试运行async方法
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # 如果已经在事件循环中，使用run_coroutine_threadsafe
                    import concurrent.futures
                    future = asyncio.run_coroutine_threadsafe(
                        sql_generator_agent.process(state),
                        loop
                    )
                    result = future.result(timeout=60)
                else:
                    result = loop.run_until_complete(sql_generator_agent.process(state))
            except RuntimeError:
                # 没有事件循环，创建新的
                result = asyncio.run(sql_generator_agent.process(state))
            
            generated_sql = result.get("generated_sql")
            
            if generated_sql:
                logger.info(f"[_regenerate_sql] SQL生成成功: {generated_sql[:100]}...")
                return generated_sql
            else:
                logger.warning("[_regenerate_sql] SQL Generator未返回SQL")
                return None
                
        except Exception as e:
            logger.error(f"[_regenerate_sql] SQL重新生成失败: {e}")
            return None


# 创建全局实例
dashboard_widget_service = DashboardWidgetService()
