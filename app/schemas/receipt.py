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
    taxable: bool = True  # Whether this item is subject to tax
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

class ChargeBase(BaseModel):
    name: str
    unit_price_cents: int
    taxable: bool = False  # Whether this charge itself is taxable (usually false)
    splits: List[SplitBase] = []
    
    model_config = {"from_attributes": True}

class ReceiptBase(BaseModel):
    title: str
    description: Optional[str] = None
    comments: Optional[str] = None
    folder_id: Optional[str] = None
    
    model_config = {"from_attributes": True}

class ReceiptCreate(ReceiptBase):
    """For Commit 6: Draft only creation - no items/payments yet"""
    pass

class ReceiptUpdate(BaseModel):
    """Update receipt - only works on draft status. All fields optional for autosave."""
    title: Optional[str] = None
    description: Optional[str] = None
    comments: Optional[str] = None
    folder_id: Optional[str] = None
    items: Optional[List[ItemBase]] = None
    charges: Optional[List[ChargeBase]] = None
    payments: Optional[List[PaymentBase]] = None
    version: int  # Required for optimistic locking

class ItemResponse(ItemBase):
    item_id: str

class ChargeResponse(ChargeBase):
    charge_id: str

class SettleSummaryEntry(BaseModel):
    user_id: str
    amount_cents: int
    paid_cents: int = 0
    net_cents: int = 0
    settled_amount_cents: int = 0
    is_settled: bool = False
    settled_at: Optional[datetime] = None
    status: str = "pending"

class ParticipantResponse(ParticipantBase):
    joined_at: datetime

class ReceiptResponse(ReceiptBase):
    id: str = Field(validation_alias="_id", serialization_alias="id")
    owner_id: str
    status: ReceiptStatus
    subtotal_cents: int
    total_cents: int
    version: int
    created_at: datetime
    updated_at: datetime
    
    participants: List[ParticipantResponse]
    items: List[ItemResponse]
    charges: List[ChargeResponse]
    settle_summary: List[SettleSummaryEntry]
    payments: List[PaymentBase]

    model_config = {"from_attributes": True, "populate_by_name": True}
