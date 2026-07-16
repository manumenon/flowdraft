import uuid
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, ConfigDict

# --- User Schemas ---

class UserRegister(BaseModel):
    email: str
    password: str


class UserLogin(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- Diagram Schemas ---

class DiagramCreate(BaseModel):
    title: str
    description: Optional[str] = None
    spec: dict
    theme: Optional[str] = None


class DiagramUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    spec: Optional[dict] = None
    theme: Optional[str] = None


class DiagramResponse(BaseModel):
    id: uuid.UUID
    diagram_id: Optional[uuid.UUID] = None
    title: str
    description: Optional[str]
    spec: dict
    theme: Optional[str]
    user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- ExportJob Schemas ---

class ExportJobCreate(BaseModel):
    diagram_id: Optional[uuid.UUID] = None
    spec_override: Optional[dict] = None
    format: str  # e.g., "mp4" or "gif"


class ExportJobResponse(BaseModel):
    id: uuid.UUID
    diagram_id: Optional[uuid.UUID]
    spec_override: Optional[dict]
    format: str
    status: str  # "queued", "processing", "completed", "failed"
    error_message: Optional[str]
    download_url: Optional[str]
    user_id: Optional[uuid.UUID]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- Token Schemas ---

class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    email: Optional[str] = None
    user_id: Optional[uuid.UUID] = None
