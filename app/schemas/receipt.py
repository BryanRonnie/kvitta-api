from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime
from app.models.receipt import ReceiptStatus
from app.models.base import PyObjectId

class SplitBase(BaseModel):
    user_id: str
    share_quantity: float
    
    model_config = {"from_attributes": True}

class ItemBase(BaseModel):
    name: str
    unit_price_cents: int  # Integer cents
    quantity: float
    splits: List[SplitBase] = []
    
    model_config = {"from_attributes": True}

class ParticipantBase(BaseModel):
    user_id: str
    role: str = "member"
    
    model_config = {"from_attributes": True}

class PaymentBase(BaseModel):
    user_id: str
    amount_paid_cents: int  # Integer cents
    
    model_config = {"from_attributes": True}

class ReceiptBase(BaseModel):
    title: str
    description: Optional[str] = None
    folder_id: Optional[str] = None
    
    model_config = {"from_attributes": True}

class ReceiptCreate(ReceiptBase):
    """For Commit 6: Draft only creation - no items/payments yet"""
    pass

class ReceiptUpdate(BaseModel):
    """For future commits - update items/payments"""
    title: Optional[str] = None
    status: Optional[ReceiptStatus] = None
    participants: Optional[List[ParticipantBase]] = None
    items: Optional[List[ItemBase]] = None
    payments: Optional[List[PaymentBase]] = None

class ItemResponse(ItemBase):
    item_id: str

class ParticipantResponse(ParticipantBase):
    joined_at: datetime

class ReceiptResponse(ReceiptBase):
    id: str = Field(validation_alias="_id", serialization_alias="id")
    owner_id: str
    status: ReceiptStatus
    subtotal_cents: int
    tax_cents: int
    tip_cents: int
    total_cents: int
    version: int
    created_at: datetime
    updated_at: datetime
    
    participants: List[ParticipantResponse]
    items: List[ItemResponse]
    payments: List[PaymentBase]

    model_config = {"from_attributes": True, "populate_by_name": True}
