"""
移除SQL Validator Agent文件
将文件移动到备份目录而不是删除
"""
import sys
from pathlib import Path
import shutil
from datetime import datetime


def main():
    print("=" * 60)
    print("移除SQL Validator Agent文件")
    print("=" * 60)
    
    # 定义路径
    agents_dir = Path("app/agents/agents")
    backup_base = Path("backups/removed_validators")
    
    # 创建带时间戳的备份目录
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = backup_base / f"validators_{timestamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    # 要移除的文件
    files_to_remove = [
        "sql_validator_agent.py",
        "sql_validator_agent_parallel.py"
    ]
    
    print(f"\n📦 备份目录: {backup_dir}")
    print(f"📁 源目录: {agents_dir}")
    print(f"\n要移除的文件:")
    for f in files_to_remove:
        print(f"  - {f}")
    
    # 移动文件
    print("\n🔄 开始移动文件...")
    moved_files = []
    
    for filename in files_to_remove:
        source_file = agents_dir / filename
        dest_file = backup_dir / filename
        
        if source_file.exists():
            try:
                shutil.move(str(source_file), str(dest_file))
                moved_files.append(filename)
                print(f"  ✅ 已移动: {filename}")
            except Exception as e:
                print(f"  ❌ 移动失败 {filename}: {e}")
                return 1
        else:
            print(f"  ⚠️  文件不存在: {filename}")
    
    # 验证移动结果
    print("\n✅ 验证移动结果...")
    all_verified = True
    
    for filename in moved_files:
        source_file = agents_dir / filename
        dest_file = backup_dir / filename
        
        # 检查源文件已删除
        if source_file.exists():
            print(f"  ❌ {filename}: 源文件仍然存在")
            all_verified = False
        # 检查目标文件存在
        elif not dest_file.exists():
            print(f"  ❌ {filename}: 备份文件不存在")
            all_verified = False
        else:
            print(f"  ✅ {filename}: 移动成功")
    
    # 检查剩余文件
    print("\n📊 剩余的agent文件:")
    remaining_files = sorted([f.name for f in agents_dir.glob("*.py") 
                             if f.is_file() and not f.name.startswith("__")])
    
    for i, f in enumerate(remaining_files, 1):
        print(f"  {i}. {f}")
    
    expected_count = 7  # 9 - 2 = 7
    actual_count = len(remaining_files)
    
    print(f"\n文件数量: {actual_count} (期望: {expected_count})")
    
    # 创建移除记录
    record_file = backup_dir / "removal_info.txt"
    with open(record_file, "w", encoding="utf-8") as f:
        f.write("SQL Validator Agent移除记录\n")
        f.write("=" * 60 + "\n\n")
        f.write(f"移除时间: {timestamp}\n")
        f.write(f"备份位置: {backup_dir}\n")
        f.write(f"移除文件数: {len(moved_files)}\n\n")
        f.write("移除的文件:\n")
        for filename in moved_files:
            f.write(f"  - {filename}\n")
        f.write(f"\n剩余文件数: {actual_count}\n")
        f.write("剩余文件:\n")
        for filename in remaining_files:
            f.write(f"  - {filename}\n")
    
    print(f"\n📝 移除记录已保存: {record_file}")
    
    if all_verified and actual_count == expected_count:
        print("\n🎉 SQL Validator Agent文件移除成功!")
        print(f"  备份位置: {backup_dir}")
        print(f"  移除文件: {len(moved_files)}个")
        print(f"  剩余文件: {actual_count}个")
        return 0
    else:
        print("\n❌ 移除过程出现问题")
        if actual_count != expected_count:
            print(f"  文件数量不符: 期望{expected_count}，实际{actual_count}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
