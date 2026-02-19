import os
import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from main import app
from app import db as db_module
from app.models.user import UserCreate
from app.repositories.user_repo import UserRepository
from app.core.auth import create_access_token
import asyncio

# Test database configuration
TEST_MONGODB_URI = os.getenv("MONGODB_URI")
TEST_MONGODB_DB = "kvitta_test"


@pytest_asyncio.fixture
async def test_db() -> AsyncIOMotorDatabase:
    """Fixture for test MongoDB database (for async repository tests)."""
    client = AsyncIOMotorClient(TEST_MONGODB_URI)
    db = client[TEST_MONGODB_DB]
    
    # Drop database before test to ensure clean state
    await client.drop_database(TEST_MONGODB_DB)
    
    # Create indexes for test database
    await db["users"].create_index("email", unique=True)
    
    yield db
    
    # Cleanup: drop all collections after tests
    await client.drop_database(TEST_MONGODB_DB)
    client.close()


@pytest.fixture
def test_client(monkeypatch):
    """Fixture for FastAPI test client."""
    # Patch the config to use test database  
    monkeypatch.setenv("DATABASE_NAME", TEST_MONGODB_DB)
    
    # Reload config to pick up test database name
    from app.core import config
    config.settings.MONGODB_DB = TEST_MONGODB_DB
    
    # Clean up test database before test (sync blocking call)
    def setup_cleanup():
        client = AsyncIOMotorClient(TEST_MONGODB_URI)
        # Create a new event loop for this cleanup
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(client.drop_database(TEST_MONGODB_DB))
        finally:
            loop.run_until_complete(asyncio.sleep(0))  # Let pending tasks complete
            client.close()
            loop.close()
    
    setup_cleanup()
    
    # Use TestClient with context manager to trigger lifespan
    # This will create MongoDB connection using TEST_MONGODB_DB
    with TestClient(app) as client:
        yield client
    
    # Cleanup after test
    setup_cleanup()


@pytest_asyncio.fixture
async def sample_user_data():
    """Sample user data for testing."""
    return {
        "name": "John Doe",
        "email": "john@example.com",
        "password": "SecurePassword123"
    }


@pytest_asyncio.fixture
async def created_user(test_db, sample_user_data):
    """Create a sample user in test database."""
    user_repo = UserRepository(test_db)
    user_create = UserCreate(**sample_user_data)
    user = await user_repo.create_user(user_create)
    return user


@pytest_asyncio.fixture
async def valid_token(created_user):
    """Create a valid JWT token for testing."""
    return create_access_token(str(created_user._id))


@pytest_asyncio.fixture
async def multiple_users(test_db):
    """Create multiple test users."""
    user_repo = UserRepository(test_db)
    users_data = [
        UserCreate(name="Alice", email="alice@example.com", password="Pass123456"),
        UserCreate(name="Bob", email="bob@example.com", password="Pass123456"),
        UserCreate(name="Charlie", email="charlie@example.com", password="Pass123456"),
    ]
    
    users = []
    for user_data in users_data:
        user = await user_repo.create_user(user_data)
        users.append(user)
    
    return users
