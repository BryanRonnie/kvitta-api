"""Member management schemas for receipts."""
from pydantic import BaseModel, EmailStr
from datetime import datetime


class MemberAdd(BaseModel):
    """Add a member by email."""
    email: EmailStr


class MemberResponse(BaseModel):
    """Member in a receipt."""
    user_id: str
    role: str  # "owner" or "member"
    joined_at: datetime
    
    model_config = {"from_attributes": True}
