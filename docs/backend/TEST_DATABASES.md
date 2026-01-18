# 进销存系统测试数据库说明

本项目包含两个进销存系统测试数据库，用于测试和演示Text-to-SQL功能。

## 📊 数据库概览

### 1. inventory_demo (简化版 - 16张表)

**用途**: 轻量级进销存系统，适合快速测试和演示

**创建脚本**: `backend/init_inventory_simple.py`

**表数量**: 16张核心表

**数据量**: 约1700+条记录

#### 数据库连接信息

```
数据库类型: MySQL
主机: localhost
端口: 3306
用户名: root
密码: mysql
数据库名: inventory_demo
```

**连接字符串**:
```
mysql://root:mysql@localhost:3306/inventory_demo
```

#### 表结构说明

##### 基础资料模块 (7张表)
1. **department** - 部门表 (5条)
   - 包含：总经办、财务部、采购部、销售部、仓储部

2. **employee** - 员工表 (10条)
   - 包含各部门的管理人员和业务人员

3. **supplier** - 供应商表 (6条)
   - 包含电子、机械、材料类供应商

4. **customer** - 客户表 (8条)
   - 包含不同信用等级的客户

5. **product_category** - 商品分类表 (10条)
   - 包含电子元器件、机械零件、原材料等分类

6. **product** - 商品表 (20条)
   - 包含电阻、电容、芯片、轴承、齿轮、原材料等

7. **warehouse** - 仓库表 (3条)
   - 原材料仓库、成品仓库、半成品仓库

##### 采购管理模块 (2张表)
8. **purchase_order** - 采购订单主表 (100单)
9. **purchase_order_detail** - 采购订单明细表 (455条)

##### 销售管理模块 (2张表)
10. **sales_order** - 销售订单主表 (150单)
11. **sales_order_detail** - 销售订单明细表 (523条)

##### 库存管理模块 (2张表)
12. **inventory** - 库存表 (28条)
13. **inventory_transaction** - 库存流水表 (200条)

##### 财务管理模块 (3张表)
14. **accounts_payable** - 应付账款表 (50条)
15. **accounts_receivable** - 应收账款表 (60条)
16. **payment_record** - 付款记录表 (90条，含付款和收款)

---

### 2. erp_inventory (完整版 - 40+张表)

**用途**: 完整的进销存ERP系统，包含复杂业务场景

**创建脚本**: `backend/init_erp_mock_data.py`

**表数量**: 40+张表

**数据量**: 约5000+条记录

#### 数据库连接信息

```
数据库类型: MySQL
主机: localhost
端口: 3306
用户名: root
密码: mysql
数据库名: erp_inventory
```

**连接字符串**:
```
mysql://root:mysql@localhost:3306/erp_inventory
```

#### 功能模块

- ✅ 基础资料管理 (部门、员工、供应商、客户、商品、仓库、库位)
- ✅ 采购管理 (采购订单、采购入库、采购退货)
- ✅ 销售管理 (销售订单、销售出库、销售退货)
- ✅ 库存管理 (库存、库存流水、库存调拨、库存盘点)
- ✅ 财务管理 (应付账款、应收账款、付款记录、收款记录)

---

## 🚀 使用方法

### 创建/重建数据库

#### 简化版 (inventory_demo)
```bash
cd backend
python3 init_inventory_simple.py
```

#### 完整版 (erp_inventory)
```bash
cd backend
python3 init_erp_mock_data.py
```

### 在Admin系统中添加数据库连接

1. 登录Admin系统
2. 进入"数据库管理"
3. 点击"添加数据库连接"
4. 填写连接信息：
   - 数据库类型: MySQL
   - 主机: localhost (或 chat_to_db_rwx-mysql 如果使用Docker)
   - 端口: 3306
   - 用户名: root
   - 密码: mysql
   - 数据库名: inventory_demo 或 erp_inventory

### 测试查询示例

#### 简单查询
```
查询所有商品
查询电子元器件类的商品
查询库存数量低于最低库存的商品
```

#### 关联查询
```
查询供应商"深圳华强电子"的所有采购订单
查询客户"广州天成科技"的销售订单总金额
查询每个仓库的库存总数量
```

#### 统计查询
```
统计每个供应商的采购总金额
统计每个客户的销售订单数量
查询销售额最高的前10个商品
统计每个月的采购入库金额
```

#### 复杂查询
```
查询应付账款超过30天未支付的供应商
查询库存周转率最低的商品
查询销售订单中折扣金额最多的订单
分析每个销售员的业绩排名
```

---

## 📝 数据特点

### inventory_demo (简化版)
- ✅ 结构清晰，16张核心表
- ✅ 数据量适中 (~1700条)
- ✅ 适合快速测试
- ✅ 包含基本业务场景
- ✅ 执行速度快

### erp_inventory (完整版)
- ✅ 完整的ERP业务流程
- ✅ 包含批次管理、库位管理
- ✅ 支持入库、出库、退货、调拨、盘点
- ✅ 完整的财务流程
- ✅ 数据量大，适合压力测试

---

## 🔧 维护说明

### 重置数据库
如果需要重置数据，直接重新运行初始化脚本即可。脚本会自动删除旧数据库并创建新的。

```bash
# 重置简化版
python3 backend/init_inventory_simple.py

# 重置完整版
python3 backend/init_erp_mock_data.py
```

### 自定义数据
如需修改Mock数据，可以编辑脚本中的常量数组，如：
- `DEPARTMENTS` - 部门数据
- `EMPLOYEES` - 员工数据
- `SUPPLIERS` - 供应商数据
- `CUSTOMERS` - 客户数据
- `PRODUCTS` - 商品数据
等

### 注意事项
1. 脚本会删除同名数据库，请确保不会误删重要数据
2. 确保MySQL服务正在运行
3. 确保配置了正确的数据库连接信息（在.env文件或脚本中）
4. 如果使用Docker，请确保容器正在运行

---

## 📞 技术支持

如有问题，请检查：
1. MySQL服务是否正常运行
2. 数据库连接配置是否正确
3. pymysql包是否已安装: `pip install pymysql`
4. python-dotenv包是否已安装: `pip install python-dotenv`

---

## 📅 更新日志

- **2026-01-18**: 创建简化版数据库 (inventory_demo)，包含16张核心表
- **2026-01-16**: 创建完整版数据库 (erp_inventory)，包含40+张表
