import pytest
from fastapi import status

from app.schemas.receipt import ReceiptCreate
from app.repositories.receipt_repo import ReceiptRepository


@pytest.mark.asyncio
async def test_create_receipt_repo(test_db, created_user):
    """Test creating a draft receipt - owner auto-added as participant."""
    repo = ReceiptRepository(test_db)
    receipt = await repo.create_receipt(
        ReceiptCreate(title="Dinner", description="Team dinner"),
        str(created_user._id)
    )

    assert receipt.title == "Dinner"
    assert receipt.description == "Team dinner"
    assert receipt.owner_id == created_user._id
    assert receipt.status == "draft"
    assert receipt.version == 1
    assert receipt.subtotal_cents == 0
    assert receipt.total_cents == 0
    assert receipt.is_deleted is False
    
    # Owner automatically added as participant with role="owner"
    assert len(receipt.participants) == 1
    assert receipt.participants[0].user_id == created_user._id
    assert receipt.participants[0].role == "owner"


@pytest.mark.asyncio
async def test_list_receipts_repo_filters_participant(test_db, created_user):
    """Test listing receipts filters by owner or participant."""
    repo = ReceiptRepository(test_db)
    other_user_id = "507f1f77bcf86cd799439011"

    # User creates their own receipt
    await repo.create_receipt(
        ReceiptCreate(title="My Receipt"),
        str(created_user._id)
    )
    
    # Other user creates their receipt
    await repo.create_receipt(
        ReceiptCreate(title="Other Receipt"),
        other_user_id
    )

    # User should only see their own receipt
    receipts = await repo.list_receipts(str(created_user._id))
    assert len(receipts) == 1
    assert receipts[0].title == "My Receipt"


@pytest.mark.asyncio
async def test_get_receipt_repo(test_db, created_user):
    """Test getting a receipt by ID."""
    repo = ReceiptRepository(test_db)
    created = await repo.create_receipt(
        ReceiptCreate(title="Lunch"),
        str(created_user._id)
    )

    retrieved = await repo.get_receipt(str(created._id), str(created_user._id))
    assert retrieved is not None
    assert retrieved.title == "Lunch"
    assert retrieved._id == created._id


def test_create_receipt_endpoint(test_client, valid_token):
    """Test POST /receipts creates draft receipt."""
    response = test_client.post(
        "/receipts",
        headers={"Authorization": f"Bearer {valid_token}"},
        json={"title": "Coffee", "description": "Morning coffee"}
    )

    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["title"] == "Coffee"
    assert data["description"] == "Morning coffee"
    assert data["status"] == "draft"
    assert data["version"] == 1
    assert data["subtotal_cents"] == 0
    assert data["total_cents"] == 0
    assert "id" in data
    assert len(data["participants"]) == 1
    assert data["participants"][0]["role"] == "owner"


def test_list_receipts_endpoint(test_client, valid_token):
    """Test GET /receipts lists user's receipts."""
    # Create multiple receipts
    test_client.post(
        "/receipts",
        headers={"Authorization": f"Bearer {valid_token}"},
        json={"title": "Receipt 1"}
    )
    test_client.post(
        "/receipts",
        headers={"Authorization": f"Bearer {valid_token}"},
        json={"title": "Receipt 2"}
    )

    response = test_client.get(
        "/receipts",
        headers={"Authorization": f"Bearer {valid_token}"}
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data) == 2
    titles = {r["title"] for r in data}
    assert "Receipt 1" in titles
    assert "Receipt 2" in titles


def test_get_receipt_endpoint(test_client, valid_token):
    """Test GET /receipts/{id} retrieves specific receipt."""
    create_response = test_client.post(
        "/receipts",
        headers={"Authorization": f"Bearer {valid_token}"},
        json={"title": "Target Receipt"}
    )
    receipt_id = create_response.json()["id"]

    response = test_client.get(
        f"/receipts/{receipt_id}",
        headers={"Authorization": f"Bearer {valid_token}"}
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["id"] == receipt_id
    assert data["title"] == "Target Receipt"


def test_get_receipt_not_found(test_client, valid_token):
    """Test 404 when receipt doesn't exist."""
    fake_id = "507f1f77bcf86cd799439999"
    response = test_client.get(
        f"/receipts/{fake_id}",
        headers={"Authorization": f"Bearer {valid_token}"}
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_create_receipt_unauthorized(test_client):
    """Test creating receipt without auth fails."""
    response = test_client.post(
        "/receipts",
        json={"title": "No Auth"}
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
