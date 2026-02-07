"""
User models and schemas
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field

class UserCreate(BaseModel):
    """Schema for user registration"""
    email: EmailStr
    password: str = Field(..., min_length=8)
    name: Optional[str] = None

class UserLogin(BaseModel):
    """Schema for user login"""
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    """Schema for user response (without password)"""
    email: str
    name: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True

class UserInDB(BaseModel):
    """Schema for user in database"""
    email: str
    name: Optional[str] = None
    hashed_password: str
    created_at: datetime
    updated_at: datetime
    is_active: bool = True

class Token(BaseModel):
    """Schema for JWT token response"""
    access_token: str
    token_type: str
    user: UserResponse

class TokenData(BaseModel):
    """Schema for token payload"""
    email: Optional[str] = None

class GroupMember(BaseModel):
    """Schema for group member"""
    email: EmailStr
    role: str = "member"  # member | admin
    joined_at: datetime

class GroupCreate(BaseModel):
    """Schema for creating a group"""
    name: str = Field(..., min_length=2, max_length=100)
    description: Optional[str] = Field(default=None, max_length=500)

class GroupUpdateRole(BaseModel):
    """Schema for updating member role"""
    role: str = Field(..., pattern="^(member|admin)$")

class GroupAddMember(BaseModel):
    """Schema for adding member by email"""
    email: EmailStr

class GroupResponse(BaseModel):
    """Schema for group response"""
    id: str
    name: str
    description: Optional[str] = None
    created_by: EmailStr
    created_at: datetime
    updated_at: datetime
    members: List[GroupMember]
    folder_id: Optional[str] = None

class FolderCreate(BaseModel):
    """Schema for creating a folder"""
    name: str = Field(..., min_length=2, max_length=100)
    color: str = Field(default="#6366F1", pattern="^#[0-9A-Fa-f]{6}$")

class FolderResponse(BaseModel):
    """Schema for folder response"""
    id: str
    name: str
    color: str
    created_by: EmailStr
    created_at: datetime
    updated_at: datetime
    receipt_count: int = 0
