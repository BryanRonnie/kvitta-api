"""
Test authentication endpoints
"""
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch, MagicMock
from app.main import app
from bson import ObjectId
from datetime import datetime, timezone


@pytest.fixture
def mock_database():
    """Mock MongoDB database for tests"""
    mock_db = MagicMock()
    
    # Mock users collection
    mock_users = MagicMock()
    mock_users.find_one = AsyncMock()
    mock_users.insert_one = AsyncMock()
    mock_users.update_one = AsyncMock()
    mock_db.users = mock_users
    
    return mock_db


@pytest.mark.asyncio
async def test_signup(mock_database):
    """Test user signup"""
    # Setup mock database
    mock_database.users.find_one.return_value = None  # No existing user
    mock_result = MagicMock()
    mock_result.inserted_id = ObjectId("507f1f77bcf86cd799439011")
    mock_database.users.insert_one.return_value = mock_result
    
    with patch("app.api.v1.endpoints.auth.get_database", return_value=mock_database):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/auth/signup",
                json={
                    "name": "Test User",
                    "email": "test@example.com",
                    "password": "testpassword123"
                }
            )
            assert response.status_code == 201
            data = response.json()
            assert "access_token" in data
            assert data["token_type"] == "bearer"
            assert data["user"]["email"] == "test@example.com"


@pytest.mark.asyncio
async def test_signup_duplicate_email(mock_database):
    """Test signup with duplicate email"""
    # Mock existing user
    existing_user = {
        "_id": ObjectId(),
        "email": "duplicate@example.com",
        "name": "Existing",
        "hashed_password": "hash"
    }
    
    with patch("app.api.v1.endpoints.auth.get_database", return_value=mock_database):
        # First call returns existing user
        mock_database.users.find_one.return_value = existing_user
        
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/auth/signup",
                json={
                    "name": "User Two",
                    "email": "duplicate@example.com",
                    "password": "password456"
                }
            )
            assert response.status_code == 400
            assert "already registered" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_login(mock_database):
    """Test user login"""
    # Mock existing user with hashed password
    from passlib.context import CryptContext
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    hashed_password = pwd_context.hash("loginpass123")
    
    existing_user = {
        "_id": ObjectId("507f1f77bcf86cd799439011"),
        "email": "login@example.com",
        "name": "Login Test",
        "hashed_password": hashed_password,
        "is_deleted": False
    }
    
    with patch("app.api.v1.endpoints.auth.get_database", return_value=mock_database):
        mock_database.users.find_one.return_value = existing_user
        
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/auth/login",
                json={
                    "email": "login@example.com",
                    "password": "loginpass123"
                }
            )
            assert response.status_code == 200
            data = response.json()
            assert "access_token" in data
            assert data["user"]["email"] == "login@example.com"


@pytest.mark.asyncio
async def test_login_wrong_password(mock_database):
    """Test login with wrong password"""
    from passlib.context import CryptContext
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    hashed_password = pwd_context.hash("correctpass123")
    
    existing_user = {
        "_id": ObjectId(),
        "email": "wrongpass@example.com",
        "name": "Wrong Pass Test",
        "hashed_password": hashed_password,
        "is_deleted": False
    }
    
    with patch("app.api.v1.endpoints.auth.get_database", return_value=mock_database):
        mock_database.users.find_one.return_value = existing_user
        
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/auth/login",
                json={
                    "email": "wrongpass@example.com",
                    "password": "wrongpassword"
                }
            )
            assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user(mock_database):
    """Test getting current user info"""
    user_id = ObjectId("507f1f77bcf86cd799439011")
    
    # Mock for signup
    mock_result = MagicMock()
    mock_result.inserted_id = user_id
    
    # Mock for get current user
    user_doc = {
        "_id": user_id,
        "email": "currentuser@example.com",
        "name": "Current User Test",
        "hashed_password": "hash",
        "is_deleted": False,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }
    
    with patch("app.api.v1.endpoints.auth.get_database", return_value=mock_database):
        # Setup mocks for signup
        mock_database.users.find_one.return_value = None
        mock_database.users.insert_one.return_value = mock_result
        
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Signup to get token
            signup_response = await client.post(
                "/api/v1/auth/signup",
                json={
                    "name": "Current User Test",
                    "email": "currentuser@example.com",
                    "password": "password123"
                }
            )
            token = signup_response.json()["access_token"]
            
            # Setup mock for get current user
            mock_database.users.find_one.return_value = user_doc
            response = await client.get(
                "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {token}"}
            )
            assert response.status_code == 200
            data = response.json()
            assert data["email"] == "currentuser@example.com"
            assert data["name"] == "Current User Test"


@pytest.mark.asyncio
async def test_unauthorized_access():
    """Test accessing protected endpoint without token"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/auth/me")
        assert response.status_code == 401  # No Authorization header


@pytest.mark.asyncio
async def test_change_password(mock_database):
    """Test changing password"""
    from passlib.context import CryptContext
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    
    user_id = ObjectId("507f1f77bcf86cd799439011")
    old_hashed = pwd_context.hash("oldpassword123")
    
    # Mock for signup
    mock_result = MagicMock()
    mock_result.inserted_id = user_id
    
    user_doc = {
        "_id": user_id,
        "email": "changepass@example.com",
        "name": "Change Pass Test",
        "hashed_password": old_hashed,
        "is_deleted": False,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }
    
    mock_update_result = AsyncMock()
    
    with patch("app.api.v1.endpoints.auth.get_database", return_value=mock_database):
        # Setup mocks for signup
        mock_database.users.find_one.return_value = None
        mock_database.users.insert_one.return_value = mock_result
        mock_database.users.update_one.return_value = mock_update_result
        
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Signup
            signup_response = await client.post(
                "/api/v1/auth/signup",
                json={
                    "name": "Change Pass Test",
                    "email": "changepass@example.com",
                    "password": "oldpassword123"
                }
            )
            token = signup_response.json()["access_token"]
            
            # Change password - setup mock to return user with old password
            mock_database.users.find_one.return_value = user_doc
            response = await client.post(
                "/api/v1/auth/change-password",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "current_password": "oldpassword123",
                    "new_password": "newpassword123"
                }
            )
            assert response.status_code == 200
