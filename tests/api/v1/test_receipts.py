from unittest.mock import AsyncMock, patch
from app.models.receipt import Receipt, ReceiptStatus
from datetime import datetime, timezone

def test_create_receipt(client):
    owner_id = "507f1f77bcf86cd799439011"
    
    mock_receipt = Receipt(
        id="507f1f77bcf86cd799439012",
        owner_id=owner_id,
        title="Dinner",
        created_by="507f1f77bcf86cd799439011",
        updated_by="507f1f77bcf86cd799439011",
        version=1,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )

    with patch("app.services.receipt_service.ReceiptService.create", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = mock_receipt
        
        response = client.post(
            f"/api/v1/receipts/?owner_id={owner_id}",
            json={"title": "Dinner"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Dinner"
        assert data["id"] == "507f1f77bcf86cd799439012"
        mock_create.assert_called_once()
