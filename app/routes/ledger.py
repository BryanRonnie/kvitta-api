from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from bson import ObjectId

from app.core.auth import get_current_user
from app.db.mongo import get_db
from app.models.user import UserResponse
from app.repositories.ledger_repo import LedgerRepository
from app.repositories.receipt_repo import ReceiptRepository
from app.schemas.ledger import LedgerSettleRequest, LedgerEntryResponse
from app.utils.receipt_validation import ReceiptValidationError

router = APIRouter(prefix="/ledger", tags=["ledger"])


@router.get("/{receipt_id}/entries", response_model=List[LedgerEntryResponse])
async def list_ledger_entries(
    receipt_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db = Depends(get_db)
):
    """List ledger entries for a receipt (owner or participant only)."""
    receipt_repo = ReceiptRepository(db)
    receipt = await receipt_repo.get_receipt(receipt_id, current_user.id)
    if not receipt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Receipt not found"
        )

    ledger_repo = LedgerRepository(db)
    entries = await ledger_repo.get_ledger_by_receipt(receipt_id)
    return [
        LedgerEntryResponse(
            id=str(entry.id),
            receipt_id=entry.receipt_id,
            debtor_id=entry.debtor_id,
            creditor_id=entry.creditor_id,
            amount_cents=entry.amount_cents,
            settled_amount_cents=entry.settled_amount_cents,
            status=entry.status,
            updated_at=entry.updated_at
        )
        for entry in entries
    ]


@router.post("/{entry_id}/settle", response_model=LedgerEntryResponse)
async def settle_ledger_entry(
    entry_id: str,
    payload: LedgerSettleRequest,
    current_user: UserResponse = Depends(get_current_user),
    db = Depends(get_db)
):
    """Settle a ledger entry (debtor only)."""
    ledger_repo = LedgerRepository(db)

    try:
        if not ObjectId.is_valid(entry_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ledger entry not found"
            )
        entry_doc = await ledger_repo.collection.find_one({"_id": ObjectId(entry_id)})
        if not entry_doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ledger entry not found"
            )
        entry_doc["_id"] = str(entry_doc["_id"])
        if entry_doc.get("debtor_id") != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the debtor can settle this entry"
            )

        entry = await ledger_repo.settle_entry(entry_id, payload.amount_cents)
        if not entry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ledger entry not found"
            )

        receipt_repo = ReceiptRepository(db)
        await receipt_repo.update_settle_summary_from_ledger(entry.receipt_id)

        return LedgerEntryResponse(
            id=str(entry.id),
            receipt_id=entry.receipt_id,
            debtor_id=entry.debtor_id,
            creditor_id=entry.creditor_id,
            amount_cents=entry.amount_cents,
            settled_amount_cents=entry.settled_amount_cents,
            status=entry.status,
            updated_at=entry.updated_at
        )
    except ReceiptValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc)
        )