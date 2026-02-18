from typing import List
from fastapi import APIRouter, HTTPException
from app.schemas.user import UserCreate, UserResponse, UserUpdate
from app.models.user import User
from app.db.session import get_database
from bson import ObjectId

router = APIRouter()

@router.post("/", response_model=UserResponse)
async def create_user(user_in: UserCreate):
    db = await get_database()
    existing = await db.users.find_one({"email": user_in.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
        
    user = User(**user_in.model_dump())
    result = await db.users.insert_one(user.model_dump(by_alias=True))
    user.id = result.inserted_id
    
    return user

@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: str):
    db = await get_database()
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=400, detail="Invalid ID")
        
    doc = await db.users.find_one({"_id": ObjectId(user_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="User not found")
        
    return User(**doc)
