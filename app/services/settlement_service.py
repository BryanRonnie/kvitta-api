from app.db.session import get_database
from app.models.settlement import Settlement
from app.models.ledger import LedgerStatus
from app.schemas.settlement import SettlementCreate
from bson import ObjectId
from fastapi import HTTPException
from datetime import datetime

class SettlementService:
    @staticmethod
    async def create(settlement_in: SettlementCreate) -> Settlement:
        db = await get_database()
        
        # 1. Validate users exist (omitted for brevity)
        
        # 2. Check if there is enough debt to settle?
        # For now, we assume user can send money even if they don't strictly "owe" it in the system 
        # (maybe pre-payment), but usually we want to settle existing debt.
        
        settlement = Settlement(**settlement_in.model_dump())
        
        async with await db.client.start_session() as session:
            async with session.start_transaction():
                # Insert settlement record
                result = await db.settlements.insert_one(settlement.model_dump(by_alias=True), session=session)
                settlement.id = result.inserted_id
                
                # Logic to "settle" ledger entries.
                # Find oldest open entries where debtor = from_user and creditor = to_user
                
                cursor = db.ledger_entries.find({
                    "debtor_id": ObjectId(settlement.from_user_id),
                    "creditor_id": ObjectId(settlement.to_user_id),
                    "status": LedgerStatus.OPEN
                }).sort("created_at", 1)
                
                remaining_amount = settlement.amount
                
                async for entry_doc in cursor:
                    if remaining_amount <= 0:
                        break
                        
                    entry_id = entry_doc["_id"]
                    entry_amount = entry_doc["amount"]
                    
                    if remaining_amount >= entry_amount:
                        # Full settlement of this entry
                        await db.ledger_entries.update_one(
                            {"_id": entry_id},
                            {"$set": {"status": LedgerStatus.SETTLED, "settled_at": datetime.utcnow()}},
                            session=session
                        )
                        remaining_amount -= entry_amount
                    else:
                        # Partial settlement - we need to split the entry?
                        # Or just reduce amount? Ledger usually implies immutable entries.
                        # Implementation Plan says "Partial reduce allowed".
                        # Let's reduce the amount of the existing entry and maybe create a settled entry?
                        # Or just keep it simple: Update amount.
                        
                        await db.ledger_entries.update_one(
                            {"_id": entry_id},
                            {"$set": {"amount": entry_amount - remaining_amount}},
                            session=session
                        )
                        # We should verify if we want to track partial history. 
                        # For now, simplest approach.
                        remaining_amount = 0
                        
        return settlement
