import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from bson import ObjectId
from app.services.ledger_service import LedgerService
from app.models.receipt import Receipt, Item, Split, Payment, ReceiptStatus
from app.models.ledger import LedgerStatus

@pytest.mark.asyncio
async def test_generate_from_receipt_simple_split(mock_db):
    # Setup: 2 users, 1 payer (User A paid 10, both owe 5)
    user_a = ObjectId()
    user_b = ObjectId()
    receipt_id = ObjectId()
    
    receipt = Receipt(
        id=receipt_id,
        owner_id=user_a,
        title="Simple Split",
        status=ReceiptStatus.FINALIZED,
        items=[
            Item(
                name="Food",
                unit_price=10.0,
                quantity=1.0,
                splits=[
                    Split(user_id=user_a, share_quantity=0.5), # User A owes 5
                    Split(user_id=user_b, share_quantity=0.5), # User B owes 5
                ]
            )
        ],
        payments=[
            Payment(user_id=user_a, amount_paid=10.0) # User A paid 10
        ],
        created_by=user_a,
        updated_by=user_a
    )

    with patch("app.services.ledger_service.get_database", return_value=mock_db):
        
        ledger_entries = await LedgerService.generate_from_receipt(receipt)
        
        # User B should owe User A 5.0
        assert len(ledger_entries) == 1
        entry = ledger_entries[0]
        assert entry.debtor_id == user_b
        assert entry.creditor_id == user_a
        assert entry.amount == 5.0
        assert entry.status == LedgerStatus.OPEN
        
        mock_db.ledger_entries.insert_many.assert_called_once()

@pytest.mark.asyncio
async def test_generate_from_receipt_unequal_split(mock_db):
    # Setup: User A paid 20, User B owes 15, User A owes 5
    user_a = ObjectId()
    user_b = ObjectId()
    receipt_id = ObjectId()
    
    receipt = Receipt(
        id=receipt_id,
        owner_id=user_a,
        title="Unequal Split",
        status=ReceiptStatus.FINALIZED,
        items=[
            Item(
                name="Steak",
                unit_price=20.0,
                quantity=1.0,
                splits=[
                    Split(user_id=user_a, share_quantity=0.25), # User A owes 5
                    Split(user_id=user_b, share_quantity=0.75), # User B owes 15
                ]
            )
        ],
        payments=[
            Payment(user_id=user_a, amount_paid=20.0) # User A paid 20
        ],
        created_by=user_a,
        updated_by=user_a
    )

    with patch("app.services.ledger_service.get_database", return_value=mock_db):
        
        ledger_entries = await LedgerService.generate_from_receipt(receipt)
        
        # User B owes User A 15.0
        assert len(ledger_entries) == 1
        entry = ledger_entries[0]
        assert entry.debtor_id == user_b
        assert entry.creditor_id == user_a
        assert entry.amount == 15.0
        
        mock_db.ledger_entries.insert_many.assert_called_once()

@pytest.mark.asyncio
async def test_get_user_balance(mock_db):
    user_id = str(ObjectId())
    
    # Mock aggregation results
    # aggregate returns a cursor, which has to_list
    mock_cursor_owed_by = MagicMock()
    mock_cursor_owed_by.to_list = AsyncMock(return_value=[{"total": 50.0}])
    
    mock_cursor_owed_to = MagicMock()
    mock_cursor_owed_to.to_list = AsyncMock(return_value=[{"total": 30.0}])
    
    # We need to handle sequential calls to aggregate
    mock_db.ledger_entries.aggregate.side_effect = [
        mock_cursor_owed_by, # Owed BY user
        mock_cursor_owed_to  # Owed TO user
    ]
    
    with patch("app.services.ledger_service.get_database", return_value=mock_db):
        balance = await LedgerService.get_user_balance(user_id)
        
        assert balance.user_id == user_id
        assert balance.owes == 50.0        # Total debtor amount
        assert balance.is_owed == 30.0     # Total creditor amount
        assert balance.net == -20.0        # 30 - 50 = -20
