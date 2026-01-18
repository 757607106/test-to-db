#!/usr/bin/env python3
"""
项目清理和重组脚本
执行项目文件的移动、删除和重组操作
"""

import os
import shutil
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent

print("="*60)
print("项目清理和重组脚本")
print("="*60)

# ============================================================
# Phase 1: 创建新目录结构
# ============================================================
print("\n📁 Phase 1: 创建新目录结构...")

new_dirs = [
    'backend/scripts',
    'docs/getting-started',
    'docs/backend',
    'docs/frontend/admin',
    'docs/frontend/chat',
    'docs/development',
]

for dir_path in new_dirs:
    full_path = PROJECT_ROOT / dir_path
    full_path.mkdir(parents=True, exist_ok=True)
    print(f"  ✅ 创建目录: {dir_path}")

# ============================================================
# Phase 2: 移动文件
# ============================================================
print("\n📦 Phase 2: 移动和整理文件...")

# 移动backend脚本到scripts/
backend_scripts = [
    ('backend/init_database_complete.sql', 'backend/scripts/init_database_complete.sql'),
    ('backend/init_mock_data.py', 'backend/scripts/init_mock_data.py'),
    ('backend/init_inventory_simple.py', 'backend/scripts/init_inventory_simple.py'),
    ('backend/init_erp_mock_data.py', 'backend/scripts/init_erp_mock_data.py'),
    ('backend/verify_inventory_db.py', 'backend/scripts/verify_inventory_db.py'),
    ('backend/cleanup_sample_db.py', 'backend/scripts/cleanup_sample_db.py'),
    ('backend/cleanup_sample_db.sql', 'backend/scripts/cleanup_sample_db.sql'),
    ('backend/init-checkpointer-db.sql', 'backend/scripts/init-checkpointer-db.sql'),
    ('backend/init-mysql.sql', 'backend/scripts/init-mysql.sql'),
]

for src, dst in backend_scripts:
    src_path = PROJECT_ROOT / src
    dst_path = PROJECT_ROOT / dst
    if src_path.exists():
        shutil.move(str(src_path), str(dst_path))
        print(f"  ✅ 移动: {src} → {dst}")

# 移动backend文档到docs/backend/
backend_docs = [
    ('backend/INVENTORY_DATABASES.md', 'docs/backend/TEST_DATABASES.md'),
    ('backend/数据库连接信息.md', 'docs/backend/DATABASE_CONNECTION_INFO.md'),
    ('backend/硬编码连接修复说明.md', 'docs/backend/HARDCODED_CONNECTION_FIX.md'),
]

for src, dst in backend_docs:
    src_path = PROJECT_ROOT / src
    dst_path = PROJECT_ROOT / dst
    if src_path.exists():
        shutil.move(str(src_path), str(dst_path))
        print(f"  ✅ 移动: {src} → {dst}")

# 移动根目录文档到docs/
root_docs_move = [
    ('DOCKER_QUICK_START.md', 'docs/deployment/DOCKER_QUICK_START.md'),
    ('PROJECT_STRUCTURE.md', 'docs/PROJECT_STRUCTURE.md'),
]

for src, dst in root_docs_move:
    src_path = PROJECT_ROOT / src
    dst_path = PROJECT_ROOT / dst
    if src_path.exists():
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src_path), str(dst_path))
        print(f"  ✅ 移动: {src} → {dst}")

# ============================================================
# Phase 3: 删除过时文件
# ============================================================
print("\n🗑️  Phase 3: 删除过时文件...")

# 删除根目录过时文档
root_docs_delete = [
    'DOCKER_更新完成.md',
    'Docker重置完成报告.md',
    'DOCKER_SETUP_COMPLETE.md',
    'PROJECT_CLEANUP_COMPLETE.md',
    'PROJECT_CLEANUP_PLAN.md',
    '数据库迁移修复完成.md',
    '最终优化报告.md',
]

for doc in root_docs_delete:
    doc_path = PROJECT_ROOT / doc
    if doc_path.exists():
        doc_path.unlink()
        print(f"  ✅ 删除: {doc}")

# 删除backend/tests中的过时文档
tests_docs_delete = [
    'backend/tests/FIX_PLAN.md',
    'backend/tests/FIX_SUMMARY.md',
    'backend/tests/REAL_ISSUE_ANALYSIS.md',
    'backend/tests/TOOL_DISPLAY_ANALYSIS.md',
    'backend/tests/test_frontend_tool_display.md',
    'backend/tests/IMPLEMENTATION_SUMMARY.md',
]

for doc in tests_docs_delete:
    doc_path = PROJECT_ROOT / doc
    if doc_path.exists():
        doc_path.unlink()
        print(f"  ✅ 删除: {doc}")

# 删除docs中的过时文档
docs_delete = [
    'docs/SETBRANCH_TYPE_ERROR_ANALYSIS.md',
    'docs/TYPESCRIPT_ERROR_ANALYSIS.md',
    'docs/typescript-error-analysis-customsubmitoptions.md',
    'docs/COPYRIGHT_TRACKING_REMOVAL.md',
    'docs/DOCUMENTATION_COMPLETE.md',
    'docs/COMPLETION_REPORT.md',
    'docs/FINAL_SUMMARY.md',
    'docs/IMPLEMENTATION_SUMMARY.md',
    'docs/OPTIMIZATION_SUMMARY.md',
    'docs/DISABLED_FEATURES.md',
    'docs/性能优化完成报告.md',
    'docs/变更总结.md',
    'docs/启动指南.md',
]

for doc in docs_delete:
    doc_path = PROJECT_ROOT / doc
    if doc_path.exists():
        doc_path.unlink()
        print(f"  ✅ 删除: {doc}")

# 删除backend/backups目录（可选，取消注释以删除）
backups_path = PROJECT_ROOT / 'backend' / 'backups'
if backups_path.exists():
    # shutil.rmtree(backups_path)
    print(f"  ⚠️  保留备份目录: backend/backups (如需删除请手动执行)")

# 删除backend/checkpoints.db
checkpoints_db = PROJECT_ROOT / 'backend' / 'checkpoints.db'
if checkpoints_db.exists():
    checkpoints_db.unlink()
    print(f"  ✅ 删除: backend/checkpoints.db")

# ============================================================
# Phase 4: 创建新文档
# ============================================================
print("\n📝 Phase 4: 创建新文档...")

# 创建backend/scripts/README.md
scripts_readme = PROJECT_ROOT / 'backend' / 'scripts' / 'README.md'
with open(scripts_readme, 'w', encoding='utf-8') as f:
    f.write("""# Backend Scripts

## 数据库初始化脚本

### init_database_complete.sql
完整的数据库表结构初始化SQL脚本，包含所有项目所需的表。

**使用方法**:
```bash
mysql -u root -p < init_database_complete.sql
```

### init_mock_data.py
初始化基础Mock数据，包括用户、数据库连接、Schema元数据等。

**使用方法**:
```bash
cd backend
python3 scripts/init_mock_data.py
```

### init_inventory_simple.py
创建简化版进销存测试数据库（16张表）。

**使用方法**:
```bash
cd backend
python3 scripts/init_inventory_simple.py
```

### init_erp_mock_data.py
创建完整版进销存ERP测试数据库（34张表）。

**使用方法**:
```bash
cd backend
python3 scripts/init_erp_mock_data.py
```

## 工具脚本

### verify_inventory_db.py
验证进销存数据库是否正确创建。

### cleanup_sample_db.py / cleanup_sample_db.sql
清理硬编码的示例数据库连接。

### init-checkpointer-db.sql
初始化LangGraph Checkpointer数据库。

### init-mysql.sql
MySQL基础初始化脚本。
""")
print(f"  ✅ 创建: backend/scripts/README.md")

# 创建docs/README.md
docs_readme = PROJECT_ROOT / 'docs' / 'README.md'
with open(docs_readme, 'w', encoding='utf-8') as f:
    f.write("""# Chat-to-DB 项目文档

## 📚 文档导航

### 快速开始
- [快速启动指南](getting-started/QUICK_START.md) - 5分钟快速开始
- [安装指南](getting-started/INSTALLATION.md) - 详细安装步骤
- [首次使用](getting-started/FIRST_STEPS.md) - 新手入门

### 架构设计
- [架构概览](architecture/OVERVIEW.md) - 系统架构总览
- [Text2SQL分析](architecture/TEXT2SQL_ANALYSIS.md) - Text2SQL技术分析
- [上下文工程](architecture/CONTEXT_ENGINEERING.md) - 上下文工程设计

### 后端开发
- [数据库表结构](backend/DATABASE_SCHEMA.md) - 完整的数据库表结构说明
- [数据库初始化](backend/DATABASE_INIT.md) - 数据库初始化指南
- [测试数据库](backend/TEST_DATABASES.md) - 测试数据库使用说明
- [API参考](backend/API_REFERENCE.md) - REST API文档
- [Agent系统](backend/AGENT_SYSTEM.md) - AI Agent系统说明

### 前端开发
- [Admin管理后台](frontend/admin/) - Admin系统文档
- [Chat聊天前端](frontend/chat/) - Chat系统文档

### 部署运维
- [Docker部署](deployment/DOCKER_DEPLOYMENT.md) - Docker部署指南
- [生产环境](deployment/PRODUCTION.md) - 生产环境部署

### 开发指南
- [开发环境搭建](development/SETUP.md) - 本地开发环境配置
- [问题排查](development/TROUBLESHOOTING.md) - 常见问题解决
- [贡献指南](development/CONTRIBUTING.md) - 如何贡献代码

### LangGraph相关
- [LangGraph设置](langgraph/SETUP.md) - LangGraph配置
- [API指南](langgraph/API_GUIDE.md) - LangGraph API使用
- [Checkpointer](langgraph/CHECKPOINTER.md) - 检查点系统

## 📖 其他资源

- [项目结构](PROJECT_STRUCTURE.md) - 项目目录结构说明
- [变更日志](../CHANGELOG.md) - 版本更新记录
- [README](../README.md) - 项目主页

## 🔍 快速查找

### 我想...
- **快速开始使用** → [快速启动指南](getting-started/QUICK_START.md)
- **了解系统架构** → [架构概览](architecture/OVERVIEW.md)
- **初始化数据库** → [数据库初始化](backend/DATABASE_INIT.md)
- **部署到服务器** → [Docker部署](deployment/DOCKER_DEPLOYMENT.md)
- **开发新功能** → [开发环境搭建](development/SETUP.md)
- **排查问题** → [问题排查](development/TROUBLESHOOTING.md)

## 📝 文档贡献

欢迎改进文档！请参考 [贡献指南](development/CONTRIBUTING.md)。
""")
print(f"  ✅ 创建: docs/README.md")

# ============================================================
# 完成
# ============================================================
print("\n" + "="*60)
print("✅ 项目清理和重组完成！")
print("="*60)
print("""
下一步操作：
1. 查看 docs/README.md 了解新的文档结构
2. 查看 backend/scripts/README.md 了解脚本使用方法
3. 根目录文档已精简，详细文档请查看 docs/ 目录
4. 所有初始化脚本已移动到 backend/scripts/ 目录

注意事项：
- backend/backups 目录已保留（如需删除请手动执行）
- 请更新任何引用旧路径的代码或配置
- 建议在继续开发前测试一下数据库初始化脚本
""")
