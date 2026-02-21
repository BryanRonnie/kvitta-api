"""
Tests for ledger repository and financial calculations.

Covers:
- Liability calculation per participant
- Tax/tip allocation
- Debtor/creditor matching
- Settlement tracking
- Balance aggregation
"""

import pytest
from datetime import datetime
from bson import ObjectId

from app.models.ledger import LedgerEntry
from app.models.receipt import Receipt, Item, Split, Participant, Payment
from app.repositories.ledger_repo import LedgerRepository
from app.utils.receipt_validation import ReceiptValidationError


@pytest.mark.asyncio
async def test_create_ledger_simple_two_user(test_db):
    """Test ledger creation: two users, one pays all."""
    repo = LedgerRepository(test_db)
    
    alice_id = ObjectId()
    bob_id = ObjectId()
    
    # Alice and Bob split pizza: Alice pays $20, Bob pays $0
    receipt = Receipt(
        owner_id=alice_id,
        created_by=alice_id,
        updated_by=alice_id,
        title="Pizza",
        description="Test",
        participants=[
            Participant(user_id=alice_id, role="owner"),
            Participant(user_id=bob_id, role="member")
        ],
        items=[
            Item(
                name="Pizza",
                unit_price_cents=2000,
                quantity=1,
                splits=[
                    Split(user_id=alice_id, share_quantity=1.0),
                    Split(user_id=bob_id, share_quantity=1.0)
                ]
            )
        ],
        payments=[
            Payment(user_id=alice_id, amount_paid_cents=2000)
        ],
        subtotal_cents=2000,
        tax_cents=0,
        tip_cents=0,
        total_cents=2000,
        status="finalized",
        version=1
    )
    
    entries = await repo.insert_ledger_entries(receipt)
    
    # Should have one entry: Bob owes Alice $10
    assert len(entries) == 1
    assert entries[0].debtor_id == str(bob_id)
    assert entries[0].creditor_id == str(alice_id)
    assert entries[0].amount_cents == 1000
    assert entries[0].status == "pending"


@pytest.mark.asyncio
async def test_create_ledger_with_tax_tip(test_db):
    """Test ledger: tax and tip allocated proportionally."""
    repo = LedgerRepository(test_db)
    
    alice_id = ObjectId()
    bob_id = ObjectId()
    
    # Subtotal $100, +$10 tax, +$10 tip = $120 total
    # Alice pays all, both split items equally
    receipt = Receipt(
        owner_id=alice_id,
        created_by=alice_id,
        updated_by=alice_id,
        title="Dinner",
        participants=[
            Participant(user_id=alice_id, role="owner"),
            Participant(user_id=bob_id, role="member")
        ],
        items=[
            Item(
                name="Entree",
                unit_price_cents=10000,
                quantity=1,
                splits=[
                    Split(user_id=alice_id, share_quantity=1.0),
                    Split(user_id=bob_id, share_quantity=1.0)
                ]
            )
        ],
        payments=[
            Payment(user_id=alice_id, amount_paid_cents=12000)
        ],
        subtotal_cents=10000,
        tax_cents=1000,
        tip_cents=1000,
        total_cents=12000,
        status="finalized",
        version=1
    )
    
    entries = await repo.insert_ledger_entries(receipt)
    
    # Bob should owe: half item ($5000) + half tax+tip ($1000) = $6000
    assert len(entries) == 1
    assert entries[0].amount_cents == 6000
    assert entries[0].debtor_id == str(bob_id)
    assert entries[0].creditor_id == str(alice_id)


@pytest.mark.asyncio
async def test_create_ledger_three_way_split(test_db):
    """Test ledger: three users with unequal splits."""
    repo = LedgerRepository(test_db)
    
    alice_id = ObjectId()
    bob_id = ObjectId()
    charlie_id = ObjectId()
    
    # $30 pizza: Alice gets 1/2, Bob gets 1/4, Charlie gets 1/4
    # Alice pays all
    receipt = Receipt(
        owner_id=alice_id,
        created_by=alice_id,
        updated_by=alice_id,
        title="Pizza",
        participants=[
            Participant(user_id=alice_id, role="owner"),
            Participant(user_id=bob_id, role="member"),
            Participant(user_id=charlie_id, role="member")
        ],
        items=[
            Item(
                name="Pizza",
                unit_price_cents=3000,
                quantity=1,
                splits=[
                    Split(user_id=alice_id, share_quantity=2.0),
                    Split(user_id=bob_id, share_quantity=1.0),
                    Split(user_id=charlie_id, share_quantity=1.0)
                ]
            )
        ],
        payments=[
            Payment(user_id=alice_id, amount_paid_cents=3000)
        ],
        subtotal_cents=3000,
        tax_cents=0,
        tip_cents=0,
        total_cents=3000,
        status="finalized",
        version=1
    )
    
    entries = await repo.insert_ledger_entries(receipt)
    
    # Should have 2 entries (Bob and Charlie each owe Alice)
    assert len(entries) == 2
    
    # Bob owes 1/4 of pizza = $750
    bob_entry = [e for e in entries if str(e.debtor_id) == str(bob_id)][0]
    assert bob_entry.amount_cents == 750
    assert bob_entry.creditor_id == str(alice_id)
    
    # Charlie owes 1/4 of pizza = $750
    charlie_entry = [e for e in entries if str(e.debtor_id) == str(charlie_id)][0]
    assert charlie_entry.amount_cents == 750
    assert charlie_entry.creditor_id == str(alice_id)


@pytest.mark.asyncio
async def test_create_ledger_complex_payments(test_db):
    """Test ledger: multiple payers, complex settlement."""
    repo = LedgerRepository(test_db)
    
    alice_id = ObjectId()
    bob_id = ObjectId()
    charlie_id = ObjectId()
    
    # $90 total: each person should pay $30
    # Alice pays $50, Bob pays $20, Charlie pays $20
    receipt = Receipt(
        owner_id=alice_id,
        created_by=alice_id,
        updated_by=alice_id,
        title="Dinner",
        participants=[
            Participant(user_id=alice_id, role="owner"),
            Participant(user_id=bob_id, role="member"),
            Participant(user_id=charlie_id, role="member")
        ],
        items=[
            Item(
                name="Food",
                unit_price_cents=9000,
                quantity=1,
                splits=[
                    Split(user_id=alice_id, share_quantity=1.0),
                    Split(user_id=bob_id, share_quantity=1.0),
                    Split(user_id=charlie_id, share_quantity=1.0)
                ]
            )
        ],
        payments=[
            Payment(user_id=alice_id, amount_paid_cents=5000),
            Payment(user_id=bob_id, amount_paid_cents=2000),
            Payment(user_id=charlie_id, amount_paid_cents=2000)
        ],
        subtotal_cents=9000,
        tax_cents=0,
        tip_cents=0,
        total_cents=9000,
        status="finalized",
        version=1
    )
    
    entries = await repo.insert_ledger_entries(receipt)
    
    # Alice overpaid by $2000, so Bob and Charlie each owe Alice $1000
    assert len(entries) == 2
    
    for entry in entries:
        assert entry.creditor_id == str(alice_id)
        assert entry.amount_cents == 1000


@pytest.mark.asyncio
async def test_ledger_entry_property_open_amount(test_db):
    """Test LedgerEntry.open_amount_cents() calculation."""
    entry = LedgerEntry(
        receipt_id=str(ObjectId()),
        debtor_id=str(ObjectId()),
        creditor_id=str(ObjectId()),
        amount_cents=1000,
        settled_amount_cents=350
    )
    
    assert entry.open_amount_cents() == 650
    assert not entry.is_fully_settled()
    
    # After settling full amount
    entry.settled_amount_cents = 1000
    assert entry.open_amount_cents() == 0
    assert entry.is_fully_settled()


@pytest.mark.asyncio
async def test_settle_entry_partial(test_db):
    """Test partial settlement of a ledger entry."""
    repo = LedgerRepository(test_db)
    
    # Create an entry
    entry = LedgerEntry(
        receipt_id=str(ObjectId()),
        debtor_id=str(ObjectId()),
        creditor_id=str(ObjectId()),
        amount_cents=1000,
        settled_amount_cents=0,
        status="pending"
    )
    
    # Insert it
    doc = entry.model_dump(by_alias=True, exclude_none=True)
    result = await repo.collection.insert_one(doc)
    entry_id = str(result.inserted_id)
    
    # Settle half
    updated = await repo.settle_entry(entry_id, 500)
    
    assert updated is not None
    assert updated.settled_amount_cents == 500
    assert updated.status == "partially_settled"
    assert updated.open_amount_cents() == 500


@pytest.mark.asyncio
async def test_settle_entry_full(test_db):
    """Test full settlement of a ledger entry."""
    repo = LedgerRepository(test_db)
    
    entry = LedgerEntry(
        receipt_id=str(ObjectId()),
        debtor_id=str(ObjectId()),
        creditor_id=str(ObjectId()),
        amount_cents=1000,
        settled_amount_cents=0,
        status="pending"
    )
    
    doc = entry.model_dump(by_alias=True, exclude_none=True)
    result = await repo.collection.insert_one(doc)
    entry_id = str(result.inserted_id)
    
    # Settle full amount
    updated = await repo.settle_entry(entry_id, 1000)
    
    assert updated is not None
    assert updated.settled_amount_cents == 1000
    assert updated.status == "settled"
    assert updated.is_fully_settled()


@pytest.mark.asyncio
async def test_settle_entry_invalid_amount(test_db):
    """Test settlement fails with invalid amount."""
    repo = LedgerRepository(test_db)
    
    entry = LedgerEntry(
        receipt_id=str(ObjectId()),
        debtor_id=str(ObjectId()),
        creditor_id=str(ObjectId()),
        amount_cents=1000,
        settled_amount_cents=0
    )
    
    doc = entry.model_dump(by_alias=True, exclude_none=True)
    result = await repo.collection.insert_one(doc)
    entry_id = str(result.inserted_id)
    
    # Try to settle more than open amount
    with pytest.raises(ReceiptValidationError):
        await repo.settle_entry(entry_id, 1500)


@pytest.mark.asyncio
async def test_get_user_balance(test_db):
    """Test balance aggregation across multiple entries."""
    repo = LedgerRepository(test_db)
    
    alice_id = ObjectId()
    bob_id = ObjectId()
    charlie_id = ObjectId()
    
    # Create entries
    entries = [
        LedgerEntry(
            receipt_id=str(ObjectId()),
            debtor_id=str(bob_id),
            creditor_id=str(alice_id),
            amount_cents=500,
            settled_amount_cents=0,
            status="pending"
        ),
        LedgerEntry(
            receipt_id=str(ObjectId()),
            debtor_id=str(charlie_id),
            creditor_id=str(alice_id),
            amount_cents=300,
            settled_amount_cents=100,
            status="partially_settled"
        )
    ]
    
    for entry in entries:
        doc = entry.model_dump(by_alias=True, exclude_none=True)
        await repo.collection.insert_one(doc)
    
    # Alice's balance: is owed $500 (from Bob) + $200 (from Charlie) = $700
    balance = await repo.get_user_balance(str(alice_id))
    
    assert balance["is_owed_cents"] == 700
    assert balance["owes_cents"] == 0
    assert balance["net_cents"] == 700


@pytest.mark.asyncio
async def test_get_ledger_by_receipt(test_db):
    """Test retrieving all entries for a receipt."""
    repo = LedgerRepository(test_db)
    
    receipt_id = str(ObjectId())
    
    entries = [
        LedgerEntry(
            receipt_id=receipt_id,
            debtor_id=str(ObjectId()),
            creditor_id=str(ObjectId()),
            amount_cents=500
        ),
        LedgerEntry(
            receipt_id=receipt_id,
            debtor_id=str(ObjectId()),
            creditor_id=str(ObjectId()),
            amount_cents=300
        )
    ]
    
    for entry in entries:
        doc = entry.model_dump(by_alias=True, exclude_none=True)
        await repo.collection.insert_one(doc)
    
    # Add entry for different receipt
    other_entry = LedgerEntry(
        receipt_id=str(ObjectId()),
        debtor_id=str(ObjectId()),
        creditor_id=str(ObjectId()),
        amount_cents=100
    )
    await repo.collection.insert_one(other_entry.model_dump(by_alias=True, exclude_none=True))
    
    # Query receipt entries
    result = await repo.get_ledger_by_receipt(receipt_id)
    
    assert len(result) == 2
    assert all(e.receipt_id == receipt_id for e in result)


@pytest.mark.asyncio
async def test_ledger_calculation_error_not_finalized(test_db):
    """Test that ledger creation fails for non-finalized receipts."""
    repo = LedgerRepository(test_db)
    
    receipt = Receipt(
        owner_id=ObjectId(),
        created_by=ObjectId(),
        updated_by=ObjectId(),
        title="Test",
        status="draft",  # Not finalized!
        version=1
    )
    
    with pytest.raises(ReceiptValidationError):
        await repo.insert_ledger_entries(receipt)


@pytest.mark.asyncio
async def test_ledger_zero_total(test_db):
    """Test ledger creation fails for zero-total receipts."""
    repo = LedgerRepository(test_db)
    
    receipt = Receipt(
        owner_id=ObjectId(),
        created_by=ObjectId(),
        updated_by=ObjectId(),
        title="Test",
        status="finalized",
        total_cents=0,  # Invalid!
        version=1
    )
    
    with pytest.raises(ReceiptValidationError):
        await repo.insert_ledger_entries(receipt)
