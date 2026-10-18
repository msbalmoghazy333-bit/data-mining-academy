"""AI Tutor endpoints (RAG over published course material).

    POST /api/v1/tutor/chat   ask a question -> grounded reply + citations

Answers are built only from chunks of **published** files, and every citation
in the response has been verified against retrieval metadata -- the structure
cannot contain an invented page number even if the model imagined one.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.tutor import TutorChatRequest, TutorChatResponse
from app.services import tutor_service
from app.services.llm_service import LLMError, LLMNotConfigured, LLMUnavailable
from app.services.vector_store import EmbeddingNotReady

router = APIRouter(prefix="/v1/tutor", tags=["tutor"])

DbSession = Annotated[Session, Depends(get_db)]


@router.post(
    "/chat",
    response_model=TutorChatResponse,
    summary="Ask the AI tutor a question grounded in published course material",
)
def tutor_chat(payload: TutorChatRequest, db: DbSession) -> TutorChatResponse:
    """One RAG turn: retrieve -> generate -> verify citations."""

    try:
        answer = tutor_service.ask(
            payload.message,
            history=[turn.model_dump() for turn in payload.history],
            difficulty_level=payload.difficulty_level,
        )
    except EmbeddingNotReady as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    except LLMNotConfigured as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except LLMUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    except LLMError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    return TutorChatResponse(
        reply=answer.reply,
        citations=answer.citations,
        retrieved=answer.retrieved,
        model=answer.model,
        used_index=answer.used_index,
    )
