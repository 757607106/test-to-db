"""
Agent系统重构执行脚本
"""
from pathlib import Path
from refactor_utils import (
    create_backup,
    compare_directories,
    delete_files,
    copy_files,
    verify_directory_sync,
    count_python_files,
    list_python_files
)


def main():
    # 定义路径
    current_agents_dir = "app/agents/agents"
    reference_agents_dir = "../backend_副本/app/agents/agents"
    
    print("=" * 60)
    print("Agent系统重构工具")
    print("=" * 60)
    
    # 1. 创建备份
    print("\n📦 步骤1: 创建备份...")
    try:
        backup_path = create_backup(current_agents_dir)
        print(f"备份路径: {backup_path}")
    except Exception as e:
        print(f"❌ 备份失败: {e}")
        return
    
    # 2. 比较目录
    print("\n🔍 步骤2: 比较目录...")
    only_in_current, only_in_reference, in_both = compare_directories(
        current_agents_dir, reference_agents_dir
    )
    
    print(f"\n当前版本独有的文件 (需要删除): {len(only_in_current)}")
    for f in sorted(only_in_current):
        print(f"  - {f}")
    
    print(f"\n参考版本独有的文件: {len(only_in_reference)}")
    for f in sorted(only_in_reference):
        print(f"  - {f}")
    
    print(f"\n两个版本都有的文件 (需要同步): {len(in_both)}")
    for f in sorted(in_both):
        print(f"  - {f}")
    
    # 3. 统计文件数量
    print("\n📊 文件统计:")
    current_count = count_python_files(current_agents_dir)
    reference_count = count_python_files(reference_agents_dir)
    print(f"当前版本: {current_count} 个文件")
    print(f"参考版本: {reference_count} 个文件")
    print(f"需要删除: {len(only_in_current)} 个文件")
    
    print("\n" + "=" * 60)
    print("备份和分析完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()
