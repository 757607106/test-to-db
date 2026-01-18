#!/usr/bin/env python3
"""
清理硬编码的示例数据库连接
"""
from app.db.session import SessionLocal
from app.models.db_connection import DBConnection

def cleanup_sample_db():
    """删除 Sample Database 连接"""
    db = SessionLocal()
    
    try:
        # 查找 Sample Database 连接
        sample_conn = db.query(DBConnection).filter(
            DBConnection.name == "Sample Database"
        ).first()
        
        if sample_conn:
            db.delete(sample_conn)
            db.commit()
            print(f"✅ 已删除连接: Sample Database (ID: {sample_conn.id})")
            print(f"   - 数据库类型: {sample_conn.db_type}")
            print(f"   - 主机: {sample_conn.host}:{sample_conn.port}")
            print(f"   - 数据库名: {sample_conn.database_name}")
        else:
            print("ℹ️  未找到 'Sample Database' 连接")
            
        # 显示当前所有连接
        all_conns = db.query(DBConnection).all()
        print(f"\n📊 当前数据库连接数: {len(all_conns)}")
        for conn in all_conns:
            print(f"  - {conn.name} ({conn.db_type}) - {conn.database_name}")
            
    except Exception as e:
        print(f"❌ 错误: {str(e)}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    print("\n" + "="*60)
    print("清理硬编码的示例数据库连接")
    print("="*60 + "\n")
    cleanup_sample_db()
    print("\n" + "="*60)
    print("✅ 清理完成")
    print("="*60 + "\n")
