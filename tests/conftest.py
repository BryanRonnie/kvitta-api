import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport
from app.main import app
from unittest.mock import AsyncMock, patch, MagicMock

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
async def async_client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

@pytest.fixture
def mock_db():
    mock = MagicMock()
    mock.client = AsyncMock()
    
    def setup_collection(name):
        col = MagicMock()
        col.insert_one = AsyncMock()
        col.insert_many = AsyncMock()
        col.update_one = AsyncMock()
        col.update_many = AsyncMock()
        col.find_one = AsyncMock()
        col.delete_one = AsyncMock()
        col.delete_many = AsyncMock()
        col.aggregate = MagicMock() # Cursor
        col.find = MagicMock()      # Cursor
        setattr(mock, name, col)
        return col

    setup_collection("ledger_entries")
    setup_collection("receipts")
    setup_collection("settlements")
    setup_collection("users")
    return mock
