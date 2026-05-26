from fastapi import APIRouter

from app.api.v1.routers import ai

api_router = APIRouter()
api_router.include_router(ai.router, prefix="/ai", tags=["ai"])
