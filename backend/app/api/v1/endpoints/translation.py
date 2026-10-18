"""On-demand translation endpoint.

    POST /api/v1/translate   translate a batch of strings (LLM, cached)

The quiz UI uses this for the per-question "show in Arabic" toggle: questions
are authored in English and translated on first request, then served from the
process cache. Failures follow the project-wide convention: 409 when no
``OPENROUTER_API_KEY`` is configured, 502 when the provider misbehaves.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.schemas.translation import TranslationRequest, TranslationResponse
from app.services import translation_service
from app.services.llm_service import LLMError, LLMNotConfigured, LLMUnavailable

router = APIRouter(prefix="/v1/translate", tags=["translation"])


@router.post(
    "",
    response_model=TranslationResponse,
    summary="Translate assessment text on demand (English <-> Egyptian Arabic)",
)
def translate(payload: TranslationRequest) -> TranslationResponse:
    """Deterministic-format LLM translation with an in-process cache."""

    try:
        result = translation_service.translate_texts(payload.texts, target=payload.target)
    except LLMNotConfigured as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except LLMUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    except LLMError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    return TranslationResponse(
        translations=result.translations,
        target=result.target,
        model=result.model,
        cached=result.cached,
    )
