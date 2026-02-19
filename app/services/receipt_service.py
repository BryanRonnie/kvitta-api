from typing import Optional, List
from app.db.session import get_database
from app.models.receipt import Receipt, ReceiptStatus, Participant
from app.schemas.receipt import ReceiptCreate, ReceiptUpdate
from app.services.ledger_service import LedgerService
from bson import ObjectId
from fastapi import HTTPException
from datetime import datetime, timezone

class ReceiptService:
    @staticmethod
    async def list_by_user(user_id: str) -> List[Receipt]:
        """List all receipts where user is a participant or owner"""
        db = await get_database()
        query = {
            "$or": [
                {"owner_id": ObjectId(user_id)},
                {"participants.user_id": ObjectId(user_id)}
            ],
            "is_deleted": False
        }
        docs = await db.receipts.find(query).sort("created_at", -1).to_list(None)
        return [Receipt(**doc) for doc in docs]

    @staticmethod
    async def create(receipt_in: ReceiptCreate, owner_id: str) -> Receipt:
        db = await get_database()
        
        receipt_dict = receipt_in.model_dump()
        receipt_dict["owner_id"] = ObjectId(owner_id)
        receipt_dict["created_by"] = ObjectId(owner_id)
        receipt_dict["updated_by"] = ObjectId(owner_id)
        receipt_dict["participants"] = [Participant(user_id=ObjectId(owner_id))]
        
        receipt = Receipt(**receipt_dict)
        
        result = await db.receipts.insert_one(receipt.model_dump(by_alias=True))
        receipt.id = result.inserted_id
        
        return receipt

    @staticmethod
    async def get(receipt_id: str) -> Optional[Receipt]:
        db = await get_database()
        try:
            doc = await db.receipts.find_one({"_id": ObjectId(receipt_id)})
            if doc:
                return Receipt(**doc)
        except:
            pass
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
        update_data["updated_at"] = datetime.now(timezone.utc)

        await db.receipts.update_one(
            {"_id": ObjectId(receipt_id)},
            {"$set": update_data}
        )
        
        return await ReceiptService.get(receipt_id)

    @staticmethod
    async def delete(receipt_id: str, user_id: str) -> bool:
        """Soft delete a receipt"""
        db = await get_database()
        
        receipt = await ReceiptService.get(receipt_id)
        if not receipt or receipt.owner_id != ObjectId(user_id):
            return False
        
        result = await db.receipts.update_one(
            {"_id": ObjectId(receipt_id)},
            {"$set": {"is_deleted": True, "updated_by": ObjectId(user_id), "updated_at": datetime.now(timezone.utc)}}
        )
        
        return result.modified_count > 0

    @staticmethod
    async def add_member(receipt_id: str, email: str, user_id: str) -> Optional[Receipt]:
        """Add a member to a receipt by email"""
        db = await get_database()
        
        receipt = await ReceiptService.get(receipt_id)
        if not receipt or receipt.owner_id != ObjectId(user_id):
            return None
        
        # Find user by email
        user_doc = await db.users.find_one({"email": email})
        if not user_doc:
            raise HTTPException(status_code=404, detail=f"User with email {email} not found")
        
        member_id = user_doc["_id"]
        
        # Check if already a member
        existing = any(p.user_id == member_id for p in receipt.participants)
        if existing:
            raise HTTPException(status_code=409, detail="User is already a member")
        
        participant = Participant(user_id=member_id)
        
        await db.receipts.update_one(
            {"_id": ObjectId(receipt_id)},
            {
                "$push": {"participants": participant.model_dump(by_alias=True)},
                "$set": {"updated_by": ObjectId(user_id), "updated_at": datetime.now(timezone.utc)}
            }
        )
        
        return await ReceiptService.get(receipt_id)

    @staticmethod
    async def remove_member(receipt_id: str, email: str, user_id: str) -> Optional[Receipt]:
        """Remove a member from a receipt"""
        db = await get_database()
        
        receipt = await ReceiptService.get(receipt_id)
        if not receipt:
            return None
        
        # Find user by email
        user_doc = await db.users.find_one({"email": email})
        if not user_doc:
            return None
        
        member_id = user_doc["_id"]
        
        await db.receipts.update_one(
            {"_id": ObjectId(receipt_id)},
            {
                "$pull": {"participants": {"user_id": member_id}},
                "$set": {"updated_by": ObjectId(user_id), "updated_at": datetime.now(timezone.utc)}
            }
        )
        
        return await ReceiptService.get(receipt_id)

    @staticmethod
    async def update_member_role(receipt_id: str, email: str, role: str, user_id: str) -> Optional[Receipt]:
        """Update member role (for future use when roles are implemented)"""
        # For now, just return the receipt since we don't have role concept yet
        return await ReceiptService.get(receipt_id)

    @staticmethod
    async def move_to_folder(receipt_id: str, folder_id: str | None, user_id: str) -> Optional[Receipt]:
        """Move receipt to a folder"""
        db = await get_database()
        
        receipt = await ReceiptService.get(receipt_id)
        if not receipt or receipt.owner_id != ObjectId(user_id):
            return None
        
        update_data = {
            "folder_id": ObjectId(folder_id) if folder_id else None,
            "updated_by": ObjectId(user_id),
            "updated_at": datetime.now(timezone.utc)
        }
        
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
