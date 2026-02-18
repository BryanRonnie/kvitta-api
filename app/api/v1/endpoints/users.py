from typing import List
from fastapi import APIRouter, HTTPException, Depends
from app.schemas.user import UserCreate, UserResponse, UserUpdate
from app.models.user import User
from app.db.session import get_database
from app.api.v1.endpoints.auth import get_current_user
from bson import ObjectId

router = APIRouter()

@router.get("/me", response_model=UserResponse)
async def get_my_profile(current_user: User = Depends(get_current_user)):
    """Get current user profile"""
    return UserResponse(
        id=str(current_user.id),
        name=current_user.name,
        email=current_user.email,
        is_deleted=current_user.is_deleted
    )

@router.patch("/me", response_model=UserResponse)
async def update_my_profile(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_user)
):
    """Update current user profile"""
    db = await get_database()
    
    update_data = {}
    if user_update.name:
        update_data["name"] = user_update.name
    if user_update.email:
        # Check if email is already taken
        existing = await db.users.find_one({
            "email": user_update.email,
            "_id": {"$ne": current_user.id}
        })
        if existing:
            raise HTTPException(status_code=400, detail="Email already in use")
        update_data["email"] = user_update.email
    
    if update_data:
        await db.users.update_one(
            {"_id": current_user.id},
            {"$set": update_data}
        )
    
    updated_user = await db.users.find_one({"_id": current_user.id})
    return UserResponse(
        id=str(updated_user["_id"]),
        name=updated_user["name"],
        email=updated_user["email"],
        is_deleted=updated_user.get("is_deleted", False)
    )

@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get user by ID (requires authentication)"""
    db = await get_database()
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=400, detail="Invalid ID")
        
    doc = await db.users.find_one({"_id": ObjectId(user_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="User not found")
        
    return UserResponse(
        id=str(doc["_id"]),
        name=doc["name"],
        email=doc["email"],
        is_deleted=doc.get("is_deleted", False)
    )
