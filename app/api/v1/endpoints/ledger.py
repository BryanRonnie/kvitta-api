from typing import List
from fastapi import APIRouter, HTTPException, Depends
from app.schemas.ledger import UserBalanceResponse, LedgerEntryResponse
from app.services.ledger_service import LedgerService
from app.models.user import User
from app.api.v1.endpoints.auth import get_current_user
from app.db.session import get_database
from bson import ObjectId

router = APIRouter()

@router.get("/balance", response_model=UserBalanceResponse)
async def get_my_balance(current_user: User = Depends(get_current_user)):
    """Get current user's balance"""
    return await LedgerService.get_user_balance(str(current_user.id))

@router.get("/balance/{user_id}", response_model=UserBalanceResponse)
async def get_balance(
    user_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get balance for a specific user"""
    return await LedgerService.get_user_balance(user_id)

@router.get("/receipt/{receipt_id}", response_model=List[LedgerEntryResponse])
async def get_receipt_ledger(
    receipt_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get ledger entries for a specific receipt"""
    db = await get_database()
    cursor = db.ledger_entries.find({"receipt_id": ObjectId(receipt_id)})
    return [doc async for doc in cursor]
