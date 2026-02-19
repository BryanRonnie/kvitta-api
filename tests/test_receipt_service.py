import pytest
import pytest_asyncio
from bson import ObjectId
from fastapi import HTTPException

from app.services import receipt_service
from app.services.receipt_service import ReceiptService
from app.schemas.receipt import ReceiptCreate, ReceiptUpdate
from app.models.receipt import ReceiptStatus


@pytest_asyncio.fixture
async def patched_db(monkeypatch, test_db):
    async def _get_database():
        return test_db

    monkeypatch.setattr(receipt_service, "get_database", _get_database)
    return test_db


@pytest_asyncio.fixture
async def seeded_users(patched_db):
    owner_id = ObjectId()
    member_id = ObjectId()
    other_id = ObjectId()

    await patched_db["users"].insert_many([
        {"_id": owner_id, "email": "owner@example.com"},
        {"_id": member_id, "email": "member@example.com"},
        {"_id": other_id, "email": "other@example.com"},
    ])

    return owner_id, member_id, other_id


@pytest.mark.asyncio
async def test_create_receipt_sets_owner_and_participant(seeded_users):
    owner_id, _, _ = seeded_users
    receipt_in = ReceiptCreate(title="Dinner", description="Team dinner")

    receipt = await ReceiptService.create(receipt_in, str(owner_id))

    assert receipt.owner_id == owner_id
    assert receipt.created_by == owner_id
    assert receipt.updated_by == owner_id
    assert len(receipt.participants) == 1
    assert receipt.participants[0].user_id == owner_id


@pytest.mark.asyncio
async def test_get_receipt_invalid_id_returns_none(patched_db):
    receipt = await ReceiptService.get("not-an-objectid")
    assert receipt is None


@pytest.mark.asyncio
async def test_update_receipt_increments_version(seeded_users, patched_db):
    owner_id, _, _ = seeded_users
    receipt_in = ReceiptCreate(title="Original")
    receipt = await ReceiptService.create(receipt_in, str(owner_id))

    update = ReceiptUpdate(title="Updated", version=receipt.version)
    updated = await ReceiptService.update(str(receipt.id), update, str(owner_id))

    assert updated is not None
    assert updated.title == "Updated"
    assert updated.version == receipt.version + 1


@pytest.mark.asyncio
async def test_update_receipt_finalized_raises(seeded_users, patched_db):
    owner_id, _, _ = seeded_users
    receipt_in = ReceiptCreate(title="Locked")
    receipt = await ReceiptService.create(receipt_in, str(owner_id))

    await patched_db["receipts"].update_one(
        {"_id": receipt.id},
        {"$set": {"status": ReceiptStatus.FINALIZED}}
    )

    with pytest.raises(HTTPException) as exc:
        await ReceiptService.update(str(receipt.id), ReceiptUpdate(title="Nope", version=receipt.version), str(owner_id))

    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_list_by_user_includes_owner_and_participant(seeded_users, patched_db):
    owner_id, member_id, other_id = seeded_users

    receipt_owner = await ReceiptService.create(ReceiptCreate(title="Owner"), str(owner_id))
    receipt_other = await ReceiptService.create(ReceiptCreate(title="Other"), str(other_id))

    await ReceiptService.add_member(str(receipt_other.id), "member@example.com", str(other_id))

    owner_receipts = await ReceiptService.list_by_user(str(owner_id))
    member_receipts = await ReceiptService.list_by_user(str(member_id))

    assert any(r.id == receipt_owner.id for r in owner_receipts)
    assert any(r.id == receipt_other.id for r in member_receipts)


@pytest.mark.asyncio
async def test_delete_receipt_only_owner(seeded_users, patched_db):
    owner_id, _, other_id = seeded_users
    receipt = await ReceiptService.create(ReceiptCreate(title="Delete"), str(owner_id))

    not_owner_result = await ReceiptService.delete(str(receipt.id), str(other_id))
    assert not_owner_result is False

    owner_result = await ReceiptService.delete(str(receipt.id), str(owner_id))
    assert owner_result is True

    doc = await patched_db["receipts"].find_one({"_id": receipt.id})
    assert doc["is_deleted"] is True


@pytest.mark.asyncio
async def test_add_member_and_remove_member(seeded_users, patched_db):
    owner_id, member_id, _ = seeded_users
    receipt = await ReceiptService.create(ReceiptCreate(title="Members"), str(owner_id))

    updated = await ReceiptService.add_member(str(receipt.id), "member@example.com", str(owner_id))
    assert updated is not None
    assert any(p.user_id == member_id for p in updated.participants)

    removed = await ReceiptService.remove_member(str(receipt.id), "member@example.com", str(owner_id))
    assert removed is not None
    assert all(p.user_id != member_id for p in removed.participants)


@pytest.mark.asyncio
async def test_add_member_duplicate_raises(seeded_users, patched_db):
    owner_id, _, _ = seeded_users
    receipt = await ReceiptService.create(ReceiptCreate(title="Dup"), str(owner_id))

    await ReceiptService.add_member(str(receipt.id), "member@example.com", str(owner_id))

    with pytest.raises(HTTPException) as exc:
        await ReceiptService.add_member(str(receipt.id), "member@example.com", str(owner_id))

    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_add_member_user_not_found_raises(seeded_users, patched_db):
    owner_id, _, _ = seeded_users
    receipt = await ReceiptService.create(ReceiptCreate(title="Missing"), str(owner_id))

    with pytest.raises(HTTPException) as exc:
        await ReceiptService.add_member(str(receipt.id), "nope@example.com", str(owner_id))

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_move_to_folder_updates_folder_id(seeded_users):
    owner_id, _, _ = seeded_users
    receipt = await ReceiptService.create(ReceiptCreate(title="Folder"), str(owner_id))

    folder_id = ObjectId()
    moved = await ReceiptService.move_to_folder(str(receipt.id), str(folder_id), str(owner_id))

    assert moved is not None
    assert moved.folder_id == folder_id


@pytest.mark.asyncio
async def test_finalize_receipt_sets_status_and_calls_ledger(seeded_users, monkeypatch):
    owner_id, _, _ = seeded_users
    receipt = await ReceiptService.create(ReceiptCreate(title="Finalize"), str(owner_id))

    called = {"count": 0}

    async def _generate_from_receipt(_receipt):
        called["count"] += 1

    monkeypatch.setattr(receipt_service.LedgerService, "generate_from_receipt", _generate_from_receipt)

    finalized = await ReceiptService.finalize(str(receipt.id), str(owner_id))

    assert finalized.status == ReceiptStatus.FINALIZED
    assert called["count"] == 1


@pytest.mark.asyncio
async def test_finalize_missing_receipt_raises(patched_db, seeded_users):
    owner_id, _, _ = seeded_users

    with pytest.raises(HTTPException) as exc:
        await ReceiptService.finalize(str(ObjectId()), str(owner_id))

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_finalize_already_finalized_raises(seeded_users, patched_db):
    owner_id, _, _ = seeded_users
    receipt = await ReceiptService.create(ReceiptCreate(title="Done"), str(owner_id))

    await patched_db["receipts"].update_one(
        {"_id": receipt.id},
        {"$set": {"status": ReceiptStatus.FINALIZED}}
    )

    with pytest.raises(HTTPException) as exc:
        await ReceiptService.finalize(str(receipt.id), str(owner_id))

    assert exc.value.status_code == 400
