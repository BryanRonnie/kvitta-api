import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from bson import ObjectId
from app.services.receipt_service import ReceiptService
from app.schemas.receipt import ReceiptCreate, ReceiptUpdate
from app.models.receipt import Receipt, ReceiptStatus

@pytest.mark.asyncio
async def test_create_receipt(mock_db):
    owner_id = str(ObjectId())
    receipt_in = ReceiptCreate(
        title="Test Receipt",
        participants=[],
        items=[],
        payments=[]
    )
    
    with patch("app.services.receipt_service.get_database", return_value=mock_db):
        mock_db.receipts.insert_one.return_value = MagicMock(inserted_id=ObjectId())
        
        receipt = await ReceiptService.create(receipt_in, owner_id)
        
        assert receipt.title == "Test Receipt"
        assert receipt.owner_id == ObjectId(owner_id)
        assert receipt.status == ReceiptStatus.DRAFT
        mock_db.receipts.insert_one.assert_called_once()

@pytest.mark.asyncio
async def test_update_receipt_draft(mock_db):
    receipt_id = str(ObjectId())
    user_id = str(ObjectId())
    
    existing_doc = {
        "_id": ObjectId(receipt_id),
        "owner_id": ObjectId(user_id),
        "title": "Old Title",
        "status": ReceiptStatus.DRAFT,
        "version": 1,
        "created_by": ObjectId(user_id),
        "updated_by": ObjectId(user_id),
        "created_at": "2024-01-01T00:00:00",
        "updated_at": "2024-01-01T00:00:00"
    }
    
    receipt_update = ReceiptUpdate(title="New Title")
    
    with patch("app.services.receipt_service.get_database", return_value=mock_db):
        mock_db.receipts.find_one = AsyncMock(side_effect=[existing_doc, {**existing_doc, "title": "New Title", "version": 2}])
        
        updated_receipt = await ReceiptService.update(receipt_id, receipt_update, user_id)
        
        assert updated_receipt.title == "New Title"
        assert updated_receipt.version == 2
        mock_db.receipts.update_one.assert_called_once()

@pytest.mark.asyncio
async def test_finalize_receipt(mock_db):
    receipt_id = str(ObjectId())
    user_id = str(ObjectId())
    
    existing_doc = {
        "_id": ObjectId(receipt_id),
        "owner_id": ObjectId(user_id),
        "title": "Test Receipt",
        "status": ReceiptStatus.DRAFT,
        "version": 1,
        "items": [],
        "payments": [],
        "created_by": ObjectId(user_id),
        "updated_by": ObjectId(user_id)
    }
    
    # Mock transaction session
    mock_session = AsyncMock()
    mock_db.client.start_session = AsyncMock(return_value=MagicMock(__aenter__=AsyncMock(return_value=mock_session)))
    mock_session.start_transaction = MagicMock(__aenter__=AsyncMock())
    
    with patch("app.services.receipt_service.get_database", return_value=mock_db):
        with patch("app.services.receipt_service.LedgerService.generate_from_receipt", new_callable=AsyncMock) as mock_ledger:
            # Mock find_one calls
            # 1. In finalize: await ReceiptService.get(receipt_id)
            # 2. In finalize: await ReceiptService.get(receipt_id) (after update)
            # 3. In finalized: await ReceiptService.get(receipt_id) (final return)
            # Actually ReceiptService.get is called multiple times.
            
            # Let's mock ReceiptService.get instead for simplicity in this test
            with patch("app.services.receipt_service.ReceiptService.get", new_callable=AsyncMock) as mock_get:
                receipt_obj = Receipt(**existing_doc)
                finalized_receipt_obj = Receipt(**{**existing_doc, "status": ReceiptStatus.FINALIZED})
                
                mock_get.side_effect = [receipt_obj, finalized_receipt_obj, finalized_receipt_obj]
                
                await ReceiptService.finalize(receipt_id, user_id)
                
                mock_ledger.assert_called_once()
                mock_db.receipts.update_one.assert_called_once()
                assert mock_db.receipts.update_one.call_args[0][1]["$set"]["status"] == ReceiptStatus.FINALIZED

