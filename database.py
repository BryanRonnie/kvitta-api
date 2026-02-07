"""
Database connection and utilities for MongoDB Atlas
"""

import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI")
DATABASE_NAME = os.getenv("DATABASE_NAME", "kvitta")

class Database:
    client: AsyncIOMotorClient = None
    
db = Database()

async def get_database():
    """Get database instance"""
    return db.client[DATABASE_NAME]

async def connect_to_mongo():
    """Connect to MongoDB Atlas"""
    db.client = AsyncIOMotorClient(MONGODB_URI)
    print("Connected to MongoDB Atlas")

async def close_mongo_connection():
    """Close MongoDB connection"""
    db.client.close()
    print("Closed MongoDB connection")

async def get_users_collection():
    """Get users collection"""
    database = await get_database()
    return database.users
