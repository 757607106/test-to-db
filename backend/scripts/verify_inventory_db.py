#!/usr/bin/env python3
"""验证进销存数据库"""
import pymysql
import os

DB_CONFIG = {
    'host': os.getenv('MYSQL_SERVER', 'localhost'),
    'port': int(os.getenv('MYSQL_PORT', 3306)),
    'user': os.getenv('MYSQL_USER', 'root'),
    'password': os.getenv('MYSQL_PASSWORD', 'mysql'),
}

def verify_database(db_name):
    print(f"\n{'='*60}")
    print(f"验证数据库: {db_name}")
    print('='*60)
    
    try:
        conn = pymysql.connect(**DB_CONFIG, database=db_name)
        cursor = conn.cursor()
        
        # 显示所有表
        cursor.execute("SHOW TABLES")
        tables = [row[0] for row in cursor.fetchall()]
        print(f"\n✅ 数据库存在，包含 {len(tables)} 张表")
        
        # 显示部分数据
        print(f"\n📊 数据示例:")
        print("-" * 60)
        
        sample_tables = ['product', 'customer', 'supplier', 'purchase_order', 'sales_order']
        
        for table in sample_tables:
            if table in tables:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                print(f"\n{table}: {count} 条记录")
                
                # 显示前3条数据
                cursor.execute(f"SELECT * FROM {table} LIMIT 3")
                rows = cursor.fetchall()
                cursor.execute(f"SHOW COLUMNS FROM {table}")
                columns = [col[0] for col in cursor.fetchall()]
                
                for row in rows:
                    print(f"  - {dict(zip(columns[:5], row[:5]))}")
        
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ 验证失败: {str(e)}")
        return False

if __name__ == "__main__":
    print("\n" + "#"*60)
    print("#  验证进销存数据库")
    print("#"*60)
    
    # 验证两个数据库
    verify_database('inventory_demo')
    verify_database('erp_inventory')
    
    print("\n" + "="*60)
    print("✅ 验证完成")
    print("="*60)
