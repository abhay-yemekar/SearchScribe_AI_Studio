"""Aggregated /api/v1 router."""

from fastapi import APIRouter

from . import articles, auth, health

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(health.router)
api_v1_router.include_router(auth.router)
api_v1_router.include_router(articles.router)
