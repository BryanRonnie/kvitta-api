"""Tests for user repository."""
import pytest
from bson import ObjectId
from app.models.user import UserCreate
from app.repositories.user_repo import UserRepository


@pytest.mark.asyncio
class TestUserRepository:
    """Test UserRepository CRUD operations."""
    
    async def test_create_user_success(self, test_db, sample_user_data):
        """Test successful user creation."""
        user_repo = UserRepository(test_db)
        user_create = UserCreate(**sample_user_data)
        
        user = await user_repo.create_user(user_create)
        
        assert user._id is not None
        assert user.name == sample_user_data["name"]
        assert user.email == sample_user_data["email"]
        assert user.password_hash != sample_user_data["password"]
        assert user.is_deleted is False
        assert user.created_at is not None
        assert user.updated_at is not None
    
    async def test_create_user_duplicate_email(self, test_db, created_user, sample_user_data):
        """Test that creating user with duplicate email fails."""
        from pymongo.errors import DuplicateKeyError
        
        user_repo = UserRepository(test_db)
        
        # Try to create user with existing email
        duplicate_user = UserCreate(
            name="Another User",
            email=created_user.email,
            password="AnotherPass123"
        )
        
        with pytest.raises(DuplicateKeyError):  # MongoDB raises this for unique index violation
            await user_repo.create_user(duplicate_user)
    
    async def test_get_user_by_email_found(self, test_db, created_user):
        """Test retrieving user by email."""
        user_repo = UserRepository(test_db)
        
        user = await user_repo.get_user_by_email(created_user.email)
        
        assert user is not None
        assert user._id == created_user._id
        assert user.name == created_user.name
        assert user.email == created_user.email
    
    async def test_get_user_by_email_not_found(self, test_db):
        """Test retrieving non-existent user by email."""
        user_repo = UserRepository(test_db)
        
        user = await user_repo.get_user_by_email("nonexistent@example.com")
        
        assert user is None
    
    async def test_get_user_by_email_deleted_user(self, test_db, created_user):
        """Test that soft-deleted users are not returned."""
        user_repo = UserRepository(test_db)
        
        # Soft delete the user
        await user_repo.soft_delete_user(str(created_user._id))
        
        # Try to get deleted user
        user = await user_repo.get_user_by_email(created_user.email)
        
        assert user is None
    
    async def test_get_user_by_id_found(self, test_db, created_user):
        """Test retrieving user by ID."""
        user_repo = UserRepository(test_db)
        
        user = await user_repo.get_user_by_id(str(created_user._id))
        
        assert user is not None
        assert user._id == created_user._id
        assert user.name == created_user.name
    
    async def test_get_user_by_id_not_found(self, test_db):
        """Test retrieving non-existent user by ID."""
        user_repo = UserRepository(test_db)
        fake_id = str(ObjectId())
        
        user = await user_repo.get_user_by_id(fake_id)
        
        assert user is None
    
    async def test_get_user_by_id_invalid_id(self, test_db):
        """Test retrieving user with invalid ID format."""
        user_repo = UserRepository(test_db)
        
        user = await user_repo.get_user_by_id("invalid_id")
        
        assert user is None
    
    async def test_get_user_by_id_deleted_user(self, test_db, created_user):
        """Test that soft-deleted users are not returned."""
        user_repo = UserRepository(test_db)
        user_id = str(created_user._id)
        
        # Soft delete the user
        await user_repo.soft_delete_user(user_id)
        
        # Try to get deleted user
        user = await user_repo.get_user_by_id(user_id)
        
        assert user is None
    
    async def test_update_user_success(self, test_db, created_user):
        """Test updating user information."""
        user_repo = UserRepository(test_db)
        
        update_data = {"name": "Updated Name"}
        updated_user = await user_repo.update_user(str(created_user._id), update_data)
        
        assert updated_user is not None
        assert updated_user.name == "Updated Name"
        assert updated_user.email == created_user.email
        # Compare without timezone info to avoid comparison issues
        assert updated_user.updated_at.replace(tzinfo=None) >= created_user.updated_at.replace(tzinfo=None)
        user_repo = UserRepository(test_db)
        fake_id = str(ObjectId())
        
        result = await user_repo.update_user(fake_id, {"name": "New Name"})
        
        assert result is None
    
    async def test_update_user_deleted_user(self, test_db, created_user):
        """Test that soft-deleted users cannot be updated."""
        user_repo = UserRepository(test_db)
        user_id = str(created_user._id)
        
        # Soft delete the user
        await user_repo.soft_delete_user(user_id)
        
        # Try to update deleted user
        result = await user_repo.update_user(user_id, {"name": "New Name"})
        
        assert result is None
    
    async def test_soft_delete_user_success(self, test_db, created_user):
        """Test soft deleting a user."""
        user_repo = UserRepository(test_db)
        
        result = await user_repo.soft_delete_user(str(created_user._id))
        
        assert result is True
        
        # Verify user is marked as deleted
        user = await user_repo.get_user_by_id(str(created_user._id))
        assert user is None
    
    async def test_soft_delete_user_not_found(self, test_db):
        """Test soft deleting non-existent user."""
        user_repo = UserRepository(test_db)
        fake_id = str(ObjectId())
        
        result = await user_repo.soft_delete_user(fake_id)
        
        assert result is False
    
    async def test_soft_delete_user_invalid_id(self, test_db):
        """Test soft deleting user with invalid ID."""
        user_repo = UserRepository(test_db)
        
        result = await user_repo.soft_delete_user("invalid_id")
        
        assert result is False
    
    async def test_multiple_users_isolation(self, test_db, multiple_users):
        """Test that operations on one user don't affect others."""
        user_repo = UserRepository(test_db)
        
        # Update first user
        await user_repo.update_user(str(multiple_users[0]._id), {"name": "Updated Alice"})
        
        # Verify other users unchanged
        bob = await user_repo.get_user_by_email("bob@example.com")
        charlie = await user_repo.get_user_by_email("charlie@example.com")
        
        assert bob.name == "Bob"
        assert charlie.name == "Charlie"
