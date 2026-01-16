"""验证agent文件同步"""
from refactor_utils import count_python_files, list_python_files, verify_directory_sync

current_dir = "app/agents/agents"
reference_dir = "../backend_副本/app/agents/agents"

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

print("=" * 60)
print("验证Agent文件同步")
print("=" * 60)

# 统计文件数量
current_count = count_python_files(current_dir)
print(f"\n当前目录文件数: {current_count}")
print(f"期望文件数: {len(expected_files)}")

if current_count == len(expected_files):
    print("✅ 文件数量正确")
else:
    print(f"❌ 文件数量不匹配")

# 列出文件
current_files = list_python_files(current_dir)
print(f"\n当前文件列表:")
for f in current_files:
    print(f"  - {f}")

# 验证内容
print(f"\n验证文件内容...")
results = verify_directory_sync(reference_dir, current_dir, expected_files)

all_match = True
for filename, result in results.items():
    status = "✅" if result["exists"] and result["content_match"] else "❌"
    print(f"{status} {filename}")
    if not result["exists"]:
        print(f"    文件不存在")
        all_match = False
    elif not result["content_match"]:
        print(f"    内容不匹配")
        all_match = False

print("\n" + "=" * 60)
if all_match and current_count == len(expected_files):
    print("✅ 所有文件同步成功且内容匹配")
else:
    print("❌ 同步验证失败")
print("=" * 60)
