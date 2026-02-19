"""
Comprehensive Test Suite for Kvitta Auth & User System

This test suite provides maximum coverage for authentication and user management features.

FILE STRUCTURE:
- conftest.py              - Pytest fixtures and test configuration
- test_security.py         - Password hashing and verification tests
- test_repositories.py     - UserRepository CRUD tests
- test_auth.py             - Auth endpoints and integration tests

RUNNING TESTS:

1. Run all tests:
   pytest

2. Run with verbose output:
   pytest -v

3. Run specific test file:
   pytest tests/test_auth.py

4. Run specific test class:
   pytest tests/test_auth.py::TestAuthEndpoints

5. Run specific test:
   pytest tests/test_auth.py::TestAuthEndpoints::test_signup_success

6. Run with coverage report:
   pytest --cov=app --cov-report=html

7. Run only integration tests:
   pytest tests/test_auth.py::TestAuthIntegration

8. Run without async tests:
   pytest -m "not asyncio"


FIXTURES PROVIDED:

test_db                    - Test MongoDB database instance
test_client                - FastAPI test client
sample_user_data          - Dictionary with sample user data
created_user              - A user created in the test database
valid_token               - Valid JWT token for created user
multiple_users            - List of 3 test users


TEST COVERAGE:

Security Tests (8 tests):
✓ Password hashing returns unique outputs
✓ Password hashing with different types (long, special chars, unicode)
✓ Password verification (correct, incorrect, edge cases)

User Repository Tests (15 tests):
✓ User creation (success, duplicate email)
✓ User retrieval (by email, by ID, invalid ID)
✓ User updates (success, not found, deleted user)
✓ Soft deletion (success, not found, invalid ID)
✓ Multi-user isolation

Auth Endpoint Tests (20+ tests):
✓ Health check endpoint
✓ Signup (success, duplicate, invalid email, short password)
✓ Login (success, invalid email, wrong password)
✓ Protected /auth/me endpoint (valid token, without token, invalid token, expired token)
✓ Auth header validation

Integration Tests (2 tests):
✓ Full signup → login → get_me flow
✓ Multiple user isolation


TOTAL: 45+ test cases

PREREQUISITES FOR TESTS:
- MongoDB running on localhost:27017
- Test database: kvitta_test (will be created/dropped automatically)
- Python packages: pytest, pytest-asyncio, httpx (in requirements.txt)

NOTES:
- Tests use a separate test database (kvitta_test) and clean up after each run
- All async tests are handled by pytest-asyncio
- FastAPI TestClient handles dependency injection overrides for database
- No external network calls required
"""
