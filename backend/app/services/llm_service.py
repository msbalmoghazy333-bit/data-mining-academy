"""LLM access layer backed by OpenRouter.

OpenRouter exposes an `OpenAI-compatible`_ REST API, so the official
``openai`` SDK is used with a swapped ``base_url``. That keeps the call sites
identical to any other OpenAI-style provider and makes swapping providers a
one-line config change.

.. _OpenAI-compatible: https://openrouter.ai/docs/quickstart

Everything above this module speaks in terms of validated Pydantic models, so
the rest of the application never has to deal with malformed model output.
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)

ModelT = TypeVar("ModelT", bound=BaseModel)

# Fences such as ```json ... ``` are the most common way a model "helpfully"
# wraps otherwise valid JSON.
_CODE_FENCE = re.compile(r"```(?:json|javascript|js)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


class LLMError(Exception):
    """Base class for every failure that came from the model layer."""


class LLMNotConfigured(LLMError):
    """Raised when no API key is available."""


class LLMUnavailable(LLMError):
    """Raised when the provider could not be reached at all."""


class LLMInvalidOutput(LLMError):
    """Raised when the model returned something that is not valid JSON."""

    def __init__(self, message: str, raw_text: str = "") -> None:
        super().__init__(message)
        self.raw_text = raw_text


@dataclass(frozen=True, slots=True)
class LLMUsage:
    """Token accounting for one call."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass(frozen=True, slots=True)
class LLMResult:
    """Raw text plus provenance metadata."""

    content: str
    model: str
    usage: LLMUsage = field(default_factory=LLMUsage)
    attempts: int = 1


# ---------------------------------------------------------------------------
# JSON extraction
# ---------------------------------------------------------------------------


def extract_json_payload(text: str) -> Any:
    """Pull the first well-formed JSON value out of arbitrary model output.

    Handles the three shapes that occur in practice:

    1. bare JSON,
    2. JSON inside a ```json fence,
    3. JSON surrounded by chatty prose.
    """

    if not text or not text.strip():
        raise LLMInvalidOutput("The model returned an empty response.")

    stripped = text.strip()

    # 1. The whole message is already JSON.
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass

    # 2. A fenced block.
    for match in _CODE_FENCE.finditer(stripped):
        candidate = match.group(1).strip()
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue

    # 3. The outermost balanced object or array, wherever it starts.
    for opener, closer in (("{", "}"), ("[", "]")):
        start = stripped.find(opener)
        if start == -1:
            continue

        end = _balanced_end(stripped, start, opener, closer)
        if end is None:
            continue

        try:
            return json.loads(stripped[start : end + 1])
        except json.JSONDecodeError:
            continue

    raise LLMInvalidOutput(
        "The model response did not contain parseable JSON.", raw_text=text[:2000]
    )


def _balanced_end(text: str, start: int, opener: str, closer: str) -> int | None:
    """Index of the ``closer`` matching the ``opener`` at ``start``."""

    depth = 0
    in_string = False
    escaped = False

    for index in range(start, len(text)):
        char = text[index]

        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == opener:
            depth += 1
        elif char == closer:
            depth -= 1
            if depth == 0:
                return index

    return None


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class LLMService:
    """Thin, retrying wrapper around an OpenAI-compatible chat endpoint."""

    def __init__(self, settings: Settings | None = None, client: Any | None = None) -> None:
        self.settings = settings or get_settings()
        self._client = client

    # -- plumbing ----------------------------------------------------------

    @property
    def configured(self) -> bool:
        return self.settings.llm_configured

    def _build_client(self) -> Any:
        from openai import OpenAI

        settings = self.settings

        # OpenRouter uses these two headers for the "OpenRouter: site" credit
        # attribution shown in its dashboard.
        default_headers = {
            "HTTP-Referer": settings.openrouter_app_url,
            "X-Title": settings.openrouter_app_name,
        }

        return OpenAI(
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url,
            timeout=settings.llm_timeout_seconds,
            default_headers=default_headers,
        )

    @property
    def client(self) -> Any:
        if self._client is None:
            if not self.configured:
                raise LLMNotConfigured(
                    "OPENROUTER_API_KEY is not set. Add it to backend/.env to "
                    "enable content generation."
                )
            self._client = self._build_client()
        return self._client

    def close(self) -> None:
        if self._client is not None:
            close = getattr(self._client, "close", None)
            if callable(close):
                close()
            self._client = None

    # -- calls -------------------------------------------------------------

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        max_attempts: int = 2,
    ) -> LLMResult:
        """Run one chat completion, retrying once on a transient failure."""

        settings = self.settings
        primary = model or settings.llm_model
        fallback = settings.llm_fallback_model

        tried: list[str] = []
        last_error: Exception | None = None

        for attempt in range(1, max_attempts + 1):
            target = primary if attempt == 1 else fallback
            if target in tried:
                break
            tried.append(target)

            try:
                return self._call_once(
                    messages,
                    model=target,
                    temperature=temperature if temperature is not None else settings.llm_temperature,
                    max_tokens=max_tokens or settings.llm_max_tokens,
                    attempts=attempt,
                )
            except LLMNotConfigured:
                raise
            except Exception as exc:  # noqa: BLE001 - normalised below
                last_error = exc
                logger.warning("LLM call to %r failed (attempt %d): %s", target, attempt, exc)
                if attempt < max_attempts:
                    time.sleep(min(2 ** attempt, 8))

        raise LLMUnavailable(f"LLM request failed after {len(tried)} attempt(s): {last_error}")

    def _call_once(
        self,
        messages: list[dict[str, str]],
        *,
        model: str,
        temperature: float,
        max_tokens: int,
        attempts: int,
    ) -> LLMResult:
        response = self.client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        choice = response.choices[0]
        content = (choice.message.content or "").strip()

        if not content:
            raise LLMInvalidOutput(f"The model {model!r} returned no content.")

        usage = LLMUsage()
        raw_usage = getattr(response, "usage", None)
        if raw_usage is not None:
            usage = LLMUsage(
                prompt_tokens=getattr(raw_usage, "prompt_tokens", 0) or 0,
                completion_tokens=getattr(raw_usage, "completion_tokens", 0) or 0,
                total_tokens=getattr(raw_usage, "total_tokens", 0) or 0,
            )

        return LLMResult(content=content, model=model, usage=usage, attempts=attempts)

    def chat_json(
        self,
        messages: list[dict[str, str]],
        *,
        schema: type[ModelT] | None = None,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> tuple[Any, LLMResult]:
        """Chat, parse JSON, and optionally validate it against ``schema``.

        Returns ``(parsed, result)`` so callers can log token usage.
        """

        result = self.chat(
            messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        try:
            payload = extract_json_payload(result.content)
        except LLMInvalidOutput:
            # One repair round: models usually fix malformed JSON when asked.
            repaired = self.chat(
                messages
                + [
                    {"role": "assistant", "content": result.content},
                    {
                        "role": "user",
                        "content": (
                            "Your previous reply was not valid JSON. "
                            "Reply again with ONLY the JSON, no prose and no code fences."
                        ),
                    },
                ],
                model=model,
                temperature=0.0,
            )
            payload = extract_json_payload(repaired.content)
            result = LLMResult(
                content=repaired.content,
                model=repaired.model,
                usage=LLMUsage(
                    prompt_tokens=result.usage.prompt_tokens + repaired.usage.prompt_tokens,
                    completion_tokens=result.usage.completion_tokens
                    + repaired.usage.completion_tokens,
                    total_tokens=result.usage.total_tokens + repaired.usage.total_tokens,
                ),
                attempts=result.attempts + repaired.attempts,
            )

        if schema is None:
            return payload, result

        try:
            validated = schema.model_validate(payload)
        except ValidationError as exc:
            raise LLMInvalidOutput(
                f"Model output did not match the expected schema: {exc.errors()[:3]}",
                raw_text=result.content[:2000],
            ) from exc

        return validated, result


# ---------------------------------------------------------------------------
# Module-level factory
# ---------------------------------------------------------------------------

_cached_service: LLMService | None = None


def get_llm_service() -> LLMService:
    """Process-wide LLMService (settings are cached, so this is cheap)."""

    global _cached_service
    if _cached_service is None:
        _cached_service = LLMService()
    return _cached_service


def reset_llm_service() -> None:
    """Drop the cached client -- used by tests and by config reloads."""

    global _cached_service
    if _cached_service is not None:
        _cached_service.close()
    _cached_service = None
