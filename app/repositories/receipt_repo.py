from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
from datetime import datetime, timezone
from typing import Optional

from app.models.receipt import Receipt, Participant, Item, Split, Payment
from app.schemas.receipt import ReceiptCreate, ReceiptUpdate
from app.utils.receipt_validation import (
    validate_items,
    validate_payments,
    calculate_subtotal,
    calculate_total,
    ReceiptValidationError
)


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
            "comments": receipt_data.comments,
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

    async def update_receipt(
        self,
        receipt_id: str,
        user_id: str,
        update_data: ReceiptUpdate
    ) -> Optional[Receipt]:
        """
        Update a receipt (draft only).
        
        Returns None if:
        - Receipt not found
        - User is not owner
        - Status is not draft
        - Version mismatch (409 conflict)
        
        Raises ReceiptValidationError for validation failures.
        """
        try:
            # First, get the receipt to check status and ownership
            existing = await self.collection.find_one({
                "_id": ObjectId(receipt_id),
                "owner_id": ObjectId(user_id),
                "is_deleted": False
            })
            
            if not existing:
                return None
            
            # Check if draft
            if existing["status"] != "draft":
                raise ReceiptValidationError("Cannot update non-draft receipt")
            
            # Check version for optimistic locking
            if existing["version"] != update_data.version:
                raise ReceiptValidationError(
                    f"Version conflict: expected {update_data.version}, current {existing['version']}"
                )
            
            # Build update dict
            updates = {}
            
            # Simple fields (each can be updated independently for autosave)
            if update_data.title is not None:
                updates["title"] = update_data.title
            if update_data.description is not None:
                updates["description"] = update_data.description
            if update_data.comments is not None:
                updates["comments"] = update_data.comments
            if update_data.folder_id is not None:
                updates["folder_id"] = ObjectId(update_data.folder_id) if update_data.folder_id else None
            
            # Items - validate and convert
            if update_data.items is not None:
                validate_items(update_data.items)
                items = [
                    Item(
                        item_id=ObjectId(),
                        name=item.name,
                        unit_price_cents=item.unit_price_cents,
                        quantity=item.quantity,
                        splits=[
                            Split(
                                user_id=ObjectId(split.user_id),
                                share_quantity=split.share_quantity
                            )
                            for split in item.splits
                        ]
                    )
                    for item in update_data.items
                ]
                updates["items"] = [item.model_dump(mode="python") for item in items]
            
            # Payments - validate and convert
            if update_data.payments is not None:
                payments = [
                    Payment(
                        user_id=ObjectId(p.user_id),
                        amount_paid_cents=p.amount_paid_cents
                    )
                    for p in update_data.payments
                ]
                validate_payments(payments, 0)  # Basic validation only
                updates["payments"] = [p.model_dump(mode="python") for p in payments]
            
            # Tax and tip
            tax_cents = update_data.tax_cents if update_data.tax_cents is not None else existing.get("tax_cents", 0)
            tip_cents = update_data.tip_cents if update_data.tip_cents is not None else existing.get("tip_cents", 0)
            
            if update_data.tax_cents is not None:
                if update_data.tax_cents < 0:
                    raise ReceiptValidationError("Tax cannot be negative")
                updates["tax_cents"] = update_data.tax_cents
                
            if update_data.tip_cents is not None:
                if update_data.tip_cents < 0:
                    raise ReceiptValidationError("Tip cannot be negative")
                updates["tip_cents"] = update_data.tip_cents
            
            # Calculate subtotal and total
            items_to_calc = update_data.items if update_data.items is not None else []
            if items_to_calc or update_data.items is not None:
                subtotal = calculate_subtotal(items_to_calc) if items_to_calc else 0
                updates["subtotal_cents"] = subtotal
                updates["total_cents"] = calculate_total(subtotal, tax_cents, tip_cents)
            elif update_data.tax_cents is not None or update_data.tip_cents is not None:
                # Recalculate total if tax or tip changed
                subtotal = existing.get("subtotal_cents", 0)
                updates["total_cents"] = calculate_total(subtotal, tax_cents, tip_cents)
            
            # Increment version and update timestamp
            updates["version"] = existing["version"] + 1
            updates["updated_at"] = datetime.now(timezone.utc)
            updates["updated_by"] = ObjectId(user_id)
            
            # Perform update with version check
            result = await self.collection.find_one_and_update(
                {
                    "_id": ObjectId(receipt_id),
                    "version": update_data.version  # Optimistic lock
                },
                {"$set": updates},
                return_document=True
            )
            
            if result:
                return Receipt(**result)
            else:
                # Version mismatch during update
                raise ReceiptValidationError("Version conflict during update")
                
        except ReceiptValidationError:
            raise
        except Exception:
            return None

    async def add_member(self, receipt_id: str, user_id: str) -> Optional[Receipt]:
        """Add a member to the receipt."""
        try:
            user_oid = ObjectId(user_id)
            
            # Check if already a member
            existing = await self.collection.find_one({
                "_id": ObjectId(receipt_id),
                "participants.user_id": user_oid
            })
            
            if existing:
                return None  # Already a member
            
            # Add member
            result = await self.collection.find_one_and_update(
                {"_id": ObjectId(receipt_id)},
                {
                    "$push": {
                        "participants": Participant(
                            user_id=user_oid,
                            role="member",
                            joined_at=datetime.now(timezone.utc)
                        ).model_dump(mode="python")
                    },
                    "$set": {"updated_at": datetime.now(timezone.utc)}
                },
                return_document=True
            )
            
            if result:
                return Receipt(**result)
        except Exception:
            return None
        return None

    async def remove_member(self, receipt_id: str, user_id: str) -> Optional[Receipt]:
        """Remove a member from the receipt."""
        try:
            user_oid = ObjectId(user_id)
            
            # Check if member has splits
            receipt = await self.collection.find_one({"_id": ObjectId(receipt_id)})
            if not receipt:
                return None
            
            # Check splits
            for item in receipt.get("items", []):
                for split in item.get("splits", []):
                    if split["user_id"] == user_oid:
                        raise ReceiptValidationError(
                            "Cannot remove member: has splits in items"
                        )
            
            # Check payments
            for payment in receipt.get("payments", []):
                if payment["user_id"] == user_oid:
                    raise ReceiptValidationError(
                        "Cannot remove member: has recorded payments"
                    )
            
            # Remove member
            result = await self.collection.find_one_and_update(
                {"_id": ObjectId(receipt_id)},
                {
                    "$pull": {"participants": {"user_id": user_oid}},
                    "$set": {"updated_at": datetime.now(timezone.utc)}
                },
                return_document=True
            )
            
            if result:
                return Receipt(**result)
        except ReceiptValidationError:
            raise
        except Exception:
            return None
        return None

    async def get_members(self, receipt_id: str) -> Optional[list[Participant]]:
        """Get all members of a receipt."""
        try:
            doc = await self.collection.find_one({"_id": ObjectId(receipt_id)})
            if doc:
                return [
                    Participant(**p) for p in doc.get("participants", [])
                ]
        except Exception:
            return None
        return None
