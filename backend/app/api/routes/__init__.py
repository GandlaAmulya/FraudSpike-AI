"""API route registration for the FraudSpike application."""

from fastapi import APIRouter

from app.api.routes.demo import router as demo_router

api_router = APIRouter()
api_router.include_router(demo_router, prefix="/api")
