"""
Receipt finalization schemas.

Finalization locks a receipt, generates immutable ledger entries,
and marks it as ready for settlement.
"""

from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from typing import List


class ReceiptFinalizeRequest(BaseModel):
    """Request to finalize a receipt."""
    pass  # No additional fields needed - just status validation


class LedgerEntryResponse(BaseModel):
    """Ledger entry in finalize response."""
    id: str = Field(validation_alias="_id")
    debtor_id: str
    creditor_id: str
    amount_cents: int
    settled_amount_cents: int
    status: str
    description: str
    created_at: datetime

    model_config = ConfigDict(populate_by_name=True)


class ReceiptFinalizeResponse(BaseModel):
    """Response after successfully finalizing receipt."""
    id: str = Field(validation_alias="_id")
    owner_id: str
    title: str
    status: str
    total_cents: int
    version: int
    updated_at: datetime
    ledger_entries: List[LedgerEntryResponse]

    model_config = ConfigDict(populate_by_name=True)
