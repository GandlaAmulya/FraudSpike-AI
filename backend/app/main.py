from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import api_router
from app.core.config import settings
from app.db.database import engine
from app.models.base import Base

app = FastAPI(
    title="FraudSpike AI API",
    version="0.1.0",
    description="Defensive payment fraud-spike detection service foundation.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup() -> None:
    """Initialize the local SQLite schema for the demo environment."""
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


app.include_router(api_router)


@app.get("/api/health", tags=["system"])
async def health() -> dict[str, str]:
    """Return service availability without touching product data."""
    return {"status": "ok", "service": "fraudspike-backend"}