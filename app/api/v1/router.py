from fastapi import APIRouter

from app.api.v1.endpoints import consent, decision, ingest, ledger, lookup, onboarding, passport, receipt, verify

api_router = APIRouter(prefix="/v1")
api_router.include_router(onboarding.router)
api_router.include_router(consent.router)
api_router.include_router(verify.router)
# receipt.router's literal POST /ingest/receipt must be registered before
# ingest.router's wildcard POST /ingest/{source_type} - Starlette matches
# routes in registration order, and 'receipt' is a valid SourceType value
# now, so the wildcard would otherwise swallow this path first.
api_router.include_router(receipt.router)
api_router.include_router(ingest.router)
api_router.include_router(passport.router)
api_router.include_router(decision.router)
api_router.include_router(ledger.router)
api_router.include_router(lookup.router)
