# 数据库表结构说明

## 📊 概览

Chat-to-DB项目使用MySQL 8.0+作为主数据库，包含12张核心表，分为6个功能模块。

**数据库名称**: `chatdb`  
**字符集**: `utf8mb4`  
**排序规则**: `utf8mb4_unicode_ci`

---

## 🗂️ 表结构分类

### 1. 用户模块 (User Module)

#### users - 用户表

存储系统用户信息，包括管理员和普通用户。

| 字段 | 类型 | 说明 | 约束 |
|------|------|------|------|
| id | BIGINT | 用户ID | 主键，自增 |
| username | VARCHAR(100) | 用户名 | 唯一，非空，索引 |
| email | VARCHAR(255) | 电子邮箱 | 唯一，非空，索引 |
| password_hash | VARCHAR(255) | 密码哈希 | 非空 |
| display_name | VARCHAR(100) | 显示名称 | 可空 |
| avatar_url | VARCHAR(500) | 头像URL | 可空 |
| role | VARCHAR(20) | 角色 | 非空，默认'user' |
| is_active | BOOLEAN | 是否激活 | 非空，默认TRUE |
| created_at | TIMESTAMP | 创建时间 | 非空，默认当前时间 |
| last_login_at | TIMESTAMP | 最后登录时间 | 可空 |

**索引**:
- `idx_users_username` (username)
- `idx_users_email` (email)

**关系**:
- 一对多: dashboards (通过 owner_id)
- 一对多: dashboard_permissions (通过 user_id)

---

### 2. 数据库连接模块 (Database Connection Module)

#### dbconnection - 数据库连接表

存储用户配置的各种数据库连接信息。

| 字段 | 类型 | 说明 | 约束 |
|------|------|------|------|
| id | BIGINT | 连接ID | 主键，自增 |
| name | VARCHAR(255) | 连接名称 | 唯一，非空，索引 |
| db_type | VARCHAR(50) | 数据库类型 | 非空 (mysql/postgresql/sqlite) |
| host | VARCHAR(255) | 主机地址 | 非空 |
| port | INT | 端口号 | 非空 |
| username | VARCHAR(255) | 用户名 | 非空 |
| password_encrypted | VARCHAR(255) | 加密的密码 | 非空 |
| database_name | VARCHAR(255) | 数据库名 | 非空 |
| created_at | TIMESTAMP | 创建时间 | 非空 |
| updated_at | TIMESTAMP | 更新时间 | 可空 |

**索引**:
- `idx_dbconn_name` (name)

**关系**:
- 一对多: schematable (Schema表信息)
- 一对多: dashboard_widgets (仪表盘组件)

---

### 3. Schema 元数据模块 (Schema Metadata Module)

#### schematable - Schema表信息表

存储数据库表的元数据信息。

| 字段 | 类型 | 说明 | 约束 |
|------|------|------|------|
| id | INT | Schema表ID | 主键，自增 |
| connection_id | INT | 数据库连接ID | 非空，外键 |
| table_name | VARCHAR(255) | 表名 | 非空，索引 |
| description | TEXT | 表描述 | 可空 |
| ui_metadata | JSON | UI元数据 | 可空 |
| created_at | TIMESTAMP | 创建时间 | 非空 |
| updated_at | TIMESTAMP | 更新时间 | 可空 |

**索引**:
- `idx_schematable_conn` (connection_id)
- `idx_schematable_name` (table_name)

**外键**:
- connection_id → dbconnection(id) ON DELETE CASCADE

**关系**:
- 多对一: dbconnection
- 一对多: schemacolumn (列信息)
- 一对多: schemarelationship (表关系)

---

#### schemacolumn - Schema列信息表

存储数据库表列的元数据信息。

| 字段 | 类型 | 说明 | 约束 |
|------|------|------|------|
| id | INT | Schema列ID | 主键，自增 |
| table_id | INT | Schema表ID | 非空，外键 |
| column_name | VARCHAR(255) | 列名 | 非空，索引 |
| data_type | VARCHAR(100) | 数据类型 | 非空 |
| description | TEXT | 列描述 | 可空 |
| is_primary_key | BOOLEAN | 是否主键 | 默认FALSE |
| is_foreign_key | BOOLEAN | 是否外键 | 默认FALSE |
| is_unique | BOOLEAN | 是否唯一 | 默认FALSE |
| created_at | TIMESTAMP | 创建时间 | 非空 |
| updated_at | TIMESTAMP | 更新时间 | 可空 |

**索引**:
- `idx_schemacolumn_table` (table_id)
- `idx_schemacolumn_name` (column_name)

**外键**:
- table_id → schematable(id) ON DELETE CASCADE

**关系**:
- 多对一: schematable
- 一对多: valuemapping (值映射)

---

#### schemarelationship - Schema关系表

存储数据库表之间的关系（外键关系）。

| 字段 | 类型 | 说明 | 约束 |
|------|------|------|------|
| id | INT | 关系ID | 主键，自增 |
| connection_id | INT | 数据库连接ID | 非空，外键 |
| source_table_id | INT | 源表ID | 非空，外键 |
| source_column_id | INT | 源列ID | 非空，外键 |
| target_table_id | INT | 目标表ID | 非空，外键 |
| target_column_id | INT | 目标列ID | 非空，外键 |
| relationship_type | VARCHAR(50) | 关系类型 | 可空 (1-to-1/1-to-N/N-to-M) |
| description | TEXT | 关系描述 | 可空 |
| created_at | TIMESTAMP | 创建时间 | 非空 |
| updated_at | TIMESTAMP | 更新时间 | 可空 |

**索引**:
- `idx_schemarel_conn` (connection_id)
- `idx_schemarel_source_table` (source_table_id)
- `idx_schemarel_target_table` (target_table_id)

**外键**:
- connection_id → dbconnection(id) ON DELETE CASCADE
- source_table_id → schematable(id) ON DELETE CASCADE
- source_column_id → schemacolumn(id) ON DELETE CASCADE
- target_table_id → schematable(id) ON DELETE CASCADE
- target_column_id → schemacolumn(id) ON DELETE CASCADE

---

#### valuemapping - 值映射表

存储自然语言术语到数据库值的映射关系，用于Text2SQL的语义理解。

| 字段 | 类型 | 说明 | 约束 |
|------|------|------|------|
| id | INT | 值映射ID | 主键，自增 |
| column_id | INT | 列ID | 非空，外键 |
| nl_term | VARCHAR(255) | 自然语言术语 | 非空，索引 |
| db_value | VARCHAR(255) | 数据库值 | 非空 |
| created_at | TIMESTAMP | 创建时间 | 非空 |
| updated_at | TIMESTAMP | 更新时间 | 可空 |

**索引**:
- `idx_valuemap_column` (column_id)
- `idx_valuemap_nl_term` (nl_term)

**外键**:
- column_id → schemacolumn(id) ON DELETE CASCADE

**示例**:
```
nl_term: "男", "男性", "male"
db_value: "M"

nl_term: "女", "女性", "female"  
db_value: "F"
```

---

### 4. Dashboard 仪表盘模块 (Dashboard Module)

#### dashboards - 仪表盘表

存储用户创建的数据可视化仪表盘。

| 字段 | 类型 | 说明 | 约束 |
|------|------|------|------|
| id | BIGINT | 仪表盘ID | 主键，自增 |
| name | VARCHAR(255) | 仪表盘名称 | 非空 |
| description | TEXT | 描述 | 可空 |
| owner_id | BIGINT | 所有者用户ID | 非空，外键，索引 |
| layout_config | JSON | 布局配置 | 非空 |
| is_public | BOOLEAN | 是否公开 | 非空，默认FALSE |
| tags | JSON | 标签 | 可空 |
| created_at | TIMESTAMP | 创建时间 | 非空，索引 |
| updated_at | TIMESTAMP | 更新时间 | 非空 |
| deleted_at | TIMESTAMP | 删除时间（软删除） | 可空，索引 |

**索引**:
- `idx_dashboards_owner` (owner_id)
- `idx_dashboards_created` (created_at)
- `idx_dashboards_deleted` (deleted_at)

**外键**:
- owner_id → users(id) ON DELETE CASCADE

**关系**:
- 多对一: users
- 一对多: dashboard_widgets
- 一对多: dashboard_permissions

---

#### dashboard_widgets - 仪表盘组件表

存储仪表盘中的各个可视化组件（图表、表格等）。

| 字段 | 类型 | 说明 | 约束 |
|------|------|------|------|
| id | BIGINT | 组件ID | 主键，自增 |
| dashboard_id | BIGINT | 仪表盘ID | 非空，外键，索引 |
| widget_type | VARCHAR(50) | 组件类型 | 非空 (chart/table/metric) |
| title | VARCHAR(255) | 组件标题 | 非空 |
| connection_id | BIGINT | 数据库连接ID | 非空，外键，索引 |
| query_config | JSON | 查询配置 | 非空 |
| chart_config | JSON | 图表配置 | 可空 |
| position_config | JSON | 位置配置 | 非空 |
| refresh_interval | INT | 刷新间隔（秒） | 非空，默认0 |
| last_refresh_at | TIMESTAMP | 最后刷新时间 | 可空 |
| data_cache | JSON | 数据缓存 | 可空 |
| created_at | TIMESTAMP | 创建时间 | 非空 |
| updated_at | TIMESTAMP | 更新时间 | 非空 |

**索引**:
- `idx_widgets_dashboard` (dashboard_id)
- `idx_widgets_connection` (connection_id)

**外键**:
- dashboard_id → dashboards(id) ON DELETE CASCADE
- connection_id → dbconnection(id) ON DELETE CASCADE

---

#### dashboard_permissions - 仪表盘权限表

存储仪表盘的共享和权限管理信息。

| 字段 | 类型 | 说明 | 约束 |
|------|------|------|------|
| id | BIGINT | 权限ID | 主键，自增 |
| dashboard_id | BIGINT | 仪表盘ID | 非空，外键，索引 |
| user_id | BIGINT | 用户ID | 非空，外键，索引 |
| permission_level | VARCHAR(20) | 权限级别 | 非空 (owner/editor/viewer) |
| granted_by | BIGINT | 授权人用户ID | 非空，外键 |
| created_at | TIMESTAMP | 创建时间 | 非空 |

**索引**:
- `idx_dashperm_dashboard` (dashboard_id)
- `idx_dashperm_user` (user_id)

**外键**:
- dashboard_id → dashboards(id) ON DELETE CASCADE
- user_id → users(id) ON DELETE CASCADE
- granted_by → users(id) ON DELETE CASCADE

---

### 5. AI Agent 配置模块 (AI Agent Configuration Module)

#### llm_configuration - LLM配置表

存储各种LLM（大语言模型）的配置信息。

| 字段 | 类型 | 说明 | 约束 |
|------|------|------|------|
| id | BIGINT | LLM配置ID | 主键，自增 |
| provider | VARCHAR(50) | LLM提供商 | 非空，索引 (openai/deepseek/aliyun) |
| api_key | VARCHAR(500) | API密钥 | 可空（建议加密存储） |
| base_url | VARCHAR(500) | API基础URL | 可空 |
| model_name | VARCHAR(100) | 模型名称 | 非空 |
| model_type | VARCHAR(20) | 模型类型 | 非空，默认'chat' (chat/embedding) |
| is_active | BOOLEAN | 是否激活 | 默认TRUE |
| created_at | TIMESTAMP | 创建时间 | 非空 |
| updated_at | TIMESTAMP | 更新时间 | 可空 |

**索引**:
- `idx_llmconfig_provider` (provider)

---

#### agent_profile - Agent配置表

存储AI Agent的配置和提示词信息。

| 字段 | 类型 | 说明 | 约束 |
|------|------|------|------|
| id | BIGINT | Agent配置ID | 主键，自增 |
| name | VARCHAR(100) | Agent名称 | 唯一，非空，索引 |
| role_description | TEXT | 角色描述 | 可空 |
| system_prompt | TEXT | 系统提示词 | 可空 |
| tools | JSON | 工具列表配置 | 可空 |
| llm_config_id | BIGINT | LLM配置ID | 可空，外键 |
| is_active | BOOLEAN | 是否激活 | 默认TRUE |
| is_system | BOOLEAN | 是否系统Agent | 默认FALSE |
| created_at | TIMESTAMP | 创建时间 | 非空 |
| updated_at | TIMESTAMP | 更新时间 | 可空 |

**索引**:
- `idx_agent_name` (name)

**外键**:
- llm_config_id → llm_configuration(id) ON DELETE SET NULL

---

### 6. 查询历史模块 (Query History Module)

#### query_history - 查询历史表

存储用户的查询历史和向量嵌入，用于相似查询检索。

| 字段 | 类型 | 说明 | 约束 |
|------|------|------|------|
| id | BIGINT | 查询历史ID | 主键，自增 |
| query_text | TEXT | 查询文本 | 非空 |
| embedding | JSON | 查询向量嵌入 | 可空（JSON格式存储） |
| connection_id | BIGINT | 数据库连接ID | 可空，索引 |
| meta_info | JSON | 元信息 | 可空（执行结果、耗时等） |
| created_at | TIMESTAMP | 创建时间 | 非空，索引 |

**索引**:
- `idx_queryhistory_created` (created_at)
- `idx_queryhistory_connection` (connection_id)

---

## 📈 ER图关系总结

```
users
  ├─→ dashboards (owner_id)
  └─→ dashboard_permissions (user_id, granted_by)

dbconnection
  ├─→ schematable (connection_id)
  ├─→ schemarelationship (connection_id)
  └─→ dashboard_widgets (connection_id)

schematable
  ├─→ schemacolumn (table_id)
  └─→ schemarelationship (source_table_id, target_table_id)

schemacolumn
  ├─→ valuemapping (column_id)
  └─→ schemarelationship (source_column_id, target_column_id)

dashboards
  ├─→ dashboard_widgets (dashboard_id)
  └─→ dashboard_permissions (dashboard_id)

llm_configuration
  └─→ agent_profile (llm_config_id)
```

---

## 🔧 维护说明

### 初始化
使用 `backend/scripts/init_database_complete.sql` 初始化完整的数据库结构。

### 迁移
使用 Alembic 进行数据库迁移：
```bash
cd backend
alembic upgrade head
```

### 备份
定期备份数据库：
```bash
mysqldump -u root -p chatdb > chatdb_backup_$(date +%Y%m%d).sql
```

---

**最后更新**: 2026-01-18
