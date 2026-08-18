from fastapi import APIRouter

from app.api.v1.endpoints import consent, ingest, lookup, onboarding, passport, verify

api_router = APIRouter(prefix="/v1")
api_router.include_router(onboarding.router)
api_router.include_router(consent.router)
api_router.include_router(verify.router)
api_router.include_router(ingest.router)
api_router.include_router(passport.router)
api_router.include_router(lookup.router)
