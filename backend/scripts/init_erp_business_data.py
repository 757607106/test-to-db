#!/usr/bin/env python3
"""
进销存业务系统 Mock 数据生成脚本 (PostgreSQL版本)

功能:
1. 生成完整的主数据(组织架构、往来单位、商品)
2. 生成近2年(2024-01至2026-01)的业务单据(采购、销售、退货、调拨)
3. 模拟真实业务场景(季节性波动、促销活动、客户分级)
4. 生成财务数据(应收应付、收付款、费用、提成)
5. 保证数据一致性(库存、往来账)

数据规模:
- 业务单据: 2-3万笔
- 总记录数: 7-11万条

使用方法:
    python init_erp_business_data.py
"""

import psycopg2
import random
from datetime import datetime, timedelta, date
from decimal import Decimal
import os
import sys
from pathlib import Path

# ============================================================
# 数据库配置
# ============================================================

# 连接postgres-checkpointer容器
DB_CONFIG = {
    'host': os.getenv('POSTGRES_HOST', 'localhost'),
    'port': int(os.getenv('POSTGRES_PORT', 5433)),
    'database': 'erp_business',
    'user': os.getenv('POSTGRES_USER', 'langgraph'),
    'password': os.getenv('POSTGRES_PASSWORD', 'langgraph_password_2026')
}

# 时间范围
START_DATE = date(2024, 1, 1)
END_DATE = date(2026, 1, 30)

# ============================================================
# 常量数据定义
# ============================================================

# 分公司数据
COMPANIES = [
    ('C001', '广州分公司', '广东省', '广州市', '天河区', '天河路123号'),
    ('C002', '深圳分公司', '广东省', '深圳市', '南山区', '科技园南路88号'),
    ('C003', '上海分公司', '上海市', '上海市', '浦东新区', '张江高科技园区'),
    ('C004', '北京分公司', '北京市', '北京市', '朝阳区', '望京SOHO'),
    ('C005', '成都分公司', '四川省', '成都市', '高新区', '天府大道中段'),
    ('C006', '杭州分公司', '浙江省', '杭州市', '滨江区', '滨江科技园'),
    ('C007', '武汉分公司', '湖北省', '武汉市', '洪山区', '光谷软件园'),
]

# 部门数据 (dept_code, dept_name, parent_code, sort_order)
DEPARTMENTS = [
    ('D001', '总经办', None, 1),
    ('D002', '财务部', None, 2),
    ('D003', '人事部', None, 3),
    ('D004', '采购部', None, 4),
    ('D005', '销售部', None, 5),
    ('D006', '仓储部', None, 6),
    ('D007', '技术部', None, 7),
    ('D008', '市场部', None, 8),
    ('D009', '销售一部', 'D005', 1),
    ('D010', '销售二部', 'D005', 2),
    ('D011', '销售三部', 'D005', 3),
]

# 员工数据 (emp_code, emp_name, position, base_salary, commission_rate)
EMPLOYEES = [
    ('E001', '张海洋', '总经理', 50000, 0),
    ('E002', '李明达', '财务经理', 30000, 0),
    ('E003', '王芳', '会计', 12000, 0),
    ('E004', '赵强', '采购经理', 25000, 0),
    ('E005', '刘洋', '采购专员', 10000, 0),
    ('E006', '钱伟', '采购专员', 10000, 0),
    ('E007', '周杰', '销售总监', 35000, 5),
    ('E008', '吴敏', '销售经理', 20000, 8),
    ('E009', '郑伟', '销售代表', 8000, 12),
    ('E010', '陈静', '销售代表', 8000, 12),
    ('E011', '孙强', '销售代表', 8000, 12),
    ('E012', '李娜', '销售代表', 8000, 12),
    ('E013', '马立成', '仓库经理', 18000, 0),
    ('E014', '朱建国', '仓管员', 8000, 0),
    ('E015', '徐鹏', '仓管员', 8000, 0),
]

# 供应商分类
SUPPLIER_CATEGORIES = [
    ('SC01', '电子元器件供应商', None),
    ('SC02', '机械零件供应商', None),
    ('SC03', '原材料供应商', None),
    ('SC04', '化工产品供应商', None),
    ('SC05', '包装材料供应商', None),
]

# 客户分类
CUSTOMER_CATEGORIES = [
    ('CC01', 'A类客户', None, 95.0),   # 95折
    ('CC02', 'B类客户', None, 97.0),   # 97折
    ('CC03', 'C类客户', None, 100.0),  # 原价
]

# 商品分类 (三级分类)
PRODUCT_CATEGORIES = [
    ('PC01', '电子元器件', None, 1),
    ('PC0101', '电阻', 'PC01', 2),
    ('PC0102', '电容', 'PC01', 2),
    ('PC0103', '芯片', 'PC01', 2),
    ('PC0104', '连接器', 'PC01', 2),
    ('PC02', '机械零件', None, 1),
    ('PC0201', '轴承', 'PC02', 2),
    ('PC0202', '齿轮', 'PC02', 2),
    ('PC0203', '紧固件', 'PC02', 2),
    ('PC03', '原材料', None, 1),
    ('PC0301', '金属材料', 'PC03', 2),
    ('PC0302', '塑料制品', 'PC03', 2),
    ('PC04', '工具设备', None, 1),
    ('PC0401', '电动工具', 'PC04', 2),
    ('PC0402', '测量仪器', 'PC04', 2),
]

# 品牌
BRANDS = [
    ('B001', 'TI德州仪器', '全球领先的半导体公司'),
    ('B002', 'NXP恩智浦', '汽车电子芯片领导者'),
    ('B003', 'ST意法半导体', '欧洲最大的半导体公司'),
    ('B004', 'SKF', '全球轴承制造商'),
    ('B005', 'NSK', '日本精密轴承品牌'),
    ('B006', '博世BOSCH', '德国工业巨头'),
    ('B007', '西门子Siemens', '德国电气工程公司'),
    ('B008', '3M', '美国多元化科技企业'),
]

# 省市地区数据
REGIONS = [
    ('R01', '广东省', '广东省', None, None, 1, None),
    ('R0101', '广州市', '广东省', '广州市', None, 2, 'R01'),
    ('R010101', '天河区', '广东省', '广州市', '天河区', 3, 'R0101'),
    ('R010102', '海珠区', '广东省', '广州市', '海珠区', 3, 'R0101'),
    ('R0102', '深圳市', '广东省', '深圳市', None, 2, 'R01'),
    ('R010201', '南山区', '广东省', '深圳市', '南山区', 3, 'R0102'),
    ('R010202', '福田区', '广东省', '深圳市', '福田区', 3, 'R0102'),
    ('R02', '上海市', '上海市', '上海市', None, 1, None),
    ('R0201', '浦东新区', '上海市', '上海市', '浦东新区', 3, 'R02'),
    ('R0202', '黄浦区', '上海市', '上海市', '黄浦区', 3, 'R02'),
    ('R03', '北京市', '北京市', '北京市', None, 1, None),
    ('R0301', '朝阳区', '北京市', '北京市', '朝阳区', 3, 'R03'),
    ('R0302', '海淀区', '北京市', '北京市', '海淀区', 3, 'R03'),
    ('R04', '浙江省', '浙江省', None, None, 1, None),
    ('R0401', '杭州市', '浙江省', '杭州市', None, 2, 'R04'),
    ('R040101', '滨江区', '浙江省', '杭州市', '滨江区', 3, 'R0401'),
]

# 仓库类型
WAREHOUSE_TYPES = ['RAW', 'SEMI', 'FINISHED']

# 付款方式
PAYMENT_METHODS = ['CASH', 'BANK', 'DRAFT', 'CHECK']

# 费用类型
EXPENSE_TYPES = ['FREIGHT', 'COMMISSION', 'ADMIN', 'OTHER']


# ============================================================
# 工具函数
# ============================================================

def random_date(start_date, end_date, weight_weekday=2.0):
    """
    生成随机日期,工作日权重更高
    """
    days = (end_date - start_date).days
    random_days = random.randint(0, days)
    result_date = start_date + timedelta(days=random_days)
    
    # 周末降低概率
    if result_date.weekday() >= 5 and random.random() > (1.0 / weight_weekday):
        return random_date(start_date, end_date, weight_weekday)
    
    return result_date


def is_business_peak(dt):
    """
    判断是否业务高峰期
    - 月初(1-5日)
    - 月末(26-31日)
    - 季度末
    - 双11、618等促销季
    """
    day = dt.day
    month = dt.month
    
    # 月初月末
    if day <= 5 or day >= 26:
        return True
    
    # 季度末
    if month in [3, 6, 9, 12] and day >= 20:
        return True
    
    # 促销季
    if (month == 6 and 15 <= day <= 20) or (month == 11 and 10 <= day <= 12):
        return True
    
    return False


def get_seasonal_factor(dt):
    """
    获取季节性系数
    春节前后、618、双11会有销售高峰
    """
    month = dt.month
    day = dt.day
    
    # 春节前(1-2月)
    if month in [1, 2]:
        return random.uniform(1.3, 1.6)
    
    # 618大促(6月)
    if month == 6 and 10 <= day <= 25:
        return random.uniform(1.4, 1.8)
    
    # 双11大促(11月)
    if month == 11 and 5 <= day <= 15:
        return random.uniform(1.5, 2.0)
    
    # 年底冲刺(12月)
    if month == 12:
        return random.uniform(1.2, 1.5)
    
    # 淡季(7-8月)
    if month in [7, 8]:
        return random.uniform(0.7, 0.9)
    
    return 1.0


# ============================================================
# 数据库操作类
# ============================================================

class ERPDataGenerator:
    def __init__(self):
        self.conn = None
        self.cursor = None
        
        # ID映射字典
        self.company_ids = {}
        self.dept_ids = {}
        self.employee_ids = {}
        self.region_ids = {}
        self.supplier_ids = {}
        self.supplier_cat_ids = {}
        self.customer_ids = {}
        self.customer_cat_ids = {}
        self.product_ids = {}
        self.product_cat_ids = {}
        self.brand_ids = {}
        self.warehouse_ids = {}
        
        # 统计数据
        self.stats = {}
    
    def connect(self):
        """连接数据库"""
        try:
            print(f"正在连接PostgreSQL数据库...")
            print(f"  主机: {DB_CONFIG['host']}:{DB_CONFIG['port']}")
            print(f"  数据库: {DB_CONFIG['database']}")
            
            self.conn = psycopg2.connect(**DB_CONFIG)
            self.cursor = self.conn.cursor()
            print("✅ 数据库连接成功\n")
        except Exception as e:
            print(f"❌ 数据库连接失败: {e}")
            sys.exit(1)
    
    def close(self):
        """关闭数据库连接"""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
    
    def execute_query(self, query, params=None):
        """执行查询"""
        try:
            self.cursor.execute(query, params)
            return self.cursor.fetchone()
        except Exception as e:
            print(f"查询执行错误: {e}")
            print(f"SQL: {query}")
            return None
    
    def execute_insert(self, query, params):
        """执行插入并返回ID"""
        try:
            self.cursor.execute(query, params)
            return self.cursor.fetchone()[0]
        except Exception as e:
            print(f"插入执行错误: {e}")
            print(f"SQL: {query}")
            print(f"Params: {params}")
            self.conn.rollback()
            return None
    
    # ============================================================
    # 1. 组织架构数据生成
    # ============================================================
    
    def generate_companies(self):
        """生成分公司数据"""
        print("=" * 60)
        print("1. 生成分公司数据")
        print("-" * 60)
        
        for comp in COMPANIES:
            code, name, province, city, district, address = comp
            query = """
                INSERT INTO t_company (company_code, company_name, province, city, district, address)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
            """
            company_id = self.execute_insert(query, (code, name, province, city, district, address))
            self.company_ids[code] = company_id
        
        self.conn.commit()
        print(f"✅ 插入分公司: {len(COMPANIES)} 家\n")
    
    def generate_departments(self):
        """生成部门数据"""
        print("2. 生成部门数据")
        print("-" * 60)
        
        # 先插入顶级部门
        for dept in DEPARTMENTS:
            code, name, parent_code, sort_order = dept
            if parent_code is None:
                company_id = random.choice(list(self.company_ids.values()))
                query = """
                    INSERT INTO t_department (dept_code, dept_name, company_id, sort_order)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id
                """
                dept_id = self.execute_insert(query, (code, name, company_id, sort_order))
                self.dept_ids[code] = dept_id
        
        # 再插入子部门
        for dept in DEPARTMENTS:
            code, name, parent_code, sort_order = dept
            if parent_code is not None:
                parent_id = self.dept_ids.get(parent_code)
                company_id = random.choice(list(self.company_ids.values()))
                query = """
                    INSERT INTO t_department (dept_code, dept_name, company_id, parent_id, sort_order)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id
                """
                dept_id = self.execute_insert(query, (code, name, company_id, parent_id, sort_order))
                self.dept_ids[code] = dept_id
        
        self.conn.commit()
        print(f"✅ 插入部门: {len(DEPARTMENTS)} 个\n")
    
    def generate_employees(self):
        """生成员工数据"""
        print("3. 生成员工数据")
        print("-" * 60)
        
        dept_list = list(self.dept_ids.values())
        company_list = list(self.company_ids.values())
        
        for emp in EMPLOYEES:
            code, name, position, salary, comm_rate = emp
            dept_id = random.choice(dept_list)
            company_id = random.choice(company_list)
            hire_date = random_date(date(2020, 1, 1), date(2023, 12, 31))
            
            query = """
                INSERT INTO t_employee (emp_code, emp_name, dept_id, company_id, position, 
                    hire_date, base_salary, commission_rate)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """
            emp_id = self.execute_insert(query, (code, name, dept_id, company_id, position, 
                                                  hire_date, salary, comm_rate))
            self.employee_ids[code] = emp_id
        
        self.conn.commit()
        print(f"✅ 插入员工: {len(EMPLOYEES)} 人\n")
    
    def generate_regions(self):
        """生成地区数据"""
        print("4. 生成地区数据")
        print("-" * 60)
        
        # 先插入省级
        for region in REGIONS:
            code, name, province, city, district, level, parent_code = region
            if level == 1:
                query = """
                    INSERT INTO t_region (region_code, region_name, province, city, district, level, sort_order)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """
                region_id = self.execute_insert(query, (code, name, province, city, district, level, 0))
                self.region_ids[code] = region_id
        
        # 再插入市级
        for region in REGIONS:
            code, name, province, city, district, level, parent_code = region
            if level == 2:
                parent_id = self.region_ids.get(parent_code)
                query = """
                    INSERT INTO t_region (region_code, region_name, province, city, district, level, parent_id, sort_order)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """
                region_id = self.execute_insert(query, (code, name, province, city, district, level, parent_id, 0))
                self.region_ids[code] = region_id
        
        # 最后插入区级
        for region in REGIONS:
            code, name, province, city, district, level, parent_code = region
            if level == 3:
                parent_id = self.region_ids.get(parent_code)
                query = """
                    INSERT INTO t_region (region_code, region_name, province, city, district, level, parent_id, sort_order)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """
                region_id = self.execute_insert(query, (code, name, province, city, district, level, parent_id, 0))
                self.region_ids[code] = region_id
        
        self.conn.commit()
        print(f"✅ 插入地区: {len(REGIONS)} 个\n")
    
    # ============================================================
    # 2. 往来单位数据生成
    # ============================================================
    
    def generate_supplier_categories(self):
        """生成供应商分类"""
        print("=" * 60)
        print("5. 生成供应商分类")
        print("-" * 60)
        
        for cat in SUPPLIER_CATEGORIES:
            code, name, parent_code = cat
            query = """
                INSERT INTO t_supplier_category (category_code, category_name, sort_order)
                VALUES (%s, %s, %s)
                RETURNING id
            """
            cat_id = self.execute_insert(query, (code, name, 0))
            self.supplier_cat_ids[code] = cat_id
        
        self.conn.commit()
        print(f"✅ 插入供应商分类: {len(SUPPLIER_CATEGORIES)} 个\n")
    
    def generate_suppliers(self):
        """生成供应商数据"""
        print("6. 生成供应商数据")
        print("-" * 60)
        
        supplier_names = [
            '深圳华强电子有限公司', '东莞华利科技有限公司', '上海精密制造有限公司',
            '苏州工业机械有限公司', '安徽新材料科技有限公司', '浙江化工原料有限公司',
            '广州电子元器件公司', '北京精密仪器有限公司', '成都机电设备有限公司',
            '杭州电气设备公司', '武汉光电科技有限公司', '南京半导体技术公司',
            '天津工业材料公司', '重庆机械制造厂', '西安电子科技公司',
            '青岛精密机械公司', '长沙电器设备厂', '郑州化工材料公司',
            '福州电子技术公司', '厦门机械设备厂', '南昌工业材料公司',
            '合肥电子元件厂', '石家庄机械公司', '太原工业设备厂',
            '沈阳精密制造公司', '大连电子科技公司', '哈尔滨机械厂',
            '长春工业材料公司', '济南电子设备公司', '南宁机械制造厂',
        ]
        
        credit_ratings = ['A', 'A', 'A', 'B', 'B', 'C']
        payment_terms_list = [30, 30, 45, 45, 60]
        
        cat_ids = list(self.supplier_cat_ids.values())
        region_ids = list(self.region_ids.values())
        
        for i, name in enumerate(supplier_names):
            code = f'S{i+1:04d}'
            cat_id = random.choice(cat_ids)
            region_id = random.choice(region_ids)
            rating = random.choice(credit_ratings)
            payment_terms = random.choice(payment_terms_list)
            credit_limit = random.randint(50, 500) * 10000
            
            query = """
                INSERT INTO t_supplier (supplier_code, supplier_name, category_id, region_id,
                    contact_person, phone, credit_rating, payment_terms, credit_limit)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """
            supplier_id = self.execute_insert(query, (
                code, name, cat_id, region_id,
                f'联系人{i+1}', f'138{random.randint(10000000, 99999999)}',
                rating, payment_terms, credit_limit
            ))
            self.supplier_ids[code] = supplier_id
            
            # 创建供应商往来账
            self.cursor.execute("""
                INSERT INTO t_supplier_account (supplier_id, total_purchase_amount, total_paid_amount, payable_balance)
                VALUES (%s, 0, 0, 0)
            """, (supplier_id,))
        
        self.conn.commit()
        print(f"✅ 插入供应商: {len(supplier_names)} 家\n")
    
    def generate_customer_categories(self):
        """生成客户分类"""
        print("7. 生成客户分类")
        print("-" * 60)
        
        for cat in CUSTOMER_CATEGORIES:
            code, name, parent_code, discount = cat
            query = """
                INSERT INTO t_customer_category (category_code, category_name, discount_rate, sort_order)
                VALUES (%s, %s, %s, %s)
                RETURNING id
            """
            cat_id = self.execute_insert(query, (code, name, discount, 0))
            self.customer_cat_ids[code] = cat_id
        
        self.conn.commit()
        print(f"✅ 插入客户分类: {len(CUSTOMER_CATEGORIES)} 个\n")
    
    def generate_customers(self):
        """生成客户数据"""
        print("8. 生成客户数据")
        print("-" * 60)
        
        customer_prefixes = ['天成', '创新', '华兴', '安达', '光谷', '美创', '美威', '机电',
                            '科技', '工业', '智能', '数码', '联想', '方正', '神州', '长城',
                            '海尔', '格力', '美的', '康佳', '海信', 'TCL', '创维', '长虹']
        
        customer_suffixes = ['科技有限公司', '电子有限公司', '机械有限公司', '工业有限公司',
                            '贸易有限公司', '集团有限公司', '实业有限公司', '技术有限公司']
        
        # 生成100-150个客户
        customer_count = random.randint(100, 150)
        
        cat_ids = list(self.customer_cat_ids.values())
        region_ids = list(self.region_ids.values())
        company_ids = list(self.company_ids.values())
        # 销售员
        salesman_ids = [self.employee_ids.get(code) for code in ['E007', 'E008', 'E009', 'E010', 'E011', 'E012'] 
                       if self.employee_ids.get(code)]
        
        credit_ratings = ['A', 'A', 'A', 'B', 'B', 'B', 'C', 'C']
        
        for i in range(customer_count):
            code = f'C{i+1:04d}'
            name = f'{random.choice(customer_prefixes)}{random.choice(customer_suffixes)}'
            cat_id = random.choice(cat_ids)
            region_id = random.choice(region_ids)
            company_id = random.choice(company_ids)
            salesman_id = random.choice(salesman_ids)
            rating = random.choice(credit_ratings)
            
            # A类客户信用额度更高
            if rating == 'A':
                credit_limit = random.randint(50, 200) * 10000
            elif rating == 'B':
                credit_limit = random.randint(20, 80) * 10000
            else:
                credit_limit = random.randint(5, 30) * 10000
            
            payment_terms = random.choice([30, 45, 60])
            
            query = """
                INSERT INTO t_customer (customer_code, customer_name, category_id, region_id,
                    company_id, salesman_id, contact_person, phone, credit_rating, 
                    credit_limit, payment_terms)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """
            customer_id = self.execute_insert(query, (
                code, name, cat_id, region_id, company_id, salesman_id,
                f'联系人{i+1}', f'138{random.randint(10000000, 99999999)}',
                rating, credit_limit, payment_terms
            ))
            self.customer_ids[code] = customer_id
            
            # 创建客户往来账
            self.cursor.execute("""
                INSERT INTO t_customer_account (customer_id, total_sales_amount, total_received_amount, receivable_balance)
                VALUES (%s, 0, 0, 0)
            """, (customer_id,))
        
        self.conn.commit()
        print(f"✅ 插入客户: {customer_count} 家\n")
    
    # ============================================================
    # 3. 商品数据生成
    # ============================================================
    
    def generate_product_categories(self):
        """生成商品分类"""
        print("=" * 60)
        print("9. 生成商品分类")
        print("-" * 60)
        
        # 先插入一级分类
        for cat in PRODUCT_CATEGORIES:
            code, name, parent_code, level = cat
            if level == 1:
                query = """
                    INSERT INTO t_product_category (category_code, category_name, level, sort_order)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id
                """
                cat_id = self.execute_insert(query, (code, name, level, 0))
                self.product_cat_ids[code] = cat_id
        
        # 再插入二级分类
        for cat in PRODUCT_CATEGORIES:
            code, name, parent_code, level = cat
            if level == 2:
                parent_id = self.product_cat_ids.get(parent_code)
                query = """
                    INSERT INTO t_product_category (category_code, category_name, parent_id, level, sort_order)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id
                """
                cat_id = self.execute_insert(query, (code, name, parent_id, level, 0))
                self.product_cat_ids[code] = cat_id
        
        self.conn.commit()
        print(f"✅ 插入商品分类: {len(PRODUCT_CATEGORIES)} 个\n")
    
    def generate_brands(self):
        """生成品牌数据"""
        print("10. 生成品牌数据")
        print("-" * 60)
        
        for brand in BRANDS:
            code, name, desc = brand
            query = """
                INSERT INTO t_brand (brand_code, brand_name, description)
                VALUES (%s, %s, %s)
                RETURNING id
            """
            brand_id = self.execute_insert(query, (code, name, desc))
            self.brand_ids[code] = brand_id
        
        self.conn.commit()
        print(f"✅ 插入品牌: {len(BRANDS)} 个\n")
    
    def generate_products(self):
        """生成商品数据"""
        print("11. 生成商品数据")
        print("-" * 60)
        
        # 商品模板
        product_templates = [
            # 电阻
            ('10KΩ电阻', 'PC0101', '个', '1/4W ±1%', 0.02, 0.05),
            ('100KΩ电阻', 'PC0101', '个', '1/4W ±1%', 0.02, 0.05),
            ('1KΩ电阻', 'PC0101', '个', '1/4W ±1%', 0.02, 0.05),
            # 电容
            ('10uF电容', 'PC0102', '个', '50V', 0.15, 0.35),
            ('100uF电容', 'PC0102', '个', '25V', 0.25, 0.55),
            ('22uF电容', 'PC0102', '个', '16V', 0.18, 0.40),
            # 芯片
            ('STM32F103芯片', 'PC0103', '个', 'LQFP48', 8.50, 18.00),
            ('STM32F407芯片', 'PC0103', '个', 'LQFP100', 35.00, 68.00),
            ('ESP32模块', 'PC0103', '个', 'WiFi+BLE', 15.00, 32.00),
            # 连接器
            ('USB Type-C接口', 'PC0104', '个', '16Pin', 0.80, 1.80),
            ('HDMI接口', 'PC0104', '个', '19Pin', 1.50, 3.50),
            # 轴承
            ('6205轴承', 'PC0201', '个', '25x52x15mm', 12.00, 28.00),
            ('6206轴承', 'PC0201', '个', '30x62x16mm', 15.00, 35.00),
            ('6207轴承', 'PC0201', '个', '35x72x17mm', 18.00, 42.00),
            # 齿轮
            ('直齿轮M1.5', 'PC0202', '个', '模数1.5 20齿', 8.50, 20.00),
            ('斜齿轮M2', 'PC0202', '个', '模数2 25齿', 12.00, 28.00),
            # 紧固件
            ('M3内六角螺丝', 'PC0203', '个', '长10mm', 0.05, 0.12),
            ('M5内六角螺丝', 'PC0203', '个', '长16mm', 0.08, 0.18),
            # 金属材料
            ('6061铝板', 'PC0301', '公斤', '5mm厚', 28.00, 55.00),
            ('6063铝型材', 'PC0301', '公斤', '40x40x3', 25.00, 48.00),
            ('45#钢棒', 'PC0301', '公斤', '直径50mm', 6.00, 12.00),
            ('304不锈钢板', 'PC0301', '公斤', '2mm厚', 18.00, 35.00),
            # 塑料制品
            ('ABS塑料板', 'PC0302', '公斤', '3mm厚', 12.00, 25.00),
            ('PVC板材', 'PC0302', '公斤', '5mm厚', 8.00, 18.00),
            # 电动工具
            ('电动螺丝刀', 'PC0401', '个', '3.6V锂电', 120.00, 280.00),
            ('角磨机', 'PC0401', '个', '720W', 180.00, 380.00),
            ('电钻', 'PC0401', '个', '500W', 150.00, 320.00),
            # 测量仪器
            ('数字万用表', 'PC0402', '个', 'DT9205', 45.00, 98.00),
            ('游标卡尺', 'PC0402', '个', '0-150mm', 28.00, 65.00),
        ]
        
        # 扩展到100-200个商品
        product_count = random.randint(100, 200)
        brand_ids = list(self.brand_ids.values())
        
        for i in range(product_count):
            if i < len(product_templates):
                name, cat_code, unit, spec, purchase_price, sale_price = product_templates[i]
            else:
                # 随机生成商品
                base_template = random.choice(product_templates)
                name = f'{base_template[0]}-{i-len(product_templates)+1}'
                cat_code = base_template[1]
                unit = base_template[2]
                spec = f'{base_template[3]}-V{i%10+1}'
                purchase_price = base_template[4] * random.uniform(0.8, 1.2)
                sale_price = base_template[5] * random.uniform(0.9, 1.1)
            
            code = f'P{i+1:05d}'
            cat_id = self.product_cat_ids.get(cat_code)
            brand_id = random.choice(brand_ids)
            barcode = f'69{random.randint(10000000, 99999999)}'
            min_stock = random.randint(50, 500)
            max_stock = min_stock * random.randint(5, 20)
            
            query = """
                INSERT INTO t_product (product_code, product_name, category_id, brand_id,
                    unit, spec, barcode, purchase_price, sale_price, min_stock, max_stock)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """
            product_id = self.execute_insert(query, (
                code, name, cat_id, brand_id, unit, spec, barcode,
                purchase_price, sale_price, min_stock, max_stock
            ))
            self.product_ids[code] = product_id
        
        self.conn.commit()
        print(f"✅ 插入商品: {product_count} 种\n")
    
    # ============================================================
    # 4. 仓库数据生成
    # ============================================================
    
    def generate_warehouses(self):
        """生成仓库数据"""
        print("=" * 60)
        print("12. 生成仓库数据")
        print("-" * 60)
        
        warehouse_data = [
            ('WH01', '广州原材料仓库', 'RAW', '广州市天河区仓储中心A栋'),
            ('WH02', '广州成品仓库', 'FINISHED', '广州市天河区仓储中心B栋'),
            ('WH03', '深圳原材料仓库', 'RAW', '深圳市南山区物流园A区'),
            ('WH04', '深圳成品仓库', 'FINISHED', '深圳市南山区物流园B区'),
            ('WH05', '上海中心仓库', 'FINISHED', '上海市浦东新区物流中心'),
            ('WH06', '北京中心仓库', 'FINISHED', '北京市朝阳区物流园'),
            ('WH07', '成都中心仓库', 'FINISHED', '成都市高新区物流园'),
            ('WH08', '杭州中心仓库', 'FINISHED', '杭州市滨江区物流中心'),
        ]
        
        company_ids = list(self.company_ids.values())
        region_ids = list(self.region_ids.values())
        manager_ids = [self.employee_ids.get(code) for code in ['E013', 'E014', 'E015'] 
                      if self.employee_ids.get(code)]
        
        for wh in warehouse_data:
            code, name, wh_type, address = wh
            company_id = random.choice(company_ids)
            region_id = random.choice(region_ids)
            manager_id = random.choice(manager_ids)
            
            query = """
                INSERT INTO t_warehouse (warehouse_code, warehouse_name, company_id, region_id,
                    warehouse_type, address, manager_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """
            wh_id = self.execute_insert(query, (code, name, company_id, region_id, wh_type, address, manager_id))
            self.warehouse_ids[code] = wh_id
        
        self.conn.commit()
        print(f"✅ 插入仓库: {len(warehouse_data)} 个\n")
    
    # ============================================================
    # 5. 业务单据生成
    # ============================================================
    
    def generate_business_documents(self):
        """生成业务单据(采购、销售、退货)"""
        print("\n" + "=" * 60)
        print("开始生成业务单据")
        print("=" * 60 + "\n")
        
        supplier_ids = list(self.supplier_ids.values())
        customer_ids = list(self.customer_ids.values())
        product_ids = list(self.product_ids.values())
        warehouse_ids = list(self.warehouse_ids.values())
        company_ids = list(self.company_ids.values())
        buyer_ids = [self.employee_ids.get(code) for code in ['E004', 'E005', 'E006'] 
                    if self.employee_ids.get(code)]
        salesman_ids = [self.employee_ids.get(code) for code in ['E007', 'E008', 'E009', 'E010', 'E011', 'E012'] 
                       if self.employee_ids.get(code)]
        
        # 生成5000-8000笔采购订单
        print("13. 生成采购订单")
        print("-" * 60)
        purchase_order_count = random.randint(5000, 8000)
        purchase_order_ids = []
        
        current_date = START_DATE
        order_counter = 1
        
        while current_date <= END_DATE and len(purchase_order_ids) < purchase_order_count:
            # 判断是否为工作日
            if current_date.weekday() >= 5 and random.random() > 0.3:
                current_date += timedelta(days=1)
                continue
            
            # 业务高峰期增加单据量
            daily_orders = 5
            if is_business_peak(current_date):
                daily_orders = random.randint(10, 15)
            else:
                daily_orders = random.randint(3, 8)
            
            for _ in range(daily_orders):
                if len(purchase_order_ids) >= purchase_order_count:
                    break
                
                order_no = f"PO{current_date.strftime('%Y%m%d')}{order_counter:04d}"
                order_counter += 1
                
                supplier_id = random.choice(supplier_ids)
                warehouse_id = random.choice(warehouse_ids)
                company_id = random.choice(company_ids)
                buyer_id = random.choice(buyer_ids)
                expected_date = current_date + timedelta(days=random.randint(7, 30))
                order_status = random.choices([0, 1, 2, 3, 4], weights=[3, 5, 10, 75, 7])[0]
                
                # 生成2-6个明细
                detail_count = random.randint(2, 6)
                selected_products = random.sample(product_ids, min(detail_count, len(product_ids)))
                
                total_qty = 0
                total_amount = 0
                
                # 插入采购订单主表
                query = """
                    INSERT INTO t_purchase_order (order_no, supplier_id, warehouse_id, company_id,
                        buyer_id, order_date, expected_date, order_status, total_qty, total_amount,
                        freight_charge)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """
                freight = random.uniform(50, 500)
                order_id = self.execute_insert(query, (
                    order_no, supplier_id, warehouse_id, company_id, buyer_id,
                    current_date, expected_date, order_status, 0, 0, round(freight, 2)
                ))
                
                if not order_id:
                    continue
                
                purchase_order_ids.append((order_id, order_no, current_date, supplier_id, order_status))
                
                # 插入采购订单明细
                for prod_id in selected_products:
                    # 获取商品采购价
                    self.cursor.execute("SELECT purchase_price FROM t_product WHERE id = %s", (prod_id,))
                    result = self.cursor.fetchone()
                    if not result:
                        continue
                    
                    base_price = float(result[0])
                    unit_price = base_price * random.uniform(0.95, 1.05)  # 价格浮动±5%
                    quantity = random.randint(50, 1000)
                    amount = quantity * unit_price
                    
                    total_qty += quantity
                    total_amount += amount
                    
                    self.cursor.execute("""
                        INSERT INTO t_purchase_order_detail (order_id, product_id, quantity, unit_price, amount, tax_rate, tax_amount)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (order_id, prod_id, quantity, round(unit_price, 4), round(amount, 2), 13, round(amount * 0.13, 2)))
                
                # 更新订单总计
                self.cursor.execute("""
                    UPDATE t_purchase_order SET total_qty = %s, total_amount = %s WHERE id = %s
                """, (round(total_qty, 3), round(total_amount, 2), order_id))
                
                # 已完成的订单生成应付账款
                if order_status == 3:
                    payable_no = f"AP{current_date.strftime('%Y%m')}{len(purchase_order_ids):05d}"
                    due_date = current_date + timedelta(days=random.choice([30, 45, 60]))
                    
                    # 部分付款
                    paid_amount = 0
                    status = 0
                    if random.random() < 0.6:
                        paid_amount = round(total_amount * random.uniform(0, 1.0), 2)
                        if paid_amount >= total_amount * 0.99:
                            status = 2
                            paid_amount = total_amount
                        elif paid_amount > 0:
                            status = 1
                    
                    unpaid = round(total_amount - paid_amount, 2)
                    
                    self.cursor.execute("""
                        INSERT INTO t_accounts_payable (payable_no, supplier_id, source_order_no,
                            payable_amount, paid_amount, unpaid_amount, due_date, status)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """, (payable_no, supplier_id, order_no, round(total_amount, 2), paid_amount, unpaid, due_date, status))
            
            current_date += timedelta(days=1)
            
            # 每1000笔提交一次
            if len(purchase_order_ids) % 1000 == 0:
                self.conn.commit()
                print(f"  已生成采购订单: {len(purchase_order_ids)} 笔")
        
        self.conn.commit()
        print(f"✅ 插入采购订单: {len(purchase_order_ids)} 笔\n")
        
        # 生成8000-12000笔销售订单
        print("14. 生成销售订单")
        print("-" * 60)
        sales_order_count = random.randint(8000, 12000)
        sales_order_ids = []
        
        current_date = START_DATE
        order_counter = 1
        
        # 客户分级 (A类客户占销售额60%)
        a_customers = [cid for cid in customer_ids if random.random() < 0.2]
        b_customers = [cid for cid in customer_ids if random.random() < 0.3 and cid not in a_customers]
        c_customers = [cid for cid in customer_ids if cid not in a_customers and cid not in b_customers]
        
        while current_date <= END_DATE and len(sales_order_ids) < sales_order_count:
            if current_date.weekday() >= 5 and random.random() > 0.3:
                current_date += timedelta(days=1)
                continue
            
            # 应用季节性系数
            seasonal_factor = get_seasonal_factor(current_date)
            daily_orders = int(random.randint(5, 12) * seasonal_factor)
            
            if is_business_peak(current_date):
                daily_orders = int(daily_orders * 1.5)
            
            for _ in range(daily_orders):
                if len(sales_order_ids) >= sales_order_count:
                    break
                
                order_no = f"SO{current_date.strftime('%Y%m%d')}{order_counter:04d}"
                order_counter += 1
                
                # 客户选择(A类客户概率更高)
                rand = random.random()
                if rand < 0.6 and a_customers:
                    customer_id = random.choice(a_customers)
                elif rand < 0.9 and b_customers:
                    customer_id = random.choice(b_customers)
                else:
                    customer_id = random.choice(c_customers) if c_customers else random.choice(customer_ids)
                
                warehouse_id = random.choice(warehouse_ids)
                company_id = random.choice(company_ids)
                salesman_id = random.choice(salesman_ids)
                delivery_date = current_date + timedelta(days=random.randint(1, 10))
                order_status = random.choices([0, 1, 2, 3, 4], weights=[2, 5, 8, 80, 5])[0]
                
                detail_count = random.randint(1, 5)
                selected_products = random.sample(product_ids, min(detail_count, len(product_ids)))
                
                total_qty = 0
                total_amount = 0
                total_cost = 0
                
                # 插入销售订单主表
                query = """
                    INSERT INTO t_sales_order (order_no, customer_id, warehouse_id, company_id,
                        salesman_id, order_date, delivery_date, order_status, total_qty, total_amount, freight_charge)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """
                freight = random.uniform(30, 300)
                order_id = self.execute_insert(query, (
                    order_no, customer_id, warehouse_id, company_id, salesman_id,
                    current_date, delivery_date, order_status, 0, 0, round(freight, 2)
                ))
                
                if not order_id:
                    continue
                
                sales_order_ids.append((order_id, order_no, current_date, customer_id, salesman_id, order_status))
                
                # 插入销售订单明细
                for prod_id in selected_products:
                    self.cursor.execute("SELECT sale_price, purchase_price FROM t_product WHERE id = %s", (prod_id,))
                    result = self.cursor.fetchone()
                    if not result:
                        continue
                    
                    base_sale_price = float(result[0])
                    cost_price = float(result[1])
                    
                    unit_price = base_sale_price * random.uniform(0.95, 1.05)
                    quantity = random.randint(10, 500)
                    amount = quantity * unit_price
                    cost_amount = quantity * cost_price
                    gross_profit = amount - cost_amount
                    
                    total_qty += quantity
                    total_amount += amount
                    total_cost += cost_amount
                    
                    self.cursor.execute("""
                        INSERT INTO t_sales_order_detail (order_id, product_id, quantity, unit_price, amount,
                            cost_price, cost_amount, gross_profit, tax_rate, tax_amount)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (order_id, prod_id, quantity, round(unit_price, 4), round(amount, 2),
                           round(cost_price, 4), round(cost_amount, 2), round(gross_profit, 2), 13, round(amount * 0.13, 2)))
                
                # 更新订单总计和提成
                commission_rate = random.uniform(3, 8)
                commission_amount = total_amount * commission_rate / 100
                
                self.cursor.execute("""
                    UPDATE t_sales_order SET total_qty = %s, total_amount = %s, commission_amount = %s WHERE id = %s
                """, (round(total_qty, 3), round(total_amount, 2), round(commission_amount, 2), order_id))
                
                # 已完成的订单生成应收账款和提成记录
                if order_status == 3:
                    receivable_no = f"AR{current_date.strftime('%Y%m')}{len(sales_order_ids):05d}"
                    due_date = current_date + timedelta(days=random.choice([30, 45, 60]))
                    
                    received_amount = 0
                    status = 0
                    rand = random.random()
                    if rand < 0.4:  # 40%全额收款
                        received_amount = total_amount
                        status = 2
                    elif rand < 0.7:  # 30%部分收款
                        received_amount = round(total_amount * random.uniform(0.3, 0.9), 2)
                        status = 1
                    # 30%未收款
                    
                    unreceived = round(total_amount - received_amount, 2)
                    
                    self.cursor.execute("""
                        INSERT INTO t_accounts_receivable (receivable_no, customer_id, source_order_no,
                            receivable_amount, received_amount, unreceived_amount, due_date, status)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """, (receivable_no, customer_id, order_no, round(total_amount, 2), received_amount, unreceived, due_date, status))
                    
                    # 生成提成记录
                    commission_no = f"CM{current_date.strftime('%Y%m')}{len(sales_order_ids):05d}"
                    settle_month = current_date.strftime('%Y-%m')
                    
                    self.cursor.execute("""
                        INSERT INTO t_commission_record (commission_no, salesman_id, sales_order_no,
                            sales_amount, gross_profit, commission_rate, commission_amount, settle_month, status)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (commission_no, salesman_id, order_no, round(total_amount, 2),
                           round(total_amount - total_cost, 2), round(commission_rate, 2),
                           round(commission_amount, 2), settle_month, 1))
            
            current_date += timedelta(days=1)
            
            if len(sales_order_ids) % 1000 == 0:
                self.conn.commit()
                print(f"  已生成销售订单: {len(sales_order_ids)} 笔")
        
        self.conn.commit()
        print(f"✅ 插入销售订单: {len(sales_order_ids)} 笔\n")
        
        print("=" * 60)
        print("✅ 业务单据生成完成!")
        print("=" * 60 + "\n")
    
    # ============================================================
    # 主执行函数
    # ============================================================
    
    def generate_all_master_data(self):
        """生成所有主数据"""
        print("\n" + "=" * 60)
        print("开始生成主数据")
        print("=" * 60 + "\n")
        
        self.generate_companies()
        self.generate_departments()
        self.generate_employees()
        self.generate_regions()
        
        self.generate_supplier_categories()
        self.generate_suppliers()
        self.generate_customer_categories()
        self.generate_customers()
        
        self.generate_product_categories()
        self.generate_brands()
        self.generate_products()
        
        self.generate_warehouses()
        
        print("=" * 60)
        print("✅ 主数据生成完成!")
        print("=" * 60 + "\n")


# ============================================================
# 主程序入口
# ============================================================

def main():
    print("\n" + "#" * 60)
    print("#  进销存业务系统 Mock 数据生成工具 (PostgreSQL)")
    print("#  数据库: erp_business")
    print("#  时间跨度: 2024-01-01 至 2026-01-30")
    print("#" * 60 + "\n")
    
    generator = ERPDataGenerator()
    
    try:
        # 连接数据库
        generator.connect()
        
        # 生成主数据
        generator.generate_all_master_data()
        
        # 生成业务单据
        generator.generate_business_documents()
        
        # 打印统计信息
        print("\n" + "=" * 60)
        print("数据生成统计")
        print("=" * 60)
        
        # 查询各表数据量
        tables = [
            't_company', 't_department', 't_employee', 't_region',
            't_supplier_category', 't_supplier', 't_customer_category', 't_customer',
            't_supplier_account', 't_customer_account',
            't_product_category', 't_brand', 't_product',
            't_warehouse',
            't_purchase_order', 't_purchase_order_detail',
            't_sales_order', 't_sales_order_detail',
            't_accounts_payable', 't_accounts_receivable',
            't_commission_record'
        ]
        
        total_rows = 0
        for table in tables:
            generator.cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = generator.cursor.fetchone()[0]
            total_rows += count
            print(f"  {table:35s}: {count:>8d} 条")
        
        print("-" * 60)
        print(f"  {'总计':35s}: {total_rows:>8d} 条\n")
        
        print("=" * 60)
        print("✅ 数据生成完成!")
        print("=" * 60)
        print("\n连接信息:")
        print(f"  数据库类型: PostgreSQL 15")
        print(f"  主机: {DB_CONFIG['host']}:{DB_CONFIG['port']}")
        print(f"  数据库名: {DB_CONFIG['database']}")
        print(f"  用户名: {DB_CONFIG['user']}\n")
        
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        generator.close()
    
    return 0


if __name__ == "__main__":
    exit(main())
