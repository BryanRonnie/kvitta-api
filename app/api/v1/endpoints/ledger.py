from typing import List
from fastapi import APIRouter, HTTPException
from app.schemas.ledger import UserBalanceResponse, LedgerEntryResponse
from app.services.ledger_service import LedgerService
from app.db.session import get_database
from bson import ObjectId

router = APIRouter()

@router.get("/balance/{user_id}", response_model=UserBalanceResponse)
async def get_balance(user_id: str):
    return await LedgerService.get_user_balance(user_id)

@router.get("/receipt/{receipt_id}", response_model=List[LedgerEntryResponse])
async def get_receipt_ledger(receipt_id: str):
    db = await get_database()
    cursor = db.ledger_entries.find({"receipt_id": ObjectId(receipt_id)})
    return [doc async for doc in cursor] # Simple conversion, schema validation handles _id
