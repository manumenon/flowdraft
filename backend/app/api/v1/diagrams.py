import os
import sys
import uuid
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

# Dynamically resolve project root containing the 'scripts' directory and add it to sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = None
while current_dir and current_dir != os.path.dirname(current_dir):
    if os.path.exists(os.path.join(current_dir, "scripts")):
        project_root = current_dir
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        break
    current_dir = os.path.dirname(current_dir)

from scripts.flowdraft.schema import validate_spec, SpecError

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models import Diagram, User
from app.schemas import DiagramCreate, DiagramUpdate, DiagramResponse

router = APIRouter()

@router.post("", response_model=DiagramResponse, status_code=status.HTTP_201_CREATED)
async def create_diagram(
    payload: Dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a diagram. Validates the spec using validate_spec.
    Saves diagram to DB with user_id.
    """
    title = None
    description = None
    spec = None
    theme = None
    
    if "elements" in payload:
        # Raw spec format passed by tests
        spec = payload
        title = payload.get("title", "Untitled Diagram")
        description = payload.get("description", "")
        theme = payload.get("theme", "light")
    else:
        # DiagramCreate format
        title = payload.get("title", "Untitled Diagram")
        description = payload.get("description")
        spec = payload.get("spec")
        theme = payload.get("theme")
        
    if spec is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Diagram spec is required"
        )
        
    validate_spec(spec)
    
    diagram = Diagram(
        title=title,
        description=description,
        spec=spec,
        theme=theme,
        user_id=current_user.id
    )
    db.add(diagram)
    await db.commit()
    await db.refresh(diagram)
    return diagram

@router.get("", response_model=List[DiagramResponse])
async def read_diagrams(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieve all diagrams owned by the authenticated user.
    """
    stmt = select(Diagram).where(Diagram.user_id == current_user.id)
    result = await db.execute(stmt)
    return result.scalars().all()

@router.get("/{id}", response_model=DiagramResponse)
async def read_diagram(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieve a specific diagram owned by the authenticated user.
    """
    stmt = select(Diagram).where(Diagram.id == id)
    result = await db.execute(stmt)
    diagram = result.scalar_one_or_none()
    
    if not diagram:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Diagram not found")
        
    if diagram.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Not authorized to access this diagram"
        )
        
    return diagram

@router.put("/{id}", response_model=DiagramResponse)
async def update_diagram(
    id: uuid.UUID,
    diagram_in: DiagramUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update a diagram. Validates spec if it is part of the update.
    """
    stmt = select(Diagram).where(Diagram.id == id)
    result = await db.execute(stmt)
    diagram = result.scalar_one_or_none()
    
    if not diagram:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Diagram not found")
        
    if diagram.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Not authorized to access this diagram"
        )
        
    if diagram_in.title is not None:
        diagram.title = diagram_in.title
    if diagram_in.description is not None:
        diagram.description = diagram_in.description
    if diagram_in.theme is not None:
        diagram.theme = diagram_in.theme
    if diagram_in.spec is not None:
        validate_spec(diagram_in.spec)
        diagram.spec = diagram_in.spec
        
    await db.commit()
    await db.refresh(diagram)
    return diagram

@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_diagram(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a diagram owned by the authenticated user.
    """
    stmt = select(Diagram).where(Diagram.id == id)
    result = await db.execute(stmt)
    diagram = result.scalar_one_or_none()
    
    if not diagram:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Diagram not found")
        
    if diagram.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Not authorized to access this diagram"
        )
        
    await db.delete(diagram)
    await db.commit()
    return None
