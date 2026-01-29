"""
Neo4j 同步
将 Schema 元数据同步到 Neo4j 图数据库
"""

from neo4j import GraphDatabase

from app.core.config import settings
from app import crud


def sync_schema_to_graph_db(connection_id: int):
    """
    Sync schema metadata to Neo4j graph database.
    """
    try:
        print(f"Starting sync to Neo4j for connection_id: {connection_id}")
        # Connect to Neo4j
        print(f"Connecting to Neo4j at {settings.NEO4J_URI} with user {settings.NEO4J_USER}")
        driver = GraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
        )

        with driver.session() as session:
            # Clear existing schema for this connection
            print(f"Clearing existing schema for connection_id: {connection_id}")
            session.run(
                "MATCH (n {connection_id: $connection_id}) DETACH DELETE n",
                connection_id=connection_id
            )

            # Get all tables for this connection from MySQL
            from sqlalchemy.orm import Session
            from app.db.session import SessionLocal

            db = SessionLocal()
            try:
                print(f"Fetching tables for connection_id: {connection_id}")
                tables = crud.schema_table.get_by_connection(db=db, connection_id=connection_id)
                print(f"Found {len(tables)} tables for connection_id: {connection_id}")

                if len(tables) == 0:
                    print(f"Warning: No tables found for connection_id: {connection_id}")
                    return False

                # Create Table nodes
                for table in tables:
                    print(f"Creating Table node for table: {table.table_name} (id: {table.id})")
                    session.run(
                        """
                        CREATE (t:Table {
                            id: $id,
                            connection_id: $connection_id,
                            name: $name,
                            description: $description
                        })
                        """,
                        id=table.id,
                        connection_id=connection_id,
                        name=table.table_name,
                        description=table.description or ""
                    )

                    # Get columns for this table
                    columns = crud.schema_column.get_by_table(db=db, table_id=table.id)
                    print(f"Found {len(columns)} columns for table: {table.table_name}")

                    # Create Column nodes and HAS_COLUMN relationships
                    for column in columns:
                        print(f"Creating Column node for column: {column.column_name} (id: {column.id})")
                        session.run(
                            """
                            CREATE (c:Column {
                                id: $id,
                                name: $name,
                                type: $type,
                                description: $description,
                                is_pk: $is_pk,
                                is_fk: $is_fk,
                                connection_id: $connection_id
                            })
                            WITH c
                            MATCH (t:Table {id: $table_id})
                            CREATE (t)-[:HAS_COLUMN]->(c)
                            """,
                            id=column.id,
                            name=column.column_name,
                            type=column.data_type,
                            description=column.description or "",
                            is_pk=column.is_primary_key,
                            is_fk=column.is_foreign_key,
                            connection_id=connection_id,
                            table_id=table.id
                        )

                # Create FOREIGN_KEY relationships
                relationships = crud.schema_relationship.get_by_connection(db=db, connection_id=connection_id)
                print(f"Found {len(relationships)} relationships for connection_id: {connection_id}")

                for rel in relationships:
                    print(f"Creating REFERENCES relationship from column id: {rel.source_column_id} to column id: {rel.target_column_id}")
                    session.run(
                        """
                        MATCH (source:Column {id: $source_column_id})
                        MATCH (target:Column {id: $target_column_id})
                        CREATE (source)-[:REFERENCES {
                            type: $relationship_type,
                            description: $description,
                            connection_id: $connection_id
                        }]->(target)
                        """,
                        source_column_id=rel.source_column_id,
                        target_column_id=rel.target_column_id,
                        relationship_type=rel.relationship_type or "unknown",
                        description=rel.description or "",
                        connection_id=connection_id
                    )

                print(f"Successfully synced schema to Neo4j for connection_id: {connection_id}")
            finally:
                db.close()

        driver.close()
        return True
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"Graph DB sync failed: {str(e)}\n{error_trace}")
        raise Exception(f"Graph DB sync failed: {str(e)}")
