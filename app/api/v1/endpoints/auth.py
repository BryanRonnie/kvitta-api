from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from app.schemas.auth import (
    UserSignup, 
    UserLogin, 
    TokenResponse, 
    PasswordReset,
    PasswordChange
)
from app.schemas.user import UserResponse
from app.models.user import User
from app.db.session import get_database
from app.core.config import settings
from bson import ObjectId

router = APIRouter()
security = HTTPBearer()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a hashed password"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password"""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> User:
    """Get current authenticated user from JWT token"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        token = credentials.credentials
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    db = await get_database()
    user_doc = await db.users.find_one({"_id": ObjectId(user_id)})
    if user_doc is None:
        raise credentials_exception
    
    return User(**user_doc)


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def signup(user_data: UserSignup):
    """Register a new user"""
    db = await get_database()
    
    # Check if user already exists
    existing_user = await db.users.find_one({"email": user_data.email})
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create new user
    user_dict = {
        "name": user_data.name,
        "email": user_data.email,
        "hashed_password": get_password_hash(user_data.password),
        "is_deleted": False,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    
    result = await db.users.insert_one(user_dict)
    user_id = str(result.inserted_id)
    
    # Create access token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user_id, "email": user_data.email},
        expires_delta=access_token_expires
    )
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse(
            id=user_id,
            name=user_data.name,
            email=user_data.email,
            is_deleted=False
        )
    )


@router.post("/login", response_model=TokenResponse)
async def login(credentials: UserLogin):
    """Login with email and password"""
    db = await get_database()
    
    # Find user by email
    user_doc = await db.users.find_one({"email": credentials.email})
    if not user_doc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    # Verify password
    if not verify_password(credentials.password, user_doc["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    # Check if user is deleted
    if user_doc.get("is_deleted", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account has been deleted"
        )
    
    # Create access token
    user_id = str(user_doc["_id"])
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user_id, "email": user_doc["email"]},
        expires_delta=access_token_expires
    )
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse(
            id=user_id,
            name=user_doc["name"],
            email=user_doc["email"],
            is_deleted=user_doc.get("is_deleted", False)
        )
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user information"""
    return UserResponse(
        id=str(current_user.id),
        name=current_user.name,
        email=current_user.email,
        is_deleted=current_user.is_deleted
    )


@router.post("/change-password")
async def change_password(
    password_data: PasswordChange,
    current_user: User = Depends(get_current_user)
):
    """Change user password"""
    db = await get_database()
    
    # Verify current password
    user_doc = await db.users.find_one({"_id": current_user.id})
    if not verify_password(password_data.current_password, user_doc["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )
    
    # Update password
    new_hashed_password = get_password_hash(password_data.new_password)
    await db.users.update_one(
        {"_id": current_user.id},
        {
            "$set": {
                "hashed_password": new_hashed_password,
                "updated_at": datetime.now(timezone.utc)
            }
        }
    )
    
    return {"message": "Password changed successfully"}


@router.post("/logout")
async def logout(current_user: User = Depends(get_current_user)):
    """Logout (client should delete token)"""
    # In a stateless JWT system, logout is handled client-side
    # Optionally, you could implement token blacklisting here
    return {"message": "Logged out successfully"}
