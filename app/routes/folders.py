from fastapi import APIRouter, Depends, HTTPException, status

from app.db.mongo import get_db
from app.core.auth import get_current_user
from app.models.user import UserResponse
from app.models.folder import FolderCreate, FolderUpdate, FolderResponse
from app.repositories.folder_repo import FolderRepository

router = APIRouter(prefix="/folders", tags=["folders"])


@router.post("", response_model=FolderResponse)
async def create_folder(
    folder_data: FolderCreate,
    current_user: UserResponse = Depends(get_current_user),
    db = Depends(get_db)
):
    """Create a folder for the current user."""
    repo = FolderRepository(db)
    folder = await repo.create_folder(folder_data, current_user.id)

    return FolderResponse(
        id=str(folder._id),
        name=folder.name,
        color=folder.color,
        owner_id=str(folder.owner_id),
        created_at=folder.created_at,
        updated_at=folder.updated_at
    )


@router.get("", response_model=list[FolderResponse])
async def list_folders(
    current_user: UserResponse = Depends(get_current_user),
    db = Depends(get_db)
):
    """List folders for the current user."""
    repo = FolderRepository(db)
    folders = await repo.list_folders(current_user.id)

    return [
        FolderResponse(
            id=str(folder._id),
            name=folder.name,
            color=folder.color,
            owner_id=str(folder.owner_id),
            created_at=folder.created_at,
            updated_at=folder.updated_at
        )
        for folder in folders
    ]


@router.patch("/{folder_id}", response_model=FolderResponse)
async def update_folder(
    folder_id: str,
    folder_data: FolderUpdate,
    current_user: UserResponse = Depends(get_current_user),
    db = Depends(get_db)
):
    """Update a folder."""
    repo = FolderRepository(db)
    folder = await repo.update_folder(folder_id, current_user.id, folder_data)
    if not folder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found")

    return FolderResponse(
        id=str(folder._id),
        name=folder.name,
        color=folder.color,
        owner_id=str(folder.owner_id),
        created_at=folder.created_at,
        updated_at=folder.updated_at
    )


@router.delete("/{folder_id}")
async def delete_folder(
    folder_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db = Depends(get_db)
):
    """Soft delete a folder."""
    repo = FolderRepository(db)
    deleted = await repo.soft_delete_folder(folder_id, current_user.id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found")

    return {"success": True}
