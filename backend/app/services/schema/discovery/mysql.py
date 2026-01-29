"""
MySQL Schema 发现
MySQL 特定的 Schema 发现方法
"""

from typing import List, Dict, Any


def discover_mysql_schema(inspector) -> List[Dict[str, Any]]:
    """
    MySQL-specific schema discovery.
    """
    print("Using MySQL-specific schema discovery")
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
            "is_view": table_name in views
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
                    "is_nullable": column.get("nullable", True)
                }
                table_info["columns"].append(column_info)

            # Mark primary keys - MySQL has reliable PK detection
            try:
                pks = inspector.get_primary_keys(table_name)
                print(f"Primary keys for {table_name}: {pks}")
                for pk in pks:
                    for column in table_info["columns"]:
                        if column["column_name"] == pk:
                            column["is_primary_key"] = True
            except Exception as pk_error:
                print(f"Warning: Could not get primary keys for {table_name}: {str(pk_error)}")
                # Try to identify primary keys by naming convention
                for column in table_info["columns"]:
                    col_name = column["column_name"].lower()
                    if col_name == 'id' or col_name.endswith('_id') or col_name == f"{table_name.lower()}_id":
                        if 'int' in column["data_type"].lower():
                            print(f"Identified potential primary key by naming convention: {column['column_name']}")
                            column["is_primary_key"] = True

            # Mark foreign keys - MySQL has reliable FK detection through INFORMATION_SCHEMA
            try:
                fks = inspector.get_foreign_keys(table_name)
                print(f"Foreign keys for {table_name}: {len(fks)}")
                for fk in fks:
                    print(f"  FK: {fk}")
                    for column in table_info["columns"]:
                        if column["column_name"] in fk["constrained_columns"]:
                            column["is_foreign_key"] = True
                            column["references"] = {
                                "table": fk["referred_table"],
                                "column": fk["referred_columns"][0]
                            }
            except Exception as fk_error:
                print(f"Warning: Could not get foreign keys for {table_name}: {str(fk_error)}")
                # Try to identify foreign keys by naming convention
                for column in table_info["columns"]:
                    col_name = column["column_name"].lower()
                    if col_name.endswith('_id') and not column["is_primary_key"]:
                        # Extract potential table name from column name
                        potential_table = col_name[:-3]  # Remove '_id' suffix
                        # Check if this table exists
                        if potential_table in [t.lower() for t in tables]:
                            print(f"Identified potential foreign key by naming convention: {column['column_name']} -> {potential_table}")
                            column["is_foreign_key"] = True
                            column["references"] = {
                                "table": next(t for t in tables if t.lower() == potential_table),
                                "column": "id"  # Assume the primary key is 'id'
                            }
        except Exception as column_error:
            print(f"Warning: Could not process columns for {table_name}: {str(column_error)}")
            continue

        schema_info.append(table_info)

    return schema_info
