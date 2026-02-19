from typing import List
from fastapi import APIRouter, HTTPException, Depends, Body
from pydantic import BaseModel
from app.schemas.receipt import ReceiptCreate, ReceiptUpdate, ReceiptResponse
from app.services.receipt_service import ReceiptService
from app.models.user import User
from app.api.v1.endpoints.auth import get_current_user

router = APIRouter()

class EmailRequest(BaseModel):
    email: str

class FolderMoveRequest(BaseModel):
    folder_id: str | None = None

class RoleUpdateRequest(BaseModel):
    role: str

@router.get("/", response_model=List[ReceiptResponse])
async def list_receipts(
    current_user: User = Depends(get_current_user)
):
    """List all receipts for the current user"""
    receipts = await ReceiptService.list_by_user(str(current_user.id))
    return receipts

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

@router.delete("/{receipt_id}")
async def delete_receipt(
    receipt_id: str,
    current_user: User = Depends(get_current_user)
):
    """Delete a receipt"""
    success = await ReceiptService.delete(receipt_id, str(current_user.id))
    if not success:
        raise HTTPException(status_code=404, detail="Receipt not found or unauthorized")
    return {"message": "Receipt deleted successfully"}

@router.post("/{receipt_id}/finalize", response_model=ReceiptResponse)
async def finalize_receipt(
    receipt_id: str,
    current_user: User = Depends(get_current_user)
):
    """Finalize a receipt and create ledger entries"""
    receipt = await ReceiptService.finalize(receipt_id, str(current_user.id))
    return receipt

@router.post("/{receipt_id}/members", response_model=ReceiptResponse)
async def add_member(
    receipt_id: str,
    request: EmailRequest,
    current_user: User = Depends(get_current_user)
):
    """Add a member to a receipt"""
    receipt = await ReceiptService.add_member(receipt_id, request.email, str(current_user.id))
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")
    return receipt

@router.patch("/{receipt_id}/members/{email}", response_model=ReceiptResponse)
async def update_member_role(
    receipt_id: str,
    email: str,
    request: RoleUpdateRequest,
    current_user: User = Depends(get_current_user)
):
    """Update member role in a receipt"""
    receipt = await ReceiptService.update_member_role(receipt_id, email, request.role, str(current_user.id))
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt or member not found")
    return receipt

@router.delete("/{receipt_id}/members/{email}", response_model=ReceiptResponse)
async def remove_member(
    receipt_id: str,
    email: str,
    current_user: User = Depends(get_current_user)
):
    """Remove a member from a receipt"""
    receipt = await ReceiptService.remove_member(receipt_id, email, str(current_user.id))
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt or member not found")
    return receipt

@router.post("/{receipt_id}/leave")
async def leave_receipt(
    receipt_id: str,
    current_user: User = Depends(get_current_user)
):
    """Remove yourself from a receipt"""
    success = await ReceiptService.remove_member(receipt_id, current_user.email, str(current_user.id))
    if not success:
        raise HTTPException(status_code=404, detail="Receipt not found")
    return {"message": "Successfully left receipt"}

@router.patch("/{receipt_id}/move")
async def move_receipt(
    receipt_id: str,
    request: FolderMoveRequest,
    current_user: User = Depends(get_current_user)
):
    """Move receipt to a folder"""
    receipt = await ReceiptService.move_to_folder(receipt_id, request.folder_id, str(current_user.id))
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")
    return receipt
