from fastapi import APIRouter, Depends, HTTPException, status
from typing import List

from app.db.mongo import get_db
from app.core.auth import get_current_user
from app.models.user import UserResponse
from app.models.receipt import Receipt
from app.schemas.receipt import ReceiptCreate, ReceiptResponse, ReceiptUpdate
from app.schemas.member import MemberAdd, MemberResponse
from app.schemas.finalize import ReceiptFinalizeResponse, LedgerEntryResponse
from app.repositories.receipt_repo import ReceiptRepository
from app.repositories.user_repo import UserRepository
from app.utils.receipt_validation import ReceiptValidationError

router = APIRouter(prefix="/receipts", tags=["receipts"])


def _to_receipt_response(receipt: Receipt) -> ReceiptResponse:
    """Convert Receipt model to ReceiptResponse schema."""
    return ReceiptResponse(
        id=str(receipt.id),
        owner_id=str(receipt.owner_id),
        folder_id=str(receipt.folder_id) if receipt.folder_id else None,
        title=receipt.title,
        description=receipt.description,
        comments=receipt.comments,
        status=receipt.status,
        participants=[
            {
                "user_id": str(p.user_id),
                "role": p.role,
                "joined_at": p.joined_at
            }
            for p in receipt.participants
        ],
        items=[
            {
                "item_id": str(item.item_id),
                "name": item.name,
                "unit_price_cents": item.unit_price_cents,
                "quantity": item.quantity,
                "taxable": item.taxable,
                "splits": [
                    {
                        "user_id": str(split.user_id),
                        "share_quantity": split.share_quantity
                    }
                    for split in item.splits
                ]
            }
            for item in receipt.items
        ],
        charges=[
            {
                "charge_id": charge.charge_id,
                "name": charge.name,
                "unit_price_cents": charge.unit_price_cents,
                "taxable": charge.taxable,
                "splits": [
                    {
                        "user_id": str(split.user_id),
                        "share_quantity": split.share_quantity
                    }
                    for split in charge.splits
                ]
            }
            for charge in receipt.charges
        ],
        payments=[
            {
                "user_id": str(p.user_id),
                "amount_paid_cents": p.amount_paid_cents
            }
            for p in receipt.payments
        ],
        settle_summary=[
            {
                "user_id": entry.user_id,
                "amount_cents": entry.amount_cents,
                "paid_cents": entry.paid_cents,
                "net_cents": entry.net_cents,
                "settled_amount_cents": entry.settled_amount_cents,
                "is_settled": entry.is_settled,
                "settled_at": entry.settled_at,
                "status": entry.status
            }
            for entry in receipt.settle_summary
        ],
        subtotal_cents=receipt.subtotal_cents,
        total_cents=receipt.total_cents,
        version=receipt.version,
        created_at=receipt.created_at,
        updated_at=receipt.updated_at
    )


@router.post("", response_model=ReceiptResponse, status_code=status.HTTP_201_CREATED)
async def create_receipt(
    receipt_data: ReceiptCreate,
    current_user: UserResponse = Depends(get_current_user),
    db = Depends(get_db)
):
    """Create a new draft receipt. Owner automatically added as participant."""
    repo = ReceiptRepository(db)
    receipt = await repo.create_receipt(receipt_data, current_user.id)
    return _to_receipt_response(receipt)


@router.get("", response_model=List[ReceiptResponse])
async def list_receipts(
    current_user: UserResponse = Depends(get_current_user),
    db = Depends(get_db)
):
    """List receipts where user is owner or participant."""
    repo = ReceiptRepository(db)
    receipts = await repo.list_receipts(current_user.id)
    return [_to_receipt_response(receipt) for receipt in receipts]


@router.get("/{receipt_id}", response_model=ReceiptResponse)
async def get_receipt(
    receipt_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db = Depends(get_db)
):
    """Get a receipt by ID if user is owner or participant."""
    repo = ReceiptRepository(db)
    receipt = await repo.get_receipt(receipt_id, current_user.id)
    
    if not receipt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Receipt not found"
        )

    return _to_receipt_response(receipt)


@router.patch("/{receipt_id}", response_model=ReceiptResponse)
async def update_receipt(
    receipt_id: str,
    update_data: ReceiptUpdate,
    current_user: UserResponse = Depends(get_current_user),
    db = Depends(get_db)
):
    """
    Update a draft receipt (owner only).
    
    - Only draft receipts can be updated
    - Requires version for optimistic locking
    - Backend calculates subtotal and total
    - Validates: non-negative values, split sum == quantity
    """
    repo = ReceiptRepository(db)
    
    try:
        receipt = await repo.update_receipt(receipt_id, current_user.id, update_data)
        
        if not receipt:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Receipt not found or you are not the owner"
            )
        
        return _to_receipt_response(receipt)
        
    except ReceiptValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/{receipt_id}/members", response_model=ReceiptResponse, status_code=status.HTTP_201_CREATED)
async def add_member(
    receipt_id: str,
    member_data: MemberAdd,
    current_user: UserResponse = Depends(get_current_user),
    db = Depends(get_db)
):
    """
    Add a member to a receipt by email (owner only).
    
    - Email must exist in the system
    - Cannot add duplicate members
    - Receipt must be draft status
    """
    receipt_repo = ReceiptRepository(db)
    user_repo = UserRepository(db)
    
    # Verify current user is owner
    receipt = await receipt_repo.get_receipt(receipt_id, current_user.id)
    if not receipt or str(receipt.owner_id) != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Receipt not found or you are not the owner"
        )
    
    # Check receipt is draft
    if receipt.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot add members to non-draft receipt"
        )
    
    # Find user by email
    user = await user_repo.get_user_by_email(member_data.email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with email {member_data.email} not found"
        )
    
    # Add member
    updated_receipt = await receipt_repo.add_member(receipt_id, str(user.id))
    
    if updated_receipt is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Member already exists in receipt or error adding member"
        )
    
    return _to_receipt_response(updated_receipt)


@router.get("/{receipt_id}/members", response_model=List[MemberResponse])
async def get_members(
    receipt_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db = Depends(get_db)
):
    """Get all members of a receipt."""
    receipt_repo = ReceiptRepository(db)
    
    # Verify user has access
    receipt = await receipt_repo.get_receipt(receipt_id, current_user.id)
    if not receipt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Receipt not found"
        )
    
    members = await receipt_repo.get_members(receipt_id)
    if members is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Receipt not found"
        )
    
    return [
        MemberResponse(
            user_id=str(m.user_id),
            role=m.role,
            joined_at=m.joined_at
        )
        for m in members
    ]


@router.delete("/{receipt_id}/members/{user_id}")
async def remove_member(
    receipt_id: str,
    user_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db = Depends(get_db)
):
    """
    Remove a member from a receipt (owner only).
    
    - Cannot remove if member has splits, payments, or ledger entries
    - Receipt must be draft status
    """
    receipt_repo = ReceiptRepository(db)
    
    # Verify current user is owner
    receipt = await receipt_repo.get_receipt(receipt_id, current_user.id)
    if not receipt or str(receipt.owner_id) != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Receipt not found or you are not the owner"
        )
    
    # Check receipt is draft
    if receipt.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove members from non-draft receipt"
        )
    
    try:
        updated_receipt = await receipt_repo.remove_member(receipt_id, user_id)
        
        if updated_receipt is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Member not found in receipt"
            )
        
        return {"success": True, "message": f"Member {user_id} removed"}
        
    except ReceiptValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/{receipt_id}/finalize", response_model=ReceiptFinalizeResponse)
async def finalize_receipt(
    receipt_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db = Depends(get_db)
):
    """
    Finalize a receipt: lock it and generate immutable ledger entries.
    
    Requirements:
    - Current user must be receipt owner
    - Receipt must be in draft status
    - All items must have valid splits
    - Payments must sum to total_cents
    
    Returns receipt with generated ledger entries.
    """
    receipt_repo = ReceiptRepository(db)
    
    # Verify ownership
    receipt = await receipt_repo.get_receipt(receipt_id, current_user.id)
    if not receipt or str(receipt.owner_id) != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Receipt not found or you are not the owner"
        )
    
    try:
        # Finalize and generate ledger
        finalized_receipt, ledger_entries = await receipt_repo.finalize_receipt(receipt_id)
        
        if not finalized_receipt:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to finalize receipt"
            )
        
        # Build response with ledger entries
        ledger_response = [
            LedgerEntryResponse(
                **{
                    **entry.model_dump(by_alias=True),
                    "id": str(entry.id) if entry.id else None
                }
            )
            for entry in ledger_entries
        ]
        
        return ReceiptFinalizeResponse(
            **{
                **{
                    "id": str(finalized_receipt.id),
                    "owner_id": str(finalized_receipt.owner_id),
                    "title": finalized_receipt.title,
                    "status": finalized_receipt.status.value,
                    "total_cents": finalized_receipt.total_cents,
                    "version": finalized_receipt.version,
                    "updated_at": finalized_receipt.updated_at,
                    "ledger_entries": ledger_response
                }
            }
        )
    
    except ReceiptValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Finalization failed: {str(e)}"
        )


@router.post("/{receipt_id}/unfinalize", response_model=ReceiptResponse)
async def unfinalize_receipt(
    receipt_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db = Depends(get_db)
):
    """Unfinalize a receipt (owner only)."""
    receipt_repo = ReceiptRepository(db)

    receipt = await receipt_repo.get_receipt(receipt_id, current_user.id)
    if not receipt or str(receipt.owner_id) != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Receipt not found or you are not the owner"
        )

    try:
        updated = await receipt_repo.unfinalize_receipt(receipt_id, current_user.id)
        if not updated:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Receipt not found or you are not the owner"
            )
        return _to_receipt_response(updated)
    except ReceiptValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.delete("/{receipt_id}")
async def delete_receipt(
    receipt_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db = Depends(get_db)
):
    """
    Soft delete a receipt (owner only).
    
    Returns 204 No Content on success.
    Returns 404 if receipt not found or user is not owner.
    """
    receipt_repo = ReceiptRepository(db)
    deleted = await receipt_repo.soft_delete_receipt(receipt_id, current_user.id)
    
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Receipt not found or you are not the owner"
        )
    
    return {"success": True}