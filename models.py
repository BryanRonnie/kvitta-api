"""
User models and schemas
"""

from datetime import datetime
from typing import Optional
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
