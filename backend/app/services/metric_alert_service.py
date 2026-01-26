"""
指标告警服务 (Metric Alert Service)

提供指标告警的 CRUD 和告警检测功能：
- 阈值告警：当指标超过/低于设定值时触发
- 同比告警：与去年同期对比变化超过阈值时触发
- 环比告警：与上期对比变化超过阈值时触发
"""
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging
import uuid

from neo4j import GraphDatabase

from app.core.config import settings
from app.schemas.metric import (
    MetricAlertCreate, MetricAlertUpdate, MetricAlert, AlertCheckResult
)

logger = logging.getLogger(__name__)


class MetricAlertService:
    """指标告警服务"""
    
    def __init__(self):
        self.driver = None
        self._initialized = False
    
    def _get_driver(self):
        """获取 Neo4j 驱动"""
        if not self.driver:
            self.driver = GraphDatabase.driver(
                settings.NEO4J_URI,
                auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
            )
        return self.driver
    
    async def initialize(self):
        """初始化服务"""
        if self._initialized:
            return
        
        try:
            driver = self._get_driver()
            with driver.session() as session:
                # 创建 MetricAlert 节点的唯一约束
                session.run("""
                    CREATE CONSTRAINT metric_alert_id IF NOT EXISTS
                    FOR (a:MetricAlert) REQUIRE a.id IS UNIQUE
                """)
                logger.info("MetricAlert service initialized")
            self._initialized = True
        except Exception as e:
            logger.warning(f"Failed to create constraints: {e}")
            self._initialized = True
    
    # ===== CRUD 操作 =====
    
    async def create_alert(self, alert_data: MetricAlertCreate) -> MetricAlert:
        """创建告警规则"""
        await self.initialize()
        
        alert_id = f"alert_{uuid.uuid4().hex[:12]}"
        now = datetime.now()
        
        driver = self._get_driver()
        with driver.session() as session:
            # 创建 MetricAlert 节点
            session.run("""
                CREATE (a:MetricAlert {
                    id: $id,
                    name: $name,
                    metric_id: $metric_id,
                    alert_type: $alert_type,
                    condition: $condition,
                    threshold_value: $threshold_value,
                    change_percent: $change_percent,
                    enabled: $enabled,
                    notify_channels: $notify_channels,
                    created_at: datetime($created_at),
                    last_triggered_at: null,
                    trigger_count: 0
                })
            """,
                id=alert_id,
                name=alert_data.name,
                metric_id=alert_data.metric_id,
                alert_type=alert_data.alert_type,
                condition=alert_data.condition,
                threshold_value=alert_data.threshold_value,
                change_percent=alert_data.change_percent,
                enabled=alert_data.enabled,
                notify_channels=alert_data.notify_channels,
                created_at=now.isoformat()
            )
            
            # 创建与 Metric 的关系
            session.run("""
                MATCH (a:MetricAlert {id: $alert_id})
                MATCH (m:Metric {id: $metric_id})
                MERGE (a)-[:MONITORS]->(m)
            """,
                alert_id=alert_id,
                metric_id=alert_data.metric_id
            )
            
            logger.info(f"Created alert: {alert_data.name} for metric {alert_data.metric_id}")
            
            return MetricAlert(
                id=alert_id,
                name=alert_data.name,
                metric_id=alert_data.metric_id,
                alert_type=alert_data.alert_type,
                condition=alert_data.condition,
                threshold_value=alert_data.threshold_value,
                change_percent=alert_data.change_percent,
                enabled=alert_data.enabled,
                notify_channels=alert_data.notify_channels,
                created_at=now,
                last_triggered_at=None,
                trigger_count=0
            )
    
    async def get_alert(self, alert_id: str) -> Optional[MetricAlert]:
        """获取单个告警"""
        await self.initialize()
        
        driver = self._get_driver()
        with driver.session() as session:
            result = session.run("""
                MATCH (a:MetricAlert {id: $alert_id})
                RETURN a
            """, alert_id=alert_id)
            
            record = result.single()
            if not record:
                return None
            
            return self._build_alert_from_record(record["a"])
    
    async def get_alerts_by_metric(self, metric_id: str) -> List[MetricAlert]:
        """获取指标的所有告警"""
        await self.initialize()
        
        driver = self._get_driver()
        with driver.session() as session:
            result = session.run("""
                MATCH (a:MetricAlert {metric_id: $metric_id})
                RETURN a
                ORDER BY a.created_at DESC
            """, metric_id=metric_id)
            
            alerts = []
            for record in result:
                alerts.append(self._build_alert_from_record(record["a"]))
            
            return alerts
    
    async def update_alert(
        self,
        alert_id: str,
        update_data: MetricAlertUpdate
    ) -> Optional[MetricAlert]:
        """更新告警"""
        await self.initialize()
        
        set_clauses = []
        params = {"alert_id": alert_id}
        
        update_dict = update_data.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            if value is not None:
                params[field] = value
                set_clauses.append(f"a.{field} = ${field}")
        
        if not set_clauses:
            return await self.get_alert(alert_id)
        
        driver = self._get_driver()
        with driver.session() as session:
            result = session.run(f"""
                MATCH (a:MetricAlert {{id: $alert_id}})
                SET {', '.join(set_clauses)}
                RETURN a
            """, **params)
            
            record = result.single()
            if not record:
                return None
            
            logger.info(f"Updated alert: {alert_id}")
            return self._build_alert_from_record(record["a"])
    
    async def delete_alert(self, alert_id: str) -> bool:
        """删除告警"""
        await self.initialize()
        
        driver = self._get_driver()
        with driver.session() as session:
            result = session.run("""
                MATCH (a:MetricAlert {id: $alert_id})
                DETACH DELETE a
                RETURN count(a) AS deleted
            """, alert_id=alert_id)
            
            record = result.single()
            deleted = record["deleted"] > 0
            
            if deleted:
                logger.info(f"Deleted alert: {alert_id}")
            
            return deleted
    
    async def toggle_alert(self, alert_id: str, enabled: bool) -> Optional[MetricAlert]:
        """启用/禁用告警"""
        await self.initialize()
        
        driver = self._get_driver()
        with driver.session() as session:
            result = session.run("""
                MATCH (a:MetricAlert {id: $alert_id})
                SET a.enabled = $enabled
                RETURN a
            """, alert_id=alert_id, enabled=enabled)
            
            record = result.single()
            if not record:
                return None
            
            return self._build_alert_from_record(record["a"])
    
    # ===== 告警检测 =====
    
    async def check_alert(
        self,
        alert: MetricAlert,
        current_value: float,
        previous_value: Optional[float] = None,
        yoy_value: Optional[float] = None
    ) -> AlertCheckResult:
        """
        检查告警是否触发
        
        Args:
            alert: 告警规则
            current_value: 当前值
            previous_value: 上期值（用于环比）
            yoy_value: 去年同期值（用于同比）
        """
        triggered = False
        threshold_or_change = 0.0
        message = ""
        
        if alert.alert_type == "threshold":
            # 阈值告警
            threshold = alert.threshold_value or 0
            triggered = self._check_condition(current_value, alert.condition, threshold)
            threshold_or_change = threshold
            message = f"当前值 {current_value} {'触发' if triggered else '未触发'}阈值告警 ({alert.condition} {threshold})"
            
        elif alert.alert_type == "mom":
            # 环比告警
            if previous_value and previous_value != 0:
                change = ((current_value - previous_value) / abs(previous_value)) * 100
                threshold = alert.change_percent or 0
                triggered = self._check_condition(abs(change), alert.condition, threshold)
                threshold_or_change = change
                message = f"环比变化 {change:.2f}% {'触发' if triggered else '未触发'}告警 (阈值 {threshold}%)"
            else:
                message = "无法计算环比（缺少上期数据）"
                
        elif alert.alert_type == "yoy":
            # 同比告警
            if yoy_value and yoy_value != 0:
                change = ((current_value - yoy_value) / abs(yoy_value)) * 100
                threshold = alert.change_percent or 0
                triggered = self._check_condition(abs(change), alert.condition, threshold)
                threshold_or_change = change
                message = f"同比变化 {change:.2f}% {'触发' if triggered else '未触发'}告警 (阈值 {threshold}%)"
            else:
                message = "无法计算同比（缺少去年同期数据）"
        
        # 如果触发，更新触发记录
        if triggered:
            await self._record_trigger(alert.id)
        
        return AlertCheckResult(
            alert_id=alert.id,
            metric_id=alert.metric_id,
            metric_name=alert.name,
            triggered=triggered,
            current_value=current_value,
            threshold_or_change=threshold_or_change,
            message=message,
            checked_at=datetime.now()
        )
    
    def _check_condition(self, value: float, condition: str, threshold: float) -> bool:
        """检查条件"""
        if condition == "gt":
            return value > threshold
        elif condition == "lt":
            return value < threshold
        elif condition == "gte":
            return value >= threshold
        elif condition == "lte":
            return value <= threshold
        elif condition == "eq":
            return value == threshold
        return False
    
    async def _record_trigger(self, alert_id: str):
        """记录告警触发"""
        driver = self._get_driver()
        with driver.session() as session:
            session.run("""
                MATCH (a:MetricAlert {id: $alert_id})
                SET a.last_triggered_at = datetime($now),
                    a.trigger_count = a.trigger_count + 1
            """, alert_id=alert_id, now=datetime.now().isoformat())
    
    # ===== 辅助方法 =====
    
    def _build_alert_from_record(self, node: Dict[str, Any]) -> MetricAlert:
        """从 Neo4j 记录构建 MetricAlert 对象"""
        created_at = node.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        elif hasattr(created_at, "to_native"):
            created_at = created_at.to_native()
        
        last_triggered_at = node.get("last_triggered_at")
        if isinstance(last_triggered_at, str):
            last_triggered_at = datetime.fromisoformat(last_triggered_at.replace("Z", "+00:00"))
        elif hasattr(last_triggered_at, "to_native"):
            last_triggered_at = last_triggered_at.to_native()
        
        return MetricAlert(
            id=node["id"],
            name=node["name"],
            metric_id=node["metric_id"],
            alert_type=node["alert_type"],
            condition=node["condition"],
            threshold_value=node.get("threshold_value"),
            change_percent=node.get("change_percent"),
            enabled=node.get("enabled", True),
            notify_channels=node.get("notify_channels", []),
            created_at=created_at,
            last_triggered_at=last_triggered_at,
            trigger_count=node.get("trigger_count", 0)
        )
    
    def close(self):
        """关闭连接"""
        if self.driver:
            self.driver.close()
            self.driver = None


# 创建全局实例
metric_alert_service = MetricAlertService()
