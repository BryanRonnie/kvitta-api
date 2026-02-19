"""Tests for security functions."""
import pytest
from app.core.security import hash_password, verify_password


class TestPasswordHashing:
    """Test password hashing and verification."""
    
    def test_hash_password_returns_string(self):
        """Test that hash_password returns a string."""
        password = "MySecurePassword123"
        hashed = hash_password(password)
        
        assert isinstance(hashed, str)
        assert len(hashed) > 0
    
    def test_hash_password_different_outputs(self):
        """Test that hashing same password produces different outputs (different salts)."""
        password = "MySecurePassword123"
        hash1 = hash_password(password)
        hash2 = hash_password(password)
        
        # Different hashes due to different salts
        assert hash1 != hash2
    
    def test_verify_password_correct(self):
        """Test password verification with correct password."""
        password = "MySecurePassword123"
        hashed = hash_password(password)
        
        assert verify_password(password, hashed) is True
    
    def test_verify_password_incorrect(self):
        """Test password verification with incorrect password."""
        password = "MySecurePassword123"
        wrong_password = "WrongPassword456"
        hashed = hash_password(password)
        
        assert verify_password(wrong_password, hashed) is False
    
    def test_verify_password_empty_string(self):
        """Test password verification with empty string."""
        password = "MySecurePassword123"
        hashed = hash_password(password)
        
        assert verify_password("", hashed) is False
    
    def test_hash_password_long_password(self):
        """Test hashing very long password (bcrypt has 72-byte limit)."""
        long_password = "a" * 100
        hashed = hash_password(long_password)
        
        # Note: bcrypt only uses first 72 bytes, so 100 "a"s and 72 "a"s produce same hash
        assert verify_password(long_password, hashed) is True
        assert verify_password("b" + "a" * 99, hashed) is False  # Different character
    
    def test_hash_password_special_characters(self):
        """Test hashing password with special characters."""
        special_password = "P@$$w0rd!#%&*()_+-=[]{}|;:,.<>?"
        hashed = hash_password(special_password)
        
        assert verify_password(special_password, hashed) is True
        assert verify_password("P@$$w0rd!", hashed) is False
    
    def test_hash_password_unicode(self):
        """Test hashing password with unicode characters."""
        unicode_password = "Пароль密码🔐Passkey"
        hashed = hash_password(unicode_password)
        
        assert verify_password(unicode_password, hashed) is True
        assert verify_password("Пароль密码", hashed) is False
