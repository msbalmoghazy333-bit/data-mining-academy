"""On-demand translation tests.

No network and no real model: the LLM is a scripted stub exactly like
``test_tutor.py``/``test_generation.py``, so the whole suite stays offline.
"""

from __future__ import annotations

import json

import pytest

from app.core.config import get_settings
from app.services import translation_service
from app.services.llm_service import LLMInvalidOutput, LLMResult, LLMService, LLMUsage
from app.services.translation_service import (
    clear_cache,
    translate_texts,
)

TRANSLATE_URL = "/api/v1/translate"


class FakeLLM(LLMService):
    """Scripted chat stub; records every message batch it receives."""

    def __init__(self, reply: str, *, model: str = "fake/translate-model") -> None:
        self.settings = get_settings()
        self._client = None
        self._reply = reply
        self.model = model
        self.calls: list[list[dict[str, str]]] = []

    @property
    def configured(self) -> bool:
        return True

    def chat(self, messages, **kwargs) -> LLMResult:
        self.calls.append(messages)
        return LLMResult(
            content=self._reply,
            model=self.model,
            usage=LLMUsage(prompt_tokens=12, completion_tokens=6, total_tokens=18),
        )


def _reply_for(translations: list[str]) -> str:
    return json.dumps({"translations": translations}, ensure_ascii=False)


@pytest.fixture(autouse=True)
def _clear_translation_cache():
    """Every test starts with an empty LRU so counts are deterministic."""

    clear_cache()
    yield
    clear_cache()


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class TestTranslationService:
    def test_translates_in_order(self):
        llm = FakeLLM(_reply_for(["ما هو K-Means؟", "ما هو DBSCAN؟"]))

        result = translate_texts(
            ["What is K-Means?", "What is DBSCAN?"], target="ar", llm=llm
        )

        assert result.translations == ["ما هو K-Means؟", "ما هو DBSCAN؟"]
        assert result.target == "ar"
        assert result.model == "fake/translate-model"
        assert result.cached is False
        assert len(llm.calls) == 1

    def test_system_prompt_asks_for_arabic_and_preserves_terms(self):
        llm = FakeLLM(_reply_for(["نص"]))

        translate_texts(["Some text"], target="ar", llm=llm)

        system = llm.calls[0][0]["content"]
        assert "JSON" in system
        assert "المصطلح" in system  # keeps English technical terms

    def test_second_call_is_served_from_cache(self):
        llm = FakeLLM(_reply_for(["نص مترجم"]))

        translate_texts(["Hello"], target="ar", llm=llm)
        second = translate_texts(["Hello"], target="ar", llm=llm)

        assert second.translations == ["نص مترجم"]
        assert second.cached is True
        assert len(llm.calls) == 1  # the model was never asked twice

    def test_duplicates_translate_once_but_return_every_item(self):
        llm = FakeLLM(_reply_for(["مكرر"]))

        result = translate_texts(["Repeat", "Repeat", "Repeat"], target="ar", llm=llm)

        assert result.translations == ["مكرر", "مكرر", "مكرر"]
        # Only the unique string was sent, once.
        user_prompt = llm.calls[0][1]["content"]
        assert user_prompt.count("Repeat") == 1

    def test_count_mismatch_is_invalid_output(self):
        llm = FakeLLM(_reply_for(["واحد فقط"]))  # 1 translation for 2 inputs

        with pytest.raises(LLMInvalidOutput):
            translate_texts(["One", "Two"], target="ar", llm=llm)

    def test_reverse_direction_uses_english_prompt(self):
        llm = FakeLLM(_reply_for(["What is clustering?"]))

        translate_texts(["إيه التجميع؟"], target="en", llm=llm)

        assert "academic English" in llm.calls[0][0]["content"]

    def test_unsupported_target_is_rejected(self):
        llm = FakeLLM(_reply_for(["x"]))

        with pytest.raises(ValueError):
            translate_texts(["Hello"], target="fr", llm=llm)

    def test_blank_input_is_rejected(self):
        llm = FakeLLM(_reply_for(["x"]))

        with pytest.raises(ValueError):
            translate_texts(["   "], target="ar", llm=llm)


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


class TestTranslationEndpoint:
    def test_returns_translations(self, client, monkeypatch):
        fake = FakeLLM(_reply_for(["إيه الفرق بين K-Means و DBSCAN؟"]))
        monkeypatch.setattr(
            translation_service, "get_llm_service", lambda: fake, raising=True
        )

        response = client.post(
            TRANSLATE_URL,
            json={"texts": ["What is the difference between K-Means and DBSCAN?"], "target": "ar"},
        )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["translations"] == ["إيه الفرق بين K-Means و DBSCAN؟"]
        assert body["target"] == "ar"
        assert body["model"] == "fake/translate-model"
        assert body["cached"] is False

    def test_second_request_reports_cached(self, client, monkeypatch):
        fake = FakeLLM(_reply_for(["مرحبا"]))
        monkeypatch.setattr(
            translation_service, "get_llm_service", lambda: fake, raising=True
        )

        client.post(TRANSLATE_URL, json={"texts": ["Hello"], "target": "ar"})
        second = client.post(TRANSLATE_URL, json={"texts": ["Hello"], "target": "ar"})

        assert second.json()["cached"] is True
        assert len(fake.calls) == 1

    def test_missing_api_key_is_409(self, client):
        # The real service runs with an empty key: llm_configured is False, so
        # touching the client raises LLMNotConfigured -> 409.
        response = client.post(TRANSLATE_URL, json={"texts": ["Hello"], "target": "ar"})

        assert response.status_code == 409, response.text
        assert "OPENROUTER_API_KEY" in response.json()["detail"]

    def test_validation(self, client):
        assert client.post(TRANSLATE_URL, json={"texts": []}).status_code == 422
        assert (
            client.post(TRANSLATE_URL, json={"texts": ["ok", "  "]}).status_code == 422
        )
        assert (
            client.post(TRANSLATE_URL, json={"texts": ["ok"], "target": "fr"}).status_code
            == 422
        )
        assert (
            client.post(
                TRANSLATE_URL, json={"texts": ["x" * 2001], "target": "ar"}
            ).status_code
            == 422
        )
        assert (
            client.post(
                TRANSLATE_URL, json={"texts": ["a"] * 21, "target": "ar"}
            ).status_code
            == 422
        )
