"""
SQLite Schema 发现
SQLite 特定的 Schema 发现方法
"""

from typing import List, Dict, Any


def discover_sqlite_schema(inspector) -> List[Dict[str, Any]]:
    """
    SQLite-specific schema discovery.
    """
    print("Using SQLite-specific schema discovery")
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
        # Get table comment (SQLite doesn't support table comments in standard way, but we keep structure)
        table_info = {
            "table_name": table_name,
            "description": f"Auto-discovered table: {table_name}",
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
                    "description": column.get("comment") or f"Auto-discovered column: {column['name']}",
                    "is_primary_key": column.get("primary_key", False),  # SQLite provides primary_key info directly
                    "is_foreign_key": False,
                    "is_nullable": column.get("nullable", True)
                }
                table_info["columns"].append(column_info)

            # SQLite doesn't always expose primary key info through the column attributes
            # so we also check through the inspector
            try:
                pks = inspector.get_pk_constraint(table_name)["constrained_columns"]
                print(f"Primary keys for {table_name}: {pks}")
                for pk in pks:
                    for column in table_info["columns"]:
                        if column["column_name"] == pk:
                            column["is_primary_key"] = True
            except Exception as pk_error:
                print(f"Warning: Could not get primary keys for {table_name}: {str(pk_error)}")
                # Already tried to identify primary keys from column attributes

            # Mark foreign keys - SQLite has basic FK support
            try:
                fks = inspector.get_foreign_keys(table_name)
                print(f"Foreign keys for {table_name}: {len(fks)}")
                
                # Process explicit foreign keys
                for fk in fks:
                    print(f"  FK: {fk}")
                    for column in table_info["columns"]:
                        if column["column_name"] in fk["constrained_columns"]:
                            column["is_foreign_key"] = True
                            column["references"] = {
                                "table": fk["referred_table"],
                                "column": fk["referred_columns"][0]
                            }
                
                # If no foreign keys found, try to infer from naming convention
                if len(fks) == 0:
                    print(f"No explicit foreign keys found for {table_name}, attempting to infer from naming convention")
                    for column in table_info["columns"]:
                        col_name = column["column_name"].lower()
                        if col_name.endswith('_id') and not column["is_primary_key"]:
                            # Extract potential table name from column name
                            potential_table_base = col_name[:-3]  # Remove '_id' suffix
                            
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
                            
                            if matched_table:
                                print(f"Identified potential foreign key by naming convention: {column['column_name']} -> {matched_table}")
                                column["is_foreign_key"] = True
                                column["references"] = {
                                    "table": matched_table,
                                    "column": "id"  # Assume the primary key is 'id'
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
