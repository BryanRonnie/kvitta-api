from typing import Optional, List
from pydantic import Field
from app.models.base import MongoModel, PyObjectId
from datetime import datetime
from enum import Enum

class FolderRole(str, Enum):
    OWNER = "owner"
    EDITOR = "editor"
    VIEWER = "viewer"

class FolderMember(MongoModel):
    folder_id: PyObjectId
    user_id: PyObjectId
    role: FolderRole
    joined_at: datetime = Field(default_factory=lambda: datetime.now(datetime.UTC))

class Folder(MongoModel):
    owner_id: PyObjectId
    name: str
    parent_folder_id: Optional[PyObjectId] = None
    is_deleted: bool = False
