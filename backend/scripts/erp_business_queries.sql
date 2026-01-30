-- ============================================================
-- 进销存业务系统 - 多维度分析查询示例
-- 数据库: erp_business
-- 这些查询展示了如何从不同维度分析业务数据
-- ============================================================

-- ============================================================
-- 1. 按分公司统计销售额、成本、毛利
-- ============================================================

SELECT 
    c.company_name AS "分公司",
    COUNT(DISTINCT so.id) AS "订单数",
    SUM(so.total_qty) AS "销售数量",
    ROUND(SUM(so.total_amount)::numeric, 2) AS "销售额",
    ROUND(SUM(sod.cost_amount)::numeric, 2) AS "销售成本",
    ROUND(SUM(sod.gross_profit)::numeric, 2) AS "毛利",
    ROUND((SUM(sod.gross_profit) / NULLIF(SUM(so.total_amount), 0) * 100)::numeric, 2) AS "毛利率(%)"
FROM t_sales_order so
JOIN t_sales_order_detail sod ON so.id = sod.order_id
JOIN t_company c ON so.company_id = c.id
WHERE so.order_status IN (2, 3)  -- 已审核或已完成
GROUP BY c.id, c.company_name
ORDER BY SUM(so.total_amount) DESC;

-- ============================================================
-- 2. 按业务员统计业绩与提成
-- ============================================================

SELECT 
    e.emp_code AS "员工编号",
    e.emp_name AS "业务员",
    d.dept_name AS "部门",
    COUNT(DISTINCT so.id) AS "订单数",
    ROUND(SUM(so.total_amount)::numeric, 2) AS "销售额",
    ROUND(SUM(sod.cost_amount)::numeric, 2) AS "销售成本",
    ROUND(SUM(sod.gross_profit)::numeric, 2) AS "毛利",
    ROUND(SUM(so.commission_amount)::numeric, 2) AS "提成金额",
    ROUND((SUM(sod.gross_profit) / NULLIF(SUM(so.total_amount), 0) * 100)::numeric, 2) AS "毛利率(%)"
FROM t_sales_order so
JOIN t_sales_order_detail sod ON so.id = sod.order_id
JOIN t_employee e ON so.salesman_id = e.id
JOIN t_department d ON e.dept_id = d.id
WHERE so.order_status = 3  -- 已完成
GROUP BY e.id, e.emp_code, e.emp_name, d.dept_name
ORDER BY SUM(so.total_amount) DESC
LIMIT 20;

-- ============================================================
-- 3. 按仓库统计出入库与库存周转
-- ============================================================

WITH inventory_in AS (
    SELECT 
        warehouse_id,
        SUM(CASE WHEN direction = 1 THEN quantity ELSE 0 END) AS total_in
    FROM t_inventory_transaction
    WHERE trans_time >= CURRENT_DATE - INTERVAL '90 days'
    GROUP BY warehouse_id
),
inventory_out AS (
    SELECT 
        warehouse_id,
        SUM(CASE WHEN direction = -1 THEN quantity ELSE 0 END) AS total_out
    FROM t_inventory_transaction
    WHERE trans_time >= CURRENT_DATE - INTERVAL '90 days'
    GROUP BY warehouse_id
),
current_inventory AS (
    SELECT 
        warehouse_id,
        SUM(quantity) AS current_qty,
        SUM(quantity * avg_cost_price) AS current_value
    FROM t_inventory
    GROUP BY warehouse_id
)
SELECT 
    w.warehouse_name AS "仓库",
    w.warehouse_type AS "类型",
    ROUND(COALESCE(ii.total_in, 0)::numeric, 2) AS "90天入库数量",
    ROUND(COALESCE(io.total_out, 0)::numeric, 2) AS "90天出库数量",
    ROUND(COALESCE(ci.current_qty, 0)::numeric, 2) AS "当前库存数量",
    ROUND(COALESCE(ci.current_value, 0)::numeric, 2) AS "库存金额",
    CASE 
        WHEN ci.current_qty > 0 THEN ROUND((io.total_out / ci.current_qty)::numeric, 2)
        ELSE 0
    END AS "库存周转次数"
FROM t_warehouse w
LEFT JOIN inventory_in ii ON w.id = ii.warehouse_id
LEFT JOIN inventory_out io ON w.id = io.warehouse_id
LEFT JOIN current_inventory ci ON w.id = ci.warehouse_id
ORDER BY w.warehouse_name;

-- ============================================================
-- 4. 按客户统计销售额与往来余额
-- ============================================================

SELECT 
    c.customer_code AS "客户编号",
    c.customer_name AS "客户名称",
    cc.category_name AS "客户分类",
    c.credit_rating AS "信用等级",
    COUNT(DISTINCT so.id) AS "订单数",
    ROUND(SUM(so.total_amount)::numeric, 2) AS "累计销售额",
    ROUND(ca.receivable_balance::numeric, 2) AS "应收余额",
    c.credit_limit AS "信用额度",
    CASE 
        WHEN c.credit_limit > 0 THEN ROUND((ca.receivable_balance / c.credit_limit * 100)::numeric, 2)
        ELSE 0
    END AS "信用额度使用率(%)",
    ca.last_trans_date AS "最后交易日期"
FROM t_customer c
LEFT JOIN t_customer_category cc ON c.category_id = cc.id
LEFT JOIN t_sales_order so ON c.id = so.customer_id AND so.order_status = 3
LEFT JOIN t_customer_account ca ON c.id = ca.customer_id
GROUP BY c.id, c.customer_code, c.customer_name, cc.category_name, 
         c.credit_rating, c.credit_limit, ca.receivable_balance, ca.last_trans_date
ORDER BY SUM(so.total_amount) DESC NULLS LAST
LIMIT 50;

-- ============================================================
-- 5. 按地区统计销售分布
-- ============================================================

SELECT 
    r.province AS "省份",
    r.city AS "城市",
    COUNT(DISTINCT c.id) AS "客户数",
    COUNT(DISTINCT so.id) AS "订单数",
    ROUND(SUM(so.total_amount)::numeric, 2) AS "销售额",
    ROUND(AVG(so.total_amount)::numeric, 2) AS "平均订单金额",
    ROUND(SUM(sod.gross_profit)::numeric, 2) AS "毛利"
FROM t_region r
JOIN t_customer c ON r.id = c.region_id
LEFT JOIN t_sales_order so ON c.id = so.customer_id AND so.order_status = 3
LEFT JOIN t_sales_order_detail sod ON so.id = sod.order_id
WHERE r.level = 2  -- 市级
GROUP BY r.province, r.city
HAVING COUNT(DISTINCT so.id) > 0
ORDER BY SUM(so.total_amount) DESC NULLS LAST
LIMIT 30;

-- ============================================================
-- 6. 按商品统计销量与库存预警
-- ============================================================

WITH product_sales AS (
    SELECT 
        sod.product_id,
        SUM(sod.quantity) AS total_sold,
        SUM(sod.amount) AS total_sales_amount,
        COUNT(DISTINCT sod.order_id) AS order_count
    FROM t_sales_order_detail sod
    JOIN t_sales_order so ON sod.order_id = so.id
    WHERE so.order_status = 3
        AND so.order_date >= CURRENT_DATE - INTERVAL '90 days'
    GROUP BY sod.product_id
),
product_inventory AS (
    SELECT 
        product_id,
        SUM(quantity) AS total_qty,
        SUM(available_qty) AS available_qty
    FROM t_inventory
    GROUP BY product_id
)
SELECT 
    p.product_code AS "商品编码",
    p.product_name AS "商品名称",
    pc.category_name AS "分类",
    b.brand_name AS "品牌",
    ROUND(COALESCE(ps.total_sold, 0)::numeric, 2) AS "90天销量",
    ROUND(COALESCE(ps.total_sales_amount, 0)::numeric, 2) AS "90天销售额",
    ROUND(COALESCE(pi.total_qty, 0)::numeric, 2) AS "库存数量",
    ROUND(COALESCE(pi.available_qty, 0)::numeric, 2) AS "可用数量",
    p.min_stock AS "最低库存",
    CASE 
        WHEN pi.total_qty IS NULL THEN '无库存'
        WHEN pi.total_qty < p.min_stock THEN '库存不足'
        WHEN pi.total_qty < p.min_stock * 1.5 THEN '库存预警'
        ELSE '库存正常'
    END AS "库存状态"
FROM t_product p
LEFT JOIN t_product_category pc ON p.category_id = pc.id
LEFT JOIN t_brand b ON p.brand_id = b.id
LEFT JOIN product_sales ps ON p.id = ps.product_id
LEFT JOIN product_inventory pi ON p.id = pi.product_id
WHERE p.status = 1
ORDER BY ps.total_sold DESC NULLS LAST
LIMIT 50;

-- ============================================================
-- 7. 按部门统计费用开支
-- ============================================================

SELECT 
    d.dept_name AS "部门",
    er.expense_type AS "费用类型",
    COUNT(*) AS "费用笔数",
    ROUND(SUM(er.amount)::numeric, 2) AS "费用总额",
    ROUND(AVG(er.amount)::numeric, 2) AS "平均金额",
    ROUND(MIN(er.amount)::numeric, 2) AS "最小金额",
    ROUND(MAX(er.amount)::numeric, 2) AS "最大金额"
FROM t_expense_record er
LEFT JOIN t_department d ON er.dept_id = d.id
GROUP BY d.dept_name, er.expense_type
ORDER BY SUM(er.amount) DESC;

-- ============================================================
-- 8. 综合利润表 (按月统计)
-- ============================================================

WITH monthly_sales AS (
    SELECT 
        TO_CHAR(so.order_date, 'YYYY-MM') AS month,
        SUM(so.total_amount) AS sales_amount,
        SUM(sod.cost_amount) AS cost_amount,
        SUM(sod.gross_profit) AS gross_profit,
        SUM(so.freight_charge) AS freight_charge,
        SUM(so.commission_amount) AS commission_amount
    FROM t_sales_order so
    JOIN t_sales_order_detail sod ON so.id = sod.order_id
    WHERE so.order_status = 3
    GROUP BY TO_CHAR(so.order_date, 'YYYY-MM')
),
monthly_expenses AS (
    SELECT 
        TO_CHAR(expense_date, 'YYYY-MM') AS month,
        SUM(CASE WHEN expense_type = 'FREIGHT' THEN amount ELSE 0 END) AS freight_expense,
        SUM(CASE WHEN expense_type = 'COMMISSION' THEN amount ELSE 0 END) AS commission_expense,
        SUM(CASE WHEN expense_type = 'ADMIN' THEN amount ELSE 0 END) AS admin_expense,
        SUM(CASE WHEN expense_type = 'OTHER' THEN amount ELSE 0 END) AS other_expense
    FROM t_expense_record
    GROUP BY TO_CHAR(expense_date, 'YYYY-MM')
)
SELECT 
    ms.month AS "月份",
    ROUND(ms.sales_amount::numeric, 2) AS "销售额",
    ROUND(ms.cost_amount::numeric, 2) AS "销售成本",
    ROUND(ms.gross_profit::numeric, 2) AS "毛利",
    ROUND((ms.gross_profit / NULLIF(ms.sales_amount, 0) * 100)::numeric, 2) AS "毛利率(%)",
    ROUND(COALESCE(me.freight_expense, 0)::numeric, 2) AS "运费",
    ROUND(COALESCE(me.commission_expense, 0)::numeric, 2) AS "业务提成",
    ROUND(COALESCE(me.admin_expense, 0)::numeric, 2) AS "管理费用",
    ROUND(COALESCE(me.other_expense, 0)::numeric, 2) AS "其他费用",
    ROUND((ms.gross_profit - COALESCE(me.freight_expense, 0) - COALESCE(me.commission_expense, 0) 
           - COALESCE(me.admin_expense, 0) - COALESCE(me.other_expense, 0))::numeric, 2) AS "净利润"
FROM monthly_sales ms
LEFT JOIN monthly_expenses me ON ms.month = me.month
ORDER BY ms.month DESC
LIMIT 24;

-- ============================================================
-- 9. 应收账款账龄分析
-- ============================================================

SELECT 
    CASE 
        WHEN ar.overdue_days <= 0 THEN '未逾期'
        WHEN ar.overdue_days <= 30 THEN '1-30天'
        WHEN ar.overdue_days <= 60 THEN '31-60天'
        WHEN ar.overdue_days <= 90 THEN '61-90天'
        WHEN ar.overdue_days <= 180 THEN '91-180天'
        ELSE '180天以上'
    END AS "账龄",
    COUNT(*) AS "笔数",
    ROUND(SUM(ar.unreceived_amount)::numeric, 2) AS "金额",
    ROUND((SUM(ar.unreceived_amount) / NULLIF((SELECT SUM(unreceived_amount) FROM t_accounts_receivable WHERE status IN (0, 1)), 0) * 100)::numeric, 2) AS "占比(%)"
FROM t_accounts_receivable ar
WHERE ar.status IN (0, 1)  -- 未收或部分收款
GROUP BY 
    CASE 
        WHEN ar.overdue_days <= 0 THEN '未逾期'
        WHEN ar.overdue_days <= 30 THEN '1-30天'
        WHEN ar.overdue_days <= 60 THEN '31-60天'
        WHEN ar.overdue_days <= 90 THEN '61-90天'
        WHEN ar.overdue_days <= 180 THEN '91-180天'
        ELSE '180天以上'
    END
ORDER BY 
    CASE 
        WHEN ar.overdue_days <= 0 THEN 1
        WHEN ar.overdue_days <= 30 THEN 2
        WHEN ar.overdue_days <= 60 THEN 3
        WHEN ar.overdue_days <= 90 THEN 4
        WHEN ar.overdue_days <= 180 THEN 5
        ELSE 6
    END;

-- ============================================================
-- 10. 供应商采购分析
-- ============================================================

SELECT 
    s.supplier_code AS "供应商编号",
    s.supplier_name AS "供应商名称",
    s.credit_rating AS "信用等级",
    COUNT(DISTINCT po.id) AS "采购订单数",
    ROUND(SUM(po.total_amount)::numeric, 2) AS "采购总额",
    ROUND(AVG(po.total_amount)::numeric, 2) AS "平均订单金额",
    ROUND(sa.payable_balance::numeric, 2) AS "应付余额",
    s.payment_terms AS "账期(天)",
    sa.last_trans_date AS "最后交易日期"
FROM t_supplier s
LEFT JOIN t_purchase_order po ON s.id = po.supplier_id AND po.order_status = 3
LEFT JOIN t_supplier_account sa ON s.id = sa.supplier_id
GROUP BY s.id, s.supplier_code, s.supplier_name, s.credit_rating, 
         s.payment_terms, sa.payable_balance, sa.last_trans_date
ORDER BY SUM(po.total_amount) DESC NULLS LAST
LIMIT 30;

-- ============================================================
-- 提示: 这些查询可以根据实际需求进行调整和扩展
-- 建议创建视图或物化视图来提升查询性能
-- ============================================================
