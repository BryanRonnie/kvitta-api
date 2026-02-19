from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
from datetime import datetime, timezone
from typing import Optional

from app.models.receipt import Receipt, Participant
from app.schemas.receipt import ReceiptCreate


class ReceiptRepository:
    """Receipt database operations."""

    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db["receipts"]

    async def create_receipt(self, receipt_data: ReceiptCreate, owner_id: str) -> Receipt:
        """Create a new draft receipt with owner as first participant."""
        owner_oid = ObjectId(owner_id)
        
        # Owner automatically added as participant with "owner" role
        owner_participant = Participant(
            user_id=owner_oid,
            role="owner",
            joined_at=datetime.now(timezone.utc)
        )
        
        receipt_dict = {
            "owner_id": owner_oid,
            "title": receipt_data.title,
            "description": receipt_data.description,
            "folder_id": ObjectId(receipt_data.folder_id) if receipt_data.folder_id else None,
            "status": "draft",
            "participants": [owner_participant.model_dump(mode="python")],
            "items": [],
            "payments": [],
            "subtotal_cents": 0,
            "tax_cents": 0,
            "tip_cents": 0,
            "total_cents": 0,
            "version": 1,
            "created_by": owner_oid,
            "updated_by": owner_oid,
            "is_deleted": False,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }

        result = await self.collection.insert_one(receipt_dict)
        receipt_dict["_id"] = result.inserted_id
        return Receipt(**receipt_dict)

    async def get_receipt(self, receipt_id: str, user_id: str) -> Optional[Receipt]:
        """Get a receipt by id if user is owner or participant."""
        try:
            doc = await self.collection.find_one({
                "_id": ObjectId(receipt_id),
                "is_deleted": False,
                "$or": [
                    {"owner_id": ObjectId(user_id)},
                    {"participants.user_id": ObjectId(user_id)}
                ]
            })
            if doc:
                return Receipt(**doc)
        except Exception:
            return None
        return None

    async def list_receipts(self, user_id: str) -> list[Receipt]:
        """List receipts where user is owner or participant."""
        cursor = self.collection.find({
            "is_deleted": False,
            "$or": [
                {"owner_id": ObjectId(user_id)},
                {"participants.user_id": ObjectId(user_id)}
            ]
        }).sort("created_at", -1)
        
        receipts = await cursor.to_list(None)
        return [Receipt(**doc) for doc in receipts]
