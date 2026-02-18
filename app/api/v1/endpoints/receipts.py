from typing import List
from fastapi import APIRouter, HTTPException, Depends
from app.schemas.receipt import ReceiptCreate, ReceiptUpdate, ReceiptResponse
from app.services.receipt_service import ReceiptService

router = APIRouter()

@router.post("/", response_model=ReceiptResponse)
async def create_receipt(receipt_in: ReceiptCreate, owner_id: str):
    receipt = await ReceiptService.create(receipt_in, owner_id)
    return receipt

@router.get("/{receipt_id}", response_model=ReceiptResponse)
async def get_receipt(receipt_id: str):
    receipt = await ReceiptService.get(receipt_id)
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")
    return receipt

@router.patch("/{receipt_id}", response_model=ReceiptResponse)
async def update_receipt(receipt_id: str, receipt_in: ReceiptUpdate, user_id: str):
    receipt = await ReceiptService.update(receipt_id, receipt_in, user_id)
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found or invalid update")
    return receipt

@router.post("/{receipt_id}/finalize", response_model=ReceiptResponse)
async def finalize_receipt(receipt_id: str, user_id: str):
    receipt = await ReceiptService.finalize(receipt_id, user_id)
    return receipt
