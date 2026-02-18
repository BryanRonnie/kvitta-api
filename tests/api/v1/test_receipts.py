from unittest.mock import AsyncMock, patch
from app.models.receipt import Receipt, ReceiptStatus
from app.models.user import User
from app.api.v1.endpoints.auth import get_current_user
from app.main import app
from datetime import datetime, timezone
from bson import ObjectId

def test_create_receipt(client):
    owner_id = "507f1f77bcf86cd799439011"
    
    # Mock user for authentication
    mock_user = User(
        id=ObjectId(owner_id),
        name="Test User",
        email="test@example.com",
        hashed_password="dummy",
        is_deleted=False
    )
    
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

    # Override the dependency
    app.dependency_overrides[get_current_user] = lambda: mock_user
    
    try:
        with patch("app.services.receipt_service.ReceiptService.create", new_callable=AsyncMock) as mock_create:
            mock_create.return_value = mock_receipt
            
            response = client.post(
                "/api/v1/receipts/",
                json={"title": "Dinner"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["title"] == "Dinner"
            assert data["id"] == "507f1f77bcf86cd799439012"
            mock_create.assert_called_once()
    finally:
        # Clean up override
        app.dependency_overrides.clear()
