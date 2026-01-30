-- ============================================================
-- 进销存业务系统数据库初始化脚本 (PostgreSQL 15)
-- 数据库名: erp_business
-- 目标容器: postgres-checkpointer (端口5433)
-- 创建时间: 2026-01-30
-- 表数量: 33张
-- ============================================================

-- 设置客户端编码
SET client_encoding = 'UTF8';

-- 创建数据库 (如果不存在)
-- 注意: 执行前请确保以管理员身份连接到postgres数据库
-- CREATE DATABASE erp_business WITH ENCODING 'UTF8' LC_COLLATE='zh_CN.UTF-8' LC_CTYPE='zh_CN.UTF-8' TEMPLATE=template0;

-- 连接到目标数据库
\c erp_business

-- 创建扩展
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================
-- 一、组织架构模块 (4张表)
-- ============================================================

-- 1. 分公司表
CREATE TABLE IF NOT EXISTS t_company (
    id SERIAL PRIMARY KEY,
    company_code VARCHAR(20) NOT NULL UNIQUE,
    company_name VARCHAR(200) NOT NULL,
    province VARCHAR(50),
    city VARCHAR(50),
    district VARCHAR(50),
    address VARCHAR(500),
    manager_id INTEGER,
    status SMALLINT DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON TABLE t_company IS '分公司表';
COMMENT ON COLUMN t_company.id IS '公司ID';
COMMENT ON COLUMN t_company.company_code IS '公司编码';
COMMENT ON COLUMN t_company.company_name IS '公司名称';
COMMENT ON COLUMN t_company.status IS '状态: 1-启用, 0-停用';

CREATE INDEX idx_company_status ON t_company(status);
CREATE INDEX idx_company_city ON t_company(city);

-- 2. 部门表
CREATE TABLE IF NOT EXISTS t_department (
    id SERIAL PRIMARY KEY,
    dept_code VARCHAR(20) NOT NULL UNIQUE,
    dept_name VARCHAR(100) NOT NULL,
    company_id INTEGER,
    parent_id INTEGER,
    manager_id INTEGER,
    sort_order INTEGER DEFAULT 0,
    status SMALLINT DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON TABLE t_department IS '部门表';
COMMENT ON COLUMN t_department.id IS '部门ID';
COMMENT ON COLUMN t_department.parent_id IS '上级部门ID';

CREATE INDEX idx_dept_company ON t_department(company_id);
CREATE INDEX idx_dept_parent ON t_department(parent_id);
CREATE INDEX idx_dept_status ON t_department(status);

-- 3. 员工表
CREATE TABLE IF NOT EXISTS t_employee (
    id SERIAL PRIMARY KEY,
    emp_code VARCHAR(20) NOT NULL UNIQUE,
    emp_name VARCHAR(50) NOT NULL,
    dept_id INTEGER,
    company_id INTEGER,
    position VARCHAR(50),
    phone VARCHAR(20),
    email VARCHAR(100),
    hire_date DATE,
    base_salary NUMERIC(12,2) DEFAULT 0,
    commission_rate NUMERIC(5,2) DEFAULT 0,
    status SMALLINT DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON TABLE t_employee IS '员工表';
COMMENT ON COLUMN t_employee.commission_rate IS '提成比例(%)';
COMMENT ON COLUMN t_employee.status IS '状态: 1-在职, 0-离职';

CREATE INDEX idx_emp_dept ON t_employee(dept_id);
CREATE INDEX idx_emp_company ON t_employee(company_id);
CREATE INDEX idx_emp_status ON t_employee(status);
CREATE INDEX idx_emp_position ON t_employee(position);

-- 4. 地区表
CREATE TABLE IF NOT EXISTS t_region (
    id SERIAL PRIMARY KEY,
    region_code VARCHAR(20) NOT NULL UNIQUE,
    region_name VARCHAR(100) NOT NULL,
    province VARCHAR(50),
    city VARCHAR(50),
    district VARCHAR(50),
    level SMALLINT DEFAULT 1,
    parent_id INTEGER,
    sort_order INTEGER DEFAULT 0
);
COMMENT ON TABLE t_region IS '地区表';
COMMENT ON COLUMN t_region.level IS '层级: 1-省, 2-市, 3-区县';

CREATE INDEX idx_region_parent ON t_region(parent_id);
CREATE INDEX idx_region_level ON t_region(level);
CREATE INDEX idx_region_city ON t_region(city);

-- ============================================================
-- 二、往来单位模块 (6张表)
-- ============================================================

-- 5. 供应商分类表
CREATE TABLE IF NOT EXISTS t_supplier_category (
    id SERIAL PRIMARY KEY,
    category_code VARCHAR(20) NOT NULL UNIQUE,
    category_name VARCHAR(100) NOT NULL,
    parent_id INTEGER,
    sort_order INTEGER DEFAULT 0,
    status SMALLINT DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON TABLE t_supplier_category IS '供应商分类表';

CREATE INDEX idx_supplier_cat_parent ON t_supplier_category(parent_id);

-- 6. 供应商表
CREATE TABLE IF NOT EXISTS t_supplier (
    id SERIAL PRIMARY KEY,
    supplier_code VARCHAR(20) NOT NULL UNIQUE,
    supplier_name VARCHAR(200) NOT NULL,
    category_id INTEGER,
    region_id INTEGER,
    contact_person VARCHAR(50),
    phone VARCHAR(20),
    address VARCHAR(500),
    bank_name VARCHAR(100),
    bank_account VARCHAR(50),
    tax_number VARCHAR(50),
    credit_rating VARCHAR(10),
    payment_terms INTEGER DEFAULT 30,
    credit_limit NUMERIC(15,2) DEFAULT 0,
    status SMALLINT DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON TABLE t_supplier IS '供应商表';
COMMENT ON COLUMN t_supplier.credit_rating IS '信用等级: A/B/C/D';
COMMENT ON COLUMN t_supplier.payment_terms IS '账期天数';

CREATE INDEX idx_supplier_category ON t_supplier(category_id);
CREATE INDEX idx_supplier_region ON t_supplier(region_id);
CREATE INDEX idx_supplier_status ON t_supplier(status);
CREATE INDEX idx_supplier_rating ON t_supplier(credit_rating);

-- 7. 客户分类表
CREATE TABLE IF NOT EXISTS t_customer_category (
    id SERIAL PRIMARY KEY,
    category_code VARCHAR(20) NOT NULL UNIQUE,
    category_name VARCHAR(100) NOT NULL,
    parent_id INTEGER,
    discount_rate NUMERIC(5,2) DEFAULT 100.00,
    sort_order INTEGER DEFAULT 0,
    status SMALLINT DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON TABLE t_customer_category IS '客户分类表';
COMMENT ON COLUMN t_customer_category.discount_rate IS '折扣率(%)';

CREATE INDEX idx_customer_cat_parent ON t_customer_category(parent_id);

-- 8. 客户表
CREATE TABLE IF NOT EXISTS t_customer (
    id SERIAL PRIMARY KEY,
    customer_code VARCHAR(20) NOT NULL UNIQUE,
    customer_name VARCHAR(200) NOT NULL,
    category_id INTEGER,
    region_id INTEGER,
    company_id INTEGER,
    salesman_id INTEGER,
    contact_person VARCHAR(50),
    phone VARCHAR(20),
    address VARCHAR(500),
    credit_rating VARCHAR(10),
    credit_limit NUMERIC(15,2) DEFAULT 0,
    payment_terms INTEGER DEFAULT 30,
    discount_rate NUMERIC(5,2) DEFAULT 100.00,
    status SMALLINT DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON TABLE t_customer IS '客户表';
COMMENT ON COLUMN t_customer.salesman_id IS '销售员ID';

CREATE INDEX idx_customer_category ON t_customer(category_id);
CREATE INDEX idx_customer_region ON t_customer(region_id);
CREATE INDEX idx_customer_company ON t_customer(company_id);
CREATE INDEX idx_customer_salesman ON t_customer(salesman_id);
CREATE INDEX idx_customer_status ON t_customer(status);
CREATE INDEX idx_customer_rating ON t_customer(credit_rating);

-- 9. 供应商往来账表
CREATE TABLE IF NOT EXISTS t_supplier_account (
    id SERIAL PRIMARY KEY,
    supplier_id INTEGER NOT NULL UNIQUE,
    total_purchase_amount NUMERIC(15,2) DEFAULT 0,
    total_paid_amount NUMERIC(15,2) DEFAULT 0,
    payable_balance NUMERIC(15,2) DEFAULT 0,
    last_trans_date DATE,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON TABLE t_supplier_account IS '供应商往来账表';
COMMENT ON COLUMN t_supplier_account.payable_balance IS '应付余额';

CREATE INDEX idx_supplier_acc_balance ON t_supplier_account(payable_balance);

-- 10. 客户往来账表
CREATE TABLE IF NOT EXISTS t_customer_account (
    id SERIAL PRIMARY KEY,
    customer_id INTEGER NOT NULL UNIQUE,
    total_sales_amount NUMERIC(15,2) DEFAULT 0,
    total_received_amount NUMERIC(15,2) DEFAULT 0,
    receivable_balance NUMERIC(15,2) DEFAULT 0,
    last_trans_date DATE,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON TABLE t_customer_account IS '客户往来账表';
COMMENT ON COLUMN t_customer_account.receivable_balance IS '应收余额';

CREATE INDEX idx_customer_acc_balance ON t_customer_account(receivable_balance);

-- ============================================================
-- 三、商品管理模块 (5张表)
-- ============================================================

-- 11. 商品分类表
CREATE TABLE IF NOT EXISTS t_product_category (
    id SERIAL PRIMARY KEY,
    category_code VARCHAR(20) NOT NULL UNIQUE,
    category_name VARCHAR(100) NOT NULL,
    parent_id INTEGER,
    level SMALLINT DEFAULT 1,
    sort_order INTEGER DEFAULT 0,
    status SMALLINT DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON TABLE t_product_category IS '商品分类表';
COMMENT ON COLUMN t_product_category.level IS '层级: 1/2/3';

CREATE INDEX idx_product_cat_parent ON t_product_category(parent_id);
CREATE INDEX idx_product_cat_level ON t_product_category(level);

-- 12. 品牌表
CREATE TABLE IF NOT EXISTS t_brand (
    id SERIAL PRIMARY KEY,
    brand_code VARCHAR(20) NOT NULL UNIQUE,
    brand_name VARCHAR(100) NOT NULL,
    logo_url VARCHAR(500),
    description TEXT,
    status SMALLINT DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON TABLE t_brand IS '品牌表';

CREATE INDEX idx_brand_status ON t_brand(status);

-- 13. 商品表
CREATE TABLE IF NOT EXISTS t_product (
    id SERIAL PRIMARY KEY,
    product_code VARCHAR(50) NOT NULL UNIQUE,
    product_name VARCHAR(200) NOT NULL,
    category_id INTEGER,
    brand_id INTEGER,
    unit VARCHAR(20) DEFAULT '个',
    spec VARCHAR(200),
    barcode VARCHAR(50),
    purchase_price NUMERIC(15,4) DEFAULT 0,
    sale_price NUMERIC(15,4) DEFAULT 0,
    cost_method VARCHAR(20) DEFAULT 'WEIGHTED',
    min_stock NUMERIC(12,2) DEFAULT 0,
    max_stock NUMERIC(12,2) DEFAULT 0,
    status SMALLINT DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON TABLE t_product IS '商品表';
COMMENT ON COLUMN t_product.cost_method IS '成本核算方法: WEIGHTED-加权平均, FIFO-先进先出';

CREATE INDEX idx_product_category ON t_product(category_id);
CREATE INDEX idx_product_brand ON t_product(brand_id);
CREATE INDEX idx_product_status ON t_product(status);
CREATE INDEX idx_product_barcode ON t_product(barcode);

-- 14. 商品价格历史表
CREATE TABLE IF NOT EXISTS t_product_price_history (
    id SERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL,
    price_type VARCHAR(20) NOT NULL,
    old_price NUMERIC(15,4),
    new_price NUMERIC(15,4) NOT NULL,
    change_date DATE NOT NULL,
    change_reason VARCHAR(200),
    operator_id INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON TABLE t_product_price_history IS '商品价格历史表';
COMMENT ON COLUMN t_product_price_history.price_type IS '价格类型: PURCHASE-采购价, SALE-销售价';

CREATE INDEX idx_price_hist_product ON t_product_price_history(product_id);
CREATE INDEX idx_price_hist_date ON t_product_price_history(change_date);

-- 15. 促销活动表
CREATE TABLE IF NOT EXISTS t_product_promotion (
    id SERIAL PRIMARY KEY,
    promotion_code VARCHAR(30) NOT NULL UNIQUE,
    promotion_name VARCHAR(200) NOT NULL,
    product_ids TEXT,
    discount_type VARCHAR(20),
    discount_value NUMERIC(10,2),
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    status SMALLINT DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON TABLE t_product_promotion IS '促销活动表';
COMMENT ON COLUMN t_product_promotion.discount_type IS '折扣类型: PERCENT-百分比, AMOUNT-固定金额';
COMMENT ON COLUMN t_product_promotion.product_ids IS '商品ID列表(逗号分隔)';

CREATE INDEX idx_promotion_date ON t_product_promotion(start_date, end_date);
CREATE INDEX idx_promotion_status ON t_product_promotion(status);

-- ============================================================
-- 四、仓储管理模块 (4张表)
-- ============================================================

-- 16. 仓库表
CREATE TABLE IF NOT EXISTS t_warehouse (
    id SERIAL PRIMARY KEY,
    warehouse_code VARCHAR(20) NOT NULL UNIQUE,
    warehouse_name VARCHAR(100) NOT NULL,
    company_id INTEGER,
    region_id INTEGER,
    warehouse_type VARCHAR(20),
    address VARCHAR(500),
    manager_id INTEGER,
    status SMALLINT DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON TABLE t_warehouse IS '仓库表';
COMMENT ON COLUMN t_warehouse.warehouse_type IS '仓库类型: RAW-原料, SEMI-半成品, FINISHED-成品';

CREATE INDEX idx_warehouse_company ON t_warehouse(company_id);
CREATE INDEX idx_warehouse_type ON t_warehouse(warehouse_type);
CREATE INDEX idx_warehouse_status ON t_warehouse(status);

-- 17. 库存表
CREATE TABLE IF NOT EXISTS t_inventory (
    id SERIAL PRIMARY KEY,
    warehouse_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity NUMERIC(15,3) DEFAULT 0,
    available_qty NUMERIC(15,3) DEFAULT 0,
    locked_qty NUMERIC(15,3) DEFAULT 0,
    avg_cost_price NUMERIC(15,4) DEFAULT 0,
    last_update TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(warehouse_id, product_id)
);
COMMENT ON TABLE t_inventory IS '库存表';
COMMENT ON COLUMN t_inventory.available_qty IS '可用数量';
COMMENT ON COLUMN t_inventory.locked_qty IS '锁定数量';

CREATE INDEX idx_inventory_warehouse ON t_inventory(warehouse_id);
CREATE INDEX idx_inventory_product ON t_inventory(product_id);
CREATE INDEX idx_inventory_qty ON t_inventory(quantity);

-- 18. 库存流水表
CREATE TABLE IF NOT EXISTS t_inventory_transaction (
    id SERIAL PRIMARY KEY,
    trans_no VARCHAR(30) NOT NULL,
    trans_type VARCHAR(20) NOT NULL,
    ref_order_no VARCHAR(30),
    warehouse_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    direction SMALLINT NOT NULL,
    quantity NUMERIC(15,3) NOT NULL,
    before_qty NUMERIC(15,3) DEFAULT 0,
    after_qty NUMERIC(15,3) DEFAULT 0,
    unit_cost NUMERIC(15,4) DEFAULT 0,
    operator_id INTEGER,
    trans_time TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON TABLE t_inventory_transaction IS '库存流水表';
COMMENT ON COLUMN t_inventory_transaction.trans_type IS '业务类型: PURCHASE_IN-采购入库, SALES_OUT-销售出库, TRANSFER-调拨, ADJUST-盘点, LOSS-报损';
COMMENT ON COLUMN t_inventory_transaction.direction IS '方向: 1-入库, -1-出库';

CREATE INDEX idx_inv_trans_type ON t_inventory_transaction(trans_type);
CREATE INDEX idx_inv_trans_ref ON t_inventory_transaction(ref_order_no);
CREATE INDEX idx_inv_trans_warehouse ON t_inventory_transaction(warehouse_id);
CREATE INDEX idx_inv_trans_product ON t_inventory_transaction(product_id);
CREATE INDEX idx_inv_trans_time ON t_inventory_transaction(trans_time);

-- 19. 调拨单表
CREATE TABLE IF NOT EXISTS t_warehouse_transfer (
    id SERIAL PRIMARY KEY,
    transfer_no VARCHAR(30) NOT NULL UNIQUE,
    from_warehouse_id INTEGER NOT NULL,
    to_warehouse_id INTEGER NOT NULL,
    transfer_date DATE NOT NULL,
    operator_id INTEGER,
    status SMALLINT DEFAULT 0,
    total_qty NUMERIC(15,3) DEFAULT 0,
    remark TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON TABLE t_warehouse_transfer IS '调拨单表';
COMMENT ON COLUMN t_warehouse_transfer.status IS '状态: 0-草稿, 1-已审核, 2-已完成';

CREATE INDEX idx_transfer_from ON t_warehouse_transfer(from_warehouse_id);
CREATE INDEX idx_transfer_to ON t_warehouse_transfer(to_warehouse_id);
CREATE INDEX idx_transfer_date ON t_warehouse_transfer(transfer_date);
CREATE INDEX idx_transfer_status ON t_warehouse_transfer(status);

-- ============================================================
-- 五、采购管理模块 (4张表)
-- ============================================================

-- 20. 采购订单主表
CREATE TABLE IF NOT EXISTS t_purchase_order (
    id SERIAL PRIMARY KEY,
    order_no VARCHAR(30) NOT NULL UNIQUE,
    supplier_id INTEGER NOT NULL,
    warehouse_id INTEGER,
    company_id INTEGER,
    buyer_id INTEGER,
    order_date DATE NOT NULL,
    expected_date DATE,
    order_status SMALLINT DEFAULT 0,
    total_qty NUMERIC(15,3) DEFAULT 0,
    total_amount NUMERIC(15,2) DEFAULT 0,
    discount_amount NUMERIC(15,2) DEFAULT 0,
    freight_charge NUMERIC(12,2) DEFAULT 0,
    other_charge NUMERIC(12,2) DEFAULT 0,
    remark TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON TABLE t_purchase_order IS '采购订单主表';
COMMENT ON COLUMN t_purchase_order.order_status IS '订单状态: 0-草稿, 1-待审核, 2-已审核, 3-已完成, 4-已取消';

CREATE INDEX idx_po_supplier ON t_purchase_order(supplier_id);
CREATE INDEX idx_po_warehouse ON t_purchase_order(warehouse_id);
CREATE INDEX idx_po_company ON t_purchase_order(company_id);
CREATE INDEX idx_po_buyer ON t_purchase_order(buyer_id);
CREATE INDEX idx_po_status ON t_purchase_order(order_status);
CREATE INDEX idx_po_date ON t_purchase_order(order_date);

-- 21. 采购订单明细表
CREATE TABLE IF NOT EXISTS t_purchase_order_detail (
    id SERIAL PRIMARY KEY,
    order_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity NUMERIC(15,3) NOT NULL,
    unit_price NUMERIC(15,4) NOT NULL,
    amount NUMERIC(15,2) DEFAULT 0,
    tax_rate NUMERIC(5,2) DEFAULT 0,
    tax_amount NUMERIC(12,2) DEFAULT 0,
    received_qty NUMERIC(15,3) DEFAULT 0,
    remark VARCHAR(500),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON TABLE t_purchase_order_detail IS '采购订单明细表';

CREATE INDEX idx_pod_order ON t_purchase_order_detail(order_id);
CREATE INDEX idx_pod_product ON t_purchase_order_detail(product_id);

-- 22. 采购退货单主表
CREATE TABLE IF NOT EXISTS t_purchase_return (
    id SERIAL PRIMARY KEY,
    return_no VARCHAR(30) NOT NULL UNIQUE,
    purchase_order_no VARCHAR(30),
    supplier_id INTEGER NOT NULL,
    warehouse_id INTEGER,
    return_date DATE NOT NULL,
    return_status SMALLINT DEFAULT 0,
    total_qty NUMERIC(15,3) DEFAULT 0,
    total_amount NUMERIC(15,2) DEFAULT 0,
    reason VARCHAR(500),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON TABLE t_purchase_return IS '采购退货单主表';
COMMENT ON COLUMN t_purchase_return.return_status IS '状态: 0-草稿, 1-已审核, 2-已完成';

CREATE INDEX idx_pr_order ON t_purchase_return(purchase_order_no);
CREATE INDEX idx_pr_supplier ON t_purchase_return(supplier_id);
CREATE INDEX idx_pr_warehouse ON t_purchase_return(warehouse_id);
CREATE INDEX idx_pr_date ON t_purchase_return(return_date);

-- 23. 采购退货明细表
CREATE TABLE IF NOT EXISTS t_purchase_return_detail (
    id SERIAL PRIMARY KEY,
    return_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity NUMERIC(15,3) NOT NULL,
    unit_price NUMERIC(15,4) NOT NULL,
    amount NUMERIC(15,2) DEFAULT 0,
    remark VARCHAR(500),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON TABLE t_purchase_return_detail IS '采购退货明细表';

CREATE INDEX idx_prd_return ON t_purchase_return_detail(return_id);
CREATE INDEX idx_prd_product ON t_purchase_return_detail(product_id);

-- ============================================================
-- 六、销售管理模块 (4张表)
-- ============================================================

-- 24. 销售订单主表
CREATE TABLE IF NOT EXISTS t_sales_order (
    id SERIAL PRIMARY KEY,
    order_no VARCHAR(30) NOT NULL UNIQUE,
    customer_id INTEGER NOT NULL,
    warehouse_id INTEGER,
    company_id INTEGER,
    salesman_id INTEGER,
    order_date DATE NOT NULL,
    delivery_date DATE,
    order_status SMALLINT DEFAULT 0,
    total_qty NUMERIC(15,3) DEFAULT 0,
    total_amount NUMERIC(15,2) DEFAULT 0,
    discount_amount NUMERIC(15,2) DEFAULT 0,
    freight_charge NUMERIC(12,2) DEFAULT 0,
    commission_amount NUMERIC(12,2) DEFAULT 0,
    remark TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON TABLE t_sales_order IS '销售订单主表';
COMMENT ON COLUMN t_sales_order.order_status IS '订单状态: 0-草稿, 1-待审核, 2-已审核, 3-已完成, 4-已取消';

CREATE INDEX idx_so_customer ON t_sales_order(customer_id);
CREATE INDEX idx_so_warehouse ON t_sales_order(warehouse_id);
CREATE INDEX idx_so_company ON t_sales_order(company_id);
CREATE INDEX idx_so_salesman ON t_sales_order(salesman_id);
CREATE INDEX idx_so_status ON t_sales_order(order_status);
CREATE INDEX idx_so_date ON t_sales_order(order_date);

-- 25. 销售订单明细表
CREATE TABLE IF NOT EXISTS t_sales_order_detail (
    id SERIAL PRIMARY KEY,
    order_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity NUMERIC(15,3) NOT NULL,
    unit_price NUMERIC(15,4) NOT NULL,
    amount NUMERIC(15,2) DEFAULT 0,
    cost_price NUMERIC(15,4) DEFAULT 0,
    cost_amount NUMERIC(15,2) DEFAULT 0,
    gross_profit NUMERIC(15,2) DEFAULT 0,
    tax_rate NUMERIC(5,2) DEFAULT 0,
    tax_amount NUMERIC(12,2) DEFAULT 0,
    shipped_qty NUMERIC(15,3) DEFAULT 0,
    remark VARCHAR(500),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON TABLE t_sales_order_detail IS '销售订单明细表';
COMMENT ON COLUMN t_sales_order_detail.gross_profit IS '毛利 = 销售额 - 成本';

CREATE INDEX idx_sod_order ON t_sales_order_detail(order_id);
CREATE INDEX idx_sod_product ON t_sales_order_detail(product_id);

-- 26. 销售退货单主表
CREATE TABLE IF NOT EXISTS t_sales_return (
    id SERIAL PRIMARY KEY,
    return_no VARCHAR(30) NOT NULL UNIQUE,
    sales_order_no VARCHAR(30),
    customer_id INTEGER NOT NULL,
    warehouse_id INTEGER,
    return_date DATE NOT NULL,
    return_status SMALLINT DEFAULT 0,
    total_qty NUMERIC(15,3) DEFAULT 0,
    total_amount NUMERIC(15,2) DEFAULT 0,
    reason VARCHAR(500),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON TABLE t_sales_return IS '销售退货单主表';
COMMENT ON COLUMN t_sales_return.return_status IS '状态: 0-草稿, 1-已审核, 2-已完成';

CREATE INDEX idx_sr_order ON t_sales_return(sales_order_no);
CREATE INDEX idx_sr_customer ON t_sales_return(customer_id);
CREATE INDEX idx_sr_warehouse ON t_sales_return(warehouse_id);
CREATE INDEX idx_sr_date ON t_sales_return(return_date);

-- 27. 销售退货明细表
CREATE TABLE IF NOT EXISTS t_sales_return_detail (
    id SERIAL PRIMARY KEY,
    return_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity NUMERIC(15,3) NOT NULL,
    unit_price NUMERIC(15,4) NOT NULL,
    amount NUMERIC(15,2) DEFAULT 0,
    remark VARCHAR(500),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON TABLE t_sales_return_detail IS '销售退货明细表';

CREATE INDEX idx_srd_return ON t_sales_return_detail(return_id);
CREATE INDEX idx_srd_product ON t_sales_return_detail(product_id);

-- ============================================================
-- 七、财务管理模块 (6张表)
-- ============================================================

-- 28. 应付账款表
CREATE TABLE IF NOT EXISTS t_accounts_payable (
    id SERIAL PRIMARY KEY,
    payable_no VARCHAR(30) NOT NULL UNIQUE,
    supplier_id INTEGER NOT NULL,
    source_order_no VARCHAR(30),
    payable_amount NUMERIC(15,2) NOT NULL,
    paid_amount NUMERIC(15,2) DEFAULT 0,
    unpaid_amount NUMERIC(15,2) NOT NULL,
    due_date DATE,
    overdue_days INTEGER DEFAULT 0,
    status SMALLINT DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON TABLE t_accounts_payable IS '应付账款表';
COMMENT ON COLUMN t_accounts_payable.status IS '状态: 0-未付, 1-部分付款, 2-已付清';

CREATE INDEX idx_ap_supplier ON t_accounts_payable(supplier_id);
CREATE INDEX idx_ap_source ON t_accounts_payable(source_order_no);
CREATE INDEX idx_ap_due ON t_accounts_payable(due_date);
CREATE INDEX idx_ap_status ON t_accounts_payable(status);

-- 29. 应收账款表
CREATE TABLE IF NOT EXISTS t_accounts_receivable (
    id SERIAL PRIMARY KEY,
    receivable_no VARCHAR(30) NOT NULL UNIQUE,
    customer_id INTEGER NOT NULL,
    source_order_no VARCHAR(30),
    receivable_amount NUMERIC(15,2) NOT NULL,
    received_amount NUMERIC(15,2) DEFAULT 0,
    unreceived_amount NUMERIC(15,2) NOT NULL,
    due_date DATE,
    overdue_days INTEGER DEFAULT 0,
    status SMALLINT DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON TABLE t_accounts_receivable IS '应收账款表';
COMMENT ON COLUMN t_accounts_receivable.status IS '状态: 0-未收, 1-部分收款, 2-已收清';

CREATE INDEX idx_ar_customer ON t_accounts_receivable(customer_id);
CREATE INDEX idx_ar_source ON t_accounts_receivable(source_order_no);
CREATE INDEX idx_ar_due ON t_accounts_receivable(due_date);
CREATE INDEX idx_ar_status ON t_accounts_receivable(status);

-- 30. 付款记录表
CREATE TABLE IF NOT EXISTS t_payment_record (
    id SERIAL PRIMARY KEY,
    payment_no VARCHAR(30) NOT NULL UNIQUE,
    supplier_id INTEGER NOT NULL,
    payment_amount NUMERIC(15,2) NOT NULL,
    payment_method VARCHAR(20) NOT NULL,
    payment_date DATE NOT NULL,
    handler_id INTEGER,
    bank_account VARCHAR(100),
    remark TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON TABLE t_payment_record IS '付款记录表';
COMMENT ON COLUMN t_payment_record.payment_method IS '付款方式: CASH-现金, BANK-银行转账, DRAFT-承兑汇票, CHECK-支票';

CREATE INDEX idx_payment_supplier ON t_payment_record(supplier_id);
CREATE INDEX idx_payment_date ON t_payment_record(payment_date);
CREATE INDEX idx_payment_method ON t_payment_record(payment_method);

-- 31. 收款记录表
CREATE TABLE IF NOT EXISTS t_receipt_record (
    id SERIAL PRIMARY KEY,
    receipt_no VARCHAR(30) NOT NULL UNIQUE,
    customer_id INTEGER NOT NULL,
    receipt_amount NUMERIC(15,2) NOT NULL,
    payment_method VARCHAR(20) NOT NULL,
    receipt_date DATE NOT NULL,
    handler_id INTEGER,
    bank_account VARCHAR(100),
    remark TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON TABLE t_receipt_record IS '收款记录表';
COMMENT ON COLUMN t_receipt_record.payment_method IS '收款方式: CASH-现金, BANK-银行转账, DRAFT-承兑汇票, CHECK-支票';

CREATE INDEX idx_receipt_customer ON t_receipt_record(customer_id);
CREATE INDEX idx_receipt_date ON t_receipt_record(receipt_date);
CREATE INDEX idx_receipt_method ON t_receipt_record(payment_method);

-- 32. 费用记录表
CREATE TABLE IF NOT EXISTS t_expense_record (
    id SERIAL PRIMARY KEY,
    expense_no VARCHAR(30) NOT NULL UNIQUE,
    expense_type VARCHAR(20) NOT NULL,
    dept_id INTEGER,
    company_id INTEGER,
    amount NUMERIC(12,2) NOT NULL,
    expense_date DATE NOT NULL,
    handler_id INTEGER,
    remark TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON TABLE t_expense_record IS '费用记录表';
COMMENT ON COLUMN t_expense_record.expense_type IS '费用类型: FREIGHT-运费, COMMISSION-业务提成, ADMIN-管理费用, OTHER-其他';

CREATE INDEX idx_expense_type ON t_expense_record(expense_type);
CREATE INDEX idx_expense_dept ON t_expense_record(dept_id);
CREATE INDEX idx_expense_company ON t_expense_record(company_id);
CREATE INDEX idx_expense_date ON t_expense_record(expense_date);

-- 33. 提成记录表
CREATE TABLE IF NOT EXISTS t_commission_record (
    id SERIAL PRIMARY KEY,
    commission_no VARCHAR(30) NOT NULL UNIQUE,
    salesman_id INTEGER NOT NULL,
    sales_order_no VARCHAR(30),
    sales_amount NUMERIC(15,2) NOT NULL,
    gross_profit NUMERIC(15,2) DEFAULT 0,
    commission_rate NUMERIC(5,2) NOT NULL,
    commission_amount NUMERIC(12,2) NOT NULL,
    settle_month VARCHAR(7),
    status SMALLINT DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON TABLE t_commission_record IS '提成记录表';
COMMENT ON COLUMN t_commission_record.settle_month IS '结算月份 (格式: YYYY-MM)';
COMMENT ON COLUMN t_commission_record.status IS '状态: 0-未结算, 1-已结算';

CREATE INDEX idx_commission_salesman ON t_commission_record(salesman_id);
CREATE INDEX idx_commission_order ON t_commission_record(sales_order_no);
CREATE INDEX idx_commission_month ON t_commission_record(settle_month);
CREATE INDEX idx_commission_status ON t_commission_record(status);

-- ============================================================
-- 初始化完成
-- ============================================================

DO $$
BEGIN
    RAISE NOTICE '=================================================';
    RAISE NOTICE '进销存业务数据库初始化完成!';
    RAISE NOTICE '数据库名: erp_business';
    RAISE NOTICE '表数量: 33张';
    RAISE NOTICE '=================================================';
END $$;
