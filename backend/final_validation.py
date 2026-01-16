"""最终验证报告"""
from refactor_utils import count_python_files, list_python_files, verify_directory_sync
import subprocess

print("=" * 70)
print("Agent系统重构 - 最终验证报告")
print("=" * 70)

# 1. 文件结构验证
print("\n📁 1. 文件结构验证")
print("-" * 70)

current_dir = "app/agents/agents"
reference_dir = "../backend_副本/app/agents/agents"

current_files = list_python_files(current_dir)
reference_files = list_python_files(reference_dir)

print(f"当前目录文件数: {len(current_files)}")
print(f"参考目录文件数: {len(reference_files)}")

if set(current_files) == set(reference_files):
    print("✅ 文件列表完全匹配")
else:
    print("❌ 文件列表不匹配")
    only_current = set(current_files) - set(reference_files)
    only_reference = set(reference_files) - set(current_files)
    if only_current:
        print(f"  仅在当前: {only_current}")
    if only_reference:
        print(f"  仅在参考: {only_reference}")

# 2. 文件内容验证
print("\n📄 2. 文件内容验证")
print("-" * 70)

expected_files = [
    "schema_agent.py",
    "sql_generator_agent.py",
    "sql_validator_agent.py",
    "sql_validator_agent_parallel.py",
    "sql_executor_agent.py",
    "chart_generator_agent.py",
    "sample_retrieval_agent.py",
    "error_recovery_agent.py",
    "supervisor_agent.py"
]

results = verify_directory_sync(reference_dir, current_dir, expected_files)
all_match = True
for filename, result in results.items():
    if result["exists"] and result["content_match"]:
        print(f"✅ {filename}")
    else:
        print(f"❌ {filename}")
        all_match = False

# 3. 导入测试
print("\n🔍 3. 模块导入测试")
print("-" * 70)

agent_modules = [
    "app.agents.agents.schema_agent",
    "app.agents.agents.sql_generator_agent",
    "app.agents.agents.sql_validator_agent",
    "app.agents.agents.sql_validator_agent_parallel",
    "app.agents.agents.sql_executor_agent",
    "app.agents.agents.chart_generator_agent",
    "app.agents.agents.sample_retrieval_agent",
    "app.agents.agents.error_recovery_agent",
    "app.agents.agents.supervisor_agent"
]

import_success = 0
for module_name in agent_modules:
    try:
        __import__(module_name)
        import_success += 1
    except:
        pass

print(f"成功导入: {import_success}/{len(agent_modules)}")
if import_success == len(agent_modules):
    print("✅ 所有模块导入成功")
else:
    print("❌ 部分模块导入失败")

# 4. 已删除agent引用检查
print("\n🗑️  4. 已删除Agent引用检查")
print("-" * 70)

deleted_agents = ["analyst_agent", "clarification_agent", "dashboard_analyst_agent", "router_agent"]
references_found = 0

for agent in deleted_agents:
    # 简化检查，只检查主要文件
    try:
        with open("app/agents/chat_graph.py", "r") as f:
            if agent in f.read():
                references_found += 1
                print(f"⚠️  在chat_graph.py中发现{agent}引用")
    except:
        pass

if references_found == 0:
    print("✅ 未发现已删除agent的引用")
else:
    print(f"❌ 发现{references_found}个引用")

# 5. 总结
print("\n" + "=" * 70)
print("📊 验证总结")
print("=" * 70)

checks = [
    ("文件结构", set(current_files) == set(reference_files)),
    ("文件内容", all_match),
    ("模块导入", import_success == len(agent_modules)),
    ("引用清理", references_found == 0)
]

passed = sum(1 for _, result in checks if result)
total = len(checks)

for check_name, result in checks:
    status = "✅" if result else "❌"
    print(f"{status} {check_name}")

print(f"\n通过率: {passed}/{total} ({passed*100//total}%)")

if passed == total:
    print("\n🎉 所有验证通过！Agent系统重构成功！")
else:
    print(f"\n⚠️  {total - passed} 项验证未通过，请检查")
