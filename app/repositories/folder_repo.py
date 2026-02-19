from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
from datetime import datetime, timezone

from app.models.folder import FolderCreate, FolderUpdate, FolderInDB


class FolderRepository:
    """Folder database operations."""

    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db["folders"]

    async def create_folder(self, folder_data: FolderCreate, owner_id: str) -> FolderInDB:
        """Create a new folder."""
        folder_dict = {
            "name": folder_data.name,
            "color": folder_data.color,
            "owner_id": ObjectId(owner_id),
            "is_deleted": False,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }

        result = await self.collection.insert_one(folder_dict)
        folder_dict["_id"] = result.inserted_id
        return FolderInDB(**folder_dict)

    async def list_folders(self, owner_id: str) -> list[FolderInDB]:
        """List folders for an owner."""
        cursor = self.collection.find({
            "owner_id": ObjectId(owner_id),
            "is_deleted": False
        }).sort("created_at", -1)
        folders = await cursor.to_list(None)
        return [FolderInDB(**doc) for doc in folders]

    async def update_folder(self, folder_id: str, owner_id: str, update_data: FolderUpdate) -> FolderInDB | None:
        """Update a folder."""
        try:
            updates = update_data.model_dump(exclude_unset=True)
            if not updates:
                return await self.get_folder(folder_id, owner_id)

            updates["updated_at"] = datetime.now(timezone.utc)
            result = await self.collection.find_one_and_update(
                {
                    "_id": ObjectId(folder_id),
                    "owner_id": ObjectId(owner_id),
                    "is_deleted": False
                },
                {"$set": updates},
                return_document=True
            )
            if result:
                return FolderInDB(**result)
        except Exception:
            return None
        return None

    async def soft_delete_folder(self, folder_id: str, owner_id: str) -> bool:
        """Soft delete a folder."""
        try:
            result = await self.collection.update_one(
                {
                    "_id": ObjectId(folder_id),
                    "owner_id": ObjectId(owner_id),
                    "is_deleted": False
                },
                {"$set": {
                    "is_deleted": True,
                    "updated_at": datetime.now(timezone.utc)
                }}
            )
            return result.modified_count > 0
        except Exception:
            return False

    async def get_folder(self, folder_id: str, owner_id: str) -> FolderInDB | None:
        """Get a folder by id for an owner."""
        try:
            doc = await self.collection.find_one({
                "_id": ObjectId(folder_id),
                "owner_id": ObjectId(owner_id),
                "is_deleted": False
            })
            if doc:
                return FolderInDB(**doc)
        except Exception:
            return None
        return None
