from fastapi import APIRouter
from app.schemas.settlement import SettlementCreate, SettlementResponse
from app.services.settlement_service import SettlementService

router = APIRouter()

@router.post("/", response_model=SettlementResponse)
async def create_settlement(settlement_in: SettlementCreate):
    return await SettlementService.create(settlement_in)
