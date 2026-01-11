# 智能SQL代理系统

基于LangGraph的create_react_agent和agent_supervisor实现的高级自然语言到SQL转换和执行系统。

## 🎯 系统特性

### 核心功能
- **智能查询分析**: 深度理解用户的自然语言查询意图
- **自动SQL生成**: 根据数据库模式生成高质量SQL语句
- **多层验证**: 语法、安全性和性能的全面验证
- **智能执行**: 安全可靠的SQL执行和结果处理
- **自愈能力**: 智能错误检测、分析和自动修复
- **多代理协作**: 专门化代理协同工作，提高效率和准确性

### 技术亮点
- 🤖 **多代理架构**: 基于LangGraph的专门化代理系统
- 🧠 **智能监督**: 监督代理协调整个工作流程
- 🔄 **自动恢复**: 智能错误处理和自愈机制
- 🛡️ **安全防护**: 多层安全验证，防止SQL注入
- ⚡ **性能优化**: 自动查询优化和性能分析
- 🔌 **多数据库支持**: 支持MySQL、PostgreSQL、SQLite等多种数据库

## 🏗️ 系统架构

### 代理组件

#### 1. 监督代理 (Supervisor Agent)
- **职责**: 协调整个工作流程，智能路由决策
- **功能**: 状态分析、错误处理、流程控制
- **文件**: `agents/supervisor_agent.py`

#### 2. Schema分析代理 (Schema Agent)
- **职责**: 分析用户查询，获取相关数据库模式
- **功能**: 查询意图识别、表结构检索、值映射
- **文件**: `agents/schema_agent.py`

#### 3. SQL生成代理 (SQL Generator Agent)
- **职责**: 根据模式信息生成高质量SQL语句
- **功能**: SQL生成、查询优化、性能建议
- **文件**: `agents/sql_generator_agent.py`

#### 4. SQL验证代理 (SQL Validator Agent)
- **职责**: 验证SQL的正确性、安全性和性能
- **功能**: 语法检查、安全扫描、性能分析
- **文件**: `agents/sql_validator_agent.py`

#### 5. SQL执行代理 (SQL Executor Agent)
- **职责**: 安全执行SQL并处理结果
- **功能**: 查询执行、结果格式化、性能监控
- **文件**: `agents/sql_executor_agent.py`

#### 6. 错误恢复代理 (Error Recovery Agent)
- **职责**: 智能错误分析和自动修复
- **功能**: 错误模式识别、恢复策略制定、自动修复
- **文件**: `agents/error_recovery_agent.py`

### 核心组件

#### 状态管理 (State Management)
```python
class SQLMessageState(MessagesState):
    connection_id: int = 15
    query_analysis: Optional[Dict[str, Any]] = None
    schema_info: Optional[SchemaInfo] = None
    generated_sql: Optional[str] = None
    validation_result: Optional[SQLValidationResult] = None
    execution_result: Optional[SQLExecutionResult] = None
    retry_count: int = 0
    current_stage: Literal[...] = "schema_analysis"
    error_history: List[Dict[str, Any]] = field(default_factory=list)
```

#### 数据库管理器 (Database Manager)
- **统一接口**: 封装多种数据库的连接和操作
- **连接池**: 支持多数据库连接管理
- **错误处理**: 智能连接恢复和超时处理
- **文件**: `database/db_manager.py`

#### 图工作流 (Graph Workflow)
- **智能路由**: 基于状态的条件路由
- **错误恢复**: 自动错误检测和恢复流程
- **并行处理**: 支持并发代理执行
- **文件**: `chat_graph.py`

## 🚀 快速开始

### 1. 安装依赖
```bash
pip install -r requirements.txt
```

### 2. 配置数据库

```python
from app.db.db_manager import DatabaseConfig, db_manager

config = DatabaseConfig(
    db_type="mysql",
    host="localhost",
    port=3306,
    database="Chinook",
    username="root",
    password="mysql"
)

db_manager.connect(config)
```

### 3. 运行演示
```bash
cd backend
python -m app.agents.demo_intelligent_sql
```

### 4. 使用API
```python
from app.agents.chat_graph import process_sql_query

# 处理自然语言查询
result = await process_sql_query(
    user_query="查询所有客户的姓名和邮箱",
    connection_id=15
)

print(f"生成的SQL: {result['generated_sql']}")
print(f"执行结果: {result['execution_result']}")
```

## 📊 使用示例

### 示例1: 基础查询
```
用户输入: "查询所有客户的姓名和邮箱"

生成SQL:
SELECT 
    CONCAT(FirstName, ' ', LastName) as full_name,
    Email
FROM Customer
ORDER BY LastName, FirstName
LIMIT 100;

执行结果: 59行数据，0.004秒
```

### 示例2: 聚合查询
```
用户输入: "哪种音乐类型的曲目平均时长最长"

生成SQL:
SELECT 
    g.Name as genre_name,
    AVG(t.Milliseconds / 1000.0) as avg_duration_seconds
FROM Genre g
JOIN Track t ON g.GenreId = t.GenreId
GROUP BY g.GenreId, g.Name
ORDER BY avg_duration_seconds DESC
LIMIT 10;

执行结果: 10行数据，0.010秒
```

### 示例3: 复杂关联查询
```
用户输入: "显示销售额最高的前5个艺术家"

生成SQL:
SELECT 
    ar.Name as artist_name,
    SUM(il.UnitPrice * il.Quantity) as total_sales
FROM Artist ar
JOIN Album al ON ar.ArtistId = al.ArtistId
JOIN Track t ON al.AlbumId = t.AlbumId
JOIN InvoiceLine il ON t.TrackId = il.TrackId
GROUP BY ar.ArtistId, ar.Name
ORDER BY total_sales DESC
LIMIT 5;

执行结果: 5行数据，0.030秒
```

## 🔧 配置选项

### 数据库配置
支持多种数据库类型：
- MySQL
- PostgreSQL  
- SQLite
- Oracle
- Snowflake
- BigQuery
- ClickHouse
- DuckDB

### 代理配置
```python
# 最大重试次数
max_retries = 3

# 查询超时时间
query_timeout = 30

# 结果限制
default_limit = 100
```

## 🛡️ 安全特性

### SQL注入防护
- 关键字检测
- 模式匹配
- 参数化查询
- 权限验证

### 性能保护
- 查询超时控制
- 结果集大小限制
- 复杂度分析
- 资源监控

## 🔍 监控和调试

### 日志记录
- 详细的执行日志
- 错误追踪
- 性能指标
- 代理通信记录

### 测试工具
```bash
# 运行完整测试
python -m app.agents.test_intelligent_sql_agent

# 运行演示
python -m app.agents.demo_intelligent_sql
```

## 🚧 扩展开发

### 添加新代理
1. 继承基础代理类
2. 实现process方法
3. 注册到图工作流
4. 更新路由逻辑

### 自定义工具
```python
@tool
def custom_analysis_tool(query: str) -> Dict[str, Any]:
    """自定义分析工具"""
    # 实现自定义逻辑
    return {"result": "analysis"}
```

### 扩展数据库支持
1. 在DatabaseManager中添加连接方法
2. 更新配置类
3. 测试连接和查询

## 📈 性能优化

### 查询优化
- 自动添加LIMIT子句
- 索引使用建议
- JOIN优化
- 子查询重写

### 缓存机制
- 查询分析缓存
- Schema信息缓存
- 连接池管理

## 🤝 贡献指南

1. Fork项目
2. 创建功能分支
3. 提交更改
4. 创建Pull Request

## 📄 许可证

MIT License

## 🆘 支持

如有问题或建议，请提交Issue或联系开发团队。
