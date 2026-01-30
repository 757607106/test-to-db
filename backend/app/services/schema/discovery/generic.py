"""
通用 Schema 发现
适用于大多数数据库类型的通用发现方法
"""

from typing import List, Dict, Any


def discover_generic_schema(inspector) -> List[Dict[str, Any]]:
    """
    Generic schema discovery that works with most database types.
    """
    schema_info = []

    # Get all tables and views
    tables = inspector.get_table_names()
    try:
        views = inspector.get_view_names()
        tables.extend(views)
    except Exception as view_error:
        print(f"Warning: Could not get views: {str(view_error)}")
        views = []

    print(f"Found {len(tables)} tables/views: {', '.join(tables)}")

    for table_name in tables:
        print(f"Processing table/view: {table_name}")
        table_info = {
            "table_name": table_name,
            "columns": [],
            "is_view": table_name in views,
            "unique_constraints": [],  # 添加唯一约束信息
            "indexes": []  # 添加索引信息
        }

        # Get columns for each table
        try:
            columns = inspector.get_columns(table_name)
            print(f"Found {len(columns)} columns in {table_name}")

            for column in columns:
                column_info = {
                    "column_name": column["name"],
                    "data_type": str(column["type"]),
                    "is_primary_key": False,
                    "is_foreign_key": False,
                    "is_nullable": column.get("nullable", True),
                    "is_unique": False  # 添加唯一标记
                }
                table_info["columns"].append(column_info)

            # Mark primary keys
            try:
                pks = inspector.get_primary_keys(table_name)
                print(f"Primary keys for {table_name}: {pks}")
                for pk in pks:
                    for column in table_info["columns"]:
                        if column["column_name"] == pk:
                            column["is_primary_key"] = True
            except Exception as pk_error:
                # Some databases might not support primary key inspection
                print(f"Warning: Could not get primary keys for {table_name}: {str(pk_error)}")
                # Try to identify primary keys by naming convention
                for column in table_info["columns"]:
                    col_name = column["column_name"].lower()
                    if col_name == 'id' or col_name.endswith('_id') or col_name == f"{table_name.lower()}_id":
                        if 'int' in column["data_type"].lower() or 'serial' in column["data_type"].lower():
                            print(f"Identified potential primary key by naming convention: {column['column_name']}")
                            column["is_primary_key"] = True

            # Mark foreign keys
            try:
                fks = inspector.get_foreign_keys(table_name)
                print(f"Foreign keys for {table_name}: {len(fks)}")
                
                # Process explicit foreign keys
                for fk in fks:
                    print(f"  FK: {fk}")
                    # 处理复合外键
                    for i, constrained_column in enumerate(fk["constrained_columns"]):
                        for column in table_info["columns"]:
                            if column["column_name"] == constrained_column:
                                column["is_foreign_key"] = True
                                # 确保引用列索引有效
                                referred_column_idx = min(i, len(fk["referred_columns"]) - 1) if fk["referred_columns"] else 0
                                referred_column = fk["referred_columns"][referred_column_idx] if fk["referred_columns"] else "id"
                                column["references"] = {
                                    "table": fk["referred_table"],
                                    "column": referred_column,
                                    "constraint_name": fk.get("name", ""),  # 保存约束名称
                                    "is_part_of_composite_key": len(fk["constrained_columns"]) > 1  # 标记是否为复合键的一部分
                                }
                
                # If no foreign keys found, try to infer from naming convention
                if len(fks) == 0:
                    print(f"No explicit foreign keys found for {table_name}, attempting to infer from naming convention")
                    for column in table_info["columns"]:
                        col_name = column["column_name"].lower()

                        # 如果列名以_id结尾且不是主键，可能是外键
                        if col_name.endswith('_id') and not column["is_primary_key"]:
                            # 提取可能的表名
                            potential_table_base = col_name[:-3]  # 移除 '_id' 后缀
                            
                            # Try multiple matching strategies
                            matched_table = None
                            
                            # Strategy 1: Exact match (lowercase)
                            for t in tables:
                                if t.lower() == potential_table_base:
                                    matched_table = t
                                    break
                            
                            # Strategy 2: Match with common prefixes (t_, tbl_, etc.)
                            if not matched_table:
                                for t in tables:
                                    t_lower = t.lower()
                                    # Remove common table prefixes
                                    for prefix in ['t_', 'tbl_', 'tb_']:
                                        if t_lower.startswith(prefix):
                                            t_base = t_lower[len(prefix):]
                                            if t_base == potential_table_base:
                                                matched_table = t
                                                break
                                    if matched_table:
                                        break
                            
                            # 如果找到匹配的表，标记为外键
                            if matched_table:
                                print(f"Identified potential foreign key by naming convention: {column['column_name']} -> {matched_table}")
                                column["is_foreign_key"] = True
                                column["references"] = {
                                    "table": matched_table,
                                    "column": "id",  # 假设主键是 'id'
                                    "constraint_name": f"fk_{table_name}_{column['column_name']}_inferred",  # 生成一个约束名
                                    "is_part_of_composite_key": False,  # 默认不是复合键的一部分
                                    "is_inferred": True  # 标记为推断的外键
                                }

                        # 如果列名与其他表名相同，也可能是外键
                        elif not column["is_primary_key"] and not column["is_foreign_key"]:
                            for table_name_to_check in tables:
                                if col_name == table_name_to_check.lower() or col_name == f"{table_name_to_check.lower()}id":
                                    print(f"Identified potential foreign key by table name match: {column['column_name']} -> {table_name_to_check}")
                                    column["is_foreign_key"] = True
                                    column["references"] = {
                                        "table": table_name_to_check,
                                        "column": "id",  # 假设主键是 'id'
                                        "constraint_name": f"fk_{table_name}_{column['column_name']}_inferred",  # 生成一个约束名
                                        "is_part_of_composite_key": False,  # 默认不是复合键的一部分
                                        "is_inferred": True  # 标记为推断的外键
                                    }
                                    break
            except Exception as fk_error:
                # Some databases might not support foreign key inspection
                print(f"Warning: Could not get foreign keys for {table_name}: {str(fk_error)}")
                # Try to identify foreign keys by naming convention
                for column in table_info["columns"]:
                    col_name = column["column_name"].lower()

                    # 如果列名以_id结尾且不是主键，可能是外键
                    if col_name.endswith('_id') and not column["is_primary_key"]:
                        # 提取可能的表名
                        potential_table = col_name[:-3]  # 移除 '_id' 后缀

                        # 检查这个表是否存在
                        table_exists = potential_table in [t.lower() for t in tables]

                        # 如果表存在，标记为外键
                        if table_exists:
                            print(f"Identified potential foreign key by naming convention: {column['column_name']} -> {potential_table}")
                            column["is_foreign_key"] = True
                            column["references"] = {
                                "table": next(t for t in tables if t.lower() == potential_table),
                                "column": "id",  # 假设主键是 'id'
                                "constraint_name": f"fk_{table_name}_{column['column_name']}_inferred",  # 生成一个约束名
                                "is_part_of_composite_key": False,  # 默认不是复合键的一部分
                                "is_inferred": True  # 标记为推断的外键
                            }

                    # 如果列名与其他表名相同，也可能是外键
                    elif not column["is_primary_key"] and not column["is_foreign_key"]:
                        for table_name_to_check in tables:
                            if col_name == table_name_to_check.lower() or col_name == f"{table_name_to_check.lower()}id":
                                print(f"Identified potential foreign key by table name match: {column['column_name']} -> {table_name_to_check}")
                                column["is_foreign_key"] = True
                                column["references"] = {
                                    "table": table_name_to_check,
                                    "column": "id",  # 假设主键是 'id'
                                    "constraint_name": f"fk_{table_name}_{column['column_name']}_inferred",  # 生成一个约束名
                                    "is_part_of_composite_key": False,  # 默认不是复合键的一部分
                                    "is_inferred": True  # 标记为推断的外键
                                }
                                break

            # 获取唯一约束
            try:
                unique_constraints = inspector.get_unique_constraints(table_name)
                print(f"Unique constraints for {table_name}: {len(unique_constraints)}")
                for uc in unique_constraints:
                    print(f"  UC: {uc}")
                    table_info["unique_constraints"].append(uc)

                    # 标记列为唯一
                    for column in table_info["columns"]:
                        if column["column_name"] in uc.get("column_names", []):
                            column["is_unique"] = True
            except Exception as uc_error:
                print(f"Warning: Could not get unique constraints for {table_name}: {str(uc_error)}")

            # 获取索引
            try:
                indexes = inspector.get_indexes(table_name)
                print(f"Indexes for {table_name}: {len(indexes)}")
                for idx in indexes:
                    print(f"  Index: {idx}")
                    table_info["indexes"].append(idx)

                    # 标记列为唯一（如果索引是唯一的）
                    if idx.get("unique", False):
                        for column in table_info["columns"]:
                            if column["column_name"] in idx.get("column_names", []):
                                column["is_unique"] = True
            except Exception as idx_error:
                print(f"Warning: Could not get indexes for {table_name}: {str(idx_error)}")

        except Exception as column_error:
            print(f"Warning: Could not process columns for {table_name}: {str(column_error)}")
            continue

        schema_info.append(table_info)

    print(f"Schema discovery completed successfully. Found {len(schema_info)} tables/views.")
    return schema_info
