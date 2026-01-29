"""
Dashboard刷新服务
P1功能：实现动态数据刷新机制，包括全局刷新和定时刷新
优化：增加并发限流，防止数据库压力过大
"""
import asyncio
import time
import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from app import crud, schemas
from app.models.dashboard_widget import DashboardWidget

logger = logging.getLogger(__name__)

# 并发限制配置
MAX_CONCURRENT_REFRESHES = 5  # 最大并发刷新数
REFRESH_TIMEOUT_SECONDS = 60  # 单个 Widget 刷新超时时间


class DashboardRefreshService:
    """Dashboard刷新服务"""
    
    def __init__(self):
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT_REFRESHES)
    
    async def global_refresh(
        self,
        db: Session,
        dashboard_id: int,
        force: bool = False,
        widget_ids: Optional[List[int]] = None
    ) -> schemas.GlobalRefreshResponse:
        """
        执行全局刷新（带并发限流）
        
        Args:
            db: 数据库会话
            dashboard_id: Dashboard ID
            force: 是否强制刷新(忽略缓存)
            widget_ids: 指定刷新的Widget ID列表，为空则刷新全部
            
        Returns:
            GlobalRefreshResponse: 刷新结果
        """
        start_time = time.time()
        logger.info(f"开始全局刷新 Dashboard {dashboard_id}, force={force}")
        
        # 获取所有需要刷新的Widget
        all_widgets = crud.crud_dashboard_widget.get_by_dashboard(db, dashboard_id=dashboard_id)
        
        # 过滤洞察分析类型的Widget
        data_widgets = [w for w in all_widgets if w.widget_type != "insight_analysis"]
        
        # 如果指定了widget_ids，则只刷新指定的Widget
        if widget_ids:
            data_widgets = [w for w in data_widgets if w.id in widget_ids]
        
        if not data_widgets:
            return schemas.GlobalRefreshResponse(
                success_count=0,
                failed_count=0,
                results={},
                total_duration_ms=0,
                refresh_timestamp=datetime.utcnow()
            )
        
        logger.info(f"需要刷新 {len(data_widgets)} 个 Widget，并发限制: {MAX_CONCURRENT_REFRESHES}")
        
        # 使用信号量限制并发
        results: Dict[int, schemas.WidgetRefreshResult] = {}
        success_count = 0
        failed_count = 0
        
        # 创建带限流的刷新任务
        async def refresh_with_limit(widget: DashboardWidget):
            async with self._semaphore:
                return await self._refresh_single_widget(db, widget, force)
        
        # 使用asyncio.gather并行执行（受信号量限制）
        refresh_tasks = [
            asyncio.wait_for(
                refresh_with_limit(widget),
                timeout=REFRESH_TIMEOUT_SECONDS
            )
            for widget in data_widgets
        ]
        
        task_results = await asyncio.gather(*refresh_tasks, return_exceptions=True)
        
        for widget, result in zip(data_widgets, task_results):
            if isinstance(result, asyncio.TimeoutError):
                results[widget.id] = schemas.WidgetRefreshResult(
                    widget_id=widget.id,
                    success=False,
                    error=f"刷新超时（>{REFRESH_TIMEOUT_SECONDS}秒）",
                    duration_ms=REFRESH_TIMEOUT_SECONDS * 1000
                )
                failed_count += 1
            elif isinstance(result, Exception):
                results[widget.id] = schemas.WidgetRefreshResult(
                    widget_id=widget.id,
                    success=False,
                    error=str(result),
                    duration_ms=0
                )
                failed_count += 1
            else:
                results[widget.id] = result
                if result.success:
                    success_count += 1
                else:
                    failed_count += 1
        
        total_duration_ms = int((time.time() - start_time) * 1000)
        logger.info(f"全局刷新完成: 成功={success_count}, 失败={failed_count}, 耗时={total_duration_ms}ms")
        
        return schemas.GlobalRefreshResponse(
            success_count=success_count,
            failed_count=failed_count,
            results=results,
            total_duration_ms=total_duration_ms,
            refresh_timestamp=datetime.utcnow()
        )
    
    async def _refresh_single_widget(
        self,
        db: Session,
        widget: DashboardWidget,
        force: bool = False
    ) -> schemas.WidgetRefreshResult:
        """
        刷新单个Widget
        
        P1-FIX: 使用run_in_executor将同步操作转为异步，避免阻塞事件循环
        
        Args:
            db: 数据库会话
            widget: Widget对象
            force: 是否强制刷新
            
        Returns:
            WidgetRefreshResult: 刷新结果
        """
        start_time = time.time()
        widget_id = widget.id
        
        try:
            # 获取Widget的SQL配置
            query_config = widget.query_config or {}
            sql = query_config.get("generated_sql")
            
            if not sql:
                return schemas.WidgetRefreshResult(
                    widget_id=widget_id,
                    success=False,
                    error="Widget没有配置SQL查询",
                    duration_ms=0
                )
            
            # P1-FIX: 使用run_in_executor执行同步的SQL查询
            loop = asyncio.get_event_loop()
            result_json = await loop.run_in_executor(
                None,  # 使用默认线程池
                self._execute_sql_sync,
                sql,
                widget.connection_id,
                force
            )
            
            result = json.loads(result_json)
            elapsed_ms = int((time.time() - start_time) * 1000)
            
            if result.get("success"):
                data = result.get("data", {})
                rows = data.get("data", [])
                columns = data.get("columns", [])
                
                # 格式化数据
                formatted_data = []
                for row in rows:
                    if isinstance(row, list) and len(row) == len(columns):
                        formatted_data.append(dict(zip(columns, row)))
                    elif isinstance(row, dict):
                        formatted_data.append(row)
                
                # 更新Widget的data_cache
                widget.data_cache = {
                    "data": formatted_data,
                    "columns": columns,
                    "row_count": len(formatted_data),
                    "refreshed_at": datetime.utcnow().isoformat()
                }
                widget.last_refresh_at = datetime.utcnow()
                db.commit()
                
                return schemas.WidgetRefreshResult(
                    widget_id=widget_id,
                    success=True,
                    duration_ms=elapsed_ms,
                    from_cache=result.get("from_cache", False),
                    row_count=len(formatted_data)
                )
            else:
                return schemas.WidgetRefreshResult(
                    widget_id=widget_id,
                    success=False,
                    error=result.get("error", "SQL执行失败"),
                    duration_ms=elapsed_ms
                )
                
        except Exception as e:
            elapsed_ms = int((time.time() - start_time) * 1000)
            logger.error(f"刷新Widget {widget_id} 失败: {e}")
            return schemas.WidgetRefreshResult(
                widget_id=widget_id,
                success=False,
                error=str(e),
                duration_ms=elapsed_ms
            )

    def _execute_sql_sync(
        self,
        sql: str,
        connection_id: int,
        force: bool
    ) -> str:
        """
        同步执行SQL查询（在线程池中运行）
        
        Args:
            sql: SQL语句
            connection_id: 连接ID
            force: 是否强制刷新
            
        Returns:
            JSON格式的结果字符串
        """
        from app.agents.agents.sql_executor_agent import execute_sql_query
        
        return execute_sql_query.invoke({
            "sql_query": sql,
            "connection_id": connection_id,
            "timeout": 30,
            "force_refresh": force
        })
    
    def get_refresh_config(self, db: Session, dashboard_id: int) -> schemas.RefreshConfig:
        """
        获取Dashboard的刷新配置
        
        P1-8修复: 直接从独立字段读取，不再遍历layout_config
        
        Args:
            db: 数据库会话
            dashboard_id: Dashboard ID
            
        Returns:
            RefreshConfig: 刷新配置
        """
        dashboard = crud.crud_dashboard.get(db, id=dashboard_id)
        if not dashboard:
            return schemas.RefreshConfig()
        
        # P1-8修复: 直接从refresh_config字段读取
        refresh_config = dashboard.refresh_config
        
        if refresh_config:
            return schemas.RefreshConfig(
                enabled=refresh_config.get("enabled", False),
                interval_seconds=refresh_config.get("interval_seconds", 300),
                auto_refresh_widget_ids=refresh_config.get("auto_refresh_widget_ids", []),
                last_global_refresh=refresh_config.get("last_global_refresh")
            )
        
        return schemas.RefreshConfig()
    
    def update_refresh_config(
        self,
        db: Session,
        dashboard_id: int,
        config: schemas.RefreshConfig
    ) -> schemas.RefreshConfig:
        """
        更新Dashboard的刷新配置
        
        P1-8修复: 直接更新独立字段，不再操作layout_config
        
        Args:
            db: 数据库会话
            dashboard_id: Dashboard ID
            config: 新的刷新配置
            
        Returns:
            RefreshConfig: 更新后的配置
        """
        dashboard = crud.crud_dashboard.get(db, id=dashboard_id)
        if not dashboard:
            raise ValueError(f"Dashboard {dashboard_id} not found")
        
        # P1-8修复: 直接更新refresh_config字段
        config_dict = config.dict()
        if config_dict.get("last_global_refresh"):
            config_dict["last_global_refresh"] = config_dict["last_global_refresh"].isoformat()
        
        dashboard.refresh_config = config_dict
        db.commit()
        db.refresh(dashboard)
        
        logger.info(f"已更新Dashboard {dashboard_id} 的刷新配置")
        return config


# 创建全局实例
dashboard_refresh_service = DashboardRefreshService()
