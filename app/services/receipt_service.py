from typing import Optional
from app.db.session import get_database
from app.models.receipt import Receipt, ReceiptStatus
from app.schemas.receipt import ReceiptCreate, ReceiptUpdate
from app.services.ledger_service import LedgerService
from bson import ObjectId
from fastapi import HTTPException

class ReceiptService:
    @staticmethod
    async def create(receipt_in: ReceiptCreate, owner_id: str) -> Receipt:
        db = await get_database()
        
        receipt_dict = receipt_in.model_dump()
        receipt_dict["owner_id"] = ObjectId(owner_id)
        receipt_dict["created_by"] = ObjectId(owner_id)
        receipt_dict["updated_by"] = ObjectId(owner_id)
        
        # Calculate totals (simple version)
        # In a real app we'd validate items/splits here
        
        receipt = Receipt(**receipt_dict)
        
        result = await db.receipts.insert_one(receipt.model_dump(by_alias=True))
        receipt.id = result.inserted_id
        
        return receipt

    @staticmethod
    async def get(receipt_id: str) -> Optional[Receipt]:
        db = await get_database()
        doc = await db.receipts.find_one({"_id": ObjectId(receipt_id)})
        if doc:
            return Receipt(**doc)
        return None

    @staticmethod
    async def update(receipt_id: str, receipt_in: ReceiptUpdate, user_id: str) -> Optional[Receipt]:
        db = await get_database()
        
        existing = await db.receipts.find_one({"_id": ObjectId(receipt_id)})
        if not existing:
            return None
            
        existing_receipt = Receipt(**existing)
        
        if existing_receipt.status != ReceiptStatus.DRAFT:
            raise HTTPException(status_code=400, detail="Cannot update finalized receipt")
            
        update_data = receipt_in.model_dump(exclude_unset=True)
        update_data["updated_by"] = ObjectId(user_id)
        update_data["version"] = existing_receipt.version + 1
        
        # If items changed, recalculate totals (simplified)
        if "items" in update_data:
             # Logic to recalc logic here
             pass

        await db.receipts.update_one(
            {"_id": ObjectId(receipt_id)},
            {"$set": update_data}
        )
        
        return await ReceiptService.get(receipt_id)

    @staticmethod
    async def finalize(receipt_id: str, user_id: str) -> Receipt:
        db = await get_database()
        receipt = await ReceiptService.get(receipt_id)
        
        if not receipt:
            raise HTTPException(status_code=404, detail="Receipt not found")
            
        if receipt.status != ReceiptStatus.DRAFT:
            raise HTTPException(status_code=400, detail="Receipt already finalized")
            
        # Add validation logic here (totals match, etc)
        
        async with await db.client.start_session() as session:
            async with session.start_transaction():
               await db.receipts.update_one(
                   {"_id": ObjectId(receipt_id)},
                   {"$set": {"status": ReceiptStatus.FINALIZED, "updated_by": ObjectId(user_id)}},
                   session=session
               )
               
               updated_receipt = await ReceiptService.get(receipt_id)
               await LedgerService.generate_from_receipt(updated_receipt)
               
        return await ReceiptService.get(receipt_id)
