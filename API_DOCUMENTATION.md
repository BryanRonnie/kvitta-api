# Kvitta API - Authentication & Integration Guide

## Overview
The Kvitta API now includes full authentication with JWT tokens and integrates authentication across all endpoints including users, folders, receipts, ledger, and settlements.

## Base URL
- Development: `http://localhost:8000`
- API Version: `/api/v1`

## Authentication Endpoints

### 1. Sign Up
**POST** `/api/v1/auth/signup`

Create a new user account.

**Request Body:**
```json
{
  "name": "John Doe",
  "email": "john@example.com",
  "password": "securepassword123"
}
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {
    "id": "507f1f77bcf86cd799439011",
    "name": "John Doe",
    "email": "john@example.com",
    "is_deleted": false
  }
}
```

### 2. Login
**POST** `/api/v1/auth/login`

Authenticate with email and password.

**Request Body:**
```json
{
  "email": "john@example.com",
  "password": "securepassword123"
}
```

**Response:** Same as signup response

### 3. Get Current User
**GET** `/api/v1/auth/me`

**Headers:** `Authorization: Bearer <token>`

**Response:**
```json
{
  "id": "507f1f77bcf86cd799439011",
  "name": "John Doe",
  "email": "john@example.com",
  "is_deleted": false
}
```

### 4. Change Password
**POST** `/api/v1/auth/change-password`

**Headers:** `Authorization: Bearer <token>`

**Request Body:**
```json
{
  "current_password": "oldpassword",
  "new_password": "newsecurepassword123"
}
```

### 5. Logout
**POST** `/api/v1/auth/logout`

**Headers:** `Authorization: Bearer <token>`

**Response:**
```json
{
  "message": "Logged out successfully"
}
```

## User Endpoints (All require authentication)

### Get My Profile
**GET** `/api/v1/users/me`

### Update My Profile
**PATCH** `/api/v1/users/me`

**Request Body:**
```json
{
  "name": "Jane Doe",
  "email": "jane@example.com"
}
```

### Get User by ID
**GET** `/api/v1/users/{user_id}`

## Folder Endpoints (All require authentication)

### Create Folder
**POST** `/api/v1/folders/`

**Request Body:**
```json
{
  "name": "Groceries",
  "parent_folder_id": null
}
```

### Get My Folders
**GET** `/api/v1/folders/`

### Get Folder by ID
**GET** `/api/v1/folders/{folder_id}`

## Receipt Endpoints (All require authentication)

### Create Receipt
**POST** `/api/v1/receipts/`

### Get Receipt
**GET** `/api/v1/receipts/{receipt_id}`

### Update Receipt
**PATCH** `/api/v1/receipts/{receipt_id}`

### Finalize Receipt
**POST** `/api/v1/receipts/{receipt_id}/finalize`

Creates ledger entries for all splits.

## Ledger Endpoints (All require authentication)

### Get My Balance
**GET** `/api/v1/ledger/balance`

### Get User Balance
**GET** `/api/v1/ledger/balance/{user_id}`

### Get Receipt Ledger
**GET** `/api/v1/ledger/receipt/{receipt_id}`

## Frontend Integration

### Using the API from React/Next.js

```typescript
// auth.ts
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

interface AuthResponse {
  access_token: string;
  token_type: string;
  user: {
    id: string;
    name: string;
    email: string;
    is_deleted: boolean;
  };
}

export async function signup(name: string, email: string, password: string): Promise<AuthResponse> {
  const response = await fetch(`${API_BASE_URL}/auth/signup`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ name, email, password }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Signup failed');
  }

  const data = await response.json();
  // Store token in localStorage or cookies
  localStorage.setItem('token', data.access_token);
  return data;
}

export async function login(email: string, password: string): Promise<AuthResponse> {
  const response = await fetch(`${API_BASE_URL}/auth/login`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ email, password }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Login failed');
  }

  const data = await response.json();
  localStorage.setItem('token', data.access_token);
  return data;
}

export function logout() {
  localStorage.removeItem('token');
}

export function getToken(): string | null {
  return localStorage.getItem('token');
}

// Authenticated request helper
export async function authRequest(url: string, options: RequestInit = {}) {
  const token = getToken();
  
  const headers = {
    'Content-Type': 'application/json',
    ...(token && { 'Authorization': `Bearer ${token}` }),
    ...options.headers,
  };

  const response = await fetch(url, { ...options, headers });

  if (response.status === 401) {
    // Token expired or invalid
    logout();
    window.location.href = '/login';
    throw new Error('Unauthorized');
  }

  return response;
}
```

### Example Usage

```typescript
// Sign up
const { access_token, user } = await signup('John Doe', 'john@example.com', 'password123');

// Login
const { access_token, user } = await login('john@example.com', 'password123');

// Make authenticated requests
const response = await authRequest(`${API_BASE_URL}/folders/`, {
  method: 'GET',
});
const folders = await response.json();

// Create a receipt
const response = await authRequest(`${API_BASE_URL}/receipts/`, {
  method: 'POST',
  body: JSON.stringify({
    items: [...],
    total_amount: 100.50,
  }),
});
```

## Configuration

Update your `.env` file:

```env
# MongoDB
MONGODB_URL=mongodb://localhost:27017
DATABASE_NAME=kvitta

# JWT Settings
SECRET_KEY=your-secret-key-change-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60

# CORS
CORS_ORIGINS=["http://localhost:3000", "https://kvitta.vercel.app"]
```

## Running the API

```bash
# Install dependencies
pip install -r requirements.txt

# Run the server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Testing

Access the interactive API documentation:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Security Notes

1. **Password Requirements**: Minimum 8 characters
2. **Token Expiration**: Tokens expire after 60 minutes (configurable)
3. **HTTPS**: Always use HTTPS in production
4. **Secret Key**: Change the SECRET_KEY in production to a secure random string
5. **CORS**: Configure CORS_ORIGINS to only include trusted domains

## Error Responses

All endpoints return standard error responses:

```json
{
  "detail": "Error message here"
}
```

Common status codes:
- `400`: Bad Request (invalid input)
- `401`: Unauthorized (missing or invalid token)
- `403`: Forbidden (insufficient permissions)
- `404`: Not Found
- `500`: Internal Server Error
