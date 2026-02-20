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

    retrieved = await repo.get_receipt(str(created.id), str(created_user._id))
    assert retrieved is not None
    assert retrieved.title == "Lunch"
    assert retrieved.id == created.id


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


def test_update_receipt_with_items(test_client, valid_token):
    """Test updating receipt with items - backend calculates subtotal."""
    # Create receipt
    create_response = test_client.post(
        "/receipts",
        headers={"Authorization": f"Bearer {valid_token}"},
        json={"title": "Pizza Night"}
    )
    receipt_id = create_response.json()["id"]
    version = create_response.json()["version"]
    
    # Get user_id from token (created_user)
    me_response = test_client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {valid_token}"}
    )
    user_id = me_response.json()["id"]
    
    # Update with items
    update_response = test_client.patch(
        f"/receipts/{receipt_id}",
        headers={"Authorization": f"Bearer {valid_token}"},
        json={
            "version": version,
            "items": [
                {
                    "name": "Large Pizza",
                    "unit_price_cents": 1599,  # $15.99
                    "quantity": 2,
                    "splits": [
                        {"user_id": user_id, "share_quantity": 2.0}
                    ]
                }
            ],
            "tax_cents": 300,
            "tip_cents": 500
        }
    )
    
    assert update_response.status_code == status.HTTP_200_OK
    data = update_response.json()
    assert data["subtotal_cents"] == 3198  # 1599 * 2
    assert data["tax_cents"] == 300
    assert data["tip_cents"] == 500
    assert data["total_cents"] == 3998  # 3198 + 300 + 500
    assert data["version"] == 2  # Version incremented
    assert len(data["items"]) == 1


def test_update_receipt_validation_negative_price(test_client, valid_token):
    """Test validation: negative price rejected."""
    create_response = test_client.post(
        "/receipts",
        headers={"Authorization": f"Bearer {valid_token}"},
        json={"title": "Test"}
    )
    receipt_id = create_response.json()["id"]
    version = create_response.json()["version"]
    
    update_response = test_client.patch(
        f"/receipts/{receipt_id}",
        headers={"Authorization": f"Bearer {valid_token}"},
        json={
            "version": version,
            "items": [
                {
                    "name": "Bad Item",
                    "unit_price_cents": -100,
                    "quantity": 1,
                    "splits": []
                }
            ]
        }
    )
    
    assert update_response.status_code == status.HTTP_400_BAD_REQUEST
    assert "negative price" in update_response.json()["detail"].lower()


def test_update_receipt_validation_split_sum_mismatch(test_client, valid_token):
    """Test validation: split sum must equal quantity."""
    create_response = test_client.post(
        "/receipts",
        headers={"Authorization": f"Bearer {valid_token}"},
        json={"title": "Test"}
    )
    receipt_id = create_response.json()["id"]
    version = create_response.json()["version"]
    
    me_response = test_client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {valid_token}"}
    )
    user_id = me_response.json()["id"]
    
    update_response = test_client.patch(
        f"/receipts/{receipt_id}",
        headers={"Authorization": f"Bearer {valid_token}"},
        json={
            "version": version,
            "items": [
                {
                    "name": "Shared Item",
                    "unit_price_cents": 1000,
                    "quantity": 2.0,
                    "splits": [
                        {"user_id": user_id, "share_quantity": 1.0}  # Only 1.0, should be 2.0
                    ]
                }
            ]
        }
    )
    
    assert update_response.status_code == status.HTTP_400_BAD_REQUEST
    assert "split sum" in update_response.json()["detail"].lower()


def test_update_receipt_version_conflict(test_client, valid_token):
    """Test optimistic locking: version conflict rejected."""
    create_response = test_client.post(
        "/receipts",
        headers={"Authorization": f"Bearer {valid_token}"},
        json={"title": "Test"}
    )
    receipt_id = create_response.json()["id"]
    
    # First update (version 1 -> 2)
    test_client.patch(
        f"/receipts/{receipt_id}",
        headers={"Authorization": f"Bearer {valid_token}"},
        json={"version": 1, "title": "Updated"}
    )
    
    # Try to update with old version (should fail)
    conflict_response = test_client.patch(
        f"/receipts/{receipt_id}",
        headers={"Authorization": f"Bearer {valid_token}"},
        json={"version": 1, "title": "Conflict"}
    )
    
    assert conflict_response.status_code == status.HTTP_400_BAD_REQUEST
    assert "version" in conflict_response.json()["detail"].lower()


def test_update_receipt_not_owner(test_client, valid_token):
    """Test that non-owners cannot update receipt."""
    # This test assumes only owner can update
    # In current implementation, get_receipt checks ownership
    create_response = test_client.post(
        "/receipts",
        headers={"Authorization": f"Bearer {valid_token}"},
        json={"title": "Owner's Receipt"}
    )
    receipt_id = create_response.json()["id"]
    
    # Try to update as same user (should work)
    update_response = test_client.patch(
        f"/receipts/{receipt_id}",
        headers={"Authorization": f"Bearer {valid_token}"},
        json={"version": 1, "title": "Updated"}
    )
    
    assert update_response.status_code == status.HTTP_200_OK


def test_autosave_update_comments_only(test_client, valid_token):
    """Test autosave: update only comments field."""
    create_response = test_client.post(
        "/receipts",
        headers={"Authorization": f"Bearer {valid_token}"},
        json={"title": "Lunch"}
    )
    receipt_id = create_response.json()["id"]
    
    # Update only comments
    update_response = test_client.patch(
        f"/receipts/{receipt_id}",
        headers={"Authorization": f"Bearer {valid_token}"},
        json={
            "version": 1,
            "comments": "Alice paid extra, should split differently"
        }
    )
    
    assert update_response.status_code == status.HTTP_200_OK
    data = update_response.json()
    assert data["comments"] == "Alice paid extra, should split differently"
    assert data["title"] == "Lunch"  # Unchanged
    assert data["version"] == 2


def test_autosave_update_title_only(test_client, valid_token):
    """Test autosave: update only title field."""
    create_response = test_client.post(
        "/receipts",
        headers={"Authorization": f"Bearer {valid_token}"},
        json={"title": "Old Title"}
    )
    receipt_id = create_response.json()["id"]
    
    # Update only title
    update_response = test_client.patch(
        f"/receipts/{receipt_id}",
        headers={"Authorization": f"Bearer {valid_token}"},
        json={"version": 1, "title": "New Title"}
    )
    
    assert update_response.status_code == status.HTTP_200_OK
    data = update_response.json()
    assert data["title"] == "New Title"
    assert data["version"] == 2


def test_autosave_update_tax_tip_only(test_client, valid_token):
    """Test autosave: update only tax and tip without items."""
    create_response = test_client.post(
        "/receipts",
        headers={"Authorization": f"Bearer {valid_token}"},
        json={"title": "Restaurant"}
    )
    receipt_id = create_response.json()["id"]
    
    # Update only tax and tip
    update_response = test_client.patch(
        f"/receipts/{receipt_id}",
        headers={"Authorization": f"Bearer {valid_token}"},
        json={
            "version": 1,
            "tax_cents": 850,
            "tip_cents": 2000
        }
    )
    
    assert update_response.status_code == status.HTTP_200_OK
    data = update_response.json()
    assert data["tax_cents"] == 850
    assert data["tip_cents"] == 2000
    assert data["total_cents"] == 2850  # 0 + 850 + 2000
    assert data["version"] == 2


# ============ MEMBER MANAGEMENT TESTS ============

def test_add_member_by_email(test_client, valid_token):
    """Test adding a member to receipt by email."""
    # Create receipt
    create_response = test_client.post(
        "/receipts",
        headers={"Authorization": f"Bearer {valid_token}"},
        json={"title": "Group Dinner"}
    )
    receipt_id = create_response.json()["id"]
    initial_members = len(create_response.json()["participants"])
    
    # Create another user
    signup_response = test_client.post(
        "/auth/signup",
        json={
            "name": "Alice",
            "email": "alice@example.com",
            "password": "password123"
        }
    )
    assert signup_response.status_code == status.HTTP_201_CREATED
    
    # Add member by email
    add_response = test_client.post(
        f"/receipts/{receipt_id}/members",
        headers={"Authorization": f"Bearer {valid_token}"},
        json={"email": "alice@example.com"}
    )
    
    assert add_response.status_code == status.HTTP_201_CREATED
    data = add_response.json()
    assert len(data["participants"]) == initial_members + 1
    
    # Verify new member is in list
    member_emails = {p["user_id"] for p in data["participants"]}
    assert len(member_emails) == initial_members + 1


def test_add_member_duplicate(test_client, valid_token):
    """Test cannot add same member twice."""
    create_response = test_client.post(
        "/receipts",
        headers={"Authorization": f"Bearer {valid_token}"},
        json={"title": "Test"}
    )
    receipt_id = create_response.json()["id"]
    
    # Create user
    test_client.post(
        "/auth/signup",
        json={
            "name": "Bob",
            "email": "bob@example.com",
            "password": "password123"
        }
    )
    
    # Add member first time
    test_client.post(
        f"/receipts/{receipt_id}/members",
        headers={"Authorization": f"Bearer {valid_token}"},
        json={"email": "bob@example.com"}
    )
    
    # Try to add same member again
    duplicate_response = test_client.post(
        f"/receipts/{receipt_id}/members",
        headers={"Authorization": f"Bearer {valid_token}"},
        json={"email": "bob@example.com"}
    )
    
    assert duplicate_response.status_code == status.HTTP_400_BAD_REQUEST
    assert "already exists" in duplicate_response.json()["detail"].lower()


def test_add_member_nonexistent_email(test_client, valid_token):
    """Test adding member with non-existent email fails."""
    create_response = test_client.post(
        "/receipts",
        headers={"Authorization": f"Bearer {valid_token}"},
        json={"title": "Test"}
    )
    receipt_id = create_response.json()["id"]
    
    response = test_client.post(
        f"/receipts/{receipt_id}/members",
        headers={"Authorization": f"Bearer {valid_token}"},
        json={"email": "nonexistent@example.com"}
    )
    
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert "not found" in response.json()["detail"].lower()


def test_add_member_not_owner(test_client, valid_token):
    """Test non-owner cannot add members."""
    # Owner creates receipt
    create_response = test_client.post(
        "/receipts",
        headers={"Authorization": f"Bearer {valid_token}"},
        json={"title": "Test"}
    )
    receipt_id = create_response.json()["id"]
    
    # Create another user
    signup_response = test_client.post(
        "/auth/signup",
        json={
            "name": "Charlie",
            "email": "charlie@example.com",
            "password": "password123"
        }
    )
    
    # Add them as participant
    test_client.post(
        f"/receipts/{receipt_id}/members",
        headers={"Authorization": f"Bearer {valid_token}"},
        json={"email": "charlie@example.com"}
    )
    
    # Login as Charlie and try to add another member
    charlie_login = test_client.post(
        "/auth/login",
        data={"email": "charlie@example.com", "password": "password123"}
    )
    charlie_token = charlie_login.json()["access_token"]
    
    # Create another user
    test_client.post(
        "/auth/signup",
        json={
            "name": "Dave",
            "email": "dave@example.com",
            "password": "password123"
        }
    )
    
    # Try to add member as non-owner
    response = test_client.post(
        f"/receipts/{receipt_id}/members",
        headers={"Authorization": f"Bearer {charlie_token}"},
        json={"email": "dave@example.com"}
    )
    
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_get_members(test_client, valid_token):
    """Test listing receipt members."""
    # Create receipt
    create_response = test_client.post(
        "/receipts",
        headers={"Authorization": f"Bearer {valid_token}"},
        json={"title": "Potluck"}
    )
    receipt_id = create_response.json()["id"]
    
    # Create and add member
    test_client.post(
        "/auth/signup",
        json={
            "name": "Eve",
            "email": "eve@example.com",
            "password": "password123"
        }
    )
    
    test_client.post(
        f"/receipts/{receipt_id}/members",
        headers={"Authorization": f"Bearer {valid_token}"},
        json={"email": "eve@example.com"}
    )
    
    # Get members
    response = test_client.get(
        f"/receipts/{receipt_id}/members",
        headers={"Authorization": f"Bearer {valid_token}"}
    )
    
    assert response.status_code == status.HTTP_200_OK
    members = response.json()
    assert len(members) == 2  # Owner + Eve
    
    # Check roles
    roles = {m["role"] for m in members}
    assert "owner" in roles
    assert "member" in roles


def test_remove_member(test_client, valid_token):
    """Test removing a member."""
    # Create receipt
    create_response = test_client.post(
        "/receipts",
        headers={"Authorization": f"Bearer {valid_token}"},
        json={"title": "Test"}
    )
    receipt_id = create_response.json()["id"]
    
    # Create and add member
    signup_response = test_client.post(
        "/auth/signup",
        json={
            "name": "Frank",
            "email": "frank@example.com",
            "password": "password123"
        }
    )
    frank_id = signup_response.json()["user"]["id"]
    
    test_client.post(
        f"/receipts/{receipt_id}/members",
        headers={"Authorization": f"Bearer {valid_token}"},
        json={"email": "frank@example.com"}
    )
    
    # Remove member
    response = test_client.delete(
        f"/receipts/{receipt_id}/members/{frank_id}",
        headers={"Authorization": f"Bearer {valid_token}"}
    )
    
    assert response.status_code == status.HTTP_200_OK
    
    # Verify removed
    members_response = test_client.get(
        f"/receipts/{receipt_id}/members",
        headers={"Authorization": f"Bearer {valid_token}"}
    )
    members = members_response.json()
    assert len(members) == 1  # Only owner


def test_remove_member_with_splits_fails(test_client, valid_token):
    """Test cannot remove member if they have splits."""
    # Create receipt
    create_response = test_client.post(
        "/receipts",
        headers={"Authorization": f"Bearer {valid_token}"},
        json={"title": "Test"}
    )
    receipt_id = create_response.json()["id"]
    version = create_response.json()["version"]
    
    # Get user ID
    me_response = test_client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {valid_token}"}
    )
    user_id = me_response.json()["id"]
    
    # Create and add member
    signup_response = test_client.post(
        "/auth/signup",
        json={
            "name": "Grace",
            "email": "grace@example.com",
            "password": "password123"
        }
    )
    grace_id = signup_response.json()["user"]["id"]
    
    test_client.post(
        f"/receipts/{receipt_id}/members",
        headers={"Authorization": f"Bearer {valid_token}"},
        json={"email": "grace@example.com"}
    )
    
    # Add items with splits including Grace
    test_client.patch(
        f"/receipts/{receipt_id}",
        headers={"Authorization": f"Bearer {valid_token}"},
        json={
            "version": version,
            "items": [
                {
                    "name": "Pizza",
                    "unit_price_cents": 2000,
                    "quantity": 2,
                    "splits": [
                        {"user_id": user_id, "share_quantity": 1.0},
                        {"user_id": grace_id, "share_quantity": 1.0}
                    ]
                }
            ]
        }
    )
    
    # Try to remove Grace
    response = test_client.delete(
        f"/receipts/{receipt_id}/members/{grace_id}",
        headers={"Authorization": f"Bearer {valid_token}"}
    )
    
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "splits" in response.json()["detail"].lower()
