from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class LedgerSettleRequest(BaseModel):
    """Request body to settle a ledger entry."""
    amount_cents: int


class LedgerEntryResponse(BaseModel):
    """Ledger entry response for settlement."""
    id: str = Field(validation_alias="_id", serialization_alias="id")
    receipt_id: str
    debtor_id: str
    creditor_id: str
    amount_cents: int
    settled_amount_cents: int
    status: str
    updated_at: datetime

    model_config = ConfigDict(populate_by_name=True)