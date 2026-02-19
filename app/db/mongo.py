from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from app.core.config import settings

class MongoDatabase:
    """MongoDB connection manager."""
    
    client: AsyncIOMotorClient = None
    db: AsyncIOMotorDatabase = None

mongodb = MongoDatabase()

async def connect_to_mongo():
    """Connect to MongoDB."""
    mongodb.client = AsyncIOMotorClient(settings.MONGODB_URI)
    mongodb.db = mongodb.client[settings.MONGODB_DB]
    
    # Create indexes
    await create_indexes()
    print(f"Connected to MongoDB: {settings.MONGODB_DB}")

async def disconnect_from_mongo():
    """Disconnect from MongoDB."""
    mongodb.client.close()
    print("Disconnected from MongoDB")

async def create_indexes():
    """Create database indexes."""
    # User email unique index
    await mongodb.db["users"].create_index("email", unique=True)
    
    # Receipt indexes
    await mongodb.db["receipts"].create_index("owner_id")
    await mongodb.db["receipts"].create_index([("participants.user_id", 1)])
    
    # Ledger indexes
    await mongodb.db["ledgers"].create_index("receipt_id")
    await mongodb.db["ledgers"].create_index([("debtor_id", 1), ("status", 1)])
    await mongodb.db["ledgers"].create_index([("creditor_id", 1), ("status", 1)])
    
    # Folder indexes
    await mongodb.db["folders"].create_index("owner_id")

def get_db() -> AsyncIOMotorDatabase:
    """Get database instance."""
    return mongodb.db
