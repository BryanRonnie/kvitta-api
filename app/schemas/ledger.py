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

class CounterpartyResponse(BaseModel):
    user_id: str
    name: str                   # resolved from user lookup
    they_owe_me_cents: int
    i_owe_them_cents: int
    net_cents: int              # positive = they owe me, negative = I owe them

class MeSummaryResponse(BaseModel):
    user_id: str
    total_i_owe_cents: int      # sum of all i_owe_them across counterparties
    total_owed_to_me_cents: int # sum of all they_owe_me across counterparties
    net_cents: int
    counterparties: list[CounterpartyResponse]