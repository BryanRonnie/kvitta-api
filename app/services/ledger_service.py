from typing import List, Dict
from app.db.session import get_database
from app.models.receipt import Receipt
from app.models.ledger import LedgerEntry, LedgerStatus
from app.schemas.ledger import UserBalanceResponse
from bson import ObjectId

class LedgerService:
    @staticmethod
    async def generate_from_receipt(receipt: Receipt):
        """
        Generates ledger entries from a finalized receipt.
        """
        db = await get_database()
        
        # 1. Compute owed per user
        owed: Dict[str, float] = {}
        for item in receipt.items:
            for split in item.splits:
                user_id = str(split.user_id)
                amount = item.unit_price * split.share_quantity
                owed[user_id] = owed.get(user_id, 0.0) + amount
                
        # 2. Compute paid per user
        paid: Dict[str, float] = {}
        for payment in receipt.payments:
            user_id = str(payment.user_id)
            paid[user_id] = paid.get(user_id, 0.0) + payment.amount_paid
            
        # 3. Compute net
        net: Dict[str, float] = {}
        all_users = set(owed.keys()) | set(paid.keys())
        
        for user_id in all_users:
            net_val = paid.get(user_id, 0.0) - owed.get(user_id, 0.0)
            net[user_id] = round(net_val, 2)
            
        creditors = []
        debtors = []
        
        for user_id, amount in net.items():
            if amount > 0.01:
                creditors.append({"user_id": user_id, "amount": amount})
            elif amount < -0.01:
                debtors.append({"user_id": user_id, "amount": -amount}) # Store positive debt amount
        
        # 4. Create pairwise debt entries
        ledger_entries: List[LedgerEntry] = []
        
        # Sort by amount to minimize number of transactions (simple heuristic)
        creditors.sort(key=lambda x: x["amount"], reverse=True)
        debtors.sort(key=lambda x: x["amount"], reverse=True)
        
        i = 0
        j = 0
        
        while i < len(debtors) and j < len(creditors):
            debtor = debtors[i]
            creditor = creditors[j]
            
            amount = min(debtor["amount"], creditor["amount"])
            
            entry = LedgerEntry(
                receipt_id=receipt.id,
                debtor_id=ObjectId(debtor["user_id"]),
                creditor_id=ObjectId(creditor["user_id"]),
                amount=round(amount, 2),
                status=LedgerStatus.OPEN
            )
            ledger_entries.append(entry)
            
            debtor["amount"] -= amount
            creditor["amount"] -= amount
            
            if debtor["amount"] < 0.01:
                i += 1
            if creditor["amount"] < 0.01:
                j += 1
                
        if ledger_entries:
            await db.ledger_entries.insert_many([entry.model_dump(by_alias=True) for entry in ledger_entries])
            
        return ledger_entries

    @staticmethod
    async def get_user_balance(user_id: str) -> UserBalanceResponse:
        db = await get_database()
        
        pipeline_owed_by = [
            {"$match": {"debtor_id": ObjectId(user_id), "status": LedgerStatus.OPEN}},
            {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
        ]
        
        pipeline_owed_to = [
            {"$match": {"creditor_id": ObjectId(user_id), "status": LedgerStatus.OPEN}},
            {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
        ]
        
        res_owed_by = await db.ledger_entries.aggregate(pipeline_owed_by).to_list(1)
        owed_by = res_owed_by[0]["total"] if res_owed_by else 0.0
        
        res_owed_to = await db.ledger_entries.aggregate(pipeline_owed_to).to_list(1)
        owed_to = res_owed_to[0]["total"] if res_owed_to else 0.0
        
        return UserBalanceResponse(
            user_id=user_id,
            owes=owed_by,
            is_owed=owed_to,
            net=owed_to - owed_by
        )
