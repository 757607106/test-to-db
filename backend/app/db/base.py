# Import all the models, so that Base has them before being
# imported by Alembic
from app.db.base_class import Base  # noqa
from app.models.user import User  # noqa
from app.models.db_connection import DBConnection  # noqa
from app.models.schema_table import SchemaTable  # noqa
from app.models.schema_column import SchemaColumn  # noqa
from app.models.schema_relationship import SchemaRelationship  # noqa
from app.models.value_mapping import ValueMapping  # noqa
from app.models.dashboard import Dashboard  # noqa
from app.models.dashboard_widget import DashboardWidget  # noqa
from app.models.dashboard_permission import DashboardPermission  # noqa
from app.models.llm_config import LLMConfiguration  # noqa
from app.models.agent_profile import AgentProfile  # noqa
from app.models.query_history import QueryHistory  # noqa
