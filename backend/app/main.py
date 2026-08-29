from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings

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


@app.get("/api/health", tags=["system"])
async def health() -> dict[str, str]:
    """Return service availability without touching product data."""
    return {"status": "ok", "service": "fraudspike-backend"}