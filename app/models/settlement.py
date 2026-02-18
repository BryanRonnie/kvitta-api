from pydantic import Field
from app.models.base import MongoModel, PyObjectId

class Settlement(MongoModel):
    from_user_id: PyObjectId
    to_user_id: PyObjectId
    amount: float
