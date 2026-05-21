from fastapi import APIRouter

from app.api.v1.routers import ai, bookings, cardnews, experiences

api_router = APIRouter()
api_router.include_router(experiences.router, prefix="/experiences", tags=["experiences"])
api_router.include_router(cardnews.router, prefix="/cardnews", tags=["cardnews"])
api_router.include_router(ai.router, prefix="/ai", tags=["ai"])
api_router.include_router(bookings.router, prefix="/bookings", tags=["bookings"])
