from fastapi import APIRouter
from app.api.v1.endpoints import auth, users, folders, receipts, ledger, settlements

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(folders.router, prefix="/folders", tags=["folders"])
api_router.include_router(receipts.router, prefix="/receipts", tags=["receipts"])
api_router.include_router(ledger.router, prefix="/ledger", tags=["ledger"])
api_router.include_router(settlements.router, prefix="/settlements", tags=["settlements"])
