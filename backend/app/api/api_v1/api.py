from fastapi import APIRouter

from app.api.api_v1.endpoints import (
    connections, schema, query, value_mappings, 
    graph_visualization, relationship_tips, hybrid_qa,
    dashboards, dashboard_widgets, dashboard_insights,
    llm_configs, agent_profiles, system_config, auth, tenant_users,
    semantic_layer
)

# 强制重新加载 - 修复API路由问题

api_router = APIRouter()
 
# 添加API根路径处理器
@api_router.get("/")
async def api_root():
    """API根路径"""
    return {
        "message": "ChatDB API",
        "version": "0.1.0",
        "status": "running",
        "endpoints": {
            "connections": "/api/connections/",
            "schema": "/api/schema/",
            "query": "/api/query/",
            "value_mappings": "/api/value-mappings/",
            "graph_visualization": "/api/graph-visualization/",
            "relationship_tips": "/api/relationship-tips/",
            "hybrid_qa": "/api/hybrid-qa/",
            "tenant": "/api/tenant/",
            "docs": "/docs",
            "openapi": "/openapi.json"
        }
    }

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(tenant_users.router, prefix="/tenant", tags=["tenant"])
api_router.include_router(connections.router, prefix="/connections", tags=["connections"])
api_router.include_router(schema.router, prefix="/schema", tags=["schema"])
api_router.include_router(query.router, prefix="/query", tags=["query"])
api_router.include_router(value_mappings.router, prefix="/value-mappings", tags=["value-mappings"])
api_router.include_router(graph_visualization.router, prefix="/graph-visualization", tags=["graph-visualization"])
api_router.include_router(relationship_tips.router, prefix="/relationship-tips", tags=["relationship-tips"])
api_router.include_router(hybrid_qa.router, prefix="/hybrid-qa", tags=["hybrid-qa"])
api_router.include_router(dashboards.router, prefix="/dashboards", tags=["dashboards"])
api_router.include_router(dashboard_widgets.router, prefix="", tags=["widgets"])
api_router.include_router(dashboard_insights.router, prefix="", tags=["insights"])
api_router.include_router(llm_configs.router, prefix="/llm-configs", tags=["llm-configs"])
api_router.include_router(agent_profiles.router, prefix="/agent-profiles", tags=["agent-profiles"])
api_router.include_router(system_config.router, prefix="/system-config", tags=["system-config"])
api_router.include_router(semantic_layer.router, prefix="/semantic-layer", tags=["semantic-layer"])