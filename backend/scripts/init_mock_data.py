#!/usr/bin/env python3
"""
初始化 Mock 数据脚本
用于在新的数据库中创建测试数据，包括：
- 用户数据
- 数据库连接
- Schema 元数据（表、列、关系）
- Value Mapping（值映射）
"""

import sys
import hashlib
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.models.db_connection import DBConnection
from app.models.user import User
from app.models.schema_table import SchemaTable
from app.models.schema_column import SchemaColumn
from app.models.schema_relationship import SchemaRelationship
from app.models.value_mapping import ValueMapping
from datetime import datetime

def simple_hash_password(password: str) -> str:
    """简单的密码哈希（仅用于测试）"""
    return hashlib.sha256(password.encode()).hexdigest()

def init_mock_data():
    """初始化 Mock 数据"""
    db: Session = SessionLocal()
    
    try:
        print("🚀 开始初始化 Mock 数据...")
        
        # 1. 创建测试用户
        print("\n📝 创建测试用户...")
        users_data = [
            {
                "username": "admin",
                "email": "admin@example.com",
                "password": "admin123",
                "display_name": "管理员",
                "role": "admin"
            },
            {
                "username": "test_user",
                "email": "test@example.com",
                "password": "test123",
                "display_name": "测试用户",
                "role": "user"
            }
        ]
        
        for user_data in users_data:
            existing_user = db.query(User).filter(User.username == user_data["username"]).first()
            if not existing_user:
                user = User(
                    username=user_data["username"],
                    email=user_data["email"],
                    password_hash=simple_hash_password(user_data["password"]),
                    display_name=user_data["display_name"],
                    role=user_data["role"],
                    is_active=True
                )
                db.add(user)
                db.commit()
                db.refresh(user)
                print(f"  ✅ 创建用户: {user.username} (ID: {user.id})")
            else:
                print(f"  ℹ️  用户已存在: {existing_user.username} (ID: {existing_user.id})")
        
        # 2. 创建测试数据库连接
        print("\n📝 创建测试数据库连接...")
        connections_data = [
            {
                "name": "Chinook Sample DB",
                "db_type": "sqlite",
                "host": "localhost",
                "port": 0,
                "username": "",
                "password": "",
                "database_name": "Chinook.db",
                "description": "SQLite 示例数据库 - 音乐商店数据"
            },
            {
                "name": "Local MySQL",
                "db_type": "mysql",
                "host": "localhost",
                "port": 3306,
                "username": "root",
                "password": "mysql",
                "database_name": "chatdb",
                "description": "本地 MySQL 数据库"
            },
            {
                "name": "Docker MySQL",
                "db_type": "mysql",
                "host": "chat_to_db_rwx-mysql",
                "port": 3306,
                "username": "root",
                "password": "mysql",
                "database_name": "chatdb",
                "description": "Docker 容器中的 MySQL"
            }
        ]
        
        for conn_data in connections_data:
            existing_conn = db.query(DBConnection).filter(DBConnection.name == conn_data["name"]).first()
            if not existing_conn:
                conn = DBConnection(
                    name=conn_data["name"],
                    db_type=conn_data["db_type"],
                    host=conn_data["host"],
                    port=conn_data["port"],
                    username=conn_data["username"],
                    password_encrypted=conn_data["password"],
                    database_name=conn_data["database_name"]
                )
                db.add(conn)
                db.commit()
                db.refresh(conn)
                print(f"  ✅ 创建连接: {conn.name} (ID: {conn.id}) - {conn_data['description']}")
            else:
                print(f"  ℹ️  连接已存在: {existing_conn.name} (ID: {existing_conn.id})")
        
        print("\n✅ Mock 数据初始化完成！")
        print("\n📊 数据统计:")
        print(f"  - 用户数: {db.query(User).count()}")
        print(f"  - 数据库连接数: {db.query(DBConnection).count()}")
        
        print("\n🔑 测试账号:")
        print("  管理员:")
        print("    用户名: admin")
        print("    密码: admin123")
        print("  普通用户:")
        print("    用户名: test_user")
        print("    密码: test123")
        
        print("\n💾 数据库连接:")
        for conn in db.query(DBConnection).all():
            print(f"  - {conn.name} ({conn.db_type})")
        
        # 3. 创建 Chinook 数据库的 Schema 元数据
        print("\n📝 创建 Chinook 数据库 Schema 元数据...")
        chinook_conn = db.query(DBConnection).filter(DBConnection.name == "Chinook Sample DB").first()
        
        if chinook_conn:
            # 创建表元数据
            tables_data = [
                {
                    "table_name": "Artist",
                    "table_comment": "艺术家表",
                    "business_description": "存储音乐艺术家信息"
                },
                {
                    "table_name": "Album",
                    "table_comment": "专辑表",
                    "business_description": "存储音乐专辑信息，每个专辑属于一个艺术家"
                },
                {
                    "table_name": "Track",
                    "table_comment": "曲目表",
                    "business_description": "存储音乐曲目信息，每个曲目属于一个专辑"
                },
                {
                    "table_name": "Customer",
                    "table_comment": "客户表",
                    "business_description": "存储客户信息"
                },
                {
                    "table_name": "Invoice",
                    "table_comment": "发票表",
                    "business_description": "存储客户购买记录"
                },
                {
                    "table_name": "InvoiceLine",
                    "table_comment": "发票明细表",
                    "business_description": "存储发票中的每个曲目购买明细"
                }
            ]
            
            for table_data in tables_data:
                existing_table = db.query(SchemaTable).filter(
                    SchemaTable.connection_id == chinook_conn.id,
                    SchemaTable.table_name == table_data["table_name"]
                ).first()
                
                if not existing_table:
                    table = SchemaTable(
                        connection_id=chinook_conn.id,
                        table_name=table_data["table_name"],
                        table_comment=table_data["table_comment"],
                        business_description=table_data["business_description"]
                    )
                    db.add(table)
                    db.commit()
                    db.refresh(table)
                    print(f"  ✅ 创建表: {table.table_name}")
                else:
                    print(f"  ℹ️  表已存在: {existing_table.table_name}")
            
            # 创建列元数据
            columns_data = [
                # Artist 表
                {"table": "Artist", "column": "ArtistId", "type": "INTEGER", "comment": "艺术家ID", "is_pk": True},
                {"table": "Artist", "column": "Name", "type": "NVARCHAR(120)", "comment": "艺术家名称"},
                # Album 表
                {"table": "Album", "column": "AlbumId", "type": "INTEGER", "comment": "专辑ID", "is_pk": True},
                {"table": "Album", "column": "Title", "type": "NVARCHAR(160)", "comment": "专辑标题"},
                {"table": "Album", "column": "ArtistId", "type": "INTEGER", "comment": "艺术家ID", "is_fk": True},
                # Track 表
                {"table": "Track", "column": "TrackId", "type": "INTEGER", "comment": "曲目ID", "is_pk": True},
                {"table": "Track", "column": "Name", "type": "NVARCHAR(200)", "comment": "曲目名称"},
                {"table": "Track", "column": "AlbumId", "type": "INTEGER", "comment": "专辑ID", "is_fk": True},
                {"table": "Track", "column": "Milliseconds", "type": "INTEGER", "comment": "时长（毫秒）"},
                {"table": "Track", "column": "UnitPrice", "type": "NUMERIC(10,2)", "comment": "单价"},
                # Customer 表
                {"table": "Customer", "column": "CustomerId", "type": "INTEGER", "comment": "客户ID", "is_pk": True},
                {"table": "Customer", "column": "FirstName", "type": "NVARCHAR(40)", "comment": "名"},
                {"table": "Customer", "column": "LastName", "type": "NVARCHAR(20)", "comment": "姓"},
                {"table": "Customer", "column": "Country", "type": "NVARCHAR(40)", "comment": "国家"},
                {"table": "Customer", "column": "Email", "type": "NVARCHAR(60)", "comment": "邮箱"},
                # Invoice 表
                {"table": "Invoice", "column": "InvoiceId", "type": "INTEGER", "comment": "发票ID", "is_pk": True},
                {"table": "Invoice", "column": "CustomerId", "type": "INTEGER", "comment": "客户ID", "is_fk": True},
                {"table": "Invoice", "column": "InvoiceDate", "type": "DATETIME", "comment": "发票日期"},
                {"table": "Invoice", "column": "Total", "type": "NUMERIC(10,2)", "comment": "总金额"},
                # InvoiceLine 表
                {"table": "InvoiceLine", "column": "InvoiceLineId", "type": "INTEGER", "comment": "发票明细ID", "is_pk": True},
                {"table": "InvoiceLine", "column": "InvoiceId", "type": "INTEGER", "comment": "发票ID", "is_fk": True},
                {"table": "InvoiceLine", "column": "TrackId", "type": "INTEGER", "comment": "曲目ID", "is_fk": True},
                {"table": "InvoiceLine", "column": "UnitPrice", "type": "NUMERIC(10,2)", "comment": "单价"},
                {"table": "InvoiceLine", "column": "Quantity", "type": "INTEGER", "comment": "数量"}
            ]
            
            for col_data in columns_data:
                table = db.query(SchemaTable).filter(
                    SchemaTable.connection_id == chinook_conn.id,
                    SchemaTable.table_name == col_data["table"]
                ).first()
                
                if table:
                    existing_col = db.query(SchemaColumn).filter(
                        SchemaColumn.table_id == table.id,
                        SchemaColumn.column_name == col_data["column"]
                    ).first()
                    
                    if not existing_col:
                        column = SchemaColumn(
                            table_id=table.id,
                            column_name=col_data["column"],
                            data_type=col_data["type"],
                            column_comment=col_data["comment"],
                            is_primary_key=col_data.get("is_pk", False),
                            is_foreign_key=col_data.get("is_fk", False),
                            is_nullable=not col_data.get("is_pk", False)
                        )
                        db.add(column)
            
            db.commit()
            print(f"  ✅ 创建了 {len(columns_data)} 个列")
            
            # 创建关系元数据
            relationships_data = [
                {
                    "source_table": "Album",
                    "source_column": "ArtistId",
                    "target_table": "Artist",
                    "target_column": "ArtistId",
                    "type": "many-to-one",
                    "description": "专辑属于艺术家"
                },
                {
                    "source_table": "Track",
                    "source_column": "AlbumId",
                    "target_table": "Album",
                    "target_column": "AlbumId",
                    "type": "many-to-one",
                    "description": "曲目属于专辑"
                },
                {
                    "source_table": "Invoice",
                    "source_column": "CustomerId",
                    "target_table": "Customer",
                    "target_column": "CustomerId",
                    "type": "many-to-one",
                    "description": "发票属于客户"
                },
                {
                    "source_table": "InvoiceLine",
                    "source_column": "InvoiceId",
                    "target_table": "Invoice",
                    "target_column": "InvoiceId",
                    "type": "many-to-one",
                    "description": "发票明细属于发票"
                },
                {
                    "source_table": "InvoiceLine",
                    "source_column": "TrackId",
                    "target_table": "Track",
                    "target_column": "TrackId",
                    "type": "many-to-one",
                    "description": "发票明细关联曲目"
                }
            ]
            
            for rel_data in relationships_data:
                existing_rel = db.query(SchemaRelationship).filter(
                    SchemaRelationship.connection_id == chinook_conn.id,
                    SchemaRelationship.source_table == rel_data["source_table"],
                    SchemaRelationship.source_column == rel_data["source_column"]
                ).first()
                
                if not existing_rel:
                    relationship = SchemaRelationship(
                        connection_id=chinook_conn.id,
                        source_table=rel_data["source_table"],
                        source_column=rel_data["source_column"],
                        target_table=rel_data["target_table"],
                        target_column=rel_data["target_column"],
                        relationship_type=rel_data["type"],
                        description=rel_data["description"]
                    )
                    db.add(relationship)
            
            db.commit()
            print(f"  ✅ 创建了 {len(relationships_data)} 个关系")
            
            # 创建值映射
            value_mappings_data = [
                {
                    "table": "Customer",
                    "column": "Country",
                    "mappings": [
                        ("USA", "美国", "美利坚合众国"),
                        ("Canada", "加拿大", "加拿大"),
                        ("Brazil", "巴西", "巴西联邦共和国"),
                        ("France", "法国", "法兰西共和国"),
                        ("Germany", "德国", "德意志联邦共和国")
                    ]
                }
            ]
            
            for vm_data in value_mappings_data:
                for original, display, desc in vm_data["mappings"]:
                    existing_vm = db.query(ValueMapping).filter(
                        ValueMapping.connection_id == chinook_conn.id,
                        ValueMapping.table_name == vm_data["table"],
                        ValueMapping.column_name == vm_data["column"],
                        ValueMapping.original_value == original
                    ).first()
                    
                    if not existing_vm:
                        vm = ValueMapping(
                            connection_id=chinook_conn.id,
                            table_name=vm_data["table"],
                            column_name=vm_data["column"],
                            original_value=original,
                            display_value=display,
                            description=desc
                        )
                        db.add(vm)
            
            db.commit()
            print(f"  ✅ 创建了值映射")
        
        print("\n✅ Mock 数据初始化完成！")
        print("\n📊 数据统计:")
        print(f"  - 用户数: {db.query(User).count()}")
        print(f"  - 数据库连接数: {db.query(DBConnection).count()}")
        print(f"  - Schema 表数: {db.query(SchemaTable).count()}")
        print(f"  - Schema 列数: {db.query(SchemaColumn).count()}")
        print(f"  - Schema 关系数: {db.query(SchemaRelationship).count()}")
        print(f"  - 值映射数: {db.query(ValueMapping).count()}")
        
        print("\n🔑 测试账号:")
        print("  管理员:")
        print("    用户名: admin")
        print("    密码: admin123")
        print("  普通用户:")
        print("    用户名: test_user")
        print("    密码: test123")
        
        print("\n💾 数据库连接:")
        for conn in db.query(DBConnection).all():
            print(f"  - {conn.name} ({conn.db_type})")
        
        print("\n📋 Text-to-SQL 测试数据:")
        print("  - Chinook 示例数据库已配置完整的 Schema 元数据")
        print("  - 包含 6 个表、25 个列、5 个关系")
        print("  - 可以测试查询：")
        print("    * 查询所有艺术家")
        print("    * 查询某个艺术家的所有专辑")
        print("    * 查询销售额最高的曲目")
        print("    * 查询各国客户数量")
        
        return True
        
    except Exception as e:
        print(f"\n❌ 初始化失败: {str(e)}")
        import traceback
        traceback.print_exc()
        db.rollback()
        return False
        
    finally:
        db.close()

if __name__ == "__main__":
    success = init_mock_data()
    sys.exit(0 if success else 1)
