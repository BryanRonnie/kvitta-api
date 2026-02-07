"""
Folder routes for organizing receipts
"""

from datetime import datetime
from typing import List
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status
from models import FolderCreate, FolderResponse, UserInDB
from auth_routes import get_current_user
from database import get_folders_collection, get_groups_collection

router = APIRouter(prefix="/folders", tags=["Folders"])


def serialize_folder(folder: dict) -> dict:
    return {
        "id": str(folder["_id"]),
        "name": folder["name"],
        "color": folder["color"],
        "created_by": folder["created_by"],
        "created_at": folder["created_at"],
        "updated_at": folder["updated_at"],
        "receipt_count": folder.get("receipt_count", 0),
    }


@router.post("", response_model=FolderResponse)
async def create_folder(
    folder_data: FolderCreate, current_user: UserInDB = Depends(get_current_user)
):
    folders_collection = await get_folders_collection()

    now = datetime.utcnow()
    folder = {
        "name": folder_data.name,
        "color": folder_data.color,
        "created_by": current_user.email,
        "created_at": now,
        "updated_at": now,
        "receipt_count": 0,
    }

    result = await folders_collection.insert_one(folder)
    folder["_id"] = result.inserted_id

    return FolderResponse(**serialize_folder(folder))


@router.get("", response_model=List[FolderResponse])
async def list_folders(current_user: UserInDB = Depends(get_current_user)):
    folders_collection = await get_folders_collection()
    groups_collection = await get_groups_collection()

    folders = await folders_collection.find({"created_by": current_user.email}).to_list(length=None)

    # Count receipts in each folder
    for folder in folders:
        folder_id = str(folder["_id"])
        count = await groups_collection.count_documents({"folder_id": folder_id})
        folder["receipt_count"] = count

    return [FolderResponse(**serialize_folder(folder)) for folder in folders]


@router.delete("/{folder_id}")
async def delete_folder(folder_id: str, current_user: UserInDB = Depends(get_current_user)):
    folders_collection = await get_folders_collection()
    groups_collection = await get_groups_collection()

    try:
        folder = await folders_collection.find_one({"_id": ObjectId(folder_id)})
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid folder id")

    if not folder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found")

    if folder["created_by"] != current_user.email:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to delete this folder"
        )

    # Remove folder_id from all receipts in this folder
    await groups_collection.update_many(
        {"folder_id": folder_id}, {"$unset": {"folder_id": ""}, "$set": {"updated_at": datetime.utcnow()}}
    )

    await folders_collection.delete_one({"_id": ObjectId(folder_id)})

    return {"message": "Folder deleted"}


@router.patch("/{folder_id}")
async def update_folder(
    folder_id: str, folder_data: FolderCreate, current_user: UserInDB = Depends(get_current_user)
):
    folders_collection = await get_folders_collection()

    try:
        folder = await folders_collection.find_one({"_id": ObjectId(folder_id)})
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid folder id")

    if not folder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found")

    if folder["created_by"] != current_user.email:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to update this folder"
        )

    now = datetime.utcnow()
    await folders_collection.update_one(
        {"_id": ObjectId(folder_id)},
        {"$set": {"name": folder_data.name, "color": folder_data.color, "updated_at": now}},
    )

    updated_folder = await folders_collection.find_one({"_id": ObjectId(folder_id)})
    groups_collection = await get_groups_collection()
    count = await groups_collection.count_documents({"folder_id": folder_id})
    updated_folder["receipt_count"] = count

    return FolderResponse(**serialize_folder(updated_folder))
