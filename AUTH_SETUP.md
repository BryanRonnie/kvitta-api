# Authentication System - Backend Setup

Complete JWT-based authentication system for Kvitta API.

## What Was Added

### Backend Files (kvitta-api/)

1. **database.py** - MongoDB Atlas connection
   - Async MongoDB client using Motor
   - Connection lifecycle management
   - Users collection accessor

2. **models.py** - Pydantic models
   - `UserCreate` - Registration schema
   - `UserLogin` - Login schema
   - `UserResponse` - User data response (no password)
   - `UserInDB` - Database user model
   - `Token` - JWT token response
   - `TokenData` - Token payload

3. **auth_utils.py** - Authentication utilities
   - Password hashing with bcrypt
   - JWT token creation and verification
   - Configurable token expiration

4. **auth_routes.py** - API endpoints
   - `POST /auth/signup` - User registration
   - `POST /auth/login` - User login
   - `POST /auth/logout` - Logout (clears client-side token)
   - `GET /auth/me` - Get current user info
   - `POST /auth/refresh` - Refresh access token

5. **main.py** - Updated with:
   - MongoDB connection on startup/shutdown
   - Auth router included
   - CORS enabled for frontend

6. **requirements.txt** - Added packages:
   - motor (async MongoDB)
   - pymongo (MongoDB driver)
   - python-jose[cryptography] (JWT)
   - passlib[bcrypt] (password hashing)
   - pydantic[email] (email validation)

### Frontend Files (kvitta-ui/)

1. **lib/auth-context.tsx** - Updated with:
   - Real API integration
   - JWT token storage (localStorage/sessionStorage)
   - Token auto-refresh every 25 minutes
   - Session verification on mount
   - Error handling

## Installation

### Backend Setup

```powershell
# Navigate to kvitta-api
cd kvitta-api

# Activate virtual environment
.\.kvitta-venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Start the server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend Setup

Frontend is already configured. Just make sure the API is running.

## Environment Variables

Already configured in `.env`:

```env
# MongoDB
MONGODB_URI=mongodb+srv://...
DATABASE_NAME=kvitta

# JWT Settings
SECRET_KEY=your-secret-key-change-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

**Important:** Change `SECRET_KEY` in production to a secure random string!

## API Endpoints

### Authentication

**Signup**
```bash
POST /auth/signup
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "securepassword",
  "name": "John Doe"  # optional
}

Response:
{
  "access_token": "eyJ0eXAiOiJKV1...",
  "token_type": "bearer",
  "user": {
    "email": "user@example.com",
    "name": "John Doe",
    "created_at": "2026-02-07T..."
  }
}
```

**Login**
```bash
POST /auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "securepassword"
}

Response: Same as signup
```

**Get Current User**
```bash
GET /auth/me
Authorization: Bearer <token>

Response:
{
  "email": "user@example.com",
  "name": "John Doe",
  "created_at": "2026-02-07T..."
}
```

**Refresh Token**
```bash
POST /auth/refresh
Authorization: Bearer <token>

Response: New token with extended expiration
```

**Logout**
```bash
POST /auth/logout
Authorization: Bearer <token>

Response:
{
  "message": "Successfully logged out"
}
```

## Database Schema

### Users Collection

```javascript
{
  _id: ObjectId("..."),
  email: "user@example.com",  // unique
  name: "John Doe",
  hashed_password: "$2b$12$...",  // bcrypt hash
  created_at: ISODate("..."),
  updated_at: ISODate("..."),
  is_active: true
}
```

MongoDB Atlas will automatically create the `users` collection on first signup.

## Security Features

✅ **Password Hashing** - bcrypt with salt  
✅ **JWT Tokens** - Secure token-based auth  
✅ **Token Expiration** - 30-minute default  
✅ **Auto Token Refresh** - Frontend refreshes every 25 minutes  
✅ **Email Validation** - Pydantic email validator  
✅ **Password Requirements** - Minimum 8 characters  
✅ **HTTPS Ready** - Works with SSL/TLS  

## Frontend Integration

The frontend automatically:
- Stores JWT tokens (localStorage for "remember me", sessionStorage otherwise)
- Sends tokens in Authorization header
- Refreshes tokens before expiration
- Redirects to login on authentication failure
- Shows loading states during auth checks

## Testing

### Test Signup
```bash
curl -X POST http://localhost:8000/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"testpass123","name":"Test User"}'
```

### Test Login
```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"testpass123"}'
```

### Test Get User (replace TOKEN)
```bash
curl http://localhost:8000/auth/me \
  -H "Authorization: Bearer TOKEN"
```

## Next Steps

1. **Start the backend:**
   ```powershell
   cd kvitta-api
   .\.kvitta-venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   uvicorn main:app --reload
   ```

2. **Start the frontend:**
   ```powershell
   cd kvitta-ui
   bun dev
   ```

3. **Test the flow:**
   - Visit http://localhost:3000
   - Click "Sign in" → "Sign up"
   - Create an account
   - Should redirect to dashboard
   - Logout and login again with "Remember me"

## Production Checklist

Before deploying to production:

- [ ] Change `SECRET_KEY` to a secure random string (32+ chars)
- [ ] Set `CORS_ORIGINS` to specific frontend domains
- [ ] Enable HTTPS
- [ ] Set secure cookie settings
- [ ] Implement rate limiting on auth endpoints
- [ ] Add email verification (optional)
- [ ] Add password reset flow (optional)
- [ ] Set up MongoDB indexes on email field
- [ ] Monitor failed login attempts
- [ ] Implement token blacklisting for logout (optional)

## Troubleshooting

**MongoDB Connection Error:**
- Check MONGODB_URI in .env
- Verify MongoDB Atlas network access (allow your IP)
- Check MongoDB Atlas user permissions

**JWT Token Invalid:**
- Check SECRET_KEY matches between sessions
- Verify token hasn't expired
- Clear browser storage and login again

**CORS Errors:**
- Backend running on port 8000
- Frontend running on port 3000
- Check CORS settings in main.py

**Import Errors:**
- Make sure all packages installed: `pip install -r requirements.txt`
- Virtual environment activated
