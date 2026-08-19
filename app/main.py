from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.db.base import Base
from app.db.session import engine

app = FastAPI(title="Nodal Liquidity Passport API", version="0.1.0")

# Wide open for the hackathon build - there's no auth layer yet to protect,
# and the frontend's dev origin/port isn't fixed. Scope this down (real
# origins, no wildcard) before any production deployment.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
