from typing import Optional
from pydantic import Field
from app.models.base import MongoModel, PyObjectId
from datetime import datetime
from enum import Enum

class LedgerStatus(str, Enum):
    OPEN = "open"
    SETTLED = "settled"

class LedgerEntry(MongoModel):
    receipt_id: PyObjectId
    debtor_id: PyObjectId
    creditor_id: PyObjectId
    amount: float
    status: LedgerStatus = LedgerStatus.OPEN
    settled_at: Optional[datetime] = None
