"""
Schema 保存
将发现的 Schema 保存到数据库
"""

from typing import List, Dict, Any, Tuple
from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app import crud, schemas
from app.services.db_service import get_db_engine
from app.services.schema_utils import determine_relationship_type
from .neo4j_sync import sync_schema_to_graph_db


def save_discovered_schema(db: Session, connection_id: int, schema_info: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Save discovered schema to the database and detect relationships.
    Returns a tuple of (tables_data, relationships_data) for frontend display.
    """
    print(f"Saving discovered schema for connection {connection_id}")

    # Get the connection
    connection = crud.db_connection.get(db=db, id=connection_id)
    if not connection:
        raise ValueError(f"Connection with ID {connection_id} not found")

    # 创建数据库检查器，用于获取更详细的表结构信息
    engine = get_db_engine(connection)
    inspector = inspect(engine)

    # Track created tables and relationships
    tables_data = []
    relationships_data = []

    # Process each table
    for table_info in schema_info:
        table_name = table_info["table_name"]
        print(f"Processing table: {table_name}")

        # Create or update the table
        existing_table = crud.schema_table.get_by_name_and_connection(
            db=db, table_name=table_name, connection_id=connection_id
        )

        if existing_table:
            print(f"Table {table_name} already exists, updating...")
            table_obj = existing_table
        else:
            print(f"Creating new table: {table_name}")
            table_create = schemas.SchemaTableCreate(
                connection_id=connection_id,
                table_name=table_name,
                description=f"Auto-discovered table: {table_name}",
                ui_metadata={"position": {"x": 0, "y": 0}}  # Default position
            )
            table_obj = crud.schema_table.create(db=db, obj_in=table_create)

        # Add to tables_data for frontend
        tables_data.append({
            "id": table_obj.id,
            "table_name": table_obj.table_name,
            "description": table_obj.description,
            "ui_metadata": table_obj.ui_metadata
        })

        # Process columns for this table
        for column_info in table_info["columns"]:
            column_name = column_info["column_name"]

            # Check if column already exists
            existing_column = crud.schema_column.get_by_name_and_table(
                db=db, column_name=column_name, table_id=table_obj.id
            )

            if existing_column:
                print(f"Column {column_name} already exists, updating...")
                column_update = schemas.SchemaColumnUpdate(
                    data_type=column_info["data_type"],
                    is_primary_key=column_info["is_primary_key"],
                    is_foreign_key=column_info["is_foreign_key"],
                    is_unique=column_info.get("is_unique", False)  # 添加唯一标记
                )
                column_obj = crud.schema_column.update(
                    db=db, db_obj=existing_column, obj_in=column_update
                )
            else:
                print(f"Creating new column: {column_name}")
                column_create = schemas.SchemaColumnCreate(
                    table_id=table_obj.id,
                    column_name=column_name,
                    data_type=column_info["data_type"],
                    description=f"Auto-discovered column: {column_name}",
                    is_primary_key=column_info["is_primary_key"],
                    is_foreign_key=column_info["is_foreign_key"],
                    is_unique=column_info.get("is_unique", False)  # 添加唯一标记
                )
                column_obj = crud.schema_column.create(db=db, obj_in=column_create)

    # Process relationships after all tables and columns are created
    for table_info in schema_info:
        for column_info in table_info["columns"]:
            if column_info.get("is_foreign_key") and column_info.get("references"):
                source_table_name = table_info["table_name"]
                source_column_name = column_info["column_name"]
                target_table_name = column_info["references"]["table"]
                target_column_name = column_info["references"]["column"]

                print(f"Processing relationship: {source_table_name}.{source_column_name} -> {target_table_name}.{target_column_name}")

                # Get source and target tables
                source_table = crud.schema_table.get_by_name_and_connection(
                    db=db, table_name=source_table_name, connection_id=connection_id
                )
                target_table = crud.schema_table.get_by_name_and_connection(
                    db=db, table_name=target_table_name, connection_id=connection_id
                )

                if not source_table or not target_table:
                    print(f"Warning: Could not find tables for relationship")
                    continue

                # Get source and target columns
                source_column = crud.schema_column.get_by_name_and_table(
                    db=db, column_name=source_column_name, table_id=source_table.id
                )
                target_column = crud.schema_column.get_by_name_and_table(
                    db=db, column_name=target_column_name, table_id=target_table.id
                )

                if not source_column or not target_column:
                    print(f"Warning: Could not find columns for relationship")
                    continue

                # Check if relationship already exists
                existing_rel = crud.schema_relationship.get_by_columns(
                    db=db, source_column_id=source_column.id, target_column_id=target_column.id
                )

                # 使用优化后的关系类型判断逻辑
                print(f"\n[DEBUG] 分析关系: {source_table_name}.{source_column_name} -> {target_table_name}.{target_column_name}")
                print(f"[DEBUG] 源列是主键: {source_column.is_primary_key}")
                print(f"[DEBUG] 目标列是主键: {target_column.is_primary_key}")

                # 使用 schema_utils 中的函数确定关系类型
                try:
                    relationship_type = determine_relationship_type(
                        inspector=inspector,
                        source_table=source_table_name,
                        source_column=source_column_name,
                        target_table=target_table_name,
                        target_column=target_column_name,
                        schema_info=schema_info
                    )
                    print(f"[DEBUG] 确定的关系类型: {relationship_type}")
                except Exception as e:
                    print(f"[WARNING] 确定关系类型时出错: {str(e)}")
                    # 回退到基本逻辑
                    relationship_type = "1-to-N"  # 默认为一对多

                print(f"[DEBUG] 最终确定的关系类型: {relationship_type}")

                if existing_rel:
                    print(f"Relationship already exists, updating...")
                    rel_update = schemas.SchemaRelationshipUpdate(
                        relationship_type=relationship_type,
                        description=f"Auto-discovered relationship: {source_table_name}.{source_column_name} -> {target_table_name}.{target_column_name}"
                    )
                    rel_obj = crud.schema_relationship.update(
                        db=db, db_obj=existing_rel, obj_in=rel_update
                    )
                else:
                    print(f"Creating new relationship")
                    rel_create = schemas.SchemaRelationshipCreate(
                        connection_id=connection_id,
                        source_table_id=source_table.id,
                        source_column_id=source_column.id,
                        target_table_id=target_table.id,
                        target_column_id=target_column.id,
                        relationship_type=relationship_type,
                        description=f"Auto-discovered relationship: {source_table_name}.{source_column_name} -> {target_table_name}.{target_column_name}"
                    )
                    rel_obj = crud.schema_relationship.create(db=db, obj_in=rel_create)

                # Add to relationships_data for frontend
                relationships_data.append({
                    "id": rel_obj.id,
                    "source_table": source_table.table_name,
                    "source_table_id": source_table.id,
                    "source_column": source_column.column_name,
                    "source_column_id": source_column.id,
                    "target_table": target_table.table_name,
                    "target_table_id": target_table.id,
                    "target_column": target_column.column_name,
                    "target_column_id": target_column.id,
                    "relationship_type": rel_obj.relationship_type,
                    "description": rel_obj.description
                })

    # Sync to graph database
    try:
        sync_schema_to_graph_db(connection_id)
    except Exception as e:
        print(f"Warning: Failed to sync to graph database: {str(e)}")

    return tables_data, relationships_data
