#!/usr/bin/env python3
"""
简化版进销存系统 Mock 数据初始化脚本

创建一个轻量级的进销存业务数据库，包含16张核心表：
- 基础资料：部门、员工、供应商、客户、商品分类、商品、仓库
- 采购管理：采购订单主表、采购订单明细表
- 销售管理：销售订单主表、销售订单明细表
- 库存管理：库存表、库存流水表
- 财务管理：应付账款、应收账款、付款记录

使用方法：
    python init_inventory_simple.py
"""

import pymysql
import random
from datetime import datetime, timedelta
from decimal import Decimal
import os
from pathlib import Path

# 加载环境变量
env_file = Path(__file__).parent.parent / ".env"
if env_file.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(env_file, override=True)
        print("✅ 已加载 .env 配置")
    except ImportError:
        print("⚠️ python-dotenv 未安装，使用默认配置")

# 数据库配置
DB_CONFIG = {
    'host': os.getenv('MYSQL_SERVER', 'localhost'),
    'port': int(os.getenv('MYSQL_PORT', 3306)),
    'user': os.getenv('MYSQL_USER', 'root'),
    'password': os.getenv('MYSQL_PASSWORD', 'mysql'),
}

# 新数据库名称
DATABASE_NAME = 'inventory_demo'

# ============================================================
# 表结构定义 (16张表)
# ============================================================

CREATE_TABLES_SQL = """
-- 1. 部门表
CREATE TABLE IF NOT EXISTS department (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '部门ID',
    dept_code VARCHAR(20) NOT NULL UNIQUE COMMENT '部门编码',
    dept_name VARCHAR(100) NOT NULL COMMENT '部门名称',
    manager_name VARCHAR(50) COMMENT '部门经理',
    status TINYINT DEFAULT 1 COMMENT '状态：1-启用，0-禁用',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='部门表';

-- 2. 员工表
CREATE TABLE IF NOT EXISTS employee (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '员工ID',
    emp_code VARCHAR(20) NOT NULL UNIQUE COMMENT '员工编号',
    emp_name VARCHAR(50) NOT NULL COMMENT '员工姓名',
    phone VARCHAR(20) COMMENT '联系电话',
    email VARCHAR(100) COMMENT '电子邮箱',
    dept_id BIGINT COMMENT '所属部门ID',
    position VARCHAR(50) COMMENT '职位',
    status TINYINT DEFAULT 1 COMMENT '状态：1-在职，0-离职',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX idx_dept (dept_id),
    FOREIGN KEY (dept_id) REFERENCES department(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='员工表';

-- 3. 供应商表
CREATE TABLE IF NOT EXISTS supplier (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '供应商ID',
    supplier_code VARCHAR(20) NOT NULL UNIQUE COMMENT '供应商编码',
    supplier_name VARCHAR(200) NOT NULL COMMENT '供应商名称',
    contact_person VARCHAR(50) COMMENT '联系人',
    contact_phone VARCHAR(20) COMMENT '联系电话',
    address VARCHAR(500) COMMENT '地址',
    city VARCHAR(50) COMMENT '城市',
    credit_rating VARCHAR(10) COMMENT '信用等级：A/B/C',
    payment_terms INT DEFAULT 30 COMMENT '账期天数',
    status TINYINT DEFAULT 1 COMMENT '状态：1-启用，0-禁用',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='供应商表';

-- 4. 客户表
CREATE TABLE IF NOT EXISTS customer (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '客户ID',
    customer_code VARCHAR(20) NOT NULL UNIQUE COMMENT '客户编码',
    customer_name VARCHAR(200) NOT NULL COMMENT '客户名称',
    contact_person VARCHAR(50) COMMENT '联系人',
    contact_phone VARCHAR(20) COMMENT '联系电话',
    address VARCHAR(500) COMMENT '地址',
    city VARCHAR(50) COMMENT '城市',
    credit_limit DECIMAL(15,2) DEFAULT 0 COMMENT '信用额度',
    credit_rating VARCHAR(10) COMMENT '信用等级：A/B/C',
    status TINYINT DEFAULT 1 COMMENT '状态：1-启用，0-禁用',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='客户表';

-- 5. 商品分类表
CREATE TABLE IF NOT EXISTS product_category (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '分类ID',
    category_code VARCHAR(20) NOT NULL UNIQUE COMMENT '分类编码',
    category_name VARCHAR(100) NOT NULL COMMENT '分类名称',
    parent_id BIGINT DEFAULT NULL COMMENT '上级分类ID',
    status TINYINT DEFAULT 1 COMMENT '状态：1-启用，0-禁用',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX idx_parent (parent_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='商品分类表';

-- 6. 商品表
CREATE TABLE IF NOT EXISTS product (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '商品ID',
    product_code VARCHAR(50) NOT NULL UNIQUE COMMENT '商品编码',
    product_name VARCHAR(200) NOT NULL COMMENT '商品名称',
    category_id BIGINT COMMENT '商品分类ID',
    unit VARCHAR(20) DEFAULT '个' COMMENT '计量单位',
    spec VARCHAR(200) COMMENT '规格型号',
    purchase_price DECIMAL(15,2) DEFAULT 0 COMMENT '采购价',
    sale_price DECIMAL(15,2) DEFAULT 0 COMMENT '销售价',
    cost_price DECIMAL(15,2) DEFAULT 0 COMMENT '成本价',
    min_stock INT DEFAULT 0 COMMENT '最低库存',
    status TINYINT DEFAULT 1 COMMENT '状态：1-启用，0-禁用',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX idx_category (category_id),
    INDEX idx_status (status),
    FOREIGN KEY (category_id) REFERENCES product_category(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='商品表';

-- 7. 仓库表
CREATE TABLE IF NOT EXISTS warehouse (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '仓库ID',
    warehouse_code VARCHAR(20) NOT NULL UNIQUE COMMENT '仓库编码',
    warehouse_name VARCHAR(100) NOT NULL COMMENT '仓库名称',
    address VARCHAR(500) COMMENT '仓库地址',
    manager_id BIGINT COMMENT '仓库管理员ID',
    status TINYINT DEFAULT 1 COMMENT '状态：1-启用，0-禁用',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX idx_manager (manager_id),
    FOREIGN KEY (manager_id) REFERENCES employee(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='仓库表';

-- 8. 采购订单主表
CREATE TABLE IF NOT EXISTS purchase_order (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '采购订单ID',
    order_no VARCHAR(30) NOT NULL UNIQUE COMMENT '采购订单号',
    supplier_id BIGINT NOT NULL COMMENT '供应商ID',
    warehouse_id BIGINT COMMENT '入库仓库ID',
    order_date DATE NOT NULL COMMENT '订单日期',
    buyer_id BIGINT COMMENT '采购员ID',
    order_status TINYINT DEFAULT 0 COMMENT '订单状态：0-草稿，1-待审核，2-已审核，3-已完成，4-已取消',
    total_qty DECIMAL(15,3) DEFAULT 0 COMMENT '总数量',
    total_amount DECIMAL(15,2) DEFAULT 0 COMMENT '总金额',
    remark TEXT COMMENT '备注',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX idx_supplier (supplier_id),
    INDEX idx_warehouse (warehouse_id),
    INDEX idx_status (order_status),
    INDEX idx_date (order_date),
    FOREIGN KEY (supplier_id) REFERENCES supplier(id),
    FOREIGN KEY (warehouse_id) REFERENCES warehouse(id),
    FOREIGN KEY (buyer_id) REFERENCES employee(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='采购订单主表';

-- 9. 采购订单明细表
CREATE TABLE IF NOT EXISTS purchase_order_detail (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '明细ID',
    order_id BIGINT NOT NULL COMMENT '采购订单ID',
    product_id BIGINT NOT NULL COMMENT '商品ID',
    quantity DECIMAL(15,3) NOT NULL COMMENT '采购数量',
    unit_price DECIMAL(15,4) NOT NULL COMMENT '单价',
    amount DECIMAL(15,2) DEFAULT 0 COMMENT '金额',
    remark VARCHAR(500) COMMENT '备注',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX idx_order (order_id),
    INDEX idx_product (product_id),
    FOREIGN KEY (order_id) REFERENCES purchase_order(id),
    FOREIGN KEY (product_id) REFERENCES product(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='采购订单明细表';

-- 10. 销售订单主表
CREATE TABLE IF NOT EXISTS sales_order (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '销售订单ID',
    order_no VARCHAR(30) NOT NULL UNIQUE COMMENT '销售订单号',
    customer_id BIGINT NOT NULL COMMENT '客户ID',
    warehouse_id BIGINT COMMENT '出库仓库ID',
    order_date DATE NOT NULL COMMENT '订单日期',
    salesman_id BIGINT COMMENT '销售员ID',
    order_status TINYINT DEFAULT 0 COMMENT '订单状态：0-草稿，1-待审核，2-已审核，3-已完成，4-已取消',
    total_qty DECIMAL(15,3) DEFAULT 0 COMMENT '总数量',
    total_amount DECIMAL(15,2) DEFAULT 0 COMMENT '总金额',
    discount_amount DECIMAL(15,2) DEFAULT 0 COMMENT '折扣金额',
    remark TEXT COMMENT '备注',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX idx_customer (customer_id),
    INDEX idx_warehouse (warehouse_id),
    INDEX idx_status (order_status),
    INDEX idx_date (order_date),
    FOREIGN KEY (customer_id) REFERENCES customer(id),
    FOREIGN KEY (warehouse_id) REFERENCES warehouse(id),
    FOREIGN KEY (salesman_id) REFERENCES employee(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='销售订单主表';

-- 11. 销售订单明细表
CREATE TABLE IF NOT EXISTS sales_order_detail (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '明细ID',
    order_id BIGINT NOT NULL COMMENT '销售订单ID',
    product_id BIGINT NOT NULL COMMENT '商品ID',
    quantity DECIMAL(15,3) NOT NULL COMMENT '销售数量',
    unit_price DECIMAL(15,4) NOT NULL COMMENT '单价',
    amount DECIMAL(15,2) DEFAULT 0 COMMENT '金额',
    remark VARCHAR(500) COMMENT '备注',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX idx_order (order_id),
    INDEX idx_product (product_id),
    FOREIGN KEY (order_id) REFERENCES sales_order(id),
    FOREIGN KEY (product_id) REFERENCES product(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='销售订单明细表';

-- 12. 库存表
CREATE TABLE IF NOT EXISTS inventory (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '库存ID',
    warehouse_id BIGINT NOT NULL COMMENT '仓库ID',
    product_id BIGINT NOT NULL COMMENT '商品ID',
    quantity DECIMAL(15,3) DEFAULT 0 COMMENT '库存数量',
    available_qty DECIMAL(15,3) DEFAULT 0 COMMENT '可用数量',
    locked_qty DECIMAL(15,3) DEFAULT 0 COMMENT '锁定数量',
    cost_price DECIMAL(15,4) DEFAULT 0 COMMENT '成本单价',
    last_update TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最后更新时间',
    UNIQUE KEY uk_warehouse_product (warehouse_id, product_id),
    INDEX idx_warehouse (warehouse_id),
    INDEX idx_product (product_id),
    FOREIGN KEY (warehouse_id) REFERENCES warehouse(id),
    FOREIGN KEY (product_id) REFERENCES product(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='库存表';

-- 13. 库存流水表
CREATE TABLE IF NOT EXISTS inventory_transaction (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '流水ID',
    transaction_no VARCHAR(30) NOT NULL COMMENT '流水号',
    transaction_type VARCHAR(20) NOT NULL COMMENT '业务类型：PURCHASE_IN-采购入库,SALES_OUT-销售出库,ADJUST-盘点调整',
    ref_order_no VARCHAR(30) COMMENT '关联单据号',
    warehouse_id BIGINT NOT NULL COMMENT '仓库ID',
    product_id BIGINT NOT NULL COMMENT '商品ID',
    direction TINYINT NOT NULL COMMENT '方向：1-入库，-1-出库',
    quantity DECIMAL(15,3) NOT NULL COMMENT '数量',
    before_qty DECIMAL(15,3) DEFAULT 0 COMMENT '变动前数量',
    after_qty DECIMAL(15,3) DEFAULT 0 COMMENT '变动后数量',
    unit_price DECIMAL(15,4) DEFAULT 0 COMMENT '单价',
    operator_id BIGINT COMMENT '操作人ID',
    transaction_time DATETIME NOT NULL COMMENT '发生时间',
    remark VARCHAR(500) COMMENT '备注',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX idx_type (transaction_type),
    INDEX idx_ref (ref_order_no),
    INDEX idx_warehouse (warehouse_id),
    INDEX idx_product (product_id),
    INDEX idx_time (transaction_time),
    FOREIGN KEY (warehouse_id) REFERENCES warehouse(id),
    FOREIGN KEY (product_id) REFERENCES product(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='库存流水表';

-- 14. 应付账款表
CREATE TABLE IF NOT EXISTS accounts_payable (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '应付ID',
    payable_no VARCHAR(30) NOT NULL UNIQUE COMMENT '应付单号',
    supplier_id BIGINT NOT NULL COMMENT '供应商ID',
    source_order_no VARCHAR(30) COMMENT '来源单据号',
    payable_amount DECIMAL(15,2) NOT NULL COMMENT '应付金额',
    paid_amount DECIMAL(15,2) DEFAULT 0 COMMENT '已付金额',
    unpaid_amount DECIMAL(15,2) NOT NULL COMMENT '未付金额',
    due_date DATE COMMENT '到期日',
    status TINYINT DEFAULT 0 COMMENT '状态：0-未付，1-部分付款，2-已付清',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX idx_supplier (supplier_id),
    INDEX idx_due (due_date),
    INDEX idx_status (status),
    FOREIGN KEY (supplier_id) REFERENCES supplier(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='应付账款表';

-- 15. 应收账款表
CREATE TABLE IF NOT EXISTS accounts_receivable (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '应收ID',
    receivable_no VARCHAR(30) NOT NULL UNIQUE COMMENT '应收单号',
    customer_id BIGINT NOT NULL COMMENT '客户ID',
    source_order_no VARCHAR(30) COMMENT '来源单据号',
    receivable_amount DECIMAL(15,2) NOT NULL COMMENT '应收金额',
    received_amount DECIMAL(15,2) DEFAULT 0 COMMENT '已收金额',
    unreceived_amount DECIMAL(15,2) NOT NULL COMMENT '未收金额',
    due_date DATE COMMENT '到期日',
    status TINYINT DEFAULT 0 COMMENT '状态：0-未收，1-部分收款，2-已收清',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX idx_customer (customer_id),
    INDEX idx_due (due_date),
    INDEX idx_status (status),
    FOREIGN KEY (customer_id) REFERENCES customer(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='应收账款表';

-- 16. 付款记录表
CREATE TABLE IF NOT EXISTS payment_record (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '付款ID',
    payment_no VARCHAR(30) NOT NULL UNIQUE COMMENT '付款单号',
    supplier_id BIGINT COMMENT '供应商ID',
    customer_id BIGINT COMMENT '客户ID',
    payment_type VARCHAR(20) NOT NULL COMMENT '类型：PAY-付款，RECEIVE-收款',
    payment_amount DECIMAL(15,2) NOT NULL COMMENT '金额',
    payment_method VARCHAR(20) NOT NULL COMMENT '方式：CASH-现金，BANK-银行转账',
    payment_date DATE NOT NULL COMMENT '日期',
    handler_id BIGINT COMMENT '经手人ID',
    remark TEXT COMMENT '备注',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX idx_supplier (supplier_id),
    INDEX idx_customer (customer_id),
    INDEX idx_date (payment_date),
    FOREIGN KEY (supplier_id) REFERENCES supplier(id),
    FOREIGN KEY (customer_id) REFERENCES customer(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='付款记录表';
"""

# ============================================================
# Mock 数据常量
# ============================================================

DEPARTMENTS = [
    ('D001', '总经办', '张海洋'),
    ('D002', '财务部', '李明达'),
    ('D003', '采购部', '赵强'),
    ('D004', '销售部', '周杰'),
    ('D005', '仓储部', '马立成'),
]

EMPLOYEES = [
    ('E001', '张海洋', '13800001001', 'zhang@company.com', 'D001', '总经理'),
    ('E002', '李明达', '13800001002', 'li@company.com', 'D002', '财务经理'),
    ('E003', '王芳', '13800001003', 'wang@company.com', 'D002', '会计'),
    ('E004', '赵强', '13800001004', 'zhao@company.com', 'D003', '采购经理'),
    ('E005', '刘洋', '13800001005', 'liu@company.com', 'D003', '采购员'),
    ('E006', '周杰', '13800001007', 'zhou@company.com', 'D004', '销售经理'),
    ('E007', '吴敏', '13800001008', 'wu@company.com', 'D004', '销售代表'),
    ('E008', '郑伟', '13800001009', 'zheng@company.com', 'D004', '销售代表'),
    ('E009', '马立成', '13800001011', 'ma@company.com', 'D005', '仓库经理'),
    ('E010', '朱建国', '13800001012', 'zhu@company.com', 'D005', '仓管员'),
]

SUPPLIERS = [
    ('S001', '深圳华强电子有限公司', '张经理', '0755-88881001', '深圳市南山区', '深圳', 'A', 30),
    ('S002', '东莞华利电子科技有限公司', '李总', '0769-22221002', '东莞市长安镇', '东莞', 'A', 45),
    ('S003', '上海精密机械制造有限公司', '王总', '021-55551003', '上海市嘉定区', '上海', 'B', 30),
    ('S004', '苏州工业机械有限公司', '刘总', '0512-66661004', '苏州市工业园区', '苏州', 'A', 30),
    ('S005', '安徽新材料科技有限公司', '赵总', '0551-77771005', '合肥市高新区', '合肥', 'B', 45),
    ('S006', '浙江化工原料有限公司', '周总', '0571-88881006', '杭州市滨江区', '杭州', 'A', 30),
]

CUSTOMERS = [
    ('C001', '广州天成科技有限公司', '张总', '020-88881001', '广州市天河区科技园', '广州', 500000, 'A'),
    ('C002', '上海创新电子有限公司', '李总', '021-77771002', '上海市浦东新区', '上海', 800000, 'A'),
    ('C003', '北京华兴机械有限公司', '王总', '010-66661003', '北京市朝阳区', '北京', 300000, 'A'),
    ('C004', '深圳安达电子有限公司', '赵总', '0755-55551004', '深圳市福田区', '深圳', 200000, 'B'),
    ('C005', '武汉光谷科技有限公司', '周总', '027-44441005', '武汉市洪山区', '武汉', 150000, 'B'),
    ('C006', '成都美创工业有限公司', '陈总', '028-33331006', '成都市高新区', '成都', 100000, 'B'),
    ('C007', '浙江美威家电有限公司', '刘总', '0571-22221007', '杭州市余杭区', '杭州', 250000, 'A'),
    ('C008', '重庆机电集团', '范总', '023-11111008', '重庆市江北区', '重庆', 600000, 'A'),
]

PRODUCT_CATEGORIES = [
    ('PC01', '电子元器件', None),
    ('PC0101', '电阻', 'PC01'),
    ('PC0102', '电容', 'PC01'),
    ('PC0103', '芯片', 'PC01'),
    ('PC02', '机械零件', None),
    ('PC0201', '轴承', 'PC02'),
    ('PC0202', '齿轮', 'PC02'),
    ('PC03', '原材料', None),
    ('PC0301', '铝材', 'PC03'),
    ('PC0302', '钢材', 'PC03'),
]

PRODUCTS = [
    ('P0001', '10KΩ电阻', 'PC0101', '个', '1/4W ±1%', 0.02, 0.05, 0.015, 5000),
    ('P0002', '100KΩ电阻', 'PC0101', '个', '1/4W ±1%', 0.02, 0.05, 0.015, 5000),
    ('P0003', '10uF电容', 'PC0102', '个', '50V', 0.15, 0.35, 0.12, 3000),
    ('P0004', '100uF电容', 'PC0102', '个', '25V', 0.25, 0.55, 0.20, 3000),
    ('P0005', 'STM32F103芯片', 'PC0103', '个', 'LQFP48', 8.50, 18.00, 7.50, 500),
    ('P0006', 'STM32F407芯片', 'PC0103', '个', 'LQFP100', 35.00, 68.00, 30.00, 200),
    ('P0007', '6205轴承', 'PC0201', '个', '25x52x15mm', 12.00, 28.00, 10.50, 200),
    ('P0008', '6206轴承', 'PC0201', '个', '30x62x16mm', 15.00, 35.00, 13.00, 200),
    ('P0009', '直齿轮M1.5', 'PC0202', '个', '模数1.5 20齿', 8.50, 20.00, 7.50, 100),
    ('P0010', '斜齿轮M2', 'PC0202', '个', '模数2 25齿', 12.00, 28.00, 10.50, 100),
    ('P0011', '6061铝板', 'PC0301', '公斤', '5mm厚', 28.00, 55.00, 25.00, 100),
    ('P0012', '6063铝型材', 'PC0301', '公斤', '40x40x3', 25.00, 48.00, 22.00, 100),
    ('P0013', '45#钢棒', 'PC0302', '公斤', '直径50mm', 6.00, 12.00, 5.50, 200),
    ('P0014', '304不锈钢板', 'PC0302', '公斤', '2mm厚', 18.00, 35.00, 16.00, 100),
    ('P0015', 'ESP32模块', 'PC0103', '个', 'WiFi+BLE', 15.00, 32.00, 13.00, 500),
    ('P0016', '1N4007二极管', 'PC0101', '个', '1A/1000V', 0.05, 0.12, 0.04, 10000),
    ('P0017', 'SS8050三极管', 'PC0101', '个', 'NPN 1.5A', 0.10, 0.25, 0.08, 8000),
    ('P0018', '57步进电机', 'PC02', '个', '57x57mm', 45.00, 98.00, 40.00, 30),
    ('P0019', '42步进电机', 'PC02', '个', '42x42mm', 28.00, 62.00, 25.00, 50),
    ('P0020', 'O型圈20x2', 'PC02', '个', 'NBR材质', 0.15, 0.40, 0.12, 2000),
]

WAREHOUSES = [
    ('WH01', '原材料仓库', '工业园区A栋', 'E009'),
    ('WH02', '成品仓库', '工业园区B栋', 'E009'),
    ('WH03', '半成品仓库', '工业园区C栋', 'E010'),
]


def create_database():
    """创建数据库和表结构"""
    print("\n" + "="*60)
    print(f"开始创建数据库: {DATABASE_NAME}")
    print("="*60)
    
    conn = pymysql.connect(**DB_CONFIG)
    cursor = conn.cursor()
    
    try:
        # 创建数据库
        cursor.execute(f"DROP DATABASE IF EXISTS {DATABASE_NAME}")
        cursor.execute(f"CREATE DATABASE {DATABASE_NAME} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        print(f"✅ 数据库创建成功")
        
        cursor.execute(f"USE {DATABASE_NAME}")
        
        # 执行建表SQL
        table_count = 0
        for statement in CREATE_TABLES_SQL.split(';'):
            statement = statement.strip()
            if statement and 'CREATE TABLE' in statement.upper():
                try:
                    cursor.execute(statement)
                    table_count += 1
                except Exception as e:
                    print(f"⚠️ 建表警告: {str(e)[:100]}")
        
        conn.commit()
        print(f"✅ 表结构创建成功 (共 {table_count} 张表)")
        
    finally:
        cursor.close()
        conn.close()


def insert_mock_data():
    """插入Mock数据"""
    print("\n" + "-"*60)
    print("正在插入Mock数据...")
    print("-"*60)
    
    conn = pymysql.connect(**DB_CONFIG, database=DATABASE_NAME)
    cursor = conn.cursor()
    
    try:
        # 1. 插入部门
        dept_id_map = {}
        for dept in DEPARTMENTS:
            cursor.execute(
                "INSERT INTO department (dept_code, dept_name, manager_name) VALUES (%s, %s, %s)",
                (dept[0], dept[1], dept[2])
            )
            dept_id_map[dept[0]] = cursor.lastrowid
        print(f"✅ 插入部门: {len(DEPARTMENTS)} 条")
        
        # 2. 插入员工
        emp_id_map = {}
        for emp in EMPLOYEES:
            dept_id = dept_id_map.get(emp[4])
            cursor.execute(
                "INSERT INTO employee (emp_code, emp_name, phone, email, dept_id, position) VALUES (%s, %s, %s, %s, %s, %s)",
                (emp[0], emp[1], emp[2], emp[3], dept_id, emp[5])
            )
            emp_id_map[emp[0]] = cursor.lastrowid
        print(f"✅ 插入员工: {len(EMPLOYEES)} 条")
        
        # 3. 插入供应商
        supplier_id_map = {}
        for s in SUPPLIERS:
            cursor.execute(
                """INSERT INTO supplier (supplier_code, supplier_name, contact_person, contact_phone, 
                   address, city, credit_rating, payment_terms) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                (s[0], s[1], s[2], s[3], s[4], s[5], s[6], s[7])
            )
            supplier_id_map[s[0]] = cursor.lastrowid
        print(f"✅ 插入供应商: {len(SUPPLIERS)} 条")
        
        # 4. 插入客户
        customer_id_map = {}
        for c in CUSTOMERS:
            cursor.execute(
                """INSERT INTO customer (customer_code, customer_name, contact_person, contact_phone,
                   address, city, credit_limit, credit_rating) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                (c[0], c[1], c[2], c[3], c[4], c[5], c[6], c[7])
            )
            customer_id_map[c[0]] = cursor.lastrowid
        print(f"✅ 插入客户: {len(CUSTOMERS)} 条")
        
        # 5. 插入商品分类
        cat_id_map = {}
        for cat in PRODUCT_CATEGORIES:
            parent_id = cat_id_map.get(cat[2]) if cat[2] else None
            cursor.execute(
                "INSERT INTO product_category (category_code, category_name, parent_id) VALUES (%s, %s, %s)",
                (cat[0], cat[1], parent_id)
            )
            cat_id_map[cat[0]] = cursor.lastrowid
        print(f"✅ 插入商品分类: {len(PRODUCT_CATEGORIES)} 条")
        
        # 6. 插入商品
        product_id_map = {}
        for p in PRODUCTS:
            cat_id = cat_id_map.get(p[2])
            cursor.execute(
                """INSERT INTO product (product_code, product_name, category_id, unit, spec,
                   purchase_price, sale_price, cost_price, min_stock) 
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (p[0], p[1], cat_id, p[3], p[4], p[5], p[6], p[7], p[8])
            )
            product_id_map[p[0]] = cursor.lastrowid
        print(f"✅ 插入商品: {len(PRODUCTS)} 条")
        
        # 7. 插入仓库
        warehouse_id_map = {}
        for wh in WAREHOUSES:
            manager_id = emp_id_map.get(wh[3])
            cursor.execute(
                "INSERT INTO warehouse (warehouse_code, warehouse_name, address, manager_id) VALUES (%s, %s, %s, %s)",
                (wh[0], wh[1], wh[2], manager_id)
            )
            warehouse_id_map[wh[0]] = cursor.lastrowid
        print(f"✅ 插入仓库: {len(WAREHOUSES)} 条")
        
        # 获取ID列表
        supplier_ids = list(supplier_id_map.values())
        customer_ids = list(customer_id_map.values())
        product_ids = list(product_id_map.values())
        warehouse_ids = list(warehouse_id_map.values())
        buyer_ids = [emp_id_map['E004'], emp_id_map['E005']]
        salesman_ids = [emp_id_map['E006'], emp_id_map['E007'], emp_id_map['E008']]
        
        # 获取商品价格
        cursor.execute("SELECT id, purchase_price, sale_price FROM product")
        product_prices = {row[0]: {'purchase': float(row[1]), 'sale': float(row[2])} for row in cursor.fetchall()}
        
        # 8. 插入采购订单 (100单)
        print("正在生成采购订单...")
        for i in range(100):
            order_date = datetime.now() - timedelta(days=random.randint(1, 180))
            order_no = f"PO{order_date.strftime('%Y%m%d')}{i+1:04d}"
            supplier_id = random.choice(supplier_ids)
            warehouse_id = warehouse_ids[0]
            buyer_id = random.choice(buyer_ids)
            order_status = random.choices([0, 1, 2, 3, 4], weights=[5, 10, 20, 60, 5])[0]
            
            # 生成3-6个明细
            detail_count = random.randint(3, 6)
            selected_products = random.sample(product_ids, min(detail_count, len(product_ids)))
            
            total_qty = 0
            total_amount = 0
            
            cursor.execute(
                """INSERT INTO purchase_order (order_no, supplier_id, warehouse_id, order_date,
                   buyer_id, order_status, total_qty, total_amount)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                (order_no, supplier_id, warehouse_id, order_date.date(), buyer_id, order_status, 0, 0)
            )
            order_id = cursor.lastrowid
            
            for prod_id in selected_products:
                qty = random.randint(100, 2000)
                unit_price = product_prices.get(prod_id, {'purchase': 10.0})['purchase']
                amount = qty * unit_price
                
                total_qty += qty
                total_amount += amount
                
                cursor.execute(
                    """INSERT INTO purchase_order_detail (order_id, product_id, quantity, unit_price, amount)
                       VALUES (%s, %s, %s, %s, %s)""",
                    (order_id, prod_id, qty, unit_price, round(amount, 2))
                )
            
            # 更新订单总计
            cursor.execute(
                "UPDATE purchase_order SET total_qty = %s, total_amount = %s WHERE id = %s",
                (round(total_qty, 3), round(total_amount, 2), order_id)
            )
        
        print(f"✅ 插入采购订单: 100 单")
        
        # 9. 插入销售订单 (150单)
        print("正在生成销售订单...")
        for i in range(150):
            order_date = datetime.now() - timedelta(days=random.randint(1, 180))
            order_no = f"SO{order_date.strftime('%Y%m%d')}{i+1:04d}"
            customer_id = random.choice(customer_ids)
            warehouse_id = warehouse_ids[1]
            salesman_id = random.choice(salesman_ids)
            order_status = random.choices([0, 1, 2, 3, 4], weights=[3, 8, 15, 70, 4])[0]
            
            detail_count = random.randint(2, 5)
            selected_products = random.sample(product_ids, min(detail_count, len(product_ids)))
            
            total_qty = 0
            total_amount = 0
            discount_amount = 0
            
            cursor.execute(
                """INSERT INTO sales_order (order_no, customer_id, warehouse_id, order_date,
                   salesman_id, order_status, total_qty, total_amount, discount_amount)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (order_no, customer_id, warehouse_id, order_date.date(), salesman_id, order_status, 0, 0, 0)
            )
            order_id = cursor.lastrowid
            
            for prod_id in selected_products:
                qty = random.randint(10, 500)
                unit_price = product_prices.get(prod_id, {'sale': 20.0})['sale'] * random.uniform(0.9, 1.0)
                amount = qty * unit_price
                
                total_qty += qty
                total_amount += amount
                
                cursor.execute(
                    """INSERT INTO sales_order_detail (order_id, product_id, quantity, unit_price, amount)
                       VALUES (%s, %s, %s, %s, %s)""",
                    (order_id, prod_id, qty, round(unit_price, 4), round(amount, 2))
                )
            
            discount_amount = total_amount * random.uniform(0, 0.05)
            
            cursor.execute(
                "UPDATE sales_order SET total_qty = %s, total_amount = %s, discount_amount = %s WHERE id = %s",
                (round(total_qty, 3), round(total_amount, 2), round(discount_amount, 2), order_id)
            )
        
        print(f"✅ 插入销售订单: 150 单")
        
        # 10. 插入库存数据
        print("正在生成库存数据...")
        inventory_count = 0
        for prod_id in product_ids:
            for wh_id in warehouse_ids[:2]:
                if random.random() < 0.7:
                    qty = random.randint(100, 5000)
                    available = int(qty * 0.9)
                    locked = qty - available
                    cost = product_prices.get(prod_id, {'purchase': 10.0})['purchase']
                    
                    cursor.execute(
                        """INSERT INTO inventory (warehouse_id, product_id, quantity, available_qty, 
                           locked_qty, cost_price) VALUES (%s, %s, %s, %s, %s, %s)""",
                        (wh_id, prod_id, qty, available, locked, cost)
                    )
                    inventory_count += 1
        
        print(f"✅ 插入库存数据: {inventory_count} 条")
        
        # 11. 插入库存流水
        print("正在生成库存流水...")
        trans_types = ['PURCHASE_IN', 'SALES_OUT', 'ADJUST']
        for i in range(200):
            trans_type = random.choice(trans_types)
            direction = 1 if trans_type in ['PURCHASE_IN', 'ADJUST'] else -1
            trans_time = datetime.now() - timedelta(days=random.randint(1, 90))
            trans_no = f"IT{trans_time.strftime('%Y%m%d%H%M')}{i:04d}"
            
            prod_id = random.choice(product_ids)
            wh_id = random.choice(warehouse_ids[:2])
            qty = random.randint(10, 500)
            before = random.randint(500, 3000)
            after = before + (qty * direction)
            price = product_prices.get(prod_id, {'purchase': 10.0})['purchase']
            
            cursor.execute(
                """INSERT INTO inventory_transaction (transaction_no, transaction_type, warehouse_id,
                   product_id, direction, quantity, before_qty, after_qty, unit_price, 
                   operator_id, transaction_time)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (trans_no, trans_type, wh_id, prod_id, direction, qty, before, max(0, after),
                 price, random.choice(list(emp_id_map.values())), trans_time)
            )
        
        print(f"✅ 插入库存流水: 200 条")
        
        # 12. 插入应付账款
        print("正在生成应付账款...")
        for i in range(50):
            payable_no = f"AP{datetime.now().strftime('%Y%m')}{i+1:04d}"
            supplier_id = random.choice(supplier_ids)
            amount = round(random.uniform(5000, 100000), 2)
            paid = 0
            status = 0
            
            if random.random() < 0.5:
                paid = amount
                status = 2
            elif random.random() < 0.3:
                paid = round(amount * random.uniform(0.3, 0.7), 2)
                status = 1
            
            due_date = datetime.now() + timedelta(days=random.randint(-15, 45))
            
            cursor.execute(
                """INSERT INTO accounts_payable (payable_no, supplier_id, payable_amount,
                   paid_amount, unpaid_amount, due_date, status)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (payable_no, supplier_id, amount, paid, round(amount - paid, 2), due_date.date(), status)
            )
        
        print(f"✅ 插入应付账款: 50 条")
        
        # 13. 插入应收账款
        print("正在生成应收账款...")
        for i in range(60):
            receivable_no = f"AR{datetime.now().strftime('%Y%m')}{i+1:04d}"
            customer_id = random.choice(customer_ids)
            amount = round(random.uniform(3000, 80000), 2)
            received = 0
            status = 0
            
            if random.random() < 0.55:
                received = amount
                status = 2
            elif random.random() < 0.25:
                received = round(amount * random.uniform(0.3, 0.7), 2)
                status = 1
            
            due_date = datetime.now() + timedelta(days=random.randint(-10, 30))
            
            cursor.execute(
                """INSERT INTO accounts_receivable (receivable_no, customer_id, receivable_amount,
                   received_amount, unreceived_amount, due_date, status)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (receivable_no, customer_id, amount, received, round(amount - received, 2), due_date.date(), status)
            )
        
        print(f"✅ 插入应收账款: 60 条")
        
        # 14. 插入付款记录
        print("正在生成付款记录...")
        payment_methods = ['CASH', 'BANK']
        
        # 付款记录
        for i in range(40):
            payment_no = f"PAY{datetime.now().strftime('%Y%m')}{i+1:04d}"
            supplier_id = random.choice(supplier_ids)
            amount = round(random.uniform(2000, 50000), 2)
            method = random.choice(payment_methods)
            date = datetime.now() - timedelta(days=random.randint(1, 90))
            
            cursor.execute(
                """INSERT INTO payment_record (payment_no, supplier_id, payment_type, payment_amount,
                   payment_method, payment_date, handler_id)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (payment_no, supplier_id, 'PAY', amount, method, date.date(), emp_id_map['E002'])
            )
        
        # 收款记录
        for i in range(50):
            payment_no = f"REC{datetime.now().strftime('%Y%m')}{i+1:04d}"
            customer_id = random.choice(customer_ids)
            amount = round(random.uniform(1500, 40000), 2)
            method = random.choice(payment_methods)
            date = datetime.now() - timedelta(days=random.randint(1, 90))
            
            cursor.execute(
                """INSERT INTO payment_record (payment_no, customer_id, payment_type, payment_amount,
                   payment_method, payment_date, handler_id)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (payment_no, customer_id, 'RECEIVE', amount, method, date.date(), emp_id_map['E002'])
            )
        
        print(f"✅ 插入付款记录: 90 条 (付款40 + 收款50)")
        
        conn.commit()
        
    finally:
        cursor.close()
        conn.close()


def print_summary():
    """打印数据库统计信息"""
    print("\n" + "="*60)
    print("数据库统计信息")
    print("="*60)
    
    conn = pymysql.connect(**DB_CONFIG, database=DATABASE_NAME)
    cursor = conn.cursor()
    
    try:
        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()
        
        print(f"\n📊 数据库: {DATABASE_NAME}")
        print(f"📋 表数量: {len(tables)}")
        print("\n各表数据统计:")
        print("-" * 50)
        
        total_rows = 0
        for (table,) in sorted(tables):
            cursor.execute(f"SELECT COUNT(*) FROM `{table}`")
            count = cursor.fetchone()[0]
            total_rows += count
            print(f"  {table:30s}: {count:>6d} 条")
        
        print("-" * 50)
        print(f"  {'总计':30s}: {total_rows:>6d} 条数据")
        
    finally:
        cursor.close()
        conn.close()


def main():
    """主函数"""
    print("\n" + "#"*60)
    print("#  简化版进销存系统 Mock 数据初始化工具")
    print("#  包含 16 张核心表")
    print("#"*60)
    
    print(f"\n📍 数据库服务器: {DB_CONFIG['host']}:{DB_CONFIG['port']}")
    print(f"📍 数据库名称: {DATABASE_NAME}")
    print(f"📍 用户名: {DB_CONFIG['user']}")
    
    try:
        # 1. 创建数据库和表
        create_database()
        
        # 2. 插入Mock数据
        insert_mock_data()
        
        # 3. 打印统计信息
        print_summary()
        
        print("\n" + "="*60)
        print("✅ 数据库初始化完成!")
        print("="*60)
        
        print(f"\n🔗 数据库连接信息:")
        print(f"  数据库类型: MySQL")
        print(f"  主机: {DB_CONFIG['host']}")
        print(f"  端口: {DB_CONFIG['port']}")
        print(f"  用户名: {DB_CONFIG['user']}")
        print(f"  密码: {DB_CONFIG['password']}")
        print(f"  数据库名: {DATABASE_NAME}")
        
        print(f"\n💡 您可以使用以下连接字符串:")
        print(f"  mysql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DATABASE_NAME}")
        
        print(f"\n📝 数据库包含以下业务模块:")
        print(f"  ✓ 基础资料 (部门、员工、供应商、客户、商品、仓库)")
        print(f"  ✓ 采购管理 (采购订单及明细)")
        print(f"  ✓ 销售管理 (销售订单及明细)")
        print(f"  ✓ 库存管理 (库存、库存流水)")
        print(f"  ✓ 财务管理 (应付/应收账款、付款记录)")
        
    except Exception as e:
        print(f"\n❌ 错误: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
