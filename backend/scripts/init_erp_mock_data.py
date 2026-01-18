#!/usr/bin/env python3
"""
进销存系统（ERP）Mock数据初始化脚本

创建一个完整的进销存业务数据库，包含：
- 基础资料：供应商、客户、商品、仓库、员工
- 采购管理：采购订单、采购入库、采购退货
- 销售管理：销售订单、销售出库、销售退货
- 库存管理：库存记录、库存流水、盘点记录
- 财务管理：应付账款、应收账款、付款记录、收款记录

使用方法：
    python init_erp_mock_data.py
"""

import pymysql
import random
from datetime import datetime, timedelta
from decimal import Decimal
import os
from pathlib import Path

# 加载环境变量
env_file = Path(__file__).parent / ".env"
if env_file.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(env_file, override=True)
        print("✅ 已加载 .env 配置")
    except ImportError:
        print("⚠️ python-dotenv 未安装")

# 数据库配置
DB_CONFIG = {
    'host': os.getenv('MYSQL_SERVER', 'localhost'),
    'port': int(os.getenv('MYSQL_PORT', 3306)),
    'user': os.getenv('MYSQL_USER', 'root'),
    'password': os.getenv('MYSQL_PASSWORD', 'mysql'),
}

# 新数据库名称
ERP_DATABASE = 'erp_inventory'

# ============================================================
# 表结构定义
# ============================================================

CREATE_TABLES_SQL = """
-- ========================================
-- 1. 基础资料模块
-- ========================================

-- 1.1 部门表
CREATE TABLE IF NOT EXISTS department (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '部门ID',
    dept_code VARCHAR(20) NOT NULL UNIQUE COMMENT '部门编码',
    dept_name VARCHAR(100) NOT NULL COMMENT '部门名称',
    parent_id BIGINT DEFAULT NULL COMMENT '上级部门ID',
    manager_id BIGINT DEFAULT NULL COMMENT '部门经理ID',
    status TINYINT DEFAULT 1 COMMENT '状态：1-启用，0-禁用',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_parent (parent_id),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='部门表';

-- 1.2 员工表
CREATE TABLE IF NOT EXISTS employee (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '员工ID',
    emp_code VARCHAR(20) NOT NULL UNIQUE COMMENT '员工编号',
    emp_name VARCHAR(50) NOT NULL COMMENT '员工姓名',
    gender TINYINT DEFAULT 1 COMMENT '性别：1-男，2-女',
    phone VARCHAR(20) COMMENT '联系电话',
    email VARCHAR(100) COMMENT '电子邮箱',
    dept_id BIGINT COMMENT '所属部门ID',
    position VARCHAR(50) COMMENT '职位',
    hire_date DATE COMMENT '入职日期',
    status TINYINT DEFAULT 1 COMMENT '状态：1-在职，0-离职',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_dept (dept_id),
    INDEX idx_status (status),
    FOREIGN KEY (dept_id) REFERENCES department(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='员工表';

-- 1.3 供应商分类表
CREATE TABLE IF NOT EXISTS supplier_category (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '分类ID',
    category_code VARCHAR(20) NOT NULL UNIQUE COMMENT '分类编码',
    category_name VARCHAR(100) NOT NULL COMMENT '分类名称',
    parent_id BIGINT DEFAULT NULL COMMENT '上级分类ID',
    sort_order INT DEFAULT 0 COMMENT '排序号',
    status TINYINT DEFAULT 1 COMMENT '状态：1-启用，0-禁用',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX idx_parent (parent_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='供应商分类表';

-- 1.4 供应商表
CREATE TABLE IF NOT EXISTS supplier (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '供应商ID',
    supplier_code VARCHAR(20) NOT NULL UNIQUE COMMENT '供应商编码',
    supplier_name VARCHAR(200) NOT NULL COMMENT '供应商名称',
    category_id BIGINT COMMENT '供应商分类ID',
    contact_person VARCHAR(50) COMMENT '联系人',
    contact_phone VARCHAR(20) COMMENT '联系电话',
    contact_email VARCHAR(100) COMMENT '电子邮箱',
    address VARCHAR(500) COMMENT '地址',
    province VARCHAR(50) COMMENT '省份',
    city VARCHAR(50) COMMENT '城市',
    district VARCHAR(50) COMMENT '区县',
    bank_name VARCHAR(100) COMMENT '开户银行',
    bank_account VARCHAR(50) COMMENT '银行账号',
    tax_number VARCHAR(50) COMMENT '税号',
    credit_rating VARCHAR(10) COMMENT '信用等级：A/B/C/D',
    payment_terms INT DEFAULT 30 COMMENT '账期天数',
    status TINYINT DEFAULT 1 COMMENT '状态：1-启用，0-禁用',
    remark TEXT COMMENT '备注',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_category (category_id),
    INDEX idx_status (status),
    INDEX idx_credit (credit_rating),
    FOREIGN KEY (category_id) REFERENCES supplier_category(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='供应商表';

-- 1.5 客户分类表
CREATE TABLE IF NOT EXISTS customer_category (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '分类ID',
    category_code VARCHAR(20) NOT NULL UNIQUE COMMENT '分类编码',
    category_name VARCHAR(100) NOT NULL COMMENT '分类名称',
    parent_id BIGINT DEFAULT NULL COMMENT '上级分类ID',
    discount_rate DECIMAL(5,2) DEFAULT 100.00 COMMENT '折扣率（百分比）',
    sort_order INT DEFAULT 0 COMMENT '排序号',
    status TINYINT DEFAULT 1 COMMENT '状态：1-启用，0-禁用',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX idx_parent (parent_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='客户分类表';

-- 1.6 客户表
CREATE TABLE IF NOT EXISTS customer (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '客户ID',
    customer_code VARCHAR(20) NOT NULL UNIQUE COMMENT '客户编码',
    customer_name VARCHAR(200) NOT NULL COMMENT '客户名称',
    customer_type TINYINT DEFAULT 1 COMMENT '客户类型：1-企业，2-个人',
    category_id BIGINT COMMENT '客户分类ID',
    contact_person VARCHAR(50) COMMENT '联系人',
    contact_phone VARCHAR(20) COMMENT '联系电话',
    contact_email VARCHAR(100) COMMENT '电子邮箱',
    address VARCHAR(500) COMMENT '地址',
    province VARCHAR(50) COMMENT '省份',
    city VARCHAR(50) COMMENT '城市',
    district VARCHAR(50) COMMENT '区县',
    credit_limit DECIMAL(15,2) DEFAULT 0 COMMENT '信用额度',
    credit_rating VARCHAR(10) COMMENT '信用等级：A/B/C/D',
    sales_rep_id BIGINT COMMENT '销售代表ID',
    payment_terms INT DEFAULT 30 COMMENT '账期天数',
    status TINYINT DEFAULT 1 COMMENT '状态：1-启用，0-禁用',
    remark TEXT COMMENT '备注',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_category (category_id),
    INDEX idx_sales_rep (sales_rep_id),
    INDEX idx_status (status),
    INDEX idx_type (customer_type),
    FOREIGN KEY (category_id) REFERENCES customer_category(id),
    FOREIGN KEY (sales_rep_id) REFERENCES employee(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='客户表';

-- 1.7 商品分类表
CREATE TABLE IF NOT EXISTS product_category (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '分类ID',
    category_code VARCHAR(20) NOT NULL UNIQUE COMMENT '分类编码',
    category_name VARCHAR(100) NOT NULL COMMENT '分类名称',
    parent_id BIGINT DEFAULT NULL COMMENT '上级分类ID',
    level INT DEFAULT 1 COMMENT '层级',
    sort_order INT DEFAULT 0 COMMENT '排序号',
    status TINYINT DEFAULT 1 COMMENT '状态：1-启用，0-禁用',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX idx_parent (parent_id),
    INDEX idx_level (level)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='商品分类表';

-- 1.8 计量单位表
CREATE TABLE IF NOT EXISTS unit (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '单位ID',
    unit_code VARCHAR(20) NOT NULL UNIQUE COMMENT '单位编码',
    unit_name VARCHAR(50) NOT NULL COMMENT '单位名称',
    status TINYINT DEFAULT 1 COMMENT '状态：1-启用，0-禁用',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='计量单位表';

-- 1.9 品牌表
CREATE TABLE IF NOT EXISTS brand (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '品牌ID',
    brand_code VARCHAR(20) NOT NULL UNIQUE COMMENT '品牌编码',
    brand_name VARCHAR(100) NOT NULL COMMENT '品牌名称',
    logo_url VARCHAR(500) COMMENT '品牌Logo',
    description TEXT COMMENT '品牌描述',
    status TINYINT DEFAULT 1 COMMENT '状态：1-启用，0-禁用',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='品牌表';

-- 1.10 商品表
CREATE TABLE IF NOT EXISTS product (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '商品ID',
    product_code VARCHAR(50) NOT NULL UNIQUE COMMENT '商品编码',
    barcode VARCHAR(50) COMMENT '条形码',
    product_name VARCHAR(200) NOT NULL COMMENT '商品名称',
    short_name VARCHAR(100) COMMENT '商品简称',
    category_id BIGINT COMMENT '商品分类ID',
    brand_id BIGINT COMMENT '品牌ID',
    unit_id BIGINT COMMENT '基本单位ID',
    spec VARCHAR(200) COMMENT '规格型号',
    color VARCHAR(50) COMMENT '颜色',
    size VARCHAR(50) COMMENT '尺寸',
    weight DECIMAL(10,3) COMMENT '重量(kg)',
    volume DECIMAL(10,3) COMMENT '体积(m³)',
    purchase_price DECIMAL(15,2) DEFAULT 0 COMMENT '采购价',
    sale_price DECIMAL(15,2) DEFAULT 0 COMMENT '销售价',
    min_price DECIMAL(15,2) DEFAULT 0 COMMENT '最低售价',
    wholesale_price DECIMAL(15,2) DEFAULT 0 COMMENT '批发价',
    cost_price DECIMAL(15,2) DEFAULT 0 COMMENT '成本价',
    tax_rate DECIMAL(5,2) DEFAULT 13.00 COMMENT '税率（百分比）',
    min_stock INT DEFAULT 0 COMMENT '最低库存',
    max_stock INT DEFAULT 0 COMMENT '最高库存',
    shelf_life INT COMMENT '保质期（天）',
    origin VARCHAR(100) COMMENT '产地',
    is_batch TINYINT DEFAULT 0 COMMENT '是否批次管理：1-是，0-否',
    is_serial TINYINT DEFAULT 0 COMMENT '是否序列号管理：1-是，0-否',
    status TINYINT DEFAULT 1 COMMENT '状态：1-启用，0-禁用',
    remark TEXT COMMENT '备注',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_category (category_id),
    INDEX idx_brand (brand_id),
    INDEX idx_barcode (barcode),
    INDEX idx_status (status),
    FOREIGN KEY (category_id) REFERENCES product_category(id),
    FOREIGN KEY (brand_id) REFERENCES brand(id),
    FOREIGN KEY (unit_id) REFERENCES unit(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='商品表';

-- 1.11 仓库表
CREATE TABLE IF NOT EXISTS warehouse (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '仓库ID',
    warehouse_code VARCHAR(20) NOT NULL UNIQUE COMMENT '仓库编码',
    warehouse_name VARCHAR(100) NOT NULL COMMENT '仓库名称',
    warehouse_type TINYINT DEFAULT 1 COMMENT '仓库类型：1-原材料仓，2-成品仓，3-半成品仓，4-退货仓',
    address VARCHAR(500) COMMENT '仓库地址',
    manager_id BIGINT COMMENT '仓库管理员ID',
    contact_phone VARCHAR(20) COMMENT '联系电话',
    area DECIMAL(10,2) COMMENT '仓库面积(m²)',
    capacity INT COMMENT '库容量',
    status TINYINT DEFAULT 1 COMMENT '状态：1-启用，0-禁用',
    remark TEXT COMMENT '备注',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_type (warehouse_type),
    INDEX idx_manager (manager_id),
    FOREIGN KEY (manager_id) REFERENCES employee(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='仓库表';

-- 1.12 库位表
CREATE TABLE IF NOT EXISTS warehouse_location (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '库位ID',
    location_code VARCHAR(30) NOT NULL UNIQUE COMMENT '库位编码',
    location_name VARCHAR(100) NOT NULL COMMENT '库位名称',
    warehouse_id BIGINT NOT NULL COMMENT '所属仓库ID',
    area VARCHAR(20) COMMENT '区域',
    shelf VARCHAR(20) COMMENT '货架',
    layer VARCHAR(20) COMMENT '层',
    position VARCHAR(20) COMMENT '位置',
    capacity INT COMMENT '库位容量',
    status TINYINT DEFAULT 1 COMMENT '状态：1-启用，0-禁用',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX idx_warehouse (warehouse_id),
    FOREIGN KEY (warehouse_id) REFERENCES warehouse(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='库位表';

-- ========================================
-- 2. 采购管理模块
-- ========================================

-- 2.1 采购订单主表
CREATE TABLE IF NOT EXISTS purchase_order (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '采购订单ID',
    order_no VARCHAR(30) NOT NULL UNIQUE COMMENT '采购订单号',
    supplier_id BIGINT NOT NULL COMMENT '供应商ID',
    warehouse_id BIGINT COMMENT '入库仓库ID',
    order_date DATE NOT NULL COMMENT '订单日期',
    expected_date DATE COMMENT '预计到货日期',
    buyer_id BIGINT COMMENT '采购员ID',
    order_status TINYINT DEFAULT 0 COMMENT '订单状态：0-草稿，1-待审核，2-已审核，3-部分入库，4-已完成，5-已取消',
    total_qty DECIMAL(15,3) DEFAULT 0 COMMENT '总数量',
    total_amount DECIMAL(15,2) DEFAULT 0 COMMENT '总金额',
    tax_amount DECIMAL(15,2) DEFAULT 0 COMMENT '税额',
    discount_amount DECIMAL(15,2) DEFAULT 0 COMMENT '折扣金额',
    payable_amount DECIMAL(15,2) DEFAULT 0 COMMENT '应付金额',
    paid_amount DECIMAL(15,2) DEFAULT 0 COMMENT '已付金额',
    payment_status TINYINT DEFAULT 0 COMMENT '付款状态：0-未付款，1-部分付款，2-已付清',
    audit_user_id BIGINT COMMENT '审核人ID',
    audit_time DATETIME COMMENT '审核时间',
    remark TEXT COMMENT '备注',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_supplier (supplier_id),
    INDEX idx_warehouse (warehouse_id),
    INDEX idx_buyer (buyer_id),
    INDEX idx_status (order_status),
    INDEX idx_date (order_date),
    FOREIGN KEY (supplier_id) REFERENCES supplier(id),
    FOREIGN KEY (warehouse_id) REFERENCES warehouse(id),
    FOREIGN KEY (buyer_id) REFERENCES employee(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='采购订单主表';

-- 2.2 采购订单明细表
CREATE TABLE IF NOT EXISTS purchase_order_detail (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '明细ID',
    order_id BIGINT NOT NULL COMMENT '采购订单ID',
    product_id BIGINT NOT NULL COMMENT '商品ID',
    unit_id BIGINT COMMENT '单位ID',
    quantity DECIMAL(15,3) NOT NULL COMMENT '采购数量',
    received_qty DECIMAL(15,3) DEFAULT 0 COMMENT '已入库数量',
    unit_price DECIMAL(15,4) NOT NULL COMMENT '单价',
    tax_rate DECIMAL(5,2) DEFAULT 13.00 COMMENT '税率',
    tax_amount DECIMAL(15,2) DEFAULT 0 COMMENT '税额',
    amount DECIMAL(15,2) DEFAULT 0 COMMENT '金额（不含税）',
    total_amount DECIMAL(15,2) DEFAULT 0 COMMENT '价税合计',
    remark VARCHAR(500) COMMENT '备注',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX idx_order (order_id),
    INDEX idx_product (product_id),
    FOREIGN KEY (order_id) REFERENCES purchase_order(id),
    FOREIGN KEY (product_id) REFERENCES product(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='采购订单明细表';

-- 2.3 采购入库单主表
CREATE TABLE IF NOT EXISTS purchase_receipt (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '入库单ID',
    receipt_no VARCHAR(30) NOT NULL UNIQUE COMMENT '入库单号',
    order_id BIGINT COMMENT '关联采购订单ID',
    supplier_id BIGINT NOT NULL COMMENT '供应商ID',
    warehouse_id BIGINT NOT NULL COMMENT '入库仓库ID',
    receipt_date DATE NOT NULL COMMENT '入库日期',
    receiver_id BIGINT COMMENT '收货人ID',
    receipt_status TINYINT DEFAULT 0 COMMENT '状态：0-草稿，1-待审核，2-已审核，3-已取消',
    total_qty DECIMAL(15,3) DEFAULT 0 COMMENT '总数量',
    total_amount DECIMAL(15,2) DEFAULT 0 COMMENT '总金额',
    audit_user_id BIGINT COMMENT '审核人ID',
    audit_time DATETIME COMMENT '审核时间',
    remark TEXT COMMENT '备注',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_order (order_id),
    INDEX idx_supplier (supplier_id),
    INDEX idx_warehouse (warehouse_id),
    INDEX idx_date (receipt_date),
    FOREIGN KEY (order_id) REFERENCES purchase_order(id),
    FOREIGN KEY (supplier_id) REFERENCES supplier(id),
    FOREIGN KEY (warehouse_id) REFERENCES warehouse(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='采购入库单主表';

-- 2.4 采购入库单明细表
CREATE TABLE IF NOT EXISTS purchase_receipt_detail (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '明细ID',
    receipt_id BIGINT NOT NULL COMMENT '入库单ID',
    order_detail_id BIGINT COMMENT '采购订单明细ID',
    product_id BIGINT NOT NULL COMMENT '商品ID',
    location_id BIGINT COMMENT '库位ID',
    batch_no VARCHAR(50) COMMENT '批次号',
    production_date DATE COMMENT '生产日期',
    expiry_date DATE COMMENT '过期日期',
    quantity DECIMAL(15,3) NOT NULL COMMENT '入库数量',
    unit_price DECIMAL(15,4) NOT NULL COMMENT '单价',
    amount DECIMAL(15,2) DEFAULT 0 COMMENT '金额',
    remark VARCHAR(500) COMMENT '备注',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX idx_receipt (receipt_id),
    INDEX idx_product (product_id),
    INDEX idx_batch (batch_no),
    FOREIGN KEY (receipt_id) REFERENCES purchase_receipt(id),
    FOREIGN KEY (product_id) REFERENCES product(id),
    FOREIGN KEY (location_id) REFERENCES warehouse_location(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='采购入库单明细表';

-- 2.5 采购退货单主表
CREATE TABLE IF NOT EXISTS purchase_return (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '退货单ID',
    return_no VARCHAR(30) NOT NULL UNIQUE COMMENT '退货单号',
    receipt_id BIGINT COMMENT '关联入库单ID',
    supplier_id BIGINT NOT NULL COMMENT '供应商ID',
    warehouse_id BIGINT NOT NULL COMMENT '出库仓库ID',
    return_date DATE NOT NULL COMMENT '退货日期',
    return_reason VARCHAR(500) COMMENT '退货原因',
    return_status TINYINT DEFAULT 0 COMMENT '状态：0-草稿，1-待审核，2-已审核，3-已取消',
    total_qty DECIMAL(15,3) DEFAULT 0 COMMENT '总数量',
    total_amount DECIMAL(15,2) DEFAULT 0 COMMENT '总金额',
    audit_user_id BIGINT COMMENT '审核人ID',
    audit_time DATETIME COMMENT '审核时间',
    remark TEXT COMMENT '备注',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_receipt (receipt_id),
    INDEX idx_supplier (supplier_id),
    INDEX idx_date (return_date),
    FOREIGN KEY (receipt_id) REFERENCES purchase_receipt(id),
    FOREIGN KEY (supplier_id) REFERENCES supplier(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='采购退货单主表';

-- 2.6 采购退货单明细表
CREATE TABLE IF NOT EXISTS purchase_return_detail (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '明细ID',
    return_id BIGINT NOT NULL COMMENT '退货单ID',
    product_id BIGINT NOT NULL COMMENT '商品ID',
    batch_no VARCHAR(50) COMMENT '批次号',
    quantity DECIMAL(15,3) NOT NULL COMMENT '退货数量',
    unit_price DECIMAL(15,4) NOT NULL COMMENT '单价',
    amount DECIMAL(15,2) DEFAULT 0 COMMENT '金额',
    return_reason VARCHAR(500) COMMENT '退货原因',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX idx_return (return_id),
    INDEX idx_product (product_id),
    FOREIGN KEY (return_id) REFERENCES purchase_return(id),
    FOREIGN KEY (product_id) REFERENCES product(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='采购退货单明细表';

-- ========================================
-- 3. 销售管理模块
-- ========================================

-- 3.1 销售订单主表
CREATE TABLE IF NOT EXISTS sales_order (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '销售订单ID',
    order_no VARCHAR(30) NOT NULL UNIQUE COMMENT '销售订单号',
    customer_id BIGINT NOT NULL COMMENT '客户ID',
    warehouse_id BIGINT COMMENT '出库仓库ID',
    order_date DATE NOT NULL COMMENT '订单日期',
    delivery_date DATE COMMENT '预计发货日期',
    salesman_id BIGINT COMMENT '销售员ID',
    order_status TINYINT DEFAULT 0 COMMENT '订单状态：0-草稿，1-待审核，2-已审核，3-部分出库，4-已完成，5-已取消',
    total_qty DECIMAL(15,3) DEFAULT 0 COMMENT '总数量',
    total_amount DECIMAL(15,2) DEFAULT 0 COMMENT '总金额',
    tax_amount DECIMAL(15,2) DEFAULT 0 COMMENT '税额',
    discount_rate DECIMAL(5,2) DEFAULT 100 COMMENT '折扣率',
    discount_amount DECIMAL(15,2) DEFAULT 0 COMMENT '折扣金额',
    receivable_amount DECIMAL(15,2) DEFAULT 0 COMMENT '应收金额',
    received_amount DECIMAL(15,2) DEFAULT 0 COMMENT '已收金额',
    payment_status TINYINT DEFAULT 0 COMMENT '收款状态：0-未收款，1-部分收款，2-已收清',
    delivery_address VARCHAR(500) COMMENT '送货地址',
    audit_user_id BIGINT COMMENT '审核人ID',
    audit_time DATETIME COMMENT '审核时间',
    remark TEXT COMMENT '备注',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_customer (customer_id),
    INDEX idx_warehouse (warehouse_id),
    INDEX idx_salesman (salesman_id),
    INDEX idx_status (order_status),
    INDEX idx_date (order_date),
    FOREIGN KEY (customer_id) REFERENCES customer(id),
    FOREIGN KEY (warehouse_id) REFERENCES warehouse(id),
    FOREIGN KEY (salesman_id) REFERENCES employee(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='销售订单主表';

-- 3.2 销售订单明细表
CREATE TABLE IF NOT EXISTS sales_order_detail (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '明细ID',
    order_id BIGINT NOT NULL COMMENT '销售订单ID',
    product_id BIGINT NOT NULL COMMENT '商品ID',
    unit_id BIGINT COMMENT '单位ID',
    quantity DECIMAL(15,3) NOT NULL COMMENT '销售数量',
    delivered_qty DECIMAL(15,3) DEFAULT 0 COMMENT '已出库数量',
    unit_price DECIMAL(15,4) NOT NULL COMMENT '单价',
    tax_rate DECIMAL(5,2) DEFAULT 13.00 COMMENT '税率',
    tax_amount DECIMAL(15,2) DEFAULT 0 COMMENT '税额',
    amount DECIMAL(15,2) DEFAULT 0 COMMENT '金额（不含税）',
    total_amount DECIMAL(15,2) DEFAULT 0 COMMENT '价税合计',
    remark VARCHAR(500) COMMENT '备注',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX idx_order (order_id),
    INDEX idx_product (product_id),
    FOREIGN KEY (order_id) REFERENCES sales_order(id),
    FOREIGN KEY (product_id) REFERENCES product(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='销售订单明细表';

-- 3.3 销售出库单主表
CREATE TABLE IF NOT EXISTS sales_delivery (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '出库单ID',
    delivery_no VARCHAR(30) NOT NULL UNIQUE COMMENT '出库单号',
    order_id BIGINT COMMENT '关联销售订单ID',
    customer_id BIGINT NOT NULL COMMENT '客户ID',
    warehouse_id BIGINT NOT NULL COMMENT '出库仓库ID',
    delivery_date DATE NOT NULL COMMENT '出库日期',
    delivery_user_id BIGINT COMMENT '发货人ID',
    delivery_status TINYINT DEFAULT 0 COMMENT '状态：0-草稿，1-待审核，2-已审核，3-已发货，4-已签收，5-已取消',
    total_qty DECIMAL(15,3) DEFAULT 0 COMMENT '总数量',
    total_amount DECIMAL(15,2) DEFAULT 0 COMMENT '总金额',
    freight DECIMAL(15,2) DEFAULT 0 COMMENT '运费',
    delivery_address VARCHAR(500) COMMENT '送货地址',
    receiver_name VARCHAR(50) COMMENT '收货人',
    receiver_phone VARCHAR(20) COMMENT '收货电话',
    logistics_company VARCHAR(100) COMMENT '物流公司',
    tracking_no VARCHAR(50) COMMENT '物流单号',
    audit_user_id BIGINT COMMENT '审核人ID',
    audit_time DATETIME COMMENT '审核时间',
    remark TEXT COMMENT '备注',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_order (order_id),
    INDEX idx_customer (customer_id),
    INDEX idx_warehouse (warehouse_id),
    INDEX idx_date (delivery_date),
    INDEX idx_tracking (tracking_no),
    FOREIGN KEY (order_id) REFERENCES sales_order(id),
    FOREIGN KEY (customer_id) REFERENCES customer(id),
    FOREIGN KEY (warehouse_id) REFERENCES warehouse(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='销售出库单主表';

-- 3.4 销售出库单明细表
CREATE TABLE IF NOT EXISTS sales_delivery_detail (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '明细ID',
    delivery_id BIGINT NOT NULL COMMENT '出库单ID',
    order_detail_id BIGINT COMMENT '销售订单明细ID',
    product_id BIGINT NOT NULL COMMENT '商品ID',
    location_id BIGINT COMMENT '库位ID',
    batch_no VARCHAR(50) COMMENT '批次号',
    quantity DECIMAL(15,3) NOT NULL COMMENT '出库数量',
    unit_price DECIMAL(15,4) NOT NULL COMMENT '单价',
    amount DECIMAL(15,2) DEFAULT 0 COMMENT '金额',
    remark VARCHAR(500) COMMENT '备注',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX idx_delivery (delivery_id),
    INDEX idx_product (product_id),
    INDEX idx_batch (batch_no),
    FOREIGN KEY (delivery_id) REFERENCES sales_delivery(id),
    FOREIGN KEY (product_id) REFERENCES product(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='销售出库单明细表';

-- 3.5 销售退货单主表
CREATE TABLE IF NOT EXISTS sales_return (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '退货单ID',
    return_no VARCHAR(30) NOT NULL UNIQUE COMMENT '退货单号',
    delivery_id BIGINT COMMENT '关联出库单ID',
    customer_id BIGINT NOT NULL COMMENT '客户ID',
    warehouse_id BIGINT NOT NULL COMMENT '入库仓库ID',
    return_date DATE NOT NULL COMMENT '退货日期',
    return_reason VARCHAR(500) COMMENT '退货原因',
    return_status TINYINT DEFAULT 0 COMMENT '状态：0-草稿，1-待审核，2-已审核，3-已取消',
    total_qty DECIMAL(15,3) DEFAULT 0 COMMENT '总数量',
    total_amount DECIMAL(15,2) DEFAULT 0 COMMENT '总金额',
    audit_user_id BIGINT COMMENT '审核人ID',
    audit_time DATETIME COMMENT '审核时间',
    remark TEXT COMMENT '备注',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_delivery (delivery_id),
    INDEX idx_customer (customer_id),
    INDEX idx_date (return_date),
    FOREIGN KEY (delivery_id) REFERENCES sales_delivery(id),
    FOREIGN KEY (customer_id) REFERENCES customer(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='销售退货单主表';

-- 3.6 销售退货单明细表
CREATE TABLE IF NOT EXISTS sales_return_detail (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '明细ID',
    return_id BIGINT NOT NULL COMMENT '退货单ID',
    product_id BIGINT NOT NULL COMMENT '商品ID',
    batch_no VARCHAR(50) COMMENT '批次号',
    quantity DECIMAL(15,3) NOT NULL COMMENT '退货数量',
    unit_price DECIMAL(15,4) NOT NULL COMMENT '单价',
    amount DECIMAL(15,2) DEFAULT 0 COMMENT '金额',
    return_reason VARCHAR(500) COMMENT '退货原因',
    quality_status TINYINT DEFAULT 1 COMMENT '质量状态：1-良品，2-次品，3-报废',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX idx_return (return_id),
    INDEX idx_product (product_id),
    FOREIGN KEY (return_id) REFERENCES sales_return(id),
    FOREIGN KEY (product_id) REFERENCES product(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='销售退货单明细表';

-- ========================================
-- 4. 库存管理模块
-- ========================================

-- 4.1 库存表
CREATE TABLE IF NOT EXISTS inventory (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '库存ID',
    warehouse_id BIGINT NOT NULL COMMENT '仓库ID',
    location_id BIGINT COMMENT '库位ID',
    product_id BIGINT NOT NULL COMMENT '商品ID',
    batch_no VARCHAR(50) COMMENT '批次号',
    quantity DECIMAL(15,3) DEFAULT 0 COMMENT '库存数量',
    available_qty DECIMAL(15,3) DEFAULT 0 COMMENT '可用数量',
    locked_qty DECIMAL(15,3) DEFAULT 0 COMMENT '锁定数量',
    cost_price DECIMAL(15,4) DEFAULT 0 COMMENT '成本单价',
    total_cost DECIMAL(15,2) DEFAULT 0 COMMENT '库存成本',
    production_date DATE COMMENT '生产日期',
    expiry_date DATE COMMENT '过期日期',
    last_in_date DATE COMMENT '最后入库日期',
    last_out_date DATE COMMENT '最后出库日期',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    UNIQUE KEY uk_inventory (warehouse_id, location_id, product_id, batch_no),
    INDEX idx_warehouse (warehouse_id),
    INDEX idx_product (product_id),
    INDEX idx_batch (batch_no),
    INDEX idx_expiry (expiry_date),
    FOREIGN KEY (warehouse_id) REFERENCES warehouse(id),
    FOREIGN KEY (location_id) REFERENCES warehouse_location(id),
    FOREIGN KEY (product_id) REFERENCES product(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='库存表';

-- 4.2 库存流水表
CREATE TABLE IF NOT EXISTS inventory_transaction (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '流水ID',
    transaction_no VARCHAR(30) NOT NULL COMMENT '流水号',
    transaction_type VARCHAR(20) NOT NULL COMMENT '业务类型：PURCHASE_IN-采购入库,PURCHASE_RETURN-采购退货,SALES_OUT-销售出库,SALES_RETURN-销售退货,TRANSFER_IN-调拨入,TRANSFER_OUT-调拨出,ADJUST-盘点调整',
    ref_order_no VARCHAR(30) COMMENT '关联单据号',
    warehouse_id BIGINT NOT NULL COMMENT '仓库ID',
    location_id BIGINT COMMENT '库位ID',
    product_id BIGINT NOT NULL COMMENT '商品ID',
    batch_no VARCHAR(50) COMMENT '批次号',
    direction TINYINT NOT NULL COMMENT '方向：1-入库，-1-出库',
    quantity DECIMAL(15,3) NOT NULL COMMENT '数量',
    before_qty DECIMAL(15,3) DEFAULT 0 COMMENT '变动前数量',
    after_qty DECIMAL(15,3) DEFAULT 0 COMMENT '变动后数量',
    unit_price DECIMAL(15,4) DEFAULT 0 COMMENT '单价',
    amount DECIMAL(15,2) DEFAULT 0 COMMENT '金额',
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

-- 4.3 库存调拨单主表
CREATE TABLE IF NOT EXISTS inventory_transfer (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '调拨单ID',
    transfer_no VARCHAR(30) NOT NULL UNIQUE COMMENT '调拨单号',
    from_warehouse_id BIGINT NOT NULL COMMENT '调出仓库ID',
    to_warehouse_id BIGINT NOT NULL COMMENT '调入仓库ID',
    transfer_date DATE NOT NULL COMMENT '调拨日期',
    transfer_status TINYINT DEFAULT 0 COMMENT '状态：0-草稿，1-待审核，2-已审核，3-调拨中，4-已完成，5-已取消',
    total_qty DECIMAL(15,3) DEFAULT 0 COMMENT '总数量',
    operator_id BIGINT COMMENT '操作人ID',
    audit_user_id BIGINT COMMENT '审核人ID',
    audit_time DATETIME COMMENT '审核时间',
    remark TEXT COMMENT '备注',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_from (from_warehouse_id),
    INDEX idx_to (to_warehouse_id),
    INDEX idx_date (transfer_date),
    FOREIGN KEY (from_warehouse_id) REFERENCES warehouse(id),
    FOREIGN KEY (to_warehouse_id) REFERENCES warehouse(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='库存调拨单主表';

-- 4.4 库存调拨单明细表
CREATE TABLE IF NOT EXISTS inventory_transfer_detail (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '明细ID',
    transfer_id BIGINT NOT NULL COMMENT '调拨单ID',
    product_id BIGINT NOT NULL COMMENT '商品ID',
    from_location_id BIGINT COMMENT '调出库位ID',
    to_location_id BIGINT COMMENT '调入库位ID',
    batch_no VARCHAR(50) COMMENT '批次号',
    quantity DECIMAL(15,3) NOT NULL COMMENT '调拨数量',
    remark VARCHAR(500) COMMENT '备注',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX idx_transfer (transfer_id),
    INDEX idx_product (product_id),
    FOREIGN KEY (transfer_id) REFERENCES inventory_transfer(id),
    FOREIGN KEY (product_id) REFERENCES product(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='库存调拨单明细表';

-- 4.5 库存盘点单主表
CREATE TABLE IF NOT EXISTS inventory_check (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '盘点单ID',
    check_no VARCHAR(30) NOT NULL UNIQUE COMMENT '盘点单号',
    warehouse_id BIGINT NOT NULL COMMENT '盘点仓库ID',
    check_date DATE NOT NULL COMMENT '盘点日期',
    check_type TINYINT DEFAULT 1 COMMENT '盘点类型：1-全盘，2-抽盘，3-动碰盘',
    check_status TINYINT DEFAULT 0 COMMENT '状态：0-草稿，1-盘点中，2-待审核，3-已审核，4-已取消',
    operator_id BIGINT COMMENT '盘点人ID',
    audit_user_id BIGINT COMMENT '审核人ID',
    audit_time DATETIME COMMENT '审核时间',
    remark TEXT COMMENT '备注',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_warehouse (warehouse_id),
    INDEX idx_date (check_date),
    FOREIGN KEY (warehouse_id) REFERENCES warehouse(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='库存盘点单主表';

-- 4.6 库存盘点单明细表
CREATE TABLE IF NOT EXISTS inventory_check_detail (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '明细ID',
    check_id BIGINT NOT NULL COMMENT '盘点单ID',
    product_id BIGINT NOT NULL COMMENT '商品ID',
    location_id BIGINT COMMENT '库位ID',
    batch_no VARCHAR(50) COMMENT '批次号',
    book_qty DECIMAL(15,3) DEFAULT 0 COMMENT '账面数量',
    actual_qty DECIMAL(15,3) DEFAULT 0 COMMENT '实盘数量',
    diff_qty DECIMAL(15,3) DEFAULT 0 COMMENT '盈亏数量',
    diff_amount DECIMAL(15,2) DEFAULT 0 COMMENT '盈亏金额',
    diff_reason VARCHAR(500) COMMENT '盈亏原因',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX idx_check (check_id),
    INDEX idx_product (product_id),
    FOREIGN KEY (check_id) REFERENCES inventory_check(id),
    FOREIGN KEY (product_id) REFERENCES product(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='库存盘点单明细表';

-- ========================================
-- 5. 财务管理模块
-- ========================================

-- 5.1 应付账款表
CREATE TABLE IF NOT EXISTS accounts_payable (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '应付ID',
    payable_no VARCHAR(30) NOT NULL UNIQUE COMMENT '应付单号',
    supplier_id BIGINT NOT NULL COMMENT '供应商ID',
    source_type VARCHAR(20) NOT NULL COMMENT '来源类型：PURCHASE-采购，RETURN-退货冲减',
    source_order_no VARCHAR(30) COMMENT '来源单据号',
    payable_amount DECIMAL(15,2) NOT NULL COMMENT '应付金额',
    paid_amount DECIMAL(15,2) DEFAULT 0 COMMENT '已付金额',
    unpaid_amount DECIMAL(15,2) NOT NULL COMMENT '未付金额',
    due_date DATE COMMENT '到期日',
    status TINYINT DEFAULT 0 COMMENT '状态：0-未付，1-部分付款，2-已付清',
    remark TEXT COMMENT '备注',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_supplier (supplier_id),
    INDEX idx_source (source_order_no),
    INDEX idx_due (due_date),
    INDEX idx_status (status),
    FOREIGN KEY (supplier_id) REFERENCES supplier(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='应付账款表';

-- 5.2 付款记录表
CREATE TABLE IF NOT EXISTS payment_record (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '付款ID',
    payment_no VARCHAR(30) NOT NULL UNIQUE COMMENT '付款单号',
    supplier_id BIGINT NOT NULL COMMENT '供应商ID',
    payable_id BIGINT COMMENT '应付单ID',
    payment_amount DECIMAL(15,2) NOT NULL COMMENT '付款金额',
    payment_method VARCHAR(20) NOT NULL COMMENT '付款方式：CASH-现金，BANK-银行转账，CHECK-支票，CREDIT-信用',
    payment_date DATE NOT NULL COMMENT '付款日期',
    bank_account VARCHAR(50) COMMENT '付款账号',
    handler_id BIGINT COMMENT '经手人ID',
    status TINYINT DEFAULT 1 COMMENT '状态：0-待审核，1-已审核，2-已取消',
    remark TEXT COMMENT '备注',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX idx_supplier (supplier_id),
    INDEX idx_payable (payable_id),
    INDEX idx_date (payment_date),
    FOREIGN KEY (supplier_id) REFERENCES supplier(id),
    FOREIGN KEY (payable_id) REFERENCES accounts_payable(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='付款记录表';

-- 5.3 应收账款表
CREATE TABLE IF NOT EXISTS accounts_receivable (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '应收ID',
    receivable_no VARCHAR(30) NOT NULL UNIQUE COMMENT '应收单号',
    customer_id BIGINT NOT NULL COMMENT '客户ID',
    source_type VARCHAR(20) NOT NULL COMMENT '来源类型：SALES-销售，RETURN-退货冲减',
    source_order_no VARCHAR(30) COMMENT '来源单据号',
    receivable_amount DECIMAL(15,2) NOT NULL COMMENT '应收金额',
    received_amount DECIMAL(15,2) DEFAULT 0 COMMENT '已收金额',
    unreceived_amount DECIMAL(15,2) NOT NULL COMMENT '未收金额',
    due_date DATE COMMENT '到期日',
    status TINYINT DEFAULT 0 COMMENT '状态：0-未收，1-部分收款，2-已收清',
    remark TEXT COMMENT '备注',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_customer (customer_id),
    INDEX idx_source (source_order_no),
    INDEX idx_due (due_date),
    INDEX idx_status (status),
    FOREIGN KEY (customer_id) REFERENCES customer(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='应收账款表';

-- 5.4 收款记录表
CREATE TABLE IF NOT EXISTS receipt_record (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '收款ID',
    receipt_no VARCHAR(30) NOT NULL UNIQUE COMMENT '收款单号',
    customer_id BIGINT NOT NULL COMMENT '客户ID',
    receivable_id BIGINT COMMENT '应收单ID',
    receipt_amount DECIMAL(15,2) NOT NULL COMMENT '收款金额',
    receipt_method VARCHAR(20) NOT NULL COMMENT '收款方式：CASH-现金，BANK-银行转账，CHECK-支票，CREDIT-信用',
    receipt_date DATE NOT NULL COMMENT '收款日期',
    bank_account VARCHAR(50) COMMENT '收款账号',
    handler_id BIGINT COMMENT '经手人ID',
    status TINYINT DEFAULT 1 COMMENT '状态：0-待审核，1-已审核，2-已取消',
    remark TEXT COMMENT '备注',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX idx_customer (customer_id),
    INDEX idx_receivable (receivable_id),
    INDEX idx_date (receipt_date),
    FOREIGN KEY (customer_id) REFERENCES customer(id),
    FOREIGN KEY (receivable_id) REFERENCES accounts_receivable(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='收款记录表';
"""

# ============================================================
# Mock 数据生成
# ============================================================

# 基础数据常量
DEPARTMENTS = [
    ('D001', '董事会', None),
    ('D002', '总经理办公室', 'D001'),
    ('D003', '财务部', 'D001'),
    ('D004', '采购部', 'D002'),
    ('D005', '销售部', 'D002'),
    ('D006', '仓储部', 'D002'),
    ('D007', '质量部', 'D002'),
    ('D008', '人力资源部', 'D002'),
    ('D009', '信息技术部', 'D002'),
]

EMPLOYEES = [
    ('E001', '张海洋', 1, '13800001001', 'zhanghy@erp.com', 'D002', '总经理'),
    ('E002', '李明达', 1, '13800001002', 'limd@erp.com', 'D003', '财务经理'),
    ('E003', '王芳', 2, '13800001003', 'wangf@erp.com', 'D003', '会计'),
    ('E004', '赵强', 1, '13800001004', 'zhaoq@erp.com', 'D004', '采购经理'),
    ('E005', '刘洋', 1, '13800001005', 'liuy@erp.com', 'D004', '采购员'),
    ('E006', '陈静', 2, '13800001006', 'chenj@erp.com', 'D004', '采购员'),
    ('E007', '周杰', 1, '13800001007', 'zhouj@erp.com', 'D005', '销售经理'),
    ('E008', '吴敏', 2, '13800001008', 'wum@erp.com', 'D005', '销售代表'),
    ('E009', '郑伟', 1, '13800001009', 'zhengw@erp.com', 'D005', '销售代表'),
    ('E010', '孙秀英', 2, '13800001010', 'sunxy@erp.com', 'D005', '销售代表'),
    ('E011', '马立成', 1, '13800001011', 'malc@erp.com', 'D006', '仓库经理'),
    ('E012', '朱建国', 1, '13800001012', 'zhujg@erp.com', 'D006', '仓管员'),
    ('E013', '胡丽', 2, '13800001013', 'hul@erp.com', 'D006', '仓管员'),
    ('E014', '高志刚', 1, '13800001014', 'gaozg@erp.com', 'D007', '质检经理'),
    ('E015', '林婷', 2, '13800001015', 'lint@erp.com', 'D008', '人事专员'),
]

SUPPLIER_CATEGORIES = [
    ('SC01', '电子元器件供应商', None),
    ('SC02', '机械零部件供应商', None),
    ('SC03', '原材料供应商', None),
    ('SC04', '包装材料供应商', None),
    ('SC05', '办公用品供应商', None),
]

SUPPLIERS = [
    ('S001', '深圳华强电子有限公司', 'SC01', '张经理', '0755-88881001', '广东', '深圳', '南山区', 'A', 30),
    ('S002', '东莞华利电子科技有限公司', 'SC01', '李总', '0769-22221002', '广东', '东莞', '长安镇', 'A', 45),
    ('S003', '上海精密机械制造有限公司', 'SC02', '王总', '021-55551003', '上海', '上海', '嘉定区', 'B', 30),
    ('S004', '苏州工业机械有限公司', 'SC02', '刘总', '0512-66661004', '江苏', '苏州', '工业园区', 'A', 30),
    ('S005', '安徽新材料科技有限公司', 'SC03', '赵总', '0551-77771005', '安徽', '合肥', '高新区', 'B', 45),
    ('S006', '浙江化工原料有限公司', 'SC03', '周总', '0571-88881006', '浙江', '杭州', '滨江区', 'A', 30),
    ('S007', '东莞包装印刷有限公司', 'SC04', '陈总', '0769-33331007', '广东', '东莞', '横沥镇', 'B', 15),
    ('S008', '广州彩印包装有限公司', 'SC04', '林总', '020-44441008', '广东', '广州', '白云区', 'A', 15),
    ('S009', '东莱办公用品有限公司', 'SC05', '高总', '021-99991009', '上海', '上海', '闵行区', 'C', 7),
    ('S010', '德力电子元件有限公司', 'SC01', '马总', '0755-12121010', '广东', '深圳', '宝安区', 'A', 30),
    ('S011', '宁波精密铸造有限公司', 'SC02', '方总', '0574-87871011', '浙江', '宁波', '北仑区', 'B', 45),
    ('S012', '江苏绿色化工有限公司', 'SC03', '周总', '025-56561012', '江苏', '南京', '浦口区', 'A', 30),
]

CUSTOMER_CATEGORIES = [
    ('CC01', 'VIP大客户', None, 90),
    ('CC02', '金牌客户', None, 92),
    ('CC03', '银牌客户', None, 95),
    ('CC04', '普通客户', None, 98),
    ('CC05', '新客户', None, 100),
]

CUSTOMERS = [
    ('C001', '广州天成科技有限公司', 1, 'CC01', '张总', '020-88881001', '广东', '广州', '天河区', 500000, 'A', 30),
    ('C002', '上海创新电子有限公司', 1, 'CC01', '李总', '021-77771002', '上海', '上海', '浦东区', 800000, 'A', 45),
    ('C003', '北京华兴机械有限公司', 1, 'CC02', '王总', '010-66661003', '北京', '北京', '朝阳区', 300000, 'A', 30),
    ('C004', '深圳安达电子有限公司', 1, 'CC02', '赵总', '0755-55551004', '广东', '深圳', '福田区', 200000, 'B', 30),
    ('C005', '武汉光谷科技有限公司', 1, 'CC03', '周总', '027-44441005', '湖北', '武汉', '洪山区', 150000, 'B', 30),
    ('C006', '成都美创工业有限公司', 1, 'CC03', '陈总', '028-33331006', '四川', '成都', '高新区', 100000, 'B', 30),
    ('C007', '浙江美威家电有限公司', 1, 'CC02', '刘总', '0571-22221007', '浙江', '杭州', '余杭区', 250000, 'A', 30),
    ('C008', '重庆机电集团', 1, 'CC01', '范总', '023-11111008', '重庆', '重庆', '江北区', 600000, 'A', 45),
    ('C009', '天津兴达科技有限公司', 1, 'CC03', '徐总', '022-88881009', '天津', '天津', '滨海区', 120000, 'B', 30),
    ('C010', '苏州卫星电子有限公司', 1, 'CC04', '胡总', '0512-99991010', '江苏', '苏州', '姑苏区', 80000, 'B', 15),
    ('C011', '东莞安远电子有限公司', 1, 'CC04', '黄总', '0769-77771011', '广东', '东莞', '塘厦镇', 60000, 'C', 15),
    ('C012', '无锡快捷工业有限公司', 1, 'CC05', '郭总', '0510-66661012', '江苏', '无锡', '新区', 50000, 'C', 15),
    ('C013', '佛山建达机械有限公司', 1, 'CC04', '卢总', '0757-55551013', '广东', '佛山', '顺德区', 70000, 'B', 30),
    ('C014', '厦门精密仪器有限公司', 1, 'CC03', '董总', '0592-44441014', '福建', '厦门', '思明区', 180000, 'A', 30),
    ('C015', '长春开元汽配有限公司', 1, 'CC05', '邹总', '0431-33331015', '吉林', '长春', '绿园区', 40000, 'C', 15),
]

PRODUCT_CATEGORIES = [
    ('PC01', '电子元器件', None, 1),
    ('PC0101', '电阻', 'PC01', 2),
    ('PC0102', '电容', 'PC01', 2),
    ('PC0103', '电感', 'PC01', 2),
    ('PC0104', '二极管', 'PC01', 2),
    ('PC0105', '三极管', 'PC01', 2),
    ('PC0106', 'IC芯片', 'PC01', 2),
    ('PC02', '机械零部件', None, 1),
    ('PC0201', '轴承', 'PC02', 2),
    ('PC0202', '齿轮', 'PC02', 2),
    ('PC0203', '联轴器', 'PC02', 2),
    ('PC0204', '密封件', 'PC02', 2),
    ('PC03', '成品设备', None, 1),
    ('PC0301', '电机', 'PC03', 2),
    ('PC0302', '控制器', 'PC03', 2),
    ('PC0303', '传感器', 'PC03', 2),
    ('PC04', '包装材料', None, 1),
    ('PC0401', '纸箱', 'PC04', 2),
    ('PC0402', '塑料袋', 'PC04', 2),
    ('PC0403', '泡棉', 'PC04', 2),
    ('PC05', '原材料', None, 1),
    ('PC0501', '铝材', 'PC05', 2),
    ('PC0502', '铜材', 'PC05', 2),
    ('PC0503', '钢材', 'PC05', 2),
    ('PC0504', '塑料粒子', 'PC05', 2),
]

UNITS = [
    ('PCS', '个'),
    ('SET', '套'),
    ('BOX', '箱'),
    ('BAG', '袋'),
    ('KG', '公斤'),
    ('M', '米'),
    ('ROLL', '卷'),
    ('SHEET', '张'),
    ('PC', '片'),
    ('BOTTLE', '瓶'),
]

BRANDS = [
    ('BR01', '华强电子'),
    ('BR02', '国巨贴片'),
    ('BR03', 'NSK'),
    ('BR04', 'SKF'),
    ('BR05', '正泰'),
    ('BR06', 'TDK'),
    ('BR07', '村田'),
    ('BR08', 'ST微电子'),
    ('BR09', '德州仪器'),
    ('BR10', '欧姆龙'),
]

PRODUCTS = [
    ('P00001', '6930578800100', '1/4W 10KΩ电阻', 'PC0101', 'BR01', 'PCS', '1/4W ±1%', 0.02, 0.05, 0.04, 0.03, 0.015, 13, 10000, 50000),
    ('P00002', '6930578800101', '1/4W 100KΩ电阻', 'PC0101', 'BR01', 'PCS', '1/4W ±1%', 0.02, 0.05, 0.04, 0.03, 0.015, 13, 10000, 50000),
    ('P00003', '6930578800102', '1/4W 1KΩ电阻', 'PC0101', 'BR01', 'PCS', '1/4W ±1%', 0.02, 0.05, 0.04, 0.03, 0.015, 13, 10000, 50000),
    ('P00004', '6930578800200', '10uF/50V铝电解电容', 'PC0102', 'BR02', 'PCS', '10uF/50V', 0.15, 0.35, 0.30, 0.25, 0.12, 13, 5000, 20000),
    ('P00005', '6930578800201', '100uF/25V铝电解电容', 'PC0102', 'BR02', 'PCS', '100uF/25V', 0.25, 0.55, 0.48, 0.40, 0.20, 13, 5000, 20000),
    ('P00006', '6930578800202', '470uF/16V铝电解电容', 'PC0102', 'BR02', 'PCS', '470uF/16V', 0.45, 0.95, 0.85, 0.70, 0.38, 13, 3000, 15000),
    ('P00007', '6930578800300', '10uH贴片电感', 'PC0103', 'BR07', 'PCS', '10uH ±10%', 0.35, 0.80, 0.70, 0.60, 0.30, 13, 3000, 10000),
    ('P00008', '6930578800301', '100uH贴片电感', 'PC0103', 'BR07', 'PCS', '100uH ±10%', 0.55, 1.20, 1.05, 0.90, 0.45, 13, 3000, 10000),
    ('P00009', '6930578800400', '1N4007整流二极管', 'PC0104', 'BR05', 'PCS', '1A/1000V', 0.05, 0.12, 0.10, 0.08, 0.04, 13, 10000, 50000),
    ('P00010', '6930578800401', '1N5819肧特基二极管', 'PC0104', 'BR05', 'PCS', '1A/40V', 0.08, 0.18, 0.15, 0.12, 0.06, 13, 8000, 40000),
    ('P00011', '6930578800500', 'SS8050三极管', 'PC0105', 'BR05', 'PCS', 'NPN 1.5A', 0.10, 0.25, 0.22, 0.18, 0.08, 13, 8000, 30000),
    ('P00012', '6930578800501', 'SS8550三极管', 'PC0105', 'BR05', 'PCS', 'PNP 1.5A', 0.10, 0.25, 0.22, 0.18, 0.08, 13, 8000, 30000),
    ('P00013', '6930578800600', 'STM32F103C8T6', 'PC0106', 'BR08', 'PCS', 'LQFP48', 8.50, 18.00, 15.50, 13.00, 7.50, 13, 500, 3000),
    ('P00014', '6930578800601', 'STM32F407VET6', 'PC0106', 'BR08', 'PCS', 'LQFP100', 35.00, 68.00, 60.00, 52.00, 30.00, 13, 200, 1500),
    ('P00015', '6930578800602', 'ESP32-WROOM-32', 'PC0106', 'BR01', 'PCS', 'WiFi+BLE', 15.00, 32.00, 28.00, 24.00, 13.00, 13, 500, 3000),
    ('P00016', '6930578800700', '6205-2RS轴承', 'PC0201', 'BR03', 'PCS', '25x52x15mm', 12.00, 28.00, 24.00, 20.00, 10.50, 13, 200, 1000),
    ('P00017', '6930578800701', '6206-2RS轴承', 'PC0201', 'BR03', 'PCS', '30x62x16mm', 15.00, 35.00, 30.00, 25.00, 13.00, 13, 200, 1000),
    ('P00018', '6930578800702', '6208-2RS轴承', 'PC0201', 'BR04', 'PCS', '40x80x18mm', 25.00, 55.00, 48.00, 40.00, 22.00, 13, 100, 500),
    ('P00019', '6930578800800', '直齿轮模数1.5/20齿', 'PC0202', 'BR09', 'PCS', '模数1.5 20齿', 8.50, 20.00, 17.00, 14.00, 7.50, 13, 100, 500),
    ('P00020', '6930578800801', '斤齿轮模数2/25齿', 'PC0202', 'BR09', 'PCS', '模数2 25齿', 12.00, 28.00, 24.00, 20.00, 10.50, 13, 100, 500),
    ('P00021', '6930578800900', '弹性联轴器—25', 'PC0203', 'BR09', 'PCS', 'D25L30', 18.00, 42.00, 36.00, 30.00, 16.00, 13, 50, 300),
    ('P00022', '6930578800901', '梅花联轴器—32', 'PC0203', 'BR09', 'PCS', 'D32L40', 25.00, 58.00, 50.00, 42.00, 22.00, 13, 50, 300),
    ('P00023', '6930578801000', 'O型圈—20x2', 'PC0204', 'BR10', 'PCS', 'NBR 20x2', 0.15, 0.40, 0.35, 0.28, 0.12, 13, 2000, 10000),
    ('P00024', '6930578801001', '油封—30x50x10', 'PC0204', 'BR10', 'PCS', 'TC 30x50x10', 2.50, 6.00, 5.20, 4.50, 2.20, 13, 500, 2000),
    ('P00025', '6930578801100', '57步进电机', 'PC0301', 'BR09', 'PCS', '57x57mm 1.8°', 45.00, 98.00, 85.00, 72.00, 40.00, 13, 30, 200),
    ('P00026', '6930578801101', '42步进电机', 'PC0301', 'BR09', 'PCS', '42x42mm 1.8°', 28.00, 62.00, 54.00, 45.00, 25.00, 13, 50, 300),
    ('P00027', '6930578801102', '775直流电机', 'PC0301', 'BR09', 'PCS', 'DC 12V', 18.00, 42.00, 36.00, 30.00, 16.00, 13, 50, 300),
    ('P00028', '6930578801200', 'PLC控制器FX3U-32MT', 'PC0302', 'BR10', 'SET', '16入16出', 850.00, 1580.00, 1420.00, 1280.00, 780.00, 13, 5, 30),
    ('P00029', '6930578801201', '温度控制器REX-C100', 'PC0302', 'BR09', 'SET', '0-400℃', 45.00, 95.00, 82.00, 70.00, 40.00, 13, 20, 100),
    ('P00030', '6930578801300', '光电传感器E3F-DS30C4', 'PC0303', 'BR10', 'PCS', 'NPN 对射', 18.00, 42.00, 36.00, 30.00, 16.00, 13, 50, 300),
    ('P00031', '6930578801301', '接近开关LJ12A3-4-Z/BX', 'PC0303', 'BR10', 'PCS', 'NPN 正常开', 8.00, 18.00, 15.00, 12.50, 7.00, 13, 100, 500),
    ('P00032', '6930578801400', '三层纸箱—1号', 'PC0401', 'BR10', 'PCS', '350x250x200mm', 3.50, 8.00, 7.00, 6.00, 3.00, 13, 500, 3000),
    ('P00033', '6930578801401', '五层纸箱—2号', 'PC0401', 'BR10', 'PCS', '450x350x300mm', 6.50, 14.00, 12.00, 10.00, 5.80, 13, 300, 2000),
    ('P00034', '6930578801500', 'PE自封袋10x15cm', 'PC0402', 'BR10', 'BAG', '10x15cm 100只/包', 5.00, 12.00, 10.00, 8.50, 4.50, 13, 200, 1000),
    ('P00035', '6930578801501', '气泡袋25x30cm', 'PC0402', 'BR10', 'BAG', '25x30cm 50只/包', 15.00, 32.00, 28.00, 24.00, 13.50, 13, 100, 500),
    ('P00036', '6930578801600', 'EPE泡棉板10mm', 'PC0403', 'BR10', 'SHEET', '100x200cm', 8.00, 18.00, 15.00, 12.50, 7.00, 13, 100, 500),
    ('P00037', '6930578801700', '6061铝板5mm', 'PC0501', 'BR10', 'KG', '1200x2400mm', 28.00, 55.00, 48.00, 42.00, 25.00, 13, 100, 500),
    ('P00038', '6930578801701', '6063铝型材', 'PC0501', 'BR10', 'KG', '方管 40x40x3', 25.00, 48.00, 42.00, 36.00, 22.00, 13, 100, 500),
    ('P00039', '6930578801800', 'T2紫铜板1.5mm', 'PC0502', 'BR10', 'KG', '600x1500mm', 65.00, 120.00, 105.00, 92.00, 58.00, 13, 50, 300),
    ('P00040', '6930578801900', '45#钢棒5mm', 'PC0503', 'BR10', 'KG', '结构钢', 6.00, 12.00, 10.50, 9.00, 5.50, 13, 200, 1000),
    ('P00041', '6930578801901', '304不锈钢板2mm', 'PC0503', 'BR10', 'KG', '1219x2438mm', 18.00, 35.00, 30.00, 26.00, 16.00, 13, 100, 500),
    ('P00042', '6930578802000', 'ABS塑料粒子', 'PC0504', 'BR10', 'KG', '通用级', 12.00, 22.00, 19.00, 16.50, 10.50, 13, 200, 1000),
    ('P00043', '6930578802001', 'PP塑料粒子', 'PC0504', 'BR10', 'KG', '注塑级', 10.00, 18.00, 15.50, 13.50, 9.00, 13, 200, 1000),
    ('P00044', '6930578802002', 'PC塑料粒子', 'PC0504', 'BR10', 'KG', '透明级', 25.00, 45.00, 39.00, 34.00, 22.00, 13, 100, 500),
    ('P00045', '6930578802100', 'SMD LED红色0603', 'PC0101', 'BR01', 'PCS', '0603 RED', 0.02, 0.05, 0.04, 0.03, 0.015, 13, 10000, 100000),
    ('P00046', '6930578802101', 'SMD LED绿色0805', 'PC0101', 'BR01', 'PCS', '0805 GREEN', 0.025, 0.06, 0.05, 0.04, 0.02, 13, 10000, 100000),
    ('P00047', '6930578802102', 'SMD LED蓝色0805', 'PC0101', 'BR01', 'PCS', '0805 BLUE', 0.03, 0.08, 0.07, 0.055, 0.025, 13, 10000, 100000),
    ('P00048', '6930578802200', '0805 100nF电容', 'PC0102', 'BR06', 'PCS', 'X7R 50V', 0.008, 0.02, 0.018, 0.015, 0.006, 13, 20000, 100000),
    ('P00049', '6930578802201', '0603 10nF电容', 'PC0102', 'BR06', 'PCS', 'X7R 50V', 0.006, 0.015, 0.012, 0.01, 0.005, 13, 20000, 100000),
    ('P00050', '6930578802300', 'LM7805稳压芯片', 'PC0106', 'BR08', 'PCS', 'TO-220', 0.80, 1.80, 1.55, 1.30, 0.70, 13, 2000, 10000),
]

WAREHOUSES = [
    ('WH01', '原材料仓库', 1, '一号工业园区A栋', 5000, 100000),
    ('WH02', '成品仓库', 2, '一号工业园区B栋', 8000, 150000),
    ('WH03', '半成品仓库', 3, '一号工业园区C栋', 3000, 50000),
    ('WH04', '退货仓库', 4, '一号工业园区D栋', 1000, 20000),
    ('WH05', '外租仓库', 2, '二号工业园区', 6000, 80000),
]

# 库位数据生成
def generate_locations():
    locations = []
    for wh_idx, wh in enumerate(WAREHOUSES, 1):
        areas = ['A', 'B', 'C', 'D']
        for area in areas[:3]:  # 每个仓库3个区域
            for shelf in range(1, 6):  # 每个区域5个货架
                for layer in range(1, 5):  # 每个货架4层
                    loc_code = f"{wh[0]}-{area}{shelf:02d}-{layer:02d}"
                    loc_name = f"{wh[1]}{area}区{shelf}号架{layer}层"
                    locations.append((loc_code, loc_name, wh_idx, area, str(shelf), str(layer), '', 100))
    return locations

LOCATIONS = generate_locations()


def create_database():
    """创建数据库和表结构"""
    print("\n" + "="*60)
    print("开始创建进销存系统Mock数据库...")
    print("="*60)
    
    # 连接MySQL服务器
    conn = pymysql.connect(**DB_CONFIG)
    cursor = conn.cursor()
    
    try:
        # 创建数据库
        cursor.execute(f"DROP DATABASE IF EXISTS {ERP_DATABASE}")
        cursor.execute(f"CREATE DATABASE {ERP_DATABASE} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        print(f"✅ 数据库 {ERP_DATABASE} 创建成功")
        
        cursor.execute(f"USE {ERP_DATABASE}")
        
        # 预处理SQL：移除注释
        sql_content = CREATE_TABLES_SQL
        # 移除单行注释
        lines = sql_content.split('\n')
        clean_lines = []
        for line in lines:
            line = line.strip()
            if not line.startswith('--'):
                # 移除行内注释
                if '--' in line:
                    line = line[:line.index('--')]
                clean_lines.append(line)
        sql_content = '\n'.join(clean_lines)
        
        # 执行建表SQL
        table_count = 0
        for statement in sql_content.split(';'):
            statement = statement.strip()
            if statement and 'CREATE TABLE' in statement.upper():
                try:
                    cursor.execute(statement)
                    table_count += 1
                except Exception as e:
                    if 'already exists' not in str(e):
                        print(f"⚠️ SQL执行警告: {str(e)[:100]}")
        
        conn.commit()
        print(f"✅ 所有表结构创建成功 ({table_count} 张表)")
        
    finally:
        cursor.close()
        conn.close()


def insert_basic_data():
    """插入基础数据"""
    print("\n" + "-"*60)
    print("正在插入基础数据...")
    print("-"*60)
    
    conn = pymysql.connect(**DB_CONFIG, database=ERP_DATABASE)
    cursor = conn.cursor()
    
    try:
        # 1. 插入部门数据
        dept_id_map = {}
        for dept in DEPARTMENTS:
            parent_id = dept_id_map.get(dept[2]) if dept[2] else None
            cursor.execute(
                "INSERT INTO department (dept_code, dept_name, parent_id) VALUES (%s, %s, %s)",
                (dept[0], dept[1], parent_id)
            )
            dept_id_map[dept[0]] = cursor.lastrowid
        print(f"✅ 插入部门数据: {len(DEPARTMENTS)} 条")
        
        # 2. 插入员工数据
        emp_id_map = {}
        for emp in EMPLOYEES:
            dept_id = dept_id_map.get(emp[5])
            cursor.execute(
                """INSERT INTO employee (emp_code, emp_name, gender, phone, email, dept_id, position, hire_date) 
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                (emp[0], emp[1], emp[2], emp[3], emp[4], dept_id, emp[6], 
                 datetime.now() - timedelta(days=random.randint(100, 1500)))
            )
            emp_id_map[emp[0]] = cursor.lastrowid
        print(f"✅ 插入员工数据: {len(EMPLOYEES)} 条")
        
        # 3. 插入供应商分类
        supplier_cat_id_map = {}
        for cat in SUPPLIER_CATEGORIES:
            parent_id = supplier_cat_id_map.get(cat[2]) if cat[2] else None
            cursor.execute(
                "INSERT INTO supplier_category (category_code, category_name, parent_id) VALUES (%s, %s, %s)",
                (cat[0], cat[1], parent_id)
            )
            supplier_cat_id_map[cat[0]] = cursor.lastrowid
        print(f"✅ 插入供应商分类: {len(SUPPLIER_CATEGORIES)} 条")
        
        # 4. 插入供应商数据
        supplier_id_map = {}
        for s in SUPPLIERS:
            cat_id = supplier_cat_id_map.get(s[2])
            cursor.execute(
                """INSERT INTO supplier (supplier_code, supplier_name, category_id, contact_person, 
                   contact_phone, province, city, district, credit_rating, payment_terms) 
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (s[0], s[1], cat_id, s[3], s[4], s[5], s[6], s[7], s[8], s[9])
            )
            supplier_id_map[s[0]] = cursor.lastrowid
        print(f"✅ 插入供应商数据: {len(SUPPLIERS)} 条")
        
        # 5. 插入客户分类
        customer_cat_id_map = {}
        for cat in CUSTOMER_CATEGORIES:
            parent_id = customer_cat_id_map.get(cat[2]) if cat[2] else None
            cursor.execute(
                "INSERT INTO customer_category (category_code, category_name, parent_id, discount_rate) VALUES (%s, %s, %s, %s)",
                (cat[0], cat[1], parent_id, cat[3])
            )
            customer_cat_id_map[cat[0]] = cursor.lastrowid
        print(f"✅ 插入客户分类: {len(CUSTOMER_CATEGORIES)} 条")
        
        # 6. 插入客户数据
        customer_id_map = {}
        sales_reps = ['E007', 'E008', 'E009', 'E010']
        for c in CUSTOMERS:
            cat_id = customer_cat_id_map.get(c[3])
            rep_id = emp_id_map.get(random.choice(sales_reps))
            cursor.execute(
                """INSERT INTO customer (customer_code, customer_name, customer_type, category_id, 
                   contact_person, contact_phone, province, city, district, credit_limit, 
                   credit_rating, sales_rep_id, payment_terms) 
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (c[0], c[1], c[2], cat_id, c[4], c[5], c[6], c[7], c[8], c[9], c[10], rep_id, c[11])
            )
            customer_id_map[c[0]] = cursor.lastrowid
        print(f"✅ 插入客户数据: {len(CUSTOMERS)} 条")
        
        # 7. 插入商品分类
        product_cat_id_map = {}
        for cat in PRODUCT_CATEGORIES:
            parent_id = product_cat_id_map.get(cat[2]) if cat[2] else None
            cursor.execute(
                "INSERT INTO product_category (category_code, category_name, parent_id, level) VALUES (%s, %s, %s, %s)",
                (cat[0], cat[1], parent_id, cat[3])
            )
            product_cat_id_map[cat[0]] = cursor.lastrowid
        print(f"✅ 插入商品分类: {len(PRODUCT_CATEGORIES)} 条")
        
        # 8. 插入计量单位
        unit_id_map = {}
        for u in UNITS:
            cursor.execute(
                "INSERT INTO unit (unit_code, unit_name) VALUES (%s, %s)",
                (u[0], u[1])
            )
            unit_id_map[u[0]] = cursor.lastrowid
        print(f"✅ 插入计量单位: {len(UNITS)} 条")
        
        # 9. 插入品牌
        brand_id_map = {}
        for b in BRANDS:
            cursor.execute(
                "INSERT INTO brand (brand_code, brand_name) VALUES (%s, %s)",
                (b[0], b[1])
            )
            brand_id_map[b[0]] = cursor.lastrowid
        print(f"✅ 插入品牌数据: {len(BRANDS)} 条")
        
        # 10. 插入商品数据
        product_id_map = {}
        for p in PRODUCTS:
            cat_id = product_cat_id_map.get(p[3])
            brand_id = brand_id_map.get(p[4])
            unit_id = unit_id_map.get(p[5])
            cursor.execute(
                """INSERT INTO product (product_code, barcode, product_name, category_id, brand_id, 
                   unit_id, spec, purchase_price, sale_price, min_price, wholesale_price, cost_price,
                   tax_rate, min_stock, max_stock) 
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (p[0], p[1], p[2], cat_id, brand_id, unit_id, p[6], 
                 p[7], p[8], p[9], p[10], p[11], p[12], p[13], p[14])
            )
            product_id_map[p[0]] = cursor.lastrowid
        print(f"✅ 插入商品数据: {len(PRODUCTS)} 条")
        
        # 11. 插入仓库数据
        warehouse_id_map = {}
        for wh in WAREHOUSES:
            manager_id = emp_id_map.get('E011')  # 仓库经理
            cursor.execute(
                """INSERT INTO warehouse (warehouse_code, warehouse_name, warehouse_type, address, 
                   manager_id, area, capacity) 
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (wh[0], wh[1], wh[2], wh[3], manager_id, wh[4], wh[5])
            )
            warehouse_id_map[wh[0]] = cursor.lastrowid
        print(f"✅ 插入仓库数据: {len(WAREHOUSES)} 条")
        
        # 12. 插入库位数据
        location_id_map = {}
        for loc in LOCATIONS:
            wh_id = list(warehouse_id_map.values())[loc[2] - 1]  # 索引从1开始
            cursor.execute(
                """INSERT INTO warehouse_location (location_code, location_name, warehouse_id, 
                   area, shelf, layer, position, capacity) 
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                (loc[0], loc[1], wh_id, loc[3], loc[4], loc[5], loc[6], loc[7])
            )
            location_id_map[loc[0]] = cursor.lastrowid
        print(f"✅ 插入库位数据: {len(LOCATIONS)} 条")
        
        conn.commit()
        
        return {
            'dept_id_map': dept_id_map,
            'emp_id_map': emp_id_map,
            'supplier_id_map': supplier_id_map,
            'customer_id_map': customer_id_map,
            'product_id_map': product_id_map,
            'product_cat_id_map': product_cat_id_map,
            'unit_id_map': unit_id_map,
            'warehouse_id_map': warehouse_id_map,
            'location_id_map': location_id_map,
        }
        
    finally:
        cursor.close()
        conn.close()


def insert_business_data(id_maps):
    """插入业务数据（采购、销售、库存等）"""
    print("\n" + "-"*60)
    print("正在插入业务数据...")
    print("-"*60)
    
    conn = pymysql.connect(**DB_CONFIG, database=ERP_DATABASE)
    cursor = conn.cursor()
    
    supplier_ids = list(id_maps['supplier_id_map'].values())
    customer_ids = list(id_maps['customer_id_map'].values())
    product_ids = list(id_maps['product_id_map'].values())
    warehouse_ids = list(id_maps['warehouse_id_map'].values())
    emp_ids = list(id_maps['emp_id_map'].values())
    location_ids = list(id_maps['location_id_map'].values())
    
    # 获取商品价格信息
    cursor.execute("SELECT id, purchase_price, sale_price, tax_rate FROM product")
    product_prices = {row[0]: {'purchase': float(row[1]), 'sale': float(row[2]), 'tax': float(row[3])} for row in cursor.fetchall()}
    
    try:
        # ============================================================
        # 生成采购订单数据 (200单)
        # ============================================================
        print("正在生成采购订单...")
        purchase_orders = []
        
        for i in range(200):
            order_date = datetime.now() - timedelta(days=random.randint(1, 365))
            order_no = f"PO{order_date.strftime('%Y%m%d')}{i+1:04d}"
            supplier_id = random.choice(supplier_ids)
            warehouse_id = warehouse_ids[0]  # 原材料仓库
            buyer_id = random.choice([emp_ids[3], emp_ids[4], emp_ids[5]])  # 采购部员工
            order_status = random.choices([0, 1, 2, 3, 4, 5], weights=[5, 5, 15, 10, 60, 5])[0]
            
            # 生成3-8个订单明细
            detail_count = random.randint(3, 8)
            selected_products = random.sample(product_ids, min(detail_count, len(product_ids)))
            
            total_qty = 0
            total_amount = 0
            tax_amount = 0
            
            details = []
            for prod_id in selected_products:
                qty = random.randint(100, 5000)
                price_info = product_prices.get(prod_id, {'purchase': 10.0, 'tax': 13.0})
                unit_price = price_info['purchase'] * random.uniform(0.95, 1.05)
                tax_rate = price_info['tax']
                
                amount = qty * unit_price
                tax = amount * tax_rate / 100
                
                total_qty += qty
                total_amount += amount
                tax_amount += tax
                
                received_qty = 0
                if order_status >= 3:
                    received_qty = qty if order_status == 4 else int(qty * random.uniform(0.3, 0.8))
                
                details.append({
                    'product_id': prod_id,
                    'quantity': qty,
                    'received_qty': received_qty,
                    'unit_price': round(unit_price, 4),
                    'tax_rate': tax_rate,
                    'tax_amount': round(tax, 2),
                    'amount': round(amount, 2),
                    'total_amount': round(amount + tax, 2)
                })
            
            payable_amount = total_amount + tax_amount
            paid_amount = 0
            payment_status = 0
            if order_status >= 2:
                if random.random() < 0.6:
                    paid_amount = payable_amount
                    payment_status = 2
                elif random.random() < 0.3:
                    paid_amount = payable_amount * random.uniform(0.3, 0.7)
                    payment_status = 1
            
            purchase_orders.append({
                'order_no': order_no,
                'supplier_id': supplier_id,
                'warehouse_id': warehouse_id,
                'order_date': order_date.date(),
                'expected_date': (order_date + timedelta(days=random.randint(3, 15))).date(),
                'buyer_id': buyer_id,
                'order_status': order_status,
                'total_qty': round(total_qty, 3),
                'total_amount': round(total_amount, 2),
                'tax_amount': round(tax_amount, 2),
                'payable_amount': round(payable_amount, 2),
                'paid_amount': round(paid_amount, 2),
                'payment_status': payment_status,
                'details': details
            })
        
        # 插入采购订单
        for po in purchase_orders:
            cursor.execute(
                """INSERT INTO purchase_order (order_no, supplier_id, warehouse_id, order_date, 
                   expected_date, buyer_id, order_status, total_qty, total_amount, tax_amount,
                   payable_amount, paid_amount, payment_status) 
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (po['order_no'], po['supplier_id'], po['warehouse_id'], po['order_date'],
                 po['expected_date'], po['buyer_id'], po['order_status'], po['total_qty'],
                 po['total_amount'], po['tax_amount'], po['payable_amount'], po['paid_amount'],
                 po['payment_status'])
            )
            order_id = cursor.lastrowid
            
            for d in po['details']:
                cursor.execute(
                    """INSERT INTO purchase_order_detail (order_id, product_id, quantity, received_qty,
                       unit_price, tax_rate, tax_amount, amount, total_amount)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (order_id, d['product_id'], d['quantity'], d['received_qty'], d['unit_price'],
                     d['tax_rate'], d['tax_amount'], d['amount'], d['total_amount'])
                )
        
        print(f"✅ 插入采购订单: {len(purchase_orders)} 单")
        
        # ============================================================
        # 生成销售订单数据 (300单)
        # ============================================================
        print("正在生成销售订单...")
        sales_orders = []
        
        for i in range(300):
            order_date = datetime.now() - timedelta(days=random.randint(1, 365))
            order_no = f"SO{order_date.strftime('%Y%m%d')}{i+1:04d}"
            customer_id = random.choice(customer_ids)
            warehouse_id = warehouse_ids[1]  # 成品仓库
            salesman_id = random.choice([emp_ids[6], emp_ids[7], emp_ids[8], emp_ids[9]])  # 销售部员工
            order_status = random.choices([0, 1, 2, 3, 4, 5], weights=[3, 5, 10, 15, 62, 5])[0]
            
            detail_count = random.randint(2, 6)
            selected_products = random.sample(product_ids, min(detail_count, len(product_ids)))
            
            total_qty = 0
            total_amount = 0
            tax_amount = 0
            
            details = []
            for prod_id in selected_products:
                qty = random.randint(10, 500)
                price_info = product_prices.get(prod_id, {'sale': 20.0, 'tax': 13.0})
                unit_price = price_info['sale'] * random.uniform(0.9, 1.0)
                tax_rate = price_info['tax']
                
                amount = qty * unit_price
                tax = amount * tax_rate / 100
                
                total_qty += qty
                total_amount += amount
                tax_amount += tax
                
                delivered_qty = 0
                if order_status >= 3:
                    delivered_qty = qty if order_status == 4 else int(qty * random.uniform(0.4, 0.9))
                
                details.append({
                    'product_id': prod_id,
                    'quantity': qty,
                    'delivered_qty': delivered_qty,
                    'unit_price': round(unit_price, 4),
                    'tax_rate': tax_rate,
                    'tax_amount': round(tax, 2),
                    'amount': round(amount, 2),
                    'total_amount': round(amount + tax, 2)
                })
            
            discount_rate = random.choice([100, 98, 95, 92, 90])
            discount_amount = total_amount * (100 - discount_rate) / 100
            receivable_amount = total_amount + tax_amount - discount_amount
            received_amount = 0
            payment_status = 0
            
            if order_status >= 2:
                if random.random() < 0.55:
                    received_amount = receivable_amount
                    payment_status = 2
                elif random.random() < 0.35:
                    received_amount = receivable_amount * random.uniform(0.3, 0.7)
                    payment_status = 1
            
            sales_orders.append({
                'order_no': order_no,
                'customer_id': customer_id,
                'warehouse_id': warehouse_id,
                'order_date': order_date.date(),
                'delivery_date': (order_date + timedelta(days=random.randint(1, 7))).date(),
                'salesman_id': salesman_id,
                'order_status': order_status,
                'total_qty': round(total_qty, 3),
                'total_amount': round(total_amount, 2),
                'tax_amount': round(tax_amount, 2),
                'discount_rate': discount_rate,
                'discount_amount': round(discount_amount, 2),
                'receivable_amount': round(receivable_amount, 2),
                'received_amount': round(received_amount, 2),
                'payment_status': payment_status,
                'details': details
            })
        
        # 插入销售订单
        for so in sales_orders:
            cursor.execute(
                """INSERT INTO sales_order (order_no, customer_id, warehouse_id, order_date,
                   delivery_date, salesman_id, order_status, total_qty, total_amount, tax_amount,
                   discount_rate, discount_amount, receivable_amount, received_amount, payment_status)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (so['order_no'], so['customer_id'], so['warehouse_id'], so['order_date'],
                 so['delivery_date'], so['salesman_id'], so['order_status'], so['total_qty'],
                 so['total_amount'], so['tax_amount'], so['discount_rate'], so['discount_amount'],
                 so['receivable_amount'], so['received_amount'], so['payment_status'])
            )
            order_id = cursor.lastrowid
            
            for d in so['details']:
                cursor.execute(
                    """INSERT INTO sales_order_detail (order_id, product_id, quantity, delivered_qty,
                       unit_price, tax_rate, tax_amount, amount, total_amount)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (order_id, d['product_id'], d['quantity'], d['delivered_qty'], d['unit_price'],
                     d['tax_rate'], d['tax_amount'], d['amount'], d['total_amount'])
                )
        
        print(f"✅ 插入销售订单: {len(sales_orders)} 单")
        
        # ============================================================
        # 生成库存数据
        # ============================================================
        print("正在生成库存数据...")
        inventory_count = 0
        
        for prod_id in product_ids:
            for wh_id in warehouse_ids[:3]:  # 前3个仓库
                if random.random() < 0.7:  # 70%概率有库存
                    qty = random.randint(100, 10000)
                    available_qty = int(qty * random.uniform(0.8, 1.0))
                    locked_qty = qty - available_qty
                    price_info = product_prices.get(prod_id, {'purchase': 10.0})
                    cost_price = price_info['purchase']
                    
                    cursor.execute(
                        """INSERT INTO inventory (warehouse_id, product_id, quantity, available_qty,
                           locked_qty, cost_price, total_cost, last_in_date)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                        (wh_id, prod_id, qty, available_qty, locked_qty, cost_price,
                         round(qty * cost_price, 2), datetime.now() - timedelta(days=random.randint(1, 30)))
                    )
                    inventory_count += 1
        
        print(f"✅ 插入库存数据: {inventory_count} 条")
        
        # ============================================================
        # 生成库存流水数据
        # ============================================================
        print("正在生成库存流水...")
        transaction_types = ['PURCHASE_IN', 'SALES_OUT', 'TRANSFER_IN', 'TRANSFER_OUT', 'ADJUST']
        transaction_count = 0
        
        for i in range(500):
            trans_type = random.choice(transaction_types)
            direction = 1 if trans_type in ['PURCHASE_IN', 'TRANSFER_IN', 'SALES_RETURN'] else -1
            trans_time = datetime.now() - timedelta(days=random.randint(1, 180), hours=random.randint(0, 23))
            trans_no = f"IT{trans_time.strftime('%Y%m%d%H%M%S')}{i:04d}"
            
            prod_id = random.choice(product_ids)
            wh_id = random.choice(warehouse_ids[:3])
            qty = random.randint(10, 500)
            before_qty = random.randint(100, 5000)
            after_qty = before_qty + (qty * direction)
            price_info = product_prices.get(prod_id, {'purchase': 10.0})
            unit_price = price_info['purchase']
            
            cursor.execute(
                """INSERT INTO inventory_transaction (transaction_no, transaction_type, warehouse_id,
                   product_id, direction, quantity, before_qty, after_qty, unit_price, amount,
                   operator_id, transaction_time)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (trans_no, trans_type, wh_id, prod_id, direction, qty, before_qty, max(0, after_qty),
                 unit_price, round(qty * unit_price, 2), random.choice(emp_ids), trans_time)
            )
            transaction_count += 1
        
        print(f"✅ 插入库存流水: {transaction_count} 条")
        
        # ============================================================
        # 生成应付账款数据
        # ============================================================
        print("正在生成应付账款...")
        payable_count = 0
        
        for i in range(80):
            payable_no = f"AP{datetime.now().strftime('%Y%m')}{i+1:04d}"
            supplier_id = random.choice(supplier_ids)
            payable_amount = round(random.uniform(5000, 200000), 2)
            paid_amount = 0
            status = 0
            
            if random.random() < 0.5:
                paid_amount = payable_amount
                status = 2
            elif random.random() < 0.3:
                paid_amount = round(payable_amount * random.uniform(0.3, 0.7), 2)
                status = 1
            
            cursor.execute(
                """INSERT INTO accounts_payable (payable_no, supplier_id, source_type, payable_amount,
                   paid_amount, unpaid_amount, due_date, status)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                (payable_no, supplier_id, 'PURCHASE', payable_amount, paid_amount,
                 round(payable_amount - paid_amount, 2),
                 (datetime.now() + timedelta(days=random.randint(-30, 60))).date(), status)
            )
            payable_count += 1
        
        print(f"✅ 插入应付账款: {payable_count} 条")
        
        # ============================================================
        # 生成应收账款数据
        # ============================================================
        print("正在生成应收账款...")
        receivable_count = 0
        
        for i in range(100):
            receivable_no = f"AR{datetime.now().strftime('%Y%m')}{i+1:04d}"
            customer_id = random.choice(customer_ids)
            receivable_amount = round(random.uniform(3000, 150000), 2)
            received_amount = 0
            status = 0
            
            if random.random() < 0.55:
                received_amount = receivable_amount
                status = 2
            elif random.random() < 0.25:
                received_amount = round(receivable_amount * random.uniform(0.3, 0.7), 2)
                status = 1
            
            cursor.execute(
                """INSERT INTO accounts_receivable (receivable_no, customer_id, source_type, 
                   receivable_amount, received_amount, unreceived_amount, due_date, status)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                (receivable_no, customer_id, 'SALES', receivable_amount, received_amount,
                 round(receivable_amount - received_amount, 2),
                 (datetime.now() + timedelta(days=random.randint(-15, 45))).date(), status)
            )
            receivable_count += 1
        
        print(f"✅ 插入应收账款: {receivable_count} 条")
        
        # ============================================================
        # 生成付款记录
        # ============================================================
        print("正在生成付款记录...")
        payment_methods = ['CASH', 'BANK', 'CHECK', 'CREDIT']
        payment_count = 0
        
        for i in range(60):
            payment_no = f"PAY{datetime.now().strftime('%Y%m')}{i+1:04d}"
            supplier_id = random.choice(supplier_ids)
            payment_amount = round(random.uniform(2000, 100000), 2)
            payment_method = random.choice(payment_methods)
            payment_date = (datetime.now() - timedelta(days=random.randint(1, 180))).date()
            
            cursor.execute(
                """INSERT INTO payment_record (payment_no, supplier_id, payment_amount, 
                   payment_method, payment_date, handler_id, status)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (payment_no, supplier_id, payment_amount, payment_method, payment_date,
                 random.choice(emp_ids[:3]), 1)
            )
            payment_count += 1
        
        print(f"✅ 插入付款记录: {payment_count} 条")
        
        # ============================================================
        # 生成收款记录
        # ============================================================
        print("正在生成收款记录...")
        receipt_count = 0
        
        for i in range(80):
            receipt_no = f"REC{datetime.now().strftime('%Y%m')}{i+1:04d}"
            customer_id = random.choice(customer_ids)
            receipt_amount = round(random.uniform(1500, 80000), 2)
            receipt_method = random.choice(payment_methods)
            receipt_date = (datetime.now() - timedelta(days=random.randint(1, 180))).date()
            
            cursor.execute(
                """INSERT INTO receipt_record (receipt_no, customer_id, receipt_amount,
                   receipt_method, receipt_date, handler_id, status)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (receipt_no, customer_id, receipt_amount, receipt_method, receipt_date,
                 random.choice(emp_ids[:3]), 1)
            )
            receipt_count += 1
        
        print(f"✅ 插入收款记录: {receipt_count} 条")
        
        conn.commit()
        
    finally:
        cursor.close()
        conn.close()


def print_summary():
    """打印数据库统计信息"""
    print("\n" + "="*60)
    print("数据库统计信息")
    print("="*60)
    
    conn = pymysql.connect(**DB_CONFIG, database=ERP_DATABASE)
    cursor = conn.cursor()
    
    try:
        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()
        
        print(f"\n数据库: {ERP_DATABASE}")
        print(f"表数量: {len(tables)}")
        print("\n各表数据统计:")
        print("-" * 40)
        
        total_rows = 0
        for (table,) in tables:
            cursor.execute(f"SELECT COUNT(*) FROM `{table}`")
            count = cursor.fetchone()[0]
            total_rows += count
            print(f"  {table}: {count} 条")
        
        print("-" * 40)
        print(f"  总计: {total_rows} 条数据")
        
    finally:
        cursor.close()
        conn.close()


def main():
    """主函数"""
    print("\n" + "#"*60)
    print("#  进销存系统 Mock 数据初始化工具")
    print("#"*60)
    
    print(f"\n数据库服务器: {DB_CONFIG['host']}:{DB_CONFIG['port']}")
    print(f"目标数据库: {ERP_DATABASE}")
    
    try:
        # 1. 创建数据库和表
        create_database()
        
        # 2. 插入基础数据
        id_maps = insert_basic_data()
        
        # 3. 插入业务数据
        insert_business_data(id_maps)
        
        # 4. 打印统计信息
        print_summary()
        
        print("\n" + "="*60)
        print("✅ 进销存系统 Mock 数据初始化完成!")
        print("="*60)
        print(f"\n您现在可以在 admin 系统中添加数据库连接:")
        print(f"  - 数据库类型: MySQL")
        print(f"  - 主机: {DB_CONFIG['host']}")
        print(f"  - 端口: {DB_CONFIG['port']}")
        print(f"  - 用户名: {DB_CONFIG['user']}")
        print(f"  - 数据库名: {ERP_DATABASE}")
        
    except Exception as e:
        print(f"\n❌ 错误: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())

