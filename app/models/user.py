from pydantic import BaseModel, EmailStr, Field, ConfigDict
from datetime import datetime
from typing import Optional
from bson import ObjectId

class UserBase(BaseModel):
    """Base user schema."""
    name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr

class UserCreate(UserBase):
    """User creation schema."""
    password: str = Field(..., min_length=8)

class UserUpdate(BaseModel):
    """User update schema."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    email: Optional[EmailStr] = None

class UserResponse(UserBase):
    """User response schema."""
    id: str = Field(validation_alias="_id", serialization_alias="id")
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True
    )

class UserInDB(BaseModel):
    """User database schema."""
    id: ObjectId = Field(alias="_id")
    name: str
    email: str
    password_hash: str
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
        """Alias for id to match MongoDB naming."""
        return self.id
