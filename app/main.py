from fastapi import FastAPI
from app.core.config import settings
from app.db.session import connect_to_mongo, close_mongo_connection
from app.api.v1.api import api_router

app = FastAPI(title=settings.PROJECT_NAME)

app.add_event_handler("startup", connect_to_mongo)
app.add_event_handler("shutdown", close_mongo_connection)

@app.get("/")
async def root():
    return {"message": "Welcome to Kvitta API"}

app.include_router(api_router, prefix=settings.API_V1_STR)
