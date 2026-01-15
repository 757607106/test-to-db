from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import crud, schemas
from app.api import deps
from app.schemas.agent_profile import AgentProfileCreate, AgentProfileUpdate

router = APIRouter()

@router.get("/", response_model=List[schemas.AgentProfile])
def read_agent_profiles(
    db: Session = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """
    Retrieve agent profiles.
    """
    profiles = crud.agent_profile.get_multi(db, skip=skip, limit=limit)
    return profiles

@router.post("/", response_model=schemas.AgentProfile)
def create_agent_profile(
    *,
    db: Session = Depends(deps.get_db),
    profile_in: AgentProfileCreate,
) -> Any:
    """
    Create new agent profile.
    """
    profile = crud.agent_profile.get_by_name(db, name=profile_in.name)
    if profile:
        raise HTTPException(status_code=400, detail="The agent profile with this name already exists")
    profile = crud.agent_profile.create(db=db, obj_in=profile_in)
    return profile

@router.put("/{profile_id}", response_model=schemas.AgentProfile)
def update_agent_profile(
    *,
    db: Session = Depends(deps.get_db),
    profile_id: int,
    profile_in: AgentProfileUpdate,
) -> Any:
    """
    Update an agent profile.
    """
    profile = crud.agent_profile.get(db=db, id=profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Agent profile not found")
    profile = crud.agent_profile.update(db=db, db_obj=profile, obj_in=profile_in)
    return profile

@router.delete("/{profile_id}", response_model=schemas.AgentProfile)
def delete_agent_profile(
    *,
    db: Session = Depends(deps.get_db),
    profile_id: int,
) -> Any:
    """
    Delete an agent profile.
    """
    profile = crud.agent_profile.get(db=db, id=profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Agent profile not found")
    profile = crud.agent_profile.remove(db=db, id=profile_id)
    return profile
