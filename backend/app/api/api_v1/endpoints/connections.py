from typing import Any, List, Dict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.api import deps
from app.models.db_connection import DBConnection # Import for type hinting mock

router = APIRouter()


@router.get("/", response_model=List[schemas.DBConnection])
def read_connections(
    db: Session = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """
    Retrieve all database connections.
    """
    connections = crud.db_connection.get_multi(db, skip=skip, limit=limit)
    return connections



@router.post("/", response_model=schemas.DBConnection)
def create_connection(
    *,
    db: Session = Depends(deps.get_db),
    connection_in: schemas.DBConnectionCreate,
) -> Any:
    """
    Create new database connection.
    """
    connection = crud.db_connection.create(db=db, obj_in=connection_in)
    return connection


@router.post("/{connection_id}/discover-and-save", response_model=Dict[str, Any])
def discover_and_save_schema(
    *,
    db: Session = Depends(deps.get_db),
    connection_id: int,
) -> Any:
    """
    Discover schema from a database connection and save it to the database.
    """
    from app.services.schema_service import discover_schema, save_discovered_schema

    connection = crud.db_connection.get(db=db, id=connection_id)
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")

    try:
        # Test the connection first
        from app.services.db_service import test_db_connection
        test_db_connection(connection)

        # Discover schema
        schema_info = discover_schema(connection)

        # Save discovered schema
        tables_data, relationships_data = save_discovered_schema(db, connection_id, schema_info)

        return {
            "status": "success",
            "message": f"Successfully discovered and saved schema for {connection.name}",
            "tables": tables_data,
            "relationships": relationships_data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error discovering and saving schema: {str(e)}")


@router.get("/{connection_id}", response_model=schemas.DBConnection)
def read_connection(
    *,
    db: Session = Depends(deps.get_db),
    connection_id: int,
) -> Any:
    """
    Get database connection by ID.
    """
    connection = crud.db_connection.get(db=db, id=connection_id)
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")
    return connection


@router.put("/{connection_id}", response_model=schemas.DBConnection)
def update_connection(
    *,
    db: Session = Depends(deps.get_db),
    connection_id: int,
    connection_in: schemas.DBConnectionUpdate,
) -> Any:
    """
    Update a database connection.
    """
    connection = crud.db_connection.get(db=db, id=connection_id)
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")
    connection = crud.db_connection.update(db=db, db_obj=connection, obj_in=connection_in)
    return connection


@router.delete("/{connection_id}", response_model=schemas.DBConnection)
def delete_connection(
    *,
    db: Session = Depends(deps.get_db),
    connection_id: int,
) -> Any:
    """
    Delete a database connection.
    """
    connection = crud.db_connection.get(db=db, id=connection_id)
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")
    connection = crud.db_connection.remove(db=db, id=connection_id)
    return connection


@router.post("/{connection_id}/test", response_model=dict)
def test_connection(
    *,
    db: Session = Depends(deps.get_db),
    connection_id: int,
) -> Any:
    """
    Test a database connection (existing).
    """
    connection = crud.db_connection.get(db=db, id=connection_id)
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")

    # Test the connection
    try:
        from app.services.db_service import test_db_connection
        test_db_connection(connection)
        return {"status": "success", "message": "Connection successful"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@router.post("/test-config", response_model=dict)
def test_connection_config(
    *,
    connection_in: schemas.DBConnectionCreate,
) -> Any:
    """
    Test a database connection configuration (before saving).
    """
    try:
        from app.services.db_service import test_db_connection
        # Create a temporary DBConnection object (not saved to DB)
        # Note: We can't easily instantiate SQLAlchemy model without session, 
        # but db_service.py expects an object with attributes.
        # Let's create a simple object or use the Pydantic model if compatible.
        
        # We need to construct an object that has the same attributes as DBConnection
        class MockConnection:
            def __init__(self, **kwargs):
                for k, v in kwargs.items():
                    setattr(self, k, v)
                self.password_encrypted = kwargs.get('password', '') # Mock encrypted as plain for test if provided
                
        mock_conn = MockConnection(**connection_in.dict())
        
        test_db_connection(mock_conn)
        return {"status": "success", "message": "Connection successful"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
