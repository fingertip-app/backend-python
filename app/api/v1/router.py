from fastapi import APIRouter

from app.api.v1.routers import ai, chungbuk

api_router = APIRouter()
api_router.include_router(ai.router, prefix="/ai", tags=["ai"])
api_router.include_router(chungbuk.router, prefix="/chungbuk", tags=["chungbuk"])
