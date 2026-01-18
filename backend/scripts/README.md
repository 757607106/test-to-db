# Backend Scripts

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
