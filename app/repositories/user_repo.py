from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
from datetime import datetime, timezone
from app.models.user import UserCreate, UserInDB
from app.core.security import hash_password

class UserRepository:
    """User database operations."""
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db["users"]
    
    async def create_user(self, user_data: UserCreate) -> UserInDB:
        """Create a new user."""
        user_dict = {
            "name": user_data.name,
            "email": user_data.email,
            "password_hash": hash_password(user_data.password),
            "is_deleted": False,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        
        result = await self.collection.insert_one(user_dict)
        user_dict["_id"] = result.inserted_id
        return UserInDB(**user_dict)
    
    async def get_user_by_email(self, email: str) -> UserInDB | None:
        """Get user by email."""
        user = await self.collection.find_one({"email": email, "is_deleted": False})
        if user:
            return UserInDB(**user)
        return None
    
    async def get_user_by_id(self, user_id: str) -> UserInDB | None:
        """Get user by ID."""
        try:
            user = await self.collection.find_one({
                "_id": ObjectId(user_id),
                "is_deleted": False
            })
            if user:
                return UserInDB(**user)
        except Exception:
            pass
        return None
    
    async def update_user(self, user_id: str, update_data: dict) -> UserInDB | None:
        """Update user."""
        try:
            update_data["updated_at"] = datetime.now(timezone.utc)
            result = await self.collection.find_one_and_update(
                {"_id": ObjectId(user_id), "is_deleted": False},
                {"$set": update_data},
                return_document=True
            )
            if result:
                return UserInDB(**result)
        except Exception:
            pass
        return None
    
    async def soft_delete_user(self, user_id: str) -> bool:
        """Soft delete user."""
        try:
            result = await self.collection.update_one(
                {"_id": ObjectId(user_id)},
                {"$set": {
                    "is_deleted": True,
                    "updated_at": datetime.now(timezone.utc)
                }}
            )
            return result.modified_count > 0
        except Exception:
            return False
