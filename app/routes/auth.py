from fastapi import APIRouter, HTTPException, status, Depends, Form
from app.models.user import UserCreate, UserResponse
from app.db.mongo import get_db
from app.repositories.user_repo import UserRepository
from app.core.auth import create_access_token, get_current_user
from app.core.security import verify_password

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/signup", response_model=dict, status_code=status.HTTP_201_CREATED)
async def signup(user_data: UserCreate, db = Depends(get_db)):
    """Create a new user account."""
    user_repo = UserRepository(db)
    
    # Check if email already exists
    existing_user = await user_repo.get_user_by_email(user_data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create user
    user = await user_repo.create_user(user_data)
    
    # Generate token
    access_token = create_access_token(str(user._id))
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": str(user._id),
            "name": user.name,
            "email": user.email
        }
    }

@router.post("/login", response_model=dict)
async def login(
    email: str = Form(...),
    password: str = Form(...),
    db = Depends(get_db)
):
    """Login with email and password."""
    user_repo = UserRepository(db)
    
    # Get user by email
    user = await user_repo.get_user_by_email(email)
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    # Generate token
    access_token = create_access_token(str(user._id))
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": str(user._id),
            "name": user.name,
            "email": user.email
        }
    }

@router.get("/me", response_model=UserResponse)
async def get_me(current_user: UserResponse = Depends(get_current_user)):
    """Get current user details."""
    return current_user
