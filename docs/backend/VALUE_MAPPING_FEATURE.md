# 数据映射（Value Mapping）功能详解

## 1. 功能概述

数据映射（Value Mapping）是 Text2SQL 系统中的重要功能，用于解决**自然语言查询中的术语与数据库实际存储值不匹配**的问题。

## 2. 核心概念

- **自然语言术语 (nl_term)**：用户查询中使用的词汇（如："中石化"）
- **数据库值 (db_value)**：数据库中实际存储的值（如："中国石化"）
- **映射关系**：建立自然语言术语到数据库值的一对一或多对一映射

## 3. 数据库设计

```sql
-- valuemapping 表结构
CREATE TABLE valuemapping (
    id INT PRIMARY KEY AUTO_INCREMENT,
    column_id INT NOT NULL,           -- 关联的列ID
    nl_term VARCHAR(255) NOT NULL,   -- 自然语言术语
    db_value VARCHAR(255) NOT NULL,  -- 数据库值
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NULL,
    
    INDEX idx_valuemap_column (column_id),
    INDEX idx_valuemap_nl_term (nl_term),
    FOREIGN KEY (column_id) REFERENCES schemacolumn(id) ON DELETE CASCADE
);
```

## 4. 业务逻辑

### 4.1 前端管理界面

- **层级选择**：数据库连接 → 表 → 列 → 值映射
- **CRUD操作**：支持创建、编辑、删除值映射
- **直观界面**：提供表单界面让用户方便地配置映射关系

### 4.2 后端处理逻辑

在 `backend/app/services/text2sql_utils.py` 中：

```python
def get_value_mappings(db: Session, schema_context: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
    """
    获取表结构上下文中列的值映射
    """
    mappings = {}

    for column in schema_context["columns"]:
        column_id = column["id"]
        column_mappings = crud.value_mapping.get_by_column(db=db, column_id=column_id)

        if column_mappings:
            table_col = f"{column['table_name']}.{column['name']}"
            mappings[table_col] = {m.nl_term: m.db_value for m in column_mappings}

    return mappings

def process_sql_with_value_mappings(sql: str, value_mappings: Dict[str, Dict[str, str]]) -> str:
    """
    处理SQL查询，将自然语言术语替换为数据库值
    """
    if not value_mappings:
        return sql

    # 使用正则表达式替换SQL中的自然语言术语为数据库值
    for column, mappings in value_mappings.items():
        table, col = column.split('.')

        for nl_term, db_value in mappings.items():
            # 匹配带表名的模式: table.column = 'natural_language_term'
            pattern1 = rf"({table}\.{col}\s*=\s*['\"])({nl_term})(['\"])"
            sql = re.sub(pattern1, f"\\1{db_value}\\3", sql, flags=re.IGNORECASE)

            # 匹配不带表名的模式: column = 'natural_language_term'
            pattern2 = rf"({col}\s*=\s*['\"])(nl_term)(['\"])"
            sql = re.sub(pattern2, f"\\1{db_value}\\3", sql, flags=re.IGNORECASE)

            # 处理LIKE模式
            pattern3 = rf"({table}\.{col}\s+LIKE\s+['\"])%?({nl_term})%?(['\"])"
            sql = re.sub(pattern3, f"\\1%{db_value}%\\3", sql, flags=re.IGNORECASE)

    return sql
```

## 5. 在SQL生成中的作用

### 5.1 上下文注入

在 `sql_generator_agent.py` 中，值映射信息会被注入到LLM提示中：

```python
# 在构建prompt时包含值映射信息
context = f"""
数据库类型: {db_type}

可用的表和字段信息:
{json.dumps(schema_data, ensure_ascii=False, indent=2)}

值映射信息:
{json.dumps(mappings_data, ensure_ascii=False, indent=2)}
"""
```

### 5.2 SQL后处理

生成的SQL会经过值映射处理，将自然语言术语替换为数据库实际值：

```python
# 在SQL生成完成后处理值映射
final_sql = process_sql_with_value_mappings(generated_sql, value_mappings)
```

## 6. 应用场景示例

假设有一个企业表 `company`，其中公司名称字段为 `name`：
- 数据库中存储：`"中国石油化工股份有限公司"`
- 用户可能查询：`"中石化销售额"` 或 `"中石油销售额"`

通过值映射配置：
- `中石化` → `中国石油化工股份有限公司`
- `中石油` → `中国石油天然气股份有限公司`

这样当用户查询 `"中石化销售额"` 时，系统会自动将其转换为：
```sql
SELECT sales FROM company WHERE name = '中国石油化工股份有限公司'
```

## 7. 工作流程

```
用户查询: "中石化去年的销售额"
    ↓
Schema Agent 获取相关表结构和值映射
    ↓
SQL Generator Agent 构建包含值映射信息的prompt
    ↓
LLM 生成初步SQL: SELECT sales FROM company WHERE name = '中石化'
    ↓
值映射后处理器: 将 '中石化' 替换为 '中国石油化工股份有限公司'
    ↓
最终SQL: SELECT sales FROM company WHERE name = '中国石油化工股份有限公司'
```

## 8. 优势

- **提高准确性**：解决了自然语言查询与数据库值不匹配的问题
- **增强灵活性**：允许用户使用习惯术语进行查询
- **降低学习成本**：用户无需记忆数据库中的具体值
- **易于维护**：通过管理界面可以方便地配置和更新映射关系

这个功能极大地提高了Text2SQL系统的准确性，特别是在处理具有多种表述方式的业务术语时非常有用。