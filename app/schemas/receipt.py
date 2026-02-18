from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime
from app.models.receipt import ReceiptStatus

class SplitBase(BaseModel):
    user_id: str
    share_quantity: float
    
    model_config = {"from_attributes": True}

class ItemBase(BaseModel):
    name: str
    unit_price: float
    quantity: float
    splits: List[SplitBase] = []
    
    model_config = {"from_attributes": True}

class ParticipantBase(BaseModel):
    user_id: str
    
    model_config = {"from_attributes": True}

class PaymentBase(BaseModel):
    user_id: str
    amount_paid: float
    
    model_config = {"from_attributes": True}

class ReceiptBase(BaseModel):
    title: str
    folder_id: Optional[str] = None
    
    model_config = {"from_attributes": True}

class ReceiptCreate(ReceiptBase):
    participants: List[ParticipantBase] = []
    items: List[ItemBase] = []
    payments: List[PaymentBase] = []

class ReceiptUpdate(BaseModel):
    title: Optional[str] = None
    status: Optional[ReceiptStatus] = None
    participants: Optional[List[ParticipantBase]] = None
    items: Optional[List[ItemBase]] = None
    payments: Optional[List[PaymentBase]] = None

class ItemResponse(ItemBase):
    item_id: str

class ParticipantResponse(ParticipantBase):
    joined_at: datetime

from app.models.base import PyObjectId

class ReceiptResponse(ReceiptBase):
    id: PyObjectId = Field(validation_alias="_id") # Read from _id, write as id
    owner_id: PyObjectId
    status: ReceiptStatus
    subtotal: float
    tax: float
    tip: float
    total: float
    version: int
    created_at: datetime
    updated_at: datetime
    
    participants: List[ParticipantResponse]
    items: List[ItemResponse]
    payments: List[PaymentBase]

    model_config = {"from_attributes": True, "populate_by_name": True}
