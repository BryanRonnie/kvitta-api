from pydantic import BaseModel
from datetime import datetime

class SettlementCreate(BaseModel):
    from_user_id: str
    to_user_id: str
    amount: float

class SettlementResponse(BaseModel):
    id: str
    from_user_id: str
    to_user_id: str
    amount: float
    created_at: datetime
