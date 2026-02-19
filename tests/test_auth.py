"""Tests for authentication endpoints."""
import pytest
import json
from fastapi import status
from app.core.auth import create_access_token
from bson import ObjectId


class TestAuthEndpoints:
    """Test authentication endpoints."""
    
    def test_health_endpoint(self, test_client):
        """Test health check endpoint."""
        response = test_client.get("/health")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "ok"
        assert "version" in data
    
    def test_signup_success(self, test_client, sample_user_data):
        """Test successful user signup."""
        response = test_client.post(
            "/auth/signup",
            json=sample_user_data
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert "user" in data
        assert data["user"]["name"] == sample_user_data["name"]
        assert data["user"]["email"] == sample_user_data["email"]
        assert "id" in data["user"]
    
    def test_signup_duplicate_email(self, test_client, created_user):
        """Test signup with duplicate email."""
        response = test_client.post(
            "/auth/signup",
            json={
                "name": "Another User",
                "email": created_user.email,
                "password": "AnotherPass123"
            }
        )
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "already registered" in response.json()["detail"]
    
    def test_signup_invalid_email(self, test_client):
        """Test signup with invalid email format."""
        response = test_client.post(
            "/auth/signup",
            json={
                "name": "Test User",
                "email": "invalid-email",
                "password": "SecurePass123"
            }
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    
    def test_signup_short_password(self, test_client):
        """Test signup with password too short."""
        response = test_client.post(
            "/auth/signup",
            json={
                "name": "Test User",
                "email": "test@example.com",
                "password": "short"
            }
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    
    def test_signup_empty_name(self, test_client):
        """Test signup with empty name."""
        response = test_client.post(
            "/auth/signup",
            json={
                "name": "",
                "email": "test@example.com",
                "password": "SecurePass123"
            }
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    
    def test_signup_missing_field(self, test_client):
        """Test signup with missing required field."""
        response = test_client.post(
            "/auth/signup",
            json={
                "name": "Test User",
                "email": "test@example.com"
                # Missing password
            }
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    
    def test_login_success(self, test_client, created_user, sample_user_data):
        """Test successful login."""
        response = test_client.post(
            "/auth/login",
            data={
                "email": sample_user_data["email"],
                "password": sample_user_data["password"]
            }
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["email"] == sample_user_data["email"]
    
    def test_login_invalid_email(self, test_client):
        """Test login with non-existent email."""
        response = test_client.post(
            "/auth/login",
            data={
                "email": "nonexistent@example.com",
                "password": "AnyPassword123"
            }
        )
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Invalid email or password" in response.json()["detail"]
    
    def test_login_wrong_password(self, test_client, created_user, sample_user_data):
        """Test login with wrong password."""
        response = test_client.post(
            "/auth/login",
            data={
                "email": sample_user_data["email"],
                "password": "WrongPassword123"
            }
        )
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Invalid email or password" in response.json()["detail"]
    
    def test_login_empty_password(self, test_client, created_user, sample_user_data):
        """Test login with empty password - validation should reject it."""
        response = test_client.post(
            "/auth/login",
            data={
                "email": sample_user_data["email"],
                "password": ""
            }
        )
        
        # FastAPI validates required form fields, returns 422 for empty password
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_login_missing_email(self, test_client):
        """Test login with missing email."""
        response = test_client.post(
            "/auth/login",
            data={
                "password": "AnyPassword123"
            }
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    
    def test_get_me_with_valid_token(self, test_client, created_user, valid_token):
        """Test getting current user with valid token."""
        response = test_client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {valid_token}"}
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["name"] == created_user.name
        assert data["email"] == created_user.email
        assert "created_at" in data
        assert "updated_at" in data
    
    def test_get_me_without_token(self, test_client):
        """Test getting current user without token."""
        response = test_client.get("/auth/me")
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_get_me_with_invalid_token(self, test_client):
        """Test getting current user with invalid token."""
        response = test_client.get(
            "/auth/me",
            headers={"Authorization": "Bearer invalid_token"}
        )
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_get_me_with_expired_token(self, test_client):
        """Test getting current user with expired token."""
        from datetime import timedelta
        from app.core.auth import create_access_token
        
        # Create a token that expired in the past
        expired_token = create_access_token(
            str(ObjectId()),
            expires_delta=timedelta(seconds=-1)
        )
        
        response = test_client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {expired_token}"}
        )
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_get_me_with_malformed_header(self, test_client):
        """Test getting current user with malformed auth header."""
        # Missing Bearer prefix
        response = test_client.get(
            "/auth/me",
            headers={"Authorization": "invalid_token"}
        )
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    @pytest.mark.asyncio
    async def test_get_me_token_for_deleted_user(self, test_client, created_user, valid_token, test_db):
        """Test accessing /auth/me with token for deleted user."""
        # Delete the user
        await test_db["users"].update_one(
            {"_id": created_user._id},
            {"$set": {"is_deleted": True}}
        )
        
        response = test_client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {valid_token}"}
        )
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestAuthIntegration:
    """Integration tests for auth flow."""
    
    def test_signup_and_login_flow(self, test_client):
        """Test complete signup and login flow."""
        # Signup
        signup_data = {
            "name": "Integration Test User",
            "email": "integration@example.com",
            "password": "IntegrationPass123"
        }
        
        signup_response = test_client.post("/auth/signup", json=signup_data)
        assert signup_response.status_code == status.HTTP_200_OK
        signup_token = signup_response.json()["access_token"]
        
        # Get user with signup token
        me_response = test_client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {signup_token}"}
        )
        assert me_response.status_code == status.HTTP_200_OK
        assert me_response.json()["name"] == signup_data["name"]
        
        # Login with credentials
        login_response = test_client.post(
            "/auth/login",
            data={
                "email": signup_data["email"],
                "password": signup_data["password"]
            }
        )
        assert login_response.status_code == status.HTTP_200_OK
        login_token = login_response.json()["access_token"]
        
        # Get user with login token
        me_response2 = test_client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {login_token}"}
        )
        assert me_response2.status_code == status.HTTP_200_OK
        assert me_response2.json()["email"] == signup_data["email"]
    
    def test_multiple_users_isolation(self, test_client):
        """Test that different users can login independently."""
        # Create user 1
        user1_data = {
            "name": "User One",
            "email": "user1@example.com",
            "password": "User1Pass123"
        }
        user1_signup = test_client.post("/auth/signup", json=user1_data)
        user1_token = user1_signup.json()["access_token"]
        
        # Create user 2
        user2_data = {
            "name": "User Two",
            "email": "user2@example.com",
            "password": "User2Pass123"
        }
        user2_signup = test_client.post("/auth/signup", json=user2_data)
        user2_token = user2_signup.json()["access_token"]
        
        # User 1 should only see their own data
        user1_me = test_client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {user1_token}"}
        ).json()
        assert user1_me["email"] == user1_data["email"]
        
        # User 2 should only see their own data
        user2_me = test_client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {user2_token}"}
        ).json()
        assert user2_me["email"] == user2_data["email"]
