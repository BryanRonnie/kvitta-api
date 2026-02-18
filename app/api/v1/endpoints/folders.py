from typing import List
from fastapi import APIRouter, HTTPException, Depends
from app.schemas.folder import FolderCreate, FolderResponse, FolderUpdate
from app.models.folder import Folder
from app.db.session import get_database
from bson import ObjectId

router = APIRouter()

# TODO: Add authentication dependency to get current_user_id
# For now, we'll pass owner_id in query or assume a default for testing
# Ideally: async def get_current_user(...)

@router.post("/", response_model=FolderResponse)
async def create_folder(folder_in: FolderCreate, owner_id: str):
    db = await get_database()
    
    folder_dict = folder_in.model_dump()
    folder_dict["owner_id"] = ObjectId(owner_id)
    if folder_in.parent_folder_id:
        folder_dict["parent_folder_id"] = ObjectId(folder_in.parent_folder_id)
        
    folder = Folder(**folder_dict)
    result = await db.folders.insert_one(folder.model_dump(by_alias=True))
    folder.id = result.inserted_id
    
    return folder

@router.get("/", response_model=List[FolderResponse])
async def get_folders(owner_id: str):
    db = await get_database()
    cursor = db.folders.find({"owner_id": ObjectId(owner_id), "is_deleted": False})
    return [Folder(**doc) async for doc in cursor]

@router.get("/{folder_id}", response_model=FolderResponse)
async def get_folder(folder_id: str):
    db = await get_database()
    doc = await db.folders.find_one({"_id": ObjectId(folder_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Folder not found")
    return Folder(**doc)
