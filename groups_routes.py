"""
Group expense room routes
"""

from datetime import datetime
from typing import List
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status
from models import (
    GroupCreate,
    GroupResponse,
    GroupMember,
    GroupAddMember,
    GroupUpdateRole,
    UserInDB,
)
from auth_routes import get_current_user
from database import get_groups_collection, get_users_collection

router = APIRouter(prefix="/groups", tags=["Groups"])

ROLE_ADMIN = "admin"
ROLE_MEMBER = "member"


def serialize_group(group: dict) -> dict:
    return {
        "id": str(group["_id"]),
        "name": group["name"],
        "description": group.get("description"),
        "created_by": group["created_by"],
        "created_at": group["created_at"],
        "updated_at": group["updated_at"],
        "members": group["members"],
        "folder_id": group.get("folder_id"),
    }


def find_member(members: List[dict], email: str) -> dict | None:
    for member in members:
        if member["email"] == email:
            return member
    return None


def ensure_admin(members: List[dict], email: str):
    member = find_member(members, email)
    if not member or member["role"] != ROLE_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin permissions required",
        )


@router.post("", response_model=GroupResponse, status_code=status.HTTP_201_CREATED)
async def create_group(group_data: GroupCreate, current_user: UserInDB = Depends(get_current_user)):
    groups_collection = await get_groups_collection()
    now = datetime.utcnow()

    members = [
        {
            "email": current_user.email,
            "role": ROLE_ADMIN,
            "joined_at": now,
        }
    ]

    group_doc = {
        "name": group_data.name,
        "description": group_data.description,
        "created_by": current_user.email,
        "created_at": now,
        "updated_at": now,
        "members": members,
        "folder_id": getattr(group_data, 'folder_id', None),
    }

    result = await groups_collection.insert_one(group_doc)
    group_doc["_id"] = result.inserted_id

    return GroupResponse(**serialize_group(group_doc))


@router.get("", response_model=List[GroupResponse])
async def list_groups(current_user: UserInDB = Depends(get_current_user)):
    groups_collection = await get_groups_collection()

    cursor = groups_collection.find({"members.email": current_user.email})
    groups = await cursor.to_list(length=100)

    return [GroupResponse(**serialize_group(group)) for group in groups]


@router.get("/{group_id}", response_model=GroupResponse)
async def get_group(group_id: str, current_user: UserInDB = Depends(get_current_user)):
    groups_collection = await get_groups_collection()

    try:
        group = await groups_collection.find_one({"_id": ObjectId(group_id)})
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid group id")

    if not group or not find_member(group["members"], current_user.email):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")

    return GroupResponse(**serialize_group(group))


@router.post("/{group_id}/members", response_model=GroupResponse)
async def add_member(
    group_id: str,
    payload: GroupAddMember,
    current_user: UserInDB = Depends(get_current_user),
):
    groups_collection = await get_groups_collection()
    users_collection = await get_users_collection()

    try:
        group = await groups_collection.find_one({"_id": ObjectId(group_id)})
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid group id")

    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")

    ensure_admin(group["members"], current_user.email)

    # Check user exists
    existing_user = await users_collection.find_one({"email": payload.email})
    if not existing_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not in kvitta")

    if find_member(group["members"], payload.email):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User already in group")

    now = datetime.utcnow()
    new_member = {
        "email": payload.email,
        "role": ROLE_MEMBER,
        "joined_at": now,
    }

    await groups_collection.update_one(
        {"_id": ObjectId(group_id)},
        {
            "$push": {"members": new_member},
            "$set": {"updated_at": now},
        },
    )

    updated_group = await groups_collection.find_one({"_id": ObjectId(group_id)})
    return GroupResponse(**serialize_group(updated_group))


@router.patch("/{group_id}/members/{member_email}", response_model=GroupResponse)
async def update_member_role(
    group_id: str,
    member_email: str,
    payload: GroupUpdateRole,
    current_user: UserInDB = Depends(get_current_user),
):
    groups_collection = await get_groups_collection()

    try:
        group = await groups_collection.find_one({"_id": ObjectId(group_id)})
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid group id")

    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")

    ensure_admin(group["members"], current_user.email)

    member = find_member(group["members"], member_email)
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")

    if member["email"] == group["created_by"] and payload.role != ROLE_ADMIN:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot demote creator")

    if member["role"] == ROLE_ADMIN and payload.role != ROLE_ADMIN:
        admin_count = sum(1 for m in group["members"] if m["role"] == ROLE_ADMIN)
        if admin_count <= 1:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="At least one admin required")

    now = datetime.utcnow()
    await groups_collection.update_one(
        {"_id": ObjectId(group_id), "members.email": member_email},
        {
            "$set": {
                "members.$.role": payload.role,
                "updated_at": now,
            }
        },
    )

    updated_group = await groups_collection.find_one({"_id": ObjectId(group_id)})
    return GroupResponse(**serialize_group(updated_group))


@router.post("/{group_id}/leave")
async def leave_group(group_id: str, current_user: UserInDB = Depends(get_current_user)):
    groups_collection = await get_groups_collection()

    try:
        group = await groups_collection.find_one({"_id": ObjectId(group_id)})
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid group id")

    if not group or not find_member(group["members"], current_user.email):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")

    admin_count = sum(1 for m in group["members"] if m["role"] == ROLE_ADMIN)
    is_admin = find_member(group["members"], current_user.email)["role"] == ROLE_ADMIN

    if is_admin and admin_count <= 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Assign another admin before leaving",
        )

    now = datetime.utcnow()
    await groups_collection.update_one(
        {"_id": ObjectId(group_id)},
        {
            "$pull": {"members": {"email": current_user.email}},
            "$set": {"updated_at": now},
        },
    )

    # If creator left and there is another admin, transfer created_by
    if group["created_by"] == current_user.email:
        updated_group = await groups_collection.find_one({"_id": ObjectId(group_id)})
        if updated_group and updated_group["members"]:
            new_admin = next((m for m in updated_group["members"] if m["role"] == ROLE_ADMIN), None)
            if new_admin:
                await groups_collection.update_one(
                    {"_id": ObjectId(group_id)},
                    {"$set": {"created_by": new_admin["email"], "updated_at": now}},
                )

    return {"message": "Left group"}


@router.delete("/{group_id}")
async def delete_group(group_id: str, current_user: UserInDB = Depends(get_current_user)):
    groups_collection = await get_groups_collection()

    try:
        group = await groups_collection.find_one({"_id": ObjectId(group_id)})
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid group id")

    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")

    # Only admins can delete the group
    ensure_admin(group["members"], current_user.email)

    await groups_collection.delete_one({"_id": ObjectId(group_id)})

    return {"message": "Group deleted"}
