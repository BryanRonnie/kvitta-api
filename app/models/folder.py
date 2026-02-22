from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from typing import Optional
from bson import ObjectId


class FolderBase(BaseModel):
    """Base folder schema."""
    name: str = Field(..., min_length=1, max_length=100)
    color: str = Field(..., min_length=1, max_length=50)


class FolderCreate(FolderBase):
    """Folder creation schema."""
    pass


class FolderUpdate(BaseModel):
    """Folder update schema."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    color: Optional[str] = Field(None, min_length=1, max_length=50)


class FolderResponse(FolderBase):
    """Folder response schema."""
    id: str = Field(validation_alias="_id", serialization_alias="id")
    owner_id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True
    )


class FolderWithCount(FolderResponse):
    """Folder response with receipt count."""
    receipt_count: int = 0


class FolderInDB(BaseModel):
    """Folder database schema."""
    id: ObjectId = Field(alias="_id")
    name: str
    color: str
    owner_id: ObjectId
    is_deleted: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True,
        arbitrary_types_allowed=True
    )

    @property
    def _id(self) -> ObjectId:
        return self.id
