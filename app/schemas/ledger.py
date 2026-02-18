from typing import Optional
from pydantic import BaseModel
from datetime import datetime
from app.models.ledger import LedgerStatus

class LedgerEntryResponse(BaseModel):
    id: str
    receipt_id: str
    debtor_id: str
    creditor_id: str
    amount: float
    status: LedgerStatus
    created_at: datetime
    settled_at: Optional[datetime] = None

class UserBalanceResponse(BaseModel):
    user_id: str
    owes: float
    is_owed: float
    net: float
