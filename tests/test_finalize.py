"""
Tests for receipt finalization and ledger generation.

Covers:
- Valid finalization (payments match total)
- Payment validation (sum != total)
- Draft status validation
- Ledger entry generation
- Authorization checks
"""

import pytest
from fastapi import status


@pytest.mark.asyncio
async def test_finalize_receipt_simple(test_client, valid_token):
    """Test successful receipt finalization."""
    # Create receipt
    create_response = test_client.post(
        "/receipts",
        headers={"Authorization": f"Bearer {valid_token}"},
        json={"title": "Dinner"}
    )
    receipt_id = create_response.json()["id"]
    version = create_response.json()["version"]
    
    # Get user ID
    me_response = test_client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {valid_token}"}
    )
    user_id = me_response.json()["id"]
    
    # Add items and payments
    test_client.patch(
        f"/receipts/{receipt_id}",
        headers={"Authorization": f"Bearer {valid_token}"},
        json={
            "version": version,
            "items": [
                {
                    "name": "Pizza",
                    "unit_price_cents": 1000,
                    "quantity": 1,
                    "splits": [{"user_id": user_id, "share_quantity": 1.0}]
                }
            ],
            "payments": [
                {"user_id": user_id, "amount_paid_cents": 1000}
            ]
        }
    )
    
    # Finalize
    response = test_client.post(
        f"/receipts/{receipt_id}/finalize",
        headers={"Authorization": f"Bearer {valid_token}"}
    )
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["status"] == "finalized"
    assert data["total_cents"] == 1000
    assert len(data["ledger_entries"]) == 0  # No debts, user paid all


@pytest.mark.asyncio
async def test_finalize_receipt_with_ledger(test_client, valid_token):
    """Test finalization with ledger entries generated."""
    # Create receipt
    create_response = test_client.post(
        "/receipts",
        headers={"Authorization": f"Bearer {valid_token}"},
        json={"title": "Dinner"}
    )
    receipt_id = create_response.json()["id"]
    version = create_response.json()["version"]
    
    # Get user ID
    me_response = test_client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {valid_token}"}
    )
    user_id = me_response.json()["id"]
    
    # Create another user
    signup_response = test_client.post(
        "/auth/signup",
        json={
            "name": "Bob",
            "email": "bob@example.com",
            "password": "password123"
        }
    )
    bob_id = signup_response.json()["user"]["id"]
    
    # Add Bob as member
    test_client.post(
        f"/receipts/{receipt_id}/members",
        headers={"Authorization": f"Bearer {valid_token}"},
        json={"email": "bob@example.com"}
    )
    
    # Add items (split between user and Bob) and payments (only user pays)
    test_client.patch(
        f"/receipts/{receipt_id}",
        headers={"Authorization": f"Bearer {valid_token}"},
        json={
            "version": version,
            "items": [
                {
                    "name": "Pizza",
                    "unit_price_cents": 2000,
                    "quantity": 1,
                    "splits": [
                        {"user_id": user_id, "share_quantity": 1.0},
                        {"user_id": bob_id, "share_quantity": 1.0}
                    ]
                }
            ],
            "payments": [
                {"user_id": user_id, "amount_paid_cents": 2000}
            ]
        }
    )
    
    # Finalize
    response = test_client.post(
        f"/receipts/{receipt_id}/finalize",
        headers={"Authorization": f"Bearer {valid_token}"}
    )
    
    if response.status_code != status.HTTP_200_OK:
        print(f"Finalize error: {response.json()}")
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["status"] == "finalized"
    assert data["total_cents"] == 2000
    
    # Should have one ledger entry: Bob owes user $1000
    assert len(data["ledger_entries"]) == 1
    entry = data["ledger_entries"][0]
    assert entry["debtor_id"] == bob_id
    assert entry["creditor_id"] == user_id
    assert entry["amount_cents"] == 1000
    assert entry["status"] == "pending"


@pytest.mark.asyncio
async def test_finalize_receipt_not_draft(test_client, valid_token):
    """Test finalization fails if receipt not in draft status."""
    # Create and finalize receipt
    create_response = test_client.post(
        "/receipts",
        headers={"Authorization": f"Bearer {valid_token}"},
        json={"title": "Dinner"}
    )
    receipt_id = create_response.json()["id"]
    version = create_response.json()["version"]
    
    me_response = test_client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {valid_token}"}
    )
    user_id = me_response.json()["id"]
    
    # Add valid items and payments
    test_client.patch(
        f"/receipts/{receipt_id}",
        headers={"Authorization": f"Bearer {valid_token}"},
        json={
            "version": version,
            "items": [
                {
                    "name": "Pizza",
                    "unit_price_cents": 1000,
                    "quantity": 1,
                    "splits": [{"user_id": user_id, "share_quantity": 1.0}]
                }
            ],
            "payments": [
                {"user_id": user_id, "amount_paid_cents": 1000}
            ]
        }
    )
    
    # First finalize succeeds
    finalize_response = test_client.post(
        f"/receipts/{receipt_id}/finalize",
        headers={"Authorization": f"Bearer {valid_token}"}
    )
    assert finalize_response.status_code == status.HTTP_200_OK
    
    # Second finalize fails
    retry_response = test_client.post(
        f"/receipts/{receipt_id}/finalize",
        headers={"Authorization": f"Bearer {valid_token}"}
    )
    assert retry_response.status_code == status.HTTP_400_BAD_REQUEST
    detail = retry_response.json()["detail"].lower()
    assert "must be 'draft'" in detail or "cannot finalize" in detail


@pytest.mark.asyncio
async def test_finalize_receipt_payment_mismatch(test_client, valid_token):
    """Test finalization fails if payments don't equal total."""
    # Create receipt
    create_response = test_client.post(
        "/receipts",
        headers={"Authorization": f"Bearer {valid_token}"},
        json={"title": "Dinner"}
    )
    receipt_id = create_response.json()["id"]
    version = create_response.json()["version"]
    
    me_response = test_client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {valid_token}"}
    )
    user_id = me_response.json()["id"]
    
    # Add items but incomplete payment
    test_client.patch(
        f"/receipts/{receipt_id}",
        headers={"Authorization": f"Bearer {valid_token}"},
        json={
            "version": version,
            "items": [
                {
                    "name": "Pizza",
                    "unit_price_cents": 2000,
                    "quantity": 1,
                    "splits": [{"user_id": user_id, "share_quantity": 1.0}]
                }
            ],
            "payments": [
                {"user_id": user_id, "amount_paid_cents": 1000}  # Only $10, but total is $20
            ]
        }
    )
    
    # Finalize should fail
    response = test_client.post(
        f"/receipts/{receipt_id}/finalize",
        headers={"Authorization": f"Bearer {valid_token}"}
    )
    
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "does not equal total" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_finalize_receipt_not_owner(test_client, valid_token):
    """Test non-owner cannot finalize receipt."""
    # Owner creates receipt
    create_response = test_client.post(
        "/receipts",
        headers={"Authorization": f"Bearer {valid_token}"},
        json={"title": "Dinner"}
    )
    receipt_id = create_response.json()["id"]
    version = create_response.json()["version"]
    
    me_response = test_client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {valid_token}"}
    )
    owner_id = me_response.json()["id"]
    
    # Add valid items and payments
    test_client.patch(
        f"/receipts/{receipt_id}",
        headers={"Authorization": f"Bearer {valid_token}"},
        json={
            "version": version,
            "items": [
                {
                    "name": "Pizza",
                    "unit_price_cents": 1000,
                    "quantity": 1,
                    "splits": [{"user_id": owner_id, "share_quantity": 1.0}]
                }
            ],
            "payments": [
                {"user_id": owner_id, "amount_paid_cents": 1000}
            ]
        }
    )
    
    # Create another user and add as member
    signup_response = test_client.post(
        "/auth/signup",
        json={
            "name": "Charlie",
            "email": "charlie@example.com",
            "password": "password123"
        }
    )
    
    test_client.post(
        f"/receipts/{receipt_id}/members",
        headers={"Authorization": f"Bearer {valid_token}"},
        json={"email": "charlie@example.com"}
    )
    
    # Login as Charlie
    charlie_login = test_client.post(
        "/auth/login",
        data={"email": "charlie@example.com", "password": "password123"}
    )
    charlie_token = charlie_login.json()["access_token"]
    
    # Charlie tries to finalize
    response = test_client.post(
        f"/receipts/{receipt_id}/finalize",
        headers={"Authorization": f"Bearer {charlie_token}"}
    )
    
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_finalize_receipt_no_items(test_client, valid_token):
    """Test finalize fails for receipt with no items (but attempts payment)."""
    create_response = test_client.post(
        "/receipts",
        headers={"Authorization": f"Bearer {valid_token}"},
        json={"title": "Empty"}
    )
    receipt_id = create_response.json()["id"]
    
    me_response = test_client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {valid_token}"}
    )
    user_id = me_response.json()["id"]
    
    # Try to finalize with no items but with payment
    response = test_client.post(
        f"/receipts/{receipt_id}/finalize",
        headers={"Authorization": f"Bearer {valid_token}"}
    )
    
    # Should fail because total is 0 or payment doesn't match
    assert response.status_code == status.HTTP_400_BAD_REQUEST
