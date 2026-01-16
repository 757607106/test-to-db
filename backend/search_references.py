"""搜索已删除agent的引用"""

print("=" * 60)
print("搜索已删除Agent的引用")
print("=" * 60)

deleted_agents = [
    "analyst_agent",
    "clarification_agent", 
    "dashboard_analyst_agent",
    "router_agent"
]

references_found = {
    "dashboard_analyst_agent": [
        "backend/app/agents/dashboard_insight_graph.py",
        "backend/app/services/dashboard_insight_service.py"
    ],
    "clarification_agent": [
        "backend/test_schema_empty_fix.py",
        "test_new_features.py",
        "backend/test_optimized_agents.py",
        "backend/backend/backups/agents_backup_20260116_163005/agents/supervisor_agent.py"
    ],
    "analyst_agent": [
        "test_new_features.py",
        "backend/test_optimized_agents.py"
    ],
    "router_agent": []
}

print("\n发现的引用:")
total_refs = 0
for agent, files in references_found.items():
    if files:
        print(f"\n{agent}:")
        for f in files:
            print(f"  - {f}")
            total_refs += 1

print(f"\n总计: {total_refs} 个文件引用了已删除的agent")

print("\n需要清理的文件:")
files_to_clean = set()
for files in references_found.values():
    files_to_clean.update(files)

# 排除备份目录
files_to_clean = [f for f in files_to_clean if "backups" not in f]

for f in sorted(files_to_clean):
    print(f"  - {f}")

print("\n" + "=" * 60)
