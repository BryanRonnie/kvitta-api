"""
API endpoint to move receipts between folders
"""
from datetime import datetime
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from models import UserInDB, GroupResponse
from auth_routes import get_current_user
from database import get_groups_collection, get_folders_collection
from groups_routes import serialize_group, find_member

router = APIRouter(prefix="/receipts", tags=["Receipts"])


class MoveReceiptPayload(BaseModel):
    folder_id: str | None


@router.patch("/{receipt_id}/move", response_model=GroupResponse)
async def move_receipt(
    receipt_id: str,
    payload: MoveReceiptPayload,
    current_user: UserInDB = Depends(get_current_user),
):
    groups_collection = await get_groups_collection()
    folders_collection = await get_folders_collection()

    try:
        receipt = await groups_collection.find_one({"_id": ObjectId(receipt_id)})
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid receipt id")

    if not receipt or not find_member(receipt["members"], current_user.email):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Receipt not found")

    # Verify folder exists if folder_id is provided
    if payload.folder_id:
        try:
            folder = await folders_collection.find_one({"_id": ObjectId(payload.folder_id)})
        except Exception:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid folder id")

        if not folder or folder["created_by"] != current_user.email:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found"
            )

    # Update receipt folder_id
    now = datetime.utcnow()
    await groups_collection.update_one(
        {"_id": ObjectId(receipt_id)},
        {"$set": {"folder_id": payload.folder_id, "updated_at": now}},
    )

    updated_receipt = await groups_collection.find_one({"_id": ObjectId(receipt_id)})
    return GroupResponse(**serialize_group(updated_receipt))
