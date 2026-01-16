"""
Agent系统重构工具函数
提供备份、文件比较、复制和验证功能
"""
import shutil
import hashlib
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Set, Tuple


def create_backup(source_dir: str, backup_base: str = "backend/backups") -> str:
    """创建agent目录的备份"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = Path(backup_base) / f"agents_backup_{timestamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    source_path = Path(source_dir)
    if source_path.exists():
        shutil.copytree(source_path, backup_dir / "agents", dirs_exist_ok=True)
        print(f"✅ 备份创建成功: {backup_dir}")
        return str(backup_dir)
    else:
        raise FileNotFoundError(f"源目录不存在: {source_dir}")


def compare_directories(dir1: str, dir2: str) -> Tuple[Set[str], Set[str], Set[str]]:
    """比较两个目录的文件列表
    
    Returns:
        (only_in_dir1, only_in_dir2, in_both)
    """
    path1 = Path(dir1)
    path2 = Path(dir2)
    
    files1 = {f.name for f in path1.glob("*.py") if f.is_file() and not f.name.startswith("__")}
    files2 = {f.name for f in path2.glob("*.py") if f.is_file() and not f.name.startswith("__")}
    
    only_in_dir1 = files1 - files2
    only_in_dir2 = files2 - files1
    in_both = files1 & files2
    
    return only_in_dir1, only_in_dir2, in_both


def delete_files(directory: str, filenames: List[str]) -> Dict[str, bool]:
    """删除指定的文件
    
    Returns:
        {filename: success}
    """
    results = {}
    dir_path = Path(directory)
    
    for filename in filenames:
        file_path = dir_path / filename
        try:
            if file_path.exists():
                file_path.unlink()
                results[filename] = True
                print(f"✅ 已删除: {filename}")
            else:
                results[filename] = False
                print(f"⚠️  文件不存在: {filename}")
        except Exception as e:
            results[filename] = False
            print(f"❌ 删除失败 {filename}: {e}")
    
    return results


def copy_file(source: str, destination: str) -> bool:
    """复制单个文件"""
    try:
        source_path = Path(source)
        dest_path = Path(destination)
        
        if not source_path.exists():
            print(f"❌ 源文件不存在: {source}")
            return False
        
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, dest_path)
        print(f"✅ 已复制: {source_path.name}")
        return True
    except Exception as e:
        print(f"❌ 复制失败 {source} -> {destination}: {e}")
        return False


def copy_files(source_dir: str, dest_dir: str, filenames: List[str]) -> Dict[str, bool]:
    """批量复制文件
    
    Returns:
        {filename: success}
    """
    results = {}
    source_path = Path(source_dir)
    dest_path = Path(dest_dir)
    
    for filename in filenames:
        source_file = source_path / filename
        dest_file = dest_path / filename
        results[filename] = copy_file(str(source_file), str(dest_file))
    
    return results


def calculate_file_hash(filepath: str) -> str:
    """计算文件的SHA256哈希值"""
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def verify_file_content(file1: str, file2: str) -> bool:
    """验证两个文件内容是否相同"""
    try:
        hash1 = calculate_file_hash(file1)
        hash2 = calculate_file_hash(file2)
        return hash1 == hash2
    except Exception as e:
        print(f"❌ 验证失败: {e}")
        return False


def verify_directory_sync(source_dir: str, dest_dir: str, expected_files: List[str]) -> Dict[str, Dict]:
    """验证目录同步结果
    
    Returns:
        {filename: {exists: bool, content_match: bool, hash: str}}
    """
    results = {}
    source_path = Path(source_dir)
    dest_path = Path(dest_dir)
    
    for filename in expected_files:
        source_file = source_path / filename
        dest_file = dest_path / filename
        
        exists = dest_file.exists()
        content_match = False
        file_hash = None
        
        if exists and source_file.exists():
            content_match = verify_file_content(str(source_file), str(dest_file))
            file_hash = calculate_file_hash(str(dest_file))
        
        results[filename] = {
            "exists": exists,
            "content_match": content_match,
            "hash": file_hash
        }
    
    return results


def count_python_files(directory: str) -> int:
    """统计目录中的Python文件数量（不包括__init__.py和__pycache__）"""
    dir_path = Path(directory)
    if not dir_path.exists():
        return 0
    
    count = 0
    for f in dir_path.glob("*.py"):
        if f.is_file() and not f.name.startswith("__"):
            count += 1
    
    return count


def list_python_files(directory: str) -> List[str]:
    """列出目录中的所有Python文件"""
    dir_path = Path(directory)
    if not dir_path.exists():
        return []
    
    files = []
    for f in dir_path.glob("*.py"):
        if f.is_file() and not f.name.startswith("__"):
            files.append(f.name)
    
    return sorted(files)
