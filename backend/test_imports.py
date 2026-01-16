"""测试所有agent模块的导入"""
import sys

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

print("=" * 60)
print("测试Agent模块导入")
print("=" * 60)

failed_imports = []
successful_imports = []

for module_name in agent_modules:
    try:
        __import__(module_name)
        print(f"✅ {module_name}")
        successful_imports.append(module_name)
    except ImportError as e:
        print(f"❌ {module_name}: {e}")
        failed_imports.append((module_name, str(e)))
    except Exception as e:
        print(f"⚠️  {module_name}: {e}")
        failed_imports.append((module_name, str(e)))

print("\n" + "=" * 60)
print(f"成功: {len(successful_imports)}/{len(agent_modules)}")
print(f"失败: {len(failed_imports)}/{len(agent_modules)}")

if failed_imports:
    print("\n失败的模块:")
    for module, error in failed_imports:
        print(f"  - {module}: {error}")
    sys.exit(1)
else:
    print("\n✅ 所有agent模块导入成功")
    sys.exit(0)
