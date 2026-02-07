"""
Authentication routes for user signup, login, and token management
"""

from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from models import UserCreate, UserLogin, Token, UserResponse, UserInDB, TokenData
from auth_utils import (
    verify_password,
    get_password_hash,
    create_access_token,
    verify_token,
    ACCESS_TOKEN_EXPIRE_MINUTES
)
from database import get_users_collection

router = APIRouter(prefix="/auth", tags=["Authentication"])
security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> UserInDB:
    """Get current authenticated user from JWT token"""
    token = credentials.credentials
    email = verify_token(token)
    
    if email is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    users_collection = await get_users_collection()
    user = await users_collection.find_one({"email": email})
    
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    
    return UserInDB(**user)

@router.post("/signup", response_model=Token, status_code=status.HTTP_201_CREATED)
async def signup(user_data: UserCreate):
    """
    Register a new user
    
    - **email**: User's email address (must be unique)
    - **password**: Password (minimum 8 characters)
    - **name**: Optional user name
    """
    users_collection = await get_users_collection()
    
    # Check if user already exists
    existing_user = await users_collection.find_one({"email": user_data.email})
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create new user
    hashed_password = get_password_hash(user_data.password)
    now = datetime.utcnow()
    
    user_dict = {
        "email": user_data.email,
        "name": user_data.name or user_data.email.split("@")[0],
        "hashed_password": hashed_password,
        "created_at": now,
        "updated_at": now,
        "is_active": True
    }
    
    await users_collection.insert_one(user_dict)
    
    # Create access token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user_data.email},
        expires_delta=access_token_expires
    )
    
    # Return token and user info
    user_response = UserResponse(
        email=user_dict["email"],
        name=user_dict["name"],
        created_at=user_dict["created_at"]
    )
    
    return Token(
        access_token=access_token,
        token_type="bearer",
        user=user_response
    )

@router.post("/login", response_model=Token)
async def login(credentials: UserLogin):
    """
    Login with email and password
    
    - **email**: User's email address
    - **password**: User's password
    
    Returns JWT access token
    """
    users_collection = await get_users_collection()
    
    # Find user by email
    user = await users_collection.find_one({"email": credentials.email})
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    
    # Verify password
    if not verify_password(credentials.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    
    # Check if user is active
    if not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled",
        )
    
    # Create access token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["email"]},
        expires_delta=access_token_expires
    )
    
    # Return token and user info
    user_response = UserResponse(
        email=user["email"],
        name=user.get("name"),
        created_at=user["created_at"]
    )
    
    return Token(
        access_token=access_token,
        token_type="bearer",
        user=user_response
    )

@router.post("/logout")
async def logout(current_user: UserInDB = Depends(get_current_user)):
    """
    Logout current user
    
    Note: With JWT, logout is handled client-side by removing the token.
    This endpoint is provided for consistency and can be extended
    to implement token blacklisting if needed.
    """
    return {"message": "Successfully logged out"}

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: UserInDB = Depends(get_current_user)):
    """
    Get current authenticated user information
    """
    return UserResponse(
        email=current_user.email,
        name=current_user.name,
        created_at=current_user.created_at
    )

@router.post("/refresh", response_model=Token)
async def refresh_token(current_user: UserInDB = Depends(get_current_user)):
    """
    Refresh access token
    
    Requires valid existing token. Returns new token with extended expiration.
    """
    # Create new access token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": current_user.email},
        expires_delta=access_token_expires
    )
    
    user_response = UserResponse(
        email=current_user.email,
        name=current_user.name,
        created_at=current_user.created_at
    )
    
    return Token(
        access_token=access_token,
        token_type="bearer",
        user=user_response
    )
