# 🚀 快速启动指南

5分钟快速开始使用Chat-to-DB！

---

## ⚡ 最快方式 (Docker)

### 1. 启动所有服务

```bash
# 克隆项目（如果还没有）
git clone <your-repo-url> chat-to-db
cd chat-to-db

# 启动Docker服务
docker-compose up -d

# 等待服务启动（约30秒）
docker-compose logs -f
```

### 2. 初始化数据库

```bash
# 初始化主数据库
docker exec -i chat_to_db_rwx-mysql mysql -uroot -pmysql < backend/scripts/init_database_complete.sql

# 初始化基础数据
docker exec -i chat_to_db_rwx-mysql bash -c "
cd /app/backend/scripts &&
python3 init_mock_data.py
"

# 初始化测试数据库（可选）
docker exec -i chat_to_db_rwx-mysql bash -c "
cd /app/backend/scripts &&
python3 init_inventory_simple.py
"
```

### 3. 访问系统

- **Admin管理后台**: http://localhost:3001
- **Chat聊天界面**: http://localhost:3000  
- **后端API**: http://localhost:8000/docs

**默认账号**:
- 用户名: `admin`
- 密码: `admin123`

### 4. 添加数据库连接

1. 登录Admin后台
2. 进入"数据源管理"
3. 点击"添加连接"，填写：
   ```
   连接名称: 进销存测试库
   数据库类型: MySQL
   主机: chat_to_db_rwx-mysql
   端口: 3306
   用户名: root
   密码: mysql
   数据库名: inventory_demo
   ```

4. 点击"测试连接" → "保存"

### 5. 开始使用

在Chat界面中输入自然语言查询：
```
查询所有商品
统计每个供应商的采购订单数量
查询库存数量最多的前10个商品
```

🎉 **完成！** 你已经成功运行Chat-to-DB了！

---

## 💻 本地开发方式

### 1. 环境准备

#### 系统要求
- Python 3.8+
- Node.js 16+
- MySQL 8.0+
- PostgreSQL 15+ (可选，用于Checkpointer)

#### 安装依赖

**后端**:
```bash
cd backend
pip3 install -r requirements.txt
```

**前端 - Admin**:
```bash
cd frontend/admin
npm install
```

**前端 - Chat**:
```bash
cd frontend/chat
npm install
```

### 2. 配置环境变量

创建 `.env` 文件：

```bash
cp .env.example .env
```

编辑 `.env`:
```bash
# 数据库配置
MYSQL_SERVER=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_password
MYSQL_DATABASE=chatdb

# LLM配置
OPENAI_API_KEY=your_openai_key
# 或使用Deepseek
DEEPSEEK_API_KEY=your_deepseek_key

# 服务端口
ADMIN_SERVER_PORT=8000
CHAT_SERVER_PORT=8001
```

### 3. 初始化数据库

```bash
cd backend/scripts

# 1. 创建数据库结构
mysql -u root -p < init_database_complete.sql

# 2. 初始化基础数据
python3 init_mock_data.py

# 3. 初始化测试数据库（可选）
python3 init_inventory_simple.py
```

### 4. 启动服务

#### 启动后端（3个终端窗口）

**终端1 - Admin服务**:
```bash
cd backend
python3 admin_server.py
```

**终端2 - Chat服务**:
```bash
cd backend
python3 chat_server.py
```

#### 启动前端（2个终端窗口）

**终端3 - Admin前端**:
```bash
cd frontend/admin
npm start
```

**终端4 - Chat前端**:
```bash
cd frontend/chat
npm run dev
```

### 5. 访问系统

- **Admin管理后台**: http://localhost:3001
- **Chat聊天界面**: http://localhost:3000
- **Admin API**: http://localhost:8000/docs
- **Chat API**: http://localhost:8001/docs

### 6. 配置数据库连接

同Docker方式第4步。

---

## 📋 验证清单

完成以下检查确保系统正常运行：

- [ ] Docker容器正在运行（或本地服务已启动）
- [ ] MySQL数据库已初始化（12张表）
- [ ] 测试数据库已创建（inventory_demo）
- [ ] Admin后台可以访问
- [ ] Chat界面可以访问
- [ ] 可以登录Admin（admin/admin123）
- [ ] 已添加至少一个数据库连接
- [ ] 可以在Chat中进行自然语言查询
- [ ] 查询结果正确返回

---

## 🎯 下一步

### 学习使用
- 📖 [用户使用指南](../frontend/chat/USER_GUIDE.md)
- 📊 [创建可视化Dashboard](../frontend/admin/DASHBOARD_GUIDE.md)
- 🤖 [配置AI Agent](../backend/AGENT_SYSTEM.md)

### 深入了解
- 🏗️ [系统架构](../architecture/OVERVIEW.md)
- 🗄️ [数据库结构](../backend/DATABASE_SCHEMA.md)
- 🔌 [API参考](../backend/API_REFERENCE.md)

### 高级功能
- 🔧 [自定义Agent](../backend/AGENT_SYSTEM.md#自定义agent)
- 📈 [配置图表](../frontend/admin/CHART_CONFIG.md)
- 🔐 [权限管理](../backend/PERMISSIONS.md)

---

## 🐛 常见问题

### Q1: Docker启动失败？

**检查端口占用**:
```bash
# 检查端口是否被占用
lsof -i :3306  # MySQL
lsof -i :3000  # Chat前端
lsof -i :3001  # Admin前端
lsof -i :8000  # Admin后端
lsof -i :8001  # Chat后端

# 停止占用端口的服务或修改docker-compose.yml中的端口映射
```

### Q2: 数据库连接失败？

**检查配置**:
```bash
# 检查MySQL是否运行
docker-compose ps
# 或
mysql -u root -p -e "SELECT 1"

# 检查.env配置是否正确
cat .env | grep MYSQL
```

### Q3: 前端无法访问后端API？

**检查CORS配置**:
- 确认后端服务已启动
- 检查前端.env中的API_URL配置
- 查看浏览器控制台错误信息

### Q4: Chat查询没有响应？

**检查LLM配置**:
```bash
# 确认已配置LLM API Key
cat .env | grep API_KEY

# 查看后端日志
docker-compose logs chat-server
# 或
tail -f backend/logs/chat.log
```

### Q5: 找不到测试数据库？

**重新初始化**:
```bash
cd backend/scripts
python3 init_inventory_simple.py

# 验证
mysql -u root -p -e "SHOW DATABASES LIKE '%inventory%';"
```

---

## 📞 获取帮助

- 📖 **完整文档**: [docs/README.md](../README.md)
- 🐛 **问题排查**: [开发指南](../development/TROUBLESHOOTING.md)
- 💬 **社区支持**: [GitHub Issues](your-repo-url/issues)

---

## 🎓 学习路径

### 初学者
1. ✅ 完成快速启动
2. 📖 阅读[用户指南](../frontend/chat/USER_GUIDE.md)
3. 🎯 尝试基础查询
4. 📊 创建第一个Dashboard

### 进阶用户
1. 🏗️ 理解[系统架构](../architecture/OVERVIEW.md)
2. 🗄️ 学习[数据库设计](../backend/DATABASE_SCHEMA.md)
3. 🤖 配置[自定义Agent](../backend/AGENT_SYSTEM.md)
4. 🔌 使用[API集成](../backend/API_REFERENCE.md)

### 开发者
1. 💻 搭建[开发环境](../development/SETUP.md)
2. 📝 阅读[代码规范](../development/CODE_STYLE.md)
3. 🧪 编写[单元测试](../development/TESTING.md)
4. 🚀 参与[项目贡献](../development/CONTRIBUTING.md)

---

**最后更新**: 2026-01-18

**祝你使用愉快！** 🎉
