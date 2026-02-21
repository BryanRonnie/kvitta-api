"""
LedgerRepository - Manages financial obligations.

Core algorithm:
1. Calculate per-user shares from receipt items
2. Allocate tax and tip proportionally
3. Determine who owes who (creditor is payer, debtor is non-payer)
4. Insert ledger entries
5. Track settlement status
"""

from typing import List, Optional, Dict, Tuple
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId

from app.models.ledger import LedgerEntry
from app.models.receipt import Receipt
from app.utils.receipt_validation import ReceiptValidationError


class LedgerRepository:
    """Repository for ledger entries (financial obligations)."""

    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db.ledger_entries

    async def insert_ledger_entries(self, receipt: Receipt) -> List[LedgerEntry]:
        """
        Create ledger entries from a finalized receipt.
        
        Algorithm:
        1. Calculate what each participant owes for their shares
        2. Subtract payments made
        3. Create (debtor, creditor) pairs
        4. Insert entries to DB
        
        Returns list of created entries.
        Raises ReceiptValidationError if calculation fails.
        """
        if receipt.status != "finalized":
            raise ReceiptValidationError("Can only create ledger for finalized receipts")

        if receipt.total_cents <= 0:
            raise ReceiptValidationError("Receipt total must be positive to finalize")

        # Calculate per-user liability (what they owe)
        user_liabilities = self._calculate_user_liabilities(receipt)
        
        # Get payments made by each user
        user_payments = self._get_user_payments(receipt)
        
        # Calculate net positions (liability - payment = amount they owe to others)
        net_positions = self._calculate_net_positions(user_liabilities, user_payments)
        
        # Determine who pays whom (simple: positive net owes to negative net)
        entries = self._match_debtors_creditors(receipt.id, net_positions)
        
        # Insert to DB
        now = datetime.utcnow()
        entries_docs = []
        for entry in entries:
            entry.created_at = now
            entry.updated_at = now
            doc = entry.model_dump(by_alias=True, exclude_none=True)
            entries_docs.append(doc)
        
        if entries_docs:
            result = await self.collection.insert_many(entries_docs)
            # Fetch inserted entries
            inserted = await self.collection.find({
                "_id": {"$in": result.inserted_ids}
            }).to_list(None)
            # Convert ObjectId to string for LedgerEntry
            for doc in inserted:
                doc["_id"] = str(doc["_id"])
            return [LedgerEntry(**doc) for doc in inserted]
        
        return []

    async def get_ledger_by_receipt(self, receipt_id: str) -> List[LedgerEntry]:
        """Get all ledger entries for a receipt."""
        docs = await self.collection.find({
            "receipt_id": receipt_id,
            "is_deleted": False
        }).to_list(None)
        
        # Convert ObjectId to string for LedgerEntry
        for doc in docs:
            doc["_id"] = str(doc["_id"])
        return [LedgerEntry(**doc) for doc in docs]

    async def get_user_balance(self, user_id: str) -> Dict[str, int]:
        """
        Aggregate user's balance across all receipts.
        
        Returns:
        {
            "owes_cents": total amount user owes,
            "is_owed_cents": total amount owed to user,
            "net_cents": owed - owes (positive = net creditor, negative = net debtor)
        }
        """
        try:
            oid = ObjectId(user_id)
        except:
            return {"owes_cents": 0, "is_owed_cents": 0, "net_cents": 0}
        
        # Amount user owes as debtor (stored as string)
        owes_result = await self.collection.aggregate([
            {
                "$match": {
                    "debtor_id": user_id,
                    "is_deleted": False,
                    "status": {"$ne": "settled"}
                }
            },
            {
                "$group": {
                    "_id": None,
                    "total": {
                        "$sum": {
                            "$subtract": ["$amount_cents", "$settled_amount_cents"]
                        }
                    }
                }
            }
        ]).to_list(None)
        
        owes_cents = owes_result[0]["total"] if owes_result else 0
        
        # Amount owed to user as creditor (stored as string)
        is_owed_result = await self.collection.aggregate([
            {
                "$match": {
                    "creditor_id": user_id,
                    "is_deleted": False,
                    "status": {"$ne": "settled"}
                }
            },
            {
                "$group": {
                    "_id": None,
                    "total": {
                        "$sum": {
                            "$subtract": ["$amount_cents", "$settled_amount_cents"]
                        }
                    }
                }
            }
        ]).to_list(None)
        
        is_owed_cents = is_owed_result[0]["total"] if is_owed_result else 0
        
        return {
            "owes_cents": owes_cents,
            "is_owed_cents": is_owed_cents,
            "net_cents": is_owed_cents - owes_cents
        }

    async def settle_entry(self, entry_id: str, amount_cents: int) -> Optional[LedgerEntry]:
        """
        Settle (partially or fully) a ledger entry.
        
        - amount_cents: amount being settled (must be <= open amount)
        - Updates settled_amount_cents and status
        
        Returns updated entry or None if not found.
        """
        try:
            oid = ObjectId(entry_id)
        except:
            return None
        
        entry_doc = await self.collection.find_one({"_id": oid})
        if not entry_doc:
            return None
        
        entry_doc["_id"] = str(entry_doc["_id"])
        entry = LedgerEntry(**entry_doc)
        open_amount = entry.open_amount_cents()
        
        if amount_cents < 0 or amount_cents > open_amount:
            raise ReceiptValidationError(
                f"Settlement amount must be 0 to {open_amount} cents"
            )
        
        new_settled = entry.settled_amount_cents + amount_cents
        new_status = "settled" if new_settled == entry.amount_cents else "partially_settled"
        
        result = await self.collection.find_one_and_update(
            {"_id": oid},
            {
                "$set": {
                    "settled_amount_cents": new_settled,
                    "status": new_status,
                    "updated_at": datetime.utcnow()
                }
            },
            return_document=True
        )
        
        if result:
            result["_id"] = str(result["_id"])
            return LedgerEntry(**result)
        return None

    # ===== PRIVATE HELPERS =====

    def _calculate_user_liabilities(self, receipt: Receipt) -> Dict[str, int]:
        """
        Calculate what each participant owes for their item shares.
        
        Returns: { user_id: their_share_of_total_cents }
        """
        liabilities = {}
        
        # Initialize all participants with 0
        for p in receipt.participants:
            liabilities[str(p.user_id)] = 0
        
        if not receipt.items or receipt.subtotal_cents <= 0:
            return liabilities
        
        # For each item, calculate per-participant liability
        total_split_qty = sum(
            sum(s.share_quantity for s in item.splits) if item.splits else 0
            for item in receipt.items
        )
        
        if total_split_qty == 0:
            return liabilities
        
        for item in receipt.items:
            if not item.splits:
                continue
            
            item_subtotal = item.unit_price_cents * item.quantity
            item_split_qty = sum(s.share_quantity for s in item.splits)
            
            if item_split_qty == 0:
                continue
            
            # Allocate item cost proportionally
            for split in item.splits:
                user_id = str(split.user_id)
                # Item's share of this total
                item_share_ratio = split.share_quantity / item_split_qty
                item_liability = int(item_subtotal * item_share_ratio)
                liabilities[user_id] = liabilities.get(user_id, 0) + item_liability
        
        # Allocate tax and tip proportionally to all participants
        if receipt.tax_cents > 0 or receipt.tip_cents > 0:
            allocation_cents = receipt.tax_cents + receipt.tip_cents
            num_participants = len(receipt.participants)
            
            if num_participants > 0:
                per_user = allocation_cents // num_participants
                remainder = allocation_cents % num_participants
                
                for i, p in enumerate(receipt.participants):
                    user_id = str(p.user_id)
                    # Distribute remainder to first few users
                    extra = 1 if i < remainder else 0
                    liabilities[user_id] = liabilities.get(user_id, 0) + per_user + extra
        
        return liabilities

    def _get_user_payments(self, receipt: Receipt) -> Dict[str, int]:
        """Get total payments made by each user."""
        payments = {}
        for payment in receipt.payments:
            user_id = str(payment.user_id)
            payments[user_id] = payments.get(user_id, 0) + payment.amount_paid_cents
        return payments

    def _calculate_net_positions(
        self,
        liabilities: Dict[str, int],
        payments: Dict[str, int]
    ) -> Dict[str, int]:
        """
        Calculate net position for each user (liability - payment).
        
        Positive = owes money
        Negative = owed money
        Zero = settled up
        """
        all_users = set(liabilities.keys()) | set(payments.keys())
        net = {}
        
        for user_id in all_users:
            liability = liabilities.get(user_id, 0)
            payment = payments.get(user_id, 0)
            net[user_id] = liability - payment
        
        return net

    def _match_debtors_creditors(
        self, receipt_id: str, net_positions: Dict[str, int]
    ) -> List[LedgerEntry]:
        """
        Create ledger entries from net positions.
        
        Simple algorithm: match positive (debtors) with negative (creditors)
        
        Returns: List of LedgerEntry objects (not yet persisted)
        """
        try:
            receipt_oid = ObjectId(receipt_id)
        except:
            receipt_oid = receipt_id
        
        entries = []
        
        # Separate debtors and creditors
        debtors = [(uid, amt) for uid, amt in net_positions.items() if amt > 0]
        creditors = [(uid, -amt) for uid, amt in net_positions.items() if amt < 0]
        
        # Simple greedy matching: pair debtors with creditors
        debtor_idx = 0
        creditor_idx = 0
        
        while debtor_idx < len(debtors) and creditor_idx < len(creditors):
            debtor_id, debtor_amt = debtors[debtor_idx]
            creditor_id, creditor_amt = creditors[creditor_idx]
            
            # Match amount
            match_amt = min(debtor_amt, creditor_amt)
            
            if match_amt > 0:
                entry = LedgerEntry(
                    receipt_id=str(receipt_id),
                    debtor_id=debtor_id,
                    creditor_id=creditor_id,
                    amount_cents=match_amt,
                    settled_amount_cents=0,
                    status="pending",
                    description=f"Settlement for receipt"
                )
                entries.append(entry)
            
            # Update remaining amounts
            debtor_amt -= match_amt
            creditor_amt -= match_amt
            
            if debtor_amt == 0:
                debtor_idx += 1
            else:
                debtors[debtor_idx] = (debtor_id, debtor_amt)
            
            if creditor_amt == 0:
                creditor_idx += 1
            else:
                creditors[creditor_idx] = (creditor_id, creditor_amt)
        
        return entries

    async def delete_entries_for_receipt(self, receipt_id: str) -> int:
        """Soft-delete all entries for a receipt (for unfinalizing)."""
        try:
            oid = ObjectId(receipt_id)
        except:
            return 0
        
        result = await self.collection.update_many(
            {"receipt_id": oid},
            {
                "$set": {
                    "is_deleted": True,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        return result.modified_count
