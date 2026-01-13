# 导入所有模型以便Alembic可以检测到
from app.models.db_connection import DBConnection
from app.models.schema_table import SchemaTable
from app.models.schema_column import SchemaColumn
from app.models.schema_relationship import SchemaRelationship
from app.models.value_mapping import ValueMapping
from app.models.user import User
from app.models.dashboard import Dashboard
from app.models.dashboard_widget import DashboardWidget
from app.models.dashboard_permission import DashboardPermission
