from typing import Optional, List
from pydantic import Field
from app.models.base import MongoModel, PyObjectId
from datetime import datetime, timezone
from enum import Enum

class ReceiptStatus(str, Enum):
    DRAFT = "draft"
    FINALIZED = "finalized"
    SETTLED = "settled"

class Participant(MongoModel):
    user_id: PyObjectId
    joined_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class Split(MongoModel):
    user_id: PyObjectId
    share_quantity: float

class Item(MongoModel):
    item_id: PyObjectId = Field(default_factory=PyObjectId)
    name: str
    unit_price: float
    quantity: float
    splits: List[Split] = []

class Payment(MongoModel):
    user_id: PyObjectId
    amount_paid: float

class Receipt(MongoModel):
    owner_id: PyObjectId
    folder_id: Optional[PyObjectId] = None
    title: str
    status: ReceiptStatus = ReceiptStatus.DRAFT
    
    participants: List[Participant] = []
    items: List[Item] = []
    payments: List[Payment] = []
    
    subtotal: float = 0.0
    tax: float = 0.0
    tip: float = 0.0
    total: float = 0.0
    
    version: int = 1
    
    created_by: PyObjectId
    updated_by: PyObjectId
    is_deleted: bool = False
