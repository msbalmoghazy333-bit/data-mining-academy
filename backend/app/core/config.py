"""Application configuration via pydantic-settings.

Every value is read from environment variables / a `.env` file, so the same
code runs unchanged on a laptop, a CI runner or a server.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve the project root (the `backend/` folder that contains `app/`).
BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Typed, validated application settings."""

    # --- General -----------------------------------------------------------
    app_name: str = "Data Mining Academy"
    app_version: str = "0.1.0"
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = True

    # --- API ---------------------------------------------------------------
    api_v1_prefix: str = "/api"
    # Comma-separated origins, e.g. "http://localhost:5173,http://127.0.0.1:5173"
    allowed_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # --- Database (SQLite + SQLAlchemy) ------------------------------------
    database_url: str = f"sqlite:///{BACKEND_ROOT / 'data' / 'dm_academy.db'}"

    # --- ChromaDB (local vector persistence) --------------------------------
    chroma_persist_directory: str = str(BACKEND_ROOT / "data" / "chroma")
    chroma_collection_name: str = "dm_academy_chunks"
    embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    # Which local/API path to use for embeddings:
    #   auto -> sentence-transformers if installed, else OpenRouter API (needs key),
    #   else ChromaDB's built-in ONNX MiniLM (works offline after first download)
    #   local -> local models only   |   api -> OpenRouter embeddings only
    embedding_backend: str = "auto"
    # OpenRouter slug used when the backend resolves to "api". Multilingual
    # retriever models (bge-m3, qwen3-embedding) handle Arabic much better
    # than the English MiniLM models.
    embedding_api_model: str = "baai/bge-m3"

    # --- RAG tutor -----------------------------------------------------------
    # Chunks fetched per query (spec wants 4-6).
    rag_top_k: int = 6
    # Conversation turns (messages) sent back to the model, capped.
    rag_max_history_messages: int = 12
    rag_temperature: float = 0.2

    # --- Chunking -----------------------------------------------------------
    chunk_target_words: int = 650
    chunk_max_words: int = 800
    # Slides are short (~25 words); merging keeps chunks in the target band.
    chunk_merge_short_pages: bool = True
    # Upper bound on how many pages/slide a merged chunk may span.
    chunk_max_page_span: int = 32

    # --- LLM (OpenRouter, OpenAI-compatible) --------------------------------
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    # Strong reasoning model; any OpenRouter slug works.
    llm_model: str = "anthropic/claude-3.5-sonnet"
    # Fallback tried once if the primary model errors out.
    llm_fallback_model: str = "google/gemini-2.0-flash"
    llm_temperature: float = 0.3
    llm_max_tokens: int = 8192
    llm_timeout_seconds: float = 120.0
    # Sent to OpenRouter so app authors get usage attribution in its dashboard.
    openrouter_app_name: str = "Data Mining Academy"
    openrouter_app_url: str = "http://localhost:5173"

    # --- File handling ------------------------------------------------------
    max_upload_size_mb: int = 50
    allowed_upload_types: str = ".pdf,.pptx,.ppt,.docx,.txt,.md"
    upload_dir: str = str(BACKEND_ROOT / "data" / "uploads")

    # --- Validators ---------------------------------------------------------
    @field_validator("allowed_origins", "allowed_upload_types", mode="before")
    @classmethod
    def _strip_whitespace(cls, value: str) -> str:
        return value.strip() if isinstance(value, str) else value

    # --- Derived helpers ----------------------------------------------------
    @property
    def cors_origins(self) -> list[str]:
        """Split the comma-separated origin list into a clean list."""
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]

    @property
    def allowed_extensions(self) -> set[str]:
        """Split the comma-separated extension list into a lowercase set."""
        return {ext.strip().lower() for ext in self.allowed_upload_types.split(",") if ext.strip()}

    @property
    def upload_path(self) -> Path:
        """Absolute path of the upload directory."""
        return Path(self.upload_dir).expanduser().resolve()

    @property
    def llm_configured(self) -> bool:
        """True when an OpenRouter key is available for content generation."""

        return bool(self.openrouter_api_key and self.openrouter_api_key.strip())

    @property
    def chroma_path(self) -> Path:
        """Absolute path of the ChromaDB persistence directory."""
        return Path(self.chroma_persist_directory).expanduser().resolve()

    model_config = SettingsConfigDict(
        env_file=BACKEND_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return a cached, process-wide singleton of :class:`Settings`."""
    return Settings()
