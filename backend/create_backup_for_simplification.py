"""
创建备份用于SQL流程简化
在移除SQL Validator Agent之前创建完整备份
"""
import sys
from pathlib import Path
from refactor_utils import (
    create_backup,
    list_python_files,
    count_python_files,
    verify_directory_sync
)

def main():
    print("=" * 60)
    print("SQL流程简化 - 创建备份")
    print("=" * 60)
    
    # 1. 记录当前状态
    print("\n📊 当前系统状态:")
    agents_dir = "app/agents/agents"
    
    agent_files = list_python_files(agents_dir)
    agent_count = count_python_files(agents_dir)
    
    print(f"  代理文件数量: {agent_count}")
    print(f"  代理文件列表:")
    for i, file in enumerate(agent_files, 1):
        print(f"    {i}. {file}")
    
    # 检查是否包含SQL Validator
    has_validator = any("validator" in f.lower() for f in agent_files)
    print(f"\n  包含SQL Validator: {'是' if has_validator else '否'}")
    
    if not has_validator:
        print("\n⚠️  警告: 未找到SQL Validator Agent文件")
        print("  可能已经被移除，或者文件名不包含'validator'")
    
    # 2. 创建备份
    print("\n💾 创建备份...")
    try:
        backup_path = create_backup(
            source_dir=agents_dir,
            backup_base="backups"
        )
        print(f"  备份路径: {backup_path}")
        
        # 3. 验证备份
        print("\n✅ 验证备份完整性...")
        backup_agents_dir = Path(backup_path) / "agents"
        
        verification_results = verify_directory_sync(
            source_dir=agents_dir,
            dest_dir=str(backup_agents_dir),
            expected_files=agent_files
        )
        
        all_verified = True
        for filename, result in verification_results.items():
            if not result["exists"]:
                print(f"  ❌ {filename}: 备份中不存在")
                all_verified = False
            elif not result["content_match"]:
                print(f"  ❌ {filename}: 内容不匹配")
                all_verified = False
            else:
                print(f"  ✅ {filename}: 验证通过")
        
        if all_verified:
            print("\n🎉 备份创建并验证成功!")
            print(f"  备份位置: {backup_path}")
            print(f"  备份文件数: {len(agent_files)}")
            
            # 4. 记录备份信息
            backup_info_file = Path(backup_path) / "backup_info.txt"
            with open(backup_info_file, "w", encoding="utf-8") as f:
                f.write("SQL流程简化 - 备份信息\n")
                f.write("=" * 60 + "\n\n")
                f.write(f"备份时间: {Path(backup_path).name.replace('agents_backup_', '')}\n")
                f.write(f"源目录: {agents_dir}\n")
                f.write(f"文件数量: {len(agent_files)}\n\n")
                f.write("备份文件列表:\n")
                for file in agent_files:
                    f.write(f"  - {file}\n")
                f.write("\n包含SQL Validator: " + ("是" if has_validator else "否") + "\n")
            
            print(f"\n📝 备份信息已保存到: {backup_info_file}")
            
            return 0
        else:
            print("\n❌ 备份验证失败!")
            return 1
            
    except Exception as e:
        print(f"\n❌ 备份创建失败: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
