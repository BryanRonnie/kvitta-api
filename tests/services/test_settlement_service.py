import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from bson import ObjectId
from app.services.settlement_service import SettlementService
from app.schemas.settlement import SettlementCreate
from app.models.ledger import LedgerStatus
from datetime import datetime

@pytest.mark.asyncio
async def test_create_settlement_full(mock_db):
    from_user = ObjectId()
    to_user = ObjectId()
    
    settlement_in = SettlementCreate(
        from_user_id=str(from_user),
        to_user_id=str(to_user),
        amount=50.0,
        payment_method="Venmo"
    )
    
    # Mock ledger entries to be settled
    mock_entry = {
        "_id": ObjectId(),
        "debtor_id": from_user,
        "creditor_id": to_user,
        "amount": 50.0,
        "status": LedgerStatus.OPEN
    }
    
    # Mock transaction session
    mock_session = AsyncMock()
    mock_db.client.start_session = AsyncMock(return_value=MagicMock(__aenter__=AsyncMock(return_value=mock_session)))
    mock_session.start_transaction = MagicMock(__aenter__=AsyncMock())
    
    # Mock find cursor
    mock_cursor = MagicMock()
    mock_cursor.sort.return_value = mock_cursor
    
    # Use a real list to mock async iteration
    async def mock_async_iter(items):
        for item in items:
            yield item
            
    mock_cursor.__aiter__ = lambda x: mock_async_iter([mock_entry])
    
    with patch("app.services.settlement_service.get_database", return_value=mock_db):
        mock_db.settlements.insert_one.return_value = MagicMock(inserted_id=ObjectId())
        mock_db.ledger_entries.find.return_value = mock_cursor
        
        await SettlementService.create(settlement_in)
        
        mock_db.settlements.insert_one.assert_called_once()
        mock_db.ledger_entries.update_one.assert_called_once()
        # Verify update_one was called with status=SETTLED
        assert mock_db.ledger_entries.update_one.call_args[0][1]["$set"]["status"] == LedgerStatus.SETTLED

@pytest.mark.asyncio
async def test_create_settlement_partial(mock_db):
    from_user = ObjectId()
    to_user = ObjectId()
    
    settlement_in = SettlementCreate(
        from_user_id=str(from_user),
        to_user_id=str(to_user),
        amount=20.0, # Settle only 20
        payment_method="Cash"
    )
    
    # Mock a larger ledger entry (50)
    mock_entry = {
        "_id": ObjectId(),
        "debtor_id": from_user,
        "creditor_id": to_user,
        "amount": 50.0,
        "status": LedgerStatus.OPEN
    }
    
    # Mock transaction session
    mock_session = AsyncMock()
    mock_db.client.start_session = AsyncMock(return_value=MagicMock(__aenter__=AsyncMock(return_value=mock_session)))
    mock_session.start_transaction = MagicMock(__aenter__=AsyncMock())
    
    # Mock find cursor
    mock_cursor = MagicMock()
    mock_cursor.sort.return_value = mock_cursor
    
    async def mock_async_iter(items):
        for item in items:
            yield item
            
    mock_cursor.__aiter__ = lambda x: mock_async_iter([mock_entry])
    
    with patch("app.services.settlement_service.get_database", return_value=mock_db):
        mock_db.settlements.insert_one.return_value = MagicMock(inserted_id=ObjectId())
        mock_db.ledger_entries.find.return_value = mock_cursor
        
        await SettlementService.create(settlement_in)
        
        # Verify update_one was called with reduced amount (50 - 20 = 30)
        assert mock_db.ledger_entries.update_one.call_args[0][1]["$set"]["amount"] == 30.0
