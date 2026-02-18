from typing import Optional
from pydantic import EmailStr, Field
from app.models.base import MongoModel

class User(MongoModel):
    name: str
    email: EmailStr
    hashed_password: str
    is_deleted: bool = False
