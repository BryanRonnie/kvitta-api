from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from bson import ObjectId

from app.core.auth import get_current_user
from app.db.mongo import get_db
from app.models.user import UserResponse
from app.repositories.ledger_repo import LedgerRepository
from app.repositories.receipt_repo import ReceiptRepository
from app.schemas.ledger import CounterpartyResponse, LedgerSettleRequest, LedgerEntryResponse, MeSummaryResponse
from app.utils.receipt_validation import ReceiptValidationError
from app.repositories.user_repo import UserRepository  # adjust import to your project

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
    


@router.get("/me", response_model=MeSummaryResponse)
async def get_my_ledger_summary(
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_db)
):
    """
    Returns a full financial picture for the current user:
    - Everyone who owes them money
    - Everyone they owe money to
    - Net per counterparty and overall
    """
    ledger_repo = LedgerRepository(db)
    user_repo = UserRepository(db)  # adjust to however you fetch users

    counterparties_raw = await ledger_repo.get_counterparties(current_user.id)

    # Resolve user names in one batch
    all_ids = [c["user_id"] for c in counterparties_raw]
    users = await user_repo.get_users_by_ids(all_ids)  # returns List[User] or Dict[id, User]
    user_map = {str(u.id): u for u in users}

    counterparties = []
    for c in counterparties_raw:
        user = user_map.get(c["user_id"])
        counterparties.append(CounterpartyResponse(
            user_id=c["user_id"],
            name=user.name if user else "Unknown",
            they_owe_me_cents=c["they_owe_me_cents"],
            i_owe_them_cents=c["i_owe_them_cents"],
            net_cents=c["net_cents"],
        ))

    # Sort: people I owe first (negative net), then people who owe me (positive net)
    counterparties.sort(key=lambda x: x.net_cents)

    total_owed_to_me = sum(c.they_owe_me_cents for c in counterparties)
    total_i_owe = sum(c.i_owe_them_cents for c in counterparties)

    return MeSummaryResponse(
        user_id=current_user.id,
        total_i_owe_cents=total_i_owe,
        total_owed_to_me_cents=total_owed_to_me,
        net_cents=total_owed_to_me - total_i_owe,
        counterparties=counterparties,
    )
