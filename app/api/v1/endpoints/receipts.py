from typing import List
from fastapi import APIRouter, HTTPException, Depends
from app.schemas.receipt import ReceiptCreate, ReceiptUpdate, ReceiptResponse
from app.services.receipt_service import ReceiptService
from app.models.user import User
from app.api.v1.endpoints.auth import get_current_user

router = APIRouter()

@router.post("/", response_model=ReceiptResponse)
async def create_receipt(
    receipt_in: ReceiptCreate,
    current_user: User = Depends(get_current_user)
):
    """Create a new receipt"""
    receipt = await ReceiptService.create(receipt_in, str(current_user.id))
    return receipt

@router.get("/{receipt_id}", response_model=ReceiptResponse)
async def get_receipt(
    receipt_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get a receipt by ID"""
    receipt = await ReceiptService.get(receipt_id)
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")
    return receipt

@router.patch("/{receipt_id}", response_model=ReceiptResponse)
async def update_receipt(
    receipt_id: str,
    receipt_in: ReceiptUpdate,
    current_user: User = Depends(get_current_user)
):
    """Update a receipt"""
    receipt = await ReceiptService.update(receipt_id, receipt_in, str(current_user.id))
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found or invalid update")
    return receipt

@router.post("/{receipt_id}/finalize", response_model=ReceiptResponse)
async def finalize_receipt(
    receipt_id: str,
    current_user: User = Depends(get_current_user)
):
    """Finalize a receipt and create ledger entries"""
    receipt = await ReceiptService.finalize(receipt_id, str(current_user.id))
    return receipt
