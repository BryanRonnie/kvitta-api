from typing import Optional, List
from pydantic import BaseModel, ConfigDict
from datetime import datetime
from app.models.folder import FolderRole

class FolderMemberBase(BaseModel):
    user_id: str
    role: FolderRole

class FolderMemberResponse(FolderMemberBase):
    joined_at: datetime
    id: str

class FolderBase(BaseModel):
    name: str
    
class FolderCreate(FolderBase):
    parent_folder_id: Optional[str] = None

class FolderUpdate(BaseModel):
    name: Optional[str] = None
    parent_folder_id: Optional[str] = None

class FolderResponse(FolderBase):
    id: str
    owner_id: str
    parent_folder_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    is_deleted: bool
