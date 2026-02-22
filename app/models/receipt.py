from typing import Optional, List
from pydantic import Field, BaseModel
from app.models.base import MongoModel, PyObjectId
from datetime import datetime, timezone
from enum import Enum

class ReceiptStatus(str, Enum):
    DRAFT = "draft"
    FINALIZED = "finalized"
    SETTLED = "settled"

# Embedded documents don't need MongoModel (no separate _id)
class Participant(BaseModel):
    user_id: PyObjectId
    role: str = "member"  # "owner" or "member"
    joined_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class Split(BaseModel):
    user_id: PyObjectId
    share_quantity: float  # e.g., 0.5 for half

class Item(BaseModel):
    item_id: PyObjectId = Field(default_factory=PyObjectId)
    name: str
    unit_price_cents: int  # Integer cents
    quantity: float  # e.g., 2.5 for 2.5 units
    taxable: bool = True  # Whether this item is subject to tax
    splits: List[Split] = []

class Charge(BaseModel):
    """Dynamic charges: taxes, tips, fees, etc. with optional splits."""
    charge_id: str = Field(default_factory=lambda: str(PyObjectId()))
    name: str  # e.g., "Tax", "Tip", "Service Fee"
    unit_price_cents: int  # Integer cents
    taxable: bool = False  # Whether this charge itself is taxable (usually false)
    splits: List[Split] = []  # If empty, charged to all equally; if specified, only to those users

class Payment(BaseModel):
    user_id: PyObjectId
    amount_paid_cents: int  # Integer cents

class Receipt(MongoModel):
    owner_id: PyObjectId
    folder_id: Optional[PyObjectId] = None
    title: str
    description: Optional[str] = None
    comments: Optional[str] = None  # For clarifications and discussions
    status: ReceiptStatus = ReceiptStatus.DRAFT
    
    participants: List[Participant] = []
    items: List[Item] = []
    charges: List[Charge] = []  # Dynamic charges (tax, tip, fees)
    payments: List[Payment] = []
    
    # All monetary values in integer cents
    subtotal_cents: int = 0
    total_cents: int = 0
    
    version: int = 1
    
    created_by: PyObjectId
    updated_by: PyObjectId
    is_deleted: bool = False
