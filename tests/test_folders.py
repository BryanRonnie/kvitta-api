import pytest
from fastapi import status

from app.models.folder import FolderCreate
from app.repositories.folder_repo import FolderRepository


@pytest.mark.asyncio
async def test_create_folder_repo(test_db, created_user):
    repo = FolderRepository(test_db)
    folder = await repo.create_folder(FolderCreate(name="Trips", color="#00AAFF"), str(created_user._id))

    assert folder.name == "Trips"
    assert folder.color == "#00AAFF"
    assert folder.owner_id == created_user._id
    assert folder.is_deleted is False


@pytest.mark.asyncio
async def test_list_folders_repo_filters_owner(test_db, created_user):
    repo = FolderRepository(test_db)
    other_owner = "507f1f77bcf86cd799439011"

    await repo.create_folder(FolderCreate(name="Mine", color="#111111"), str(created_user._id))
    await repo.create_folder(FolderCreate(name="Other", color="#222222"), other_owner)

    folders = await repo.list_folders(str(created_user._id))

    assert len(folders) == 1
    assert folders[0].name == "Mine"


def test_create_folder_endpoint(test_client, valid_token):
    response = test_client.post(
        "/folders",
        headers={"Authorization": f"Bearer {valid_token}"},
        json={"name": "Food", "color": "#FFAA00"}
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["name"] == "Food"
    assert data["color"] == "#FFAA00"
    assert "id" in data


def test_list_folders_endpoint(test_client, valid_token):
    test_client.post(
        "/folders",
        headers={"Authorization": f"Bearer {valid_token}"},
        json={"name": "Bills", "color": "#00FF00"}
    )

    response = test_client.get(
        "/folders",
        headers={"Authorization": f"Bearer {valid_token}"}
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "Bills"


def test_update_folder_endpoint(test_client, valid_token):
    create_response = test_client.post(
        "/folders",
        headers={"Authorization": f"Bearer {valid_token}"},
        json={"name": "Old", "color": "#123456"}
    )
    folder_id = create_response.json()["id"]

    update_response = test_client.patch(
        f"/folders/{folder_id}",
        headers={"Authorization": f"Bearer {valid_token}"},
        json={"name": "New", "color": "#654321"}
    )

    assert update_response.status_code == status.HTTP_200_OK
    data = update_response.json()
    assert data["name"] == "New"
    assert data["color"] == "#654321"


def test_delete_folder_endpoint(test_client, valid_token):
    create_response = test_client.post(
        "/folders",
        headers={"Authorization": f"Bearer {valid_token}"},
        json={"name": "Trash", "color": "#000000"}
    )
    folder_id = create_response.json()["id"]

    delete_response = test_client.delete(
        f"/folders/{folder_id}",
        headers={"Authorization": f"Bearer {valid_token}"}
    )

    assert delete_response.status_code == status.HTTP_200_OK
    assert delete_response.json()["success"] is True


def test_folders_requires_auth(test_client):
    response = test_client.get("/folders")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
