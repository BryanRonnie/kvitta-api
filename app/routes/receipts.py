from fastapi import APIRouter, Depends, HTTPException, status
from typing import List

from app.db.mongo import get_db
from app.core.auth import get_current_user
from app.models.user import UserResponse
from app.schemas.receipt import ReceiptCreate, ReceiptResponse, ReceiptUpdate
from app.repositories.receipt_repo import ReceiptRepository
from app.utils.receipt_validation import ReceiptValidationError

router = APIRouter(prefix="/receipts", tags=["receipts"])


@router.post("", response_model=ReceiptResponse, status_code=status.HTTP_201_CREATED)
async def create_receipt(
    receipt_data: ReceiptCreate,
    current_user: UserResponse = Depends(get_current_user),
    db = Depends(get_db)
):
    """Create a new draft receipt. Owner automatically added as participant."""
    repo = ReceiptRepository(db)
    receipt = await repo.create_receipt(receipt_data, current_user.id)

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
        items=[],
        payments=[],
        subtotal_cents=receipt.subtotal_cents,
        tax_cents=receipt.tax_cents,
        tip_cents=receipt.tip_cents,
        total_cents=receipt.total_cents,
        version=receipt.version,
        created_at=receipt.created_at,
        updated_at=receipt.updated_at
    )


@router.get("", response_model=List[ReceiptResponse])
async def list_receipts(
    current_user: UserResponse = Depends(get_current_user),
    db = Depends(get_db)
):
    """List receipts where user is owner or participant."""
    repo = ReceiptRepository(db)
    receipts = await repo.list_receipts(current_user.id)

    return [
        ReceiptResponse(
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
            items=[],
            payments=[],
            subtotal_cents=receipt.subtotal_cents,
            tax_cents=receipt.tax_cents,
            tip_cents=receipt.tip_cents,
            total_cents=receipt.total_cents,
            version=receipt.version,
            created_at=receipt.created_at,
            updated_at=receipt.updated_at
        )
        for receipt in receipts
    ]


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
        items=[],
        payments=[],
        subtotal_cents=receipt.subtotal_cents,
        tax_cents=receipt.tax_cents,
        tip_cents=receipt.tip_cents,
        total_cents=receipt.total_cents,
        version=receipt.version,
        created_at=receipt.created_at,
        updated_at=receipt.updated_at
    )


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
            payments=[
                {
                    "user_id": str(p.user_id),
                    "amount_paid_cents": p.amount_paid_cents
                }
                for p in receipt.payments
            ],
            subtotal_cents=receipt.subtotal_cents,
            tax_cents=receipt.tax_cents,
            tip_cents=receipt.tip_cents,
            total_cents=receipt.total_cents,
            version=receipt.version,
            created_at=receipt.created_at,
            updated_at=receipt.updated_at
        )
        
    except ReceiptValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
