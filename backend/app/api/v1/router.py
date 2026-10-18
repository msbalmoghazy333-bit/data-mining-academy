"""Aggregates every v1 endpoint into a single router.

New feature modules are added here so that `/api` stays a stable public contract.
"""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    dashboard,
    files,
    flashcards,
    generation,
    health,
    lessons,
    quizzes,
    topics,
    translation,
    tutor,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(files.router)
api_router.include_router(generation.router)
api_router.include_router(topics.router)
api_router.include_router(lessons.router)
api_router.include_router(translation.router)
api_router.include_router(tutor.router)
api_router.include_router(quizzes.router)
api_router.include_router(flashcards.router)
api_router.include_router(dashboard.router)

__all__ = ["api_router"]
