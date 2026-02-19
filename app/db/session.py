from app.db.mongo import mongodb


async def get_database():
    """Return the active database connection."""
    return mongodb.db
