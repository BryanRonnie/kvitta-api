from typing import List
from fastapi import APIRouter, HTTPException, Depends
from app.schemas.folder import FolderCreate, FolderResponse, FolderUpdate
from app.models.folder import Folder
from app.models.user import User
from app.db.session import get_database
from app.api.v1.endpoints.auth import get_current_user
from bson import ObjectId

router = APIRouter()

@router.post("/", response_model=FolderResponse)
async def create_folder(
    folder_in: FolderCreate,
    current_user: User = Depends(get_current_user)
):
    """Create a new folder"""
    db = await get_database()
    
    folder_dict = folder_in.model_dump()
    folder_dict["owner_id"] = current_user.id
    if folder_in.parent_folder_id:
        folder_dict["parent_folder_id"] = ObjectId(folder_in.parent_folder_id)
        
    folder = Folder(**folder_dict)
    result = await db.folders.insert_one(folder.model_dump(by_alias=True))
    folder.id = result.inserted_id
    
    return folder

@router.get("/", response_model=List[FolderResponse])
async def get_folders(current_user: User = Depends(get_current_user)):
    """Get all folders for current user"""
    db = await get_database()
    cursor = db.folders.find({"owner_id": current_user.id, "is_deleted": False})
    return [Folder(**doc) async for doc in cursor]

@router.get("/{folder_id}", response_model=FolderResponse)
async def get_folder(
    folder_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get a specific folder"""
    db = await get_database()
    doc = await db.folders.find_one({
        "_id": ObjectId(folder_id),
        "owner_id": current_user.id
    })
    if not doc:
        raise HTTPException(status_code=404, detail="Folder not found")
    return Folder(**doc)
