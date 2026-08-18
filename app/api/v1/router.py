from fastapi import APIRouter

from app.api.v1.endpoints import consent, onboarding

api_router = APIRouter(prefix="/v1")
api_router.include_router(onboarding.router)
api_router.include_router(consent.router)
