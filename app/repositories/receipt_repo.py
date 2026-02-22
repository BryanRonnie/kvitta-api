from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
from datetime import datetime, timezone
from typing import Optional, Tuple, List

from app.models.receipt import Receipt, Participant, Item, Split, Payment, Charge
from app.schemas.receipt import ReceiptCreate, ReceiptUpdate
from app.utils.receipt_validation import (
    validate_items,
    validate_charges,
    validate_payments,
    calculate_subtotal,
    calculate_charges_total,
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
            "charges": [],
            "settle_summary": [],
            "payments": [],
            "subtotal_cents": 0,
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

    def _build_settle_summary(
        self,
        participants: list[Participant],
        items: list[Item],
        charges: list[Charge],
        payments: list[Payment]
    ) -> list[dict]:
        """Compute per-user settle summary from items, charges, and payments."""
        if not participants:
            return []

        liabilities: dict[str, int] = {}
        for participant in participants:
            liabilities[str(participant.user_id)] = 0

        payments_by_user: dict[str, int] = {}
        for payment in payments:
            user_id = str(payment.user_id)
            payments_by_user[user_id] = payments_by_user.get(user_id, 0) + payment.amount_paid_cents

        # Item liabilities
        for item in items:
            if not item.splits:
                continue

            item_subtotal = item.unit_price_cents * item.quantity
            item_split_qty = sum(s.share_quantity for s in item.splits)

            if item_split_qty == 0:
                continue

            for split in item.splits:
                user_id = str(split.user_id)
                item_share_ratio = split.share_quantity / item_split_qty
                item_liability = int(item_subtotal * item_share_ratio)
                liabilities[user_id] = liabilities.get(user_id, 0) + item_liability

        # Charge liabilities
        for charge in charges:
            if charge.splits:
                for split in charge.splits:
                    user_id = str(split.user_id)
                    charge_liability = int(charge.unit_price_cents * split.share_quantity)
                    liabilities[user_id] = liabilities.get(user_id, 0) + charge_liability
            else:
                num_participants = len(participants)
                if num_participants > 0:
                    per_user = charge.unit_price_cents // num_participants
                    remainder = charge.unit_price_cents % num_participants

                    for index, participant in enumerate(participants):
                        user_id = str(participant.user_id)
                        extra = 1 if index < remainder else 0
                        liabilities[user_id] = liabilities.get(user_id, 0) + per_user + extra

        summary: list[dict] = []
        for participant in participants:
            user_id = str(participant.user_id)
            liability_cents = liabilities.get(user_id, 0)
            paid_cents = payments_by_user.get(user_id, 0)
            net_cents = liability_cents - paid_cents
            amount_cents = max(net_cents, 0)
            is_settled = net_cents == 0
            if net_cents < 0:
                status = "creditor"
            elif net_cents == 0:
                status = "settled"
            else:
                status = "pending"
            summary.append({
                "user_id": user_id,
                "amount_cents": amount_cents,
                "paid_cents": paid_cents,
                "net_cents": net_cents,
                "settled_amount_cents": 0,
                "is_settled": is_settled,
                "settled_at": None,
                "status": status
            })

        return summary

    async def update_settle_summary_from_ledger(self, receipt_id: str) -> bool:
        """Update settle summary using ledger settlements for a receipt."""
        try:
            if not ObjectId.is_valid(receipt_id):
                return False
            receipt_oid = ObjectId(receipt_id)
            receipt_doc = await self.collection.find_one({
                "_id": receipt_oid,
                "is_deleted": False
            })
            if not receipt_doc:
                return False

            participants = [Participant(**p) for p in receipt_doc.get("participants", [])]
            items = [Item(**item) for item in receipt_doc.get("items", [])]
            charges = [Charge(**charge) for charge in receipt_doc.get("charges", [])]
            payments = [Payment(**payment) for payment in receipt_doc.get("payments", [])]
            base_summary = self._build_settle_summary(participants, items, charges, payments)

            from app.repositories.ledger_repo import LedgerRepository
            ledger_repo = LedgerRepository(self.db)
            entries = await ledger_repo.get_ledger_by_receipt(str(receipt_doc.get("_id")))

            settled_by_debtor: dict[str, int] = {}
            for entry in entries:
                if entry.is_deleted:
                    continue
                settled_by_debtor[entry.debtor_id] = (
                    settled_by_debtor.get(entry.debtor_id, 0) + entry.settled_amount_cents
                )

            now = datetime.now(timezone.utc)
            for summary in base_summary:
                user_id = summary["user_id"]
                settled_amount = min(
                    summary["amount_cents"],
                    settled_by_debtor.get(user_id, 0)
                )
                summary["settled_amount_cents"] = settled_amount
                summary["is_settled"] = settled_amount >= summary["amount_cents"]
                if summary["is_settled"] and summary["amount_cents"] > 0:
                    summary["status"] = "settled"
                    summary["settled_at"] = now
                elif settled_amount > 0:
                    summary["status"] = "partially_settled"
                    summary["settled_at"] = None
                else:
                    summary["status"] = "pending"
                    summary["settled_at"] = None

            result = await self.collection.update_one(
                {"_id": receipt_oid},
                {
                    "$set": {
                        "settle_summary": base_summary,
                        "updated_at": now
                    }
                }
            )
            return result.modified_count > 0
        except Exception:
            return False

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
            items_models = None
            charges_models = None
            
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
                        taxable=item.taxable,
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
                items_models = items
            
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
            
            # Charges - validate and convert
            if update_data.charges is not None:
                validate_charges(update_data.charges)
                charges = [
                    Charge(
                        charge_id=charge.charge_id if hasattr(charge, 'charge_id') else str(ObjectId()),
                        name=charge.name,
                        unit_price_cents=charge.unit_price_cents,
                        taxable=charge.taxable,
                        splits=[
                            Split(
                                user_id=ObjectId(split.user_id),
                                share_quantity=split.share_quantity
                            )
                            for split in charge.splits
                        ]
                    )
                    for charge in update_data.charges
                ]
                updates["charges"] = [charge.model_dump(mode="python") for charge in charges]
                charges_models = charges
            
            # Calculate subtotal and total
            items_to_calc = update_data.items if update_data.items is not None else []
            charges_models_for_calc = charges_models
            if charges_models_for_calc is None:
                charges_models_for_calc = [Charge(**charge) for charge in existing.get("charges", [])]
            
            if items_to_calc or update_data.items is not None:
                subtotal = calculate_subtotal(items_to_calc) if items_to_calc else 0
                updates["subtotal_cents"] = subtotal
                updates["total_cents"] = calculate_total(subtotal, charges_models_for_calc)
            elif update_data.charges is not None:
                # Recalculate total if charges changed
                subtotal = existing.get("subtotal_cents", 0)
                updates["total_cents"] = calculate_total(subtotal, charges_models_for_calc)

            participants_models = [Participant(**p) for p in existing.get("participants", [])]
            if items_models is None:
                items_models = [Item(**item) for item in existing.get("items", [])]
            if charges_models is None:
                charges_models = charges_models_for_calc
            payments_models = []
            if update_data.payments is not None:
                payments_models = [
                    Payment(
                        user_id=ObjectId(p.user_id),
                        amount_paid_cents=p.amount_paid_cents
                    )
                    for p in update_data.payments
                ]
            else:
                payments_models = [Payment(**p) for p in existing.get("payments", [])]
            updates["settle_summary"] = self._build_settle_summary(
                participants_models,
                items_models,
                charges_models,
                payments_models
            )
            
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

    async def finalize_receipt(self, receipt_id: str) -> Tuple[Optional[Receipt], Optional[list]]:
        """
        Finalize a receipt: lock it and generate ledger entries.
        
        Process:
        1. Fetch receipt and validate draft status
        2. Validate payments sum equals total_cents
        3. Update receipt status to "finalized"
        4. Create ledger entries via LedgerRepository
        
        Returns: (receipt, ledger_entries) or (None, None) if failed
        Raises ReceiptValidationError if validation fails
        """
        try:
            receipt_oid = ObjectId(receipt_id)
        except:
            raise ReceiptValidationError("Invalid receipt ID")
        
        # Fetch receipt
        doc = await self.collection.find_one({"_id": receipt_oid})
        if not doc:
            raise ReceiptValidationError("Receipt not found")
        
        receipt = Receipt(**doc)
        
        # Validate draft status
        if receipt.status.value != "draft":
            raise ReceiptValidationError(
                f"Cannot finalize receipt with status '{receipt.status.value}'. Must be 'draft'."
            )
        
        # Validate payments sum equals total
        total_paid = sum(p.amount_paid_cents for p in receipt.payments)
        if total_paid != receipt.total_cents:
            raise ReceiptValidationError(
                f"Payments sum ({total_paid} cents) does not equal total ({receipt.total_cents} cents)"
            )
        
        # Update receipt status to finalized
        now = datetime.now(timezone.utc)
        result = await self.collection.find_one_and_update(
            {"_id": receipt_oid},
            {
                "$set": {
                    "status": "finalized",
                    "updated_at": now
                }
            },
            return_document=True
        )
        
        if not result:
            raise ReceiptValidationError("Failed to finalize receipt")
        
        finalized_receipt = Receipt(**result)
        
        # Create ledger entries
        from app.repositories.ledger_repo import LedgerRepository
        ledger_repo = LedgerRepository(self.db)
        ledger_entries = await ledger_repo.insert_ledger_entries(finalized_receipt)
        
        return finalized_receipt, ledger_entries

    async def unfinalize_receipt(self, receipt_id: str, user_id: str) -> Optional[Receipt]:
        """Revert a finalized receipt back to draft and remove ledger entries."""
        try:
            receipt_oid = ObjectId(receipt_id)
            user_oid = ObjectId(user_id)
        except Exception:
            raise ReceiptValidationError("Invalid receipt ID")

        receipt_doc = await self.collection.find_one({
            "_id": receipt_oid,
            "owner_id": user_oid,
            "is_deleted": False
        })
        if not receipt_doc:
            return None

        if receipt_doc.get("status") != "finalized":
            raise ReceiptValidationError("Can only unfinalize a finalized receipt")

        from app.repositories.ledger_repo import LedgerRepository
        ledger_repo = LedgerRepository(self.db)
        await ledger_repo.delete_entries_for_receipt(receipt_id)

        now = datetime.now(timezone.utc)
        result = await self.collection.find_one_and_update(
            {
                "_id": receipt_oid,
                "owner_id": user_oid,
                "is_deleted": False
            },
            {
                "$set": {
                    "status": "draft",
                    "updated_at": now,
                    "updated_by": user_oid
                },
                "$inc": {"version": 1}
            },
            return_document=True
        )

        if result:
            return Receipt(**result)
        return None

    async def soft_delete_receipt(self, receipt_id: str, user_id: str) -> bool:
        """
        Soft delete a receipt (owner only).
        
        Returns True if deleted, False if not found or not owner.
        """
        try:
            result = await self.collection.update_one(
                {
                    "_id": ObjectId(receipt_id),
                    "owner_id": ObjectId(user_id),
                    "is_deleted": False
                },
                {
                    "$set": {
                        "is_deleted": True,
                        "updated_at": datetime.now(timezone.utc)
                    }
                }
            )
            return result.modified_count > 0
        except Exception:
            return False