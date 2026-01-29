"""添加Dashboard刷新配置独立字段

Revision ID: 007_add_dashboard_refresh_config
Revises: 006_add_join_rules_to_skills
Create Date: 2024-01-29 10:00:00.000000

P1-8修复: 将刷新配置从layout_config提升为独立字段
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '007_add_dashboard_refresh_config'
down_revision = '006_add_join_rules_to_skills'
branch_labels = None
depends_on = None


def upgrade():
    """添加refresh_config字段并迁移数据"""
    # 1. 添加新字段
    op.add_column(
        'dashboards',
        sa.Column('refresh_config', sa.JSON(), nullable=True, comment='刷新配置(独立存储)')
    )
    
    # 2. 从layout_config迁移刷新配置数据
    # 使用原生SQL处理JSON数据
    connection = op.get_bind()
    
    # 获取所有dashboard
    result = connection.execute(sa.text("SELECT id, layout_config FROM dashboards"))
    dashboards = result.fetchall()
    
    for dashboard in dashboards:
        dashboard_id = dashboard[0]
        layout_config = dashboard[1]
        
        if not layout_config:
            continue
            
        # 解析layout_config，查找refresh_config项
        import json
        try:
            if isinstance(layout_config, str):
                layout_items = json.loads(layout_config)
            else:
                layout_items = layout_config
            
            if not isinstance(layout_items, list):
                continue
                
            # 找到刷新配置项并提取
            refresh_config = None
            new_layout_items = []
            
            for item in layout_items:
                if isinstance(item, dict) and item.get("type") == "refresh_config":
                    # 移除type字段，保留其他配置
                    refresh_config = {k: v for k, v in item.items() if k != "type"}
                else:
                    new_layout_items.append(item)
            
            if refresh_config:
                # 更新dashboard：设置新字段，清理layout_config
                connection.execute(
                    sa.text("""
                        UPDATE dashboards 
                        SET refresh_config = :refresh_config, 
                            layout_config = :layout_config 
                        WHERE id = :id
                    """),
                    {
                        "refresh_config": json.dumps(refresh_config),
                        "layout_config": json.dumps(new_layout_items),
                        "id": dashboard_id
                    }
                )
        except (json.JSONDecodeError, TypeError):
            # 无法解析的跳过
            continue


def downgrade():
    """回滚：将refresh_config合并回layout_config"""
    connection = op.get_bind()
    
    # 获取所有有refresh_config的dashboard
    result = connection.execute(
        sa.text("SELECT id, layout_config, refresh_config FROM dashboards WHERE refresh_config IS NOT NULL")
    )
    dashboards = result.fetchall()
    
    import json
    for dashboard in dashboards:
        dashboard_id = dashboard[0]
        layout_config = dashboard[1]
        refresh_config = dashboard[2]
        
        try:
            if isinstance(layout_config, str):
                layout_items = json.loads(layout_config) if layout_config else []
            else:
                layout_items = layout_config or []
                
            if isinstance(refresh_config, str):
                refresh_cfg = json.loads(refresh_config)
            else:
                refresh_cfg = refresh_config
            
            if refresh_cfg:
                refresh_cfg["type"] = "refresh_config"
                layout_items.append(refresh_cfg)
                
                connection.execute(
                    sa.text("UPDATE dashboards SET layout_config = :layout_config WHERE id = :id"),
                    {"layout_config": json.dumps(layout_items), "id": dashboard_id}
                )
        except (json.JSONDecodeError, TypeError):
            continue
    
    # 删除refresh_config字段
    op.drop_column('dashboards', 'refresh_config')
