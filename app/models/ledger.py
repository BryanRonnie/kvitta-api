"""
Ledger model - Financial obligations from finalized receipts.

Design principles:
- One ledger entry per (debtor, creditor) pair per receipt
- Immutable once created (from finalized receipt)
- Supports partial settlement
- Status: pending → partially_settled → settled
- All amounts in integer cents
"""

from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class LedgerEntry(BaseModel):
    """
    Financial obligation: debtor owes creditor amount_cents.
    
    Invariants:
    - settled_amount_cents <= amount_cents
    - status = settled iff settled_amount_cents == amount_cents
    - Immutable: only status/settled_amount_cents can change
    """
    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)
    
    id: Optional[str] = Field(default=None, validation_alias="_id", serialization_alias="_id")
    
    # References
    receipt_id: str  # Which receipt generated this entry
    debtor_id: str   # Who owes money
    creditor_id: str # Who is owed money
    
    # Financial
    amount_cents: int           # Total owed (integer cents, > 0)
    settled_amount_cents: int = 0   # How much settled (0 to amount_cents)
    
    # Tracking
    status: str = "pending"  # pending | partially_settled | settled
    description: str = ""    # e.g., "Share of Pizza + Tax"
    
    # Lifecycle
    is_deleted: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    def open_amount_cents(self) -> int:
        """How much remains unsettled."""
        return self.amount_cents - self.settled_amount_cents

    def is_fully_settled(self) -> bool:
        """Check if completely settled."""
        return self.settled_amount_cents == self.amount_cents
