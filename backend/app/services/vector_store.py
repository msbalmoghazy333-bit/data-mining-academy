"""Vector store (ChromaDB) + pluggable embedding backends.

Only **published** files' chunks are indexed, so an upload still under human
review can never be answered by the tutor. Every vector carries its provenance
(``file_id``, ``filename``, ``page_number``, ``chunk_id``) which is what makes
the tutor's mandatory citations truthful -- they come from retrieval metadata,
never from the model's imagination.

Embedding backends are tried in the order given by ``EMBEDDING_BACKEND``:

* ``sentence-transformers`` locally (if the package is installed),
* the OpenRouter OpenAI-compatible ``/embeddings`` endpoint (recommended for
  Arabic -- bge-m3 / qwen3-embedding are multilingual),
* ChromaDB's built-in ONNX MiniLM (works offline after a one-time download).

The abstraction exists because this project targets Python 3.14, where torch
may not be installable yet -- the tests therefore inject a deterministic
hash-based embedder instead of any of the three above.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Protocol, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import SessionLocal
from app.models import DocumentChunk, SourceFile
from app.models.enums import SourceFileStatus

logger = logging.getLogger(__name__)

MAX_EMBED_BATCH = 64


class EmbeddingNotReady(Exception):
    """No embedding backend is usable right now."""


class Embedder(Protocol):
    """Anything that can turn text into fixed-size vectors."""

    name: str

    def embed(self, texts: list[str]) -> list[list[float]]: ...


# ---------------------------------------------------------------------------
# Backends
# ---------------------------------------------------------------------------


class SentenceTransformerEmbedder:
    """Local ``sentence-transformers`` models (best free quality)."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._model: Any = None

    @property
    def name(self) -> str:
        return f"sentence-transformers:{self._settings.embedding_model}"

    def embed(self, texts: list[str]) -> list[list[float]]:
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            logger.info("Loading sentence-transformers model %r ...", self._settings.embedding_model)
            self._model = SentenceTransformer(self._settings.embedding_model)
        return [row.tolist() for row in self._model.encode(texts, normalize_embeddings=True)]


class ApiEmbedder:
    """OpenRouter ``/embeddings`` -- OpenAI-compatible, multilingual models."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client: Any = None

    @property
    def name(self) -> str:
        return f"api:{self._settings.embedding_api_model}"

    def _get_client(self) -> Any:
        if self._client is None:
            from openai import OpenAI

            self._client = OpenAI(
                api_key=self._settings.openrouter_api_key,
                base_url=self._settings.openrouter_base_url,
                timeout=self._settings.llm_timeout_seconds,
                default_headers={
                    "HTTP-Referer": self._settings.openrouter_app_url,
                    "X-Title": self._settings.openrouter_app_name,
                },
            )
        return self._client

    def embed(self, texts: list[str]) -> list[list[float]]:
        client = self._get_client()
        vectors: list[list[float]] = []

        # /embeddings accepts batches, but cap size to keep requests small.
        for start in range(0, len(texts), MAX_EMBED_BATCH):
            batch = texts[start : start + MAX_EMBED_BATCH]
            response = client.embeddings.create(
                model=self._settings.embedding_api_model,
                input=batch,
            )
            batch_vectors = [item.embedding for item in response.data]
            if len(batch_vectors) != len(batch):
                raise EmbeddingNotReady(
                    f"The embedding API returned {len(batch_vectors)} vectors "
                    f"for {len(batch)} inputs."
                )
            vectors.extend(batch_vectors)

        return vectors


class OnnxMiniLMEmbedder:
    """ChromaDB's built-in ONNX MiniLM -- no torch/sentence-transformers needed.

    Downloads the ~80 MB model on first use, then runs fully offline.
    Quality on Arabic is weaker than the API models; it is the zero-cost
    fallback when no API key is available and sentence-transformers is missing.
    """

    def __init__(self) -> None:
        self._ef: Any = None

    @property
    def name(self) -> str:
        return "onnx:all-MiniLM-L6-v2"

    def embed(self, texts: list[str]) -> list[list[float]]:
        if self._ef is None:
            from chromadb.utils.embedding_functions.onnx_mini_lm_l6_v2 import (  # noqa: I001
                ONNXMiniLM_L6_V2,
            )

            self._ef = ONNXMiniLM_L6_V2()

        result = self._ef(input=texts)
        if isinstance(result, dict):  # some chroma versions return {"embeddings": [...]}
            result = result["embeddings"]
        return [list(vector) for vector in result]


# ---------------------------------------------------------------------------
# Backend selection
# ---------------------------------------------------------------------------


def _sentence_transformers_available() -> bool:
    try:
        import sentence_transformers  # noqa: F401

        return True
    except ImportError:
        return False


def build_embedder(settings: Settings | None = None) -> Embedder:
    """Instantiate the embedding backend named by ``EMBEDDING_BACKEND``.

    Raises :class:`EmbeddingNotReady` when the requested backend cannot work
    in this environment.
    """

    settings = settings or get_settings()
    backend = (settings.embedding_backend or "auto").strip().lower()

    def _local_or_api_fallback(surface: str) -> Embedder:
        return _try_chain(
            [
                ("sentence-transformers", lambda: SentenceTransformerEmbedder(settings)),
                ("openrouter-api", lambda: ApiEmbedder(settings)),
                ("chromadb-onnx", OnnxMiniLMEmbedder),
            ],
            context=f"{surface} fallback",
        )

    if backend == "local":
        return _local_or_api_fallback("local")
    if backend == "api":
        return _try_chain(
            [("openrouter-api", lambda: ApiEmbedder(settings))],
            context="api",
        )

    # auto: local first (free + private), then API, then built-in ONNX.
    if _sentence_transformers_available():
        return SentenceTransformerEmbedder(settings)
    if settings.llm_configured:
        return _try_chain(
            [("openrouter-api", lambda: ApiEmbedder(settings)), ("chromadb-onnx", OnnxMiniLMEmbedder)],
            context="auto",
        )
    return _try_chain(
        [("chromadb-onnx", OnnxMiniLMEmbedder)],
        context="auto-without-api-key",
    )


def _try_chain(candidates: list[tuple[str, Any]], *, context: str) -> Embedder:
    """Build the first workable backend, reporting every failure on the way."""

    errors: list[str] = []

    for label, factory in candidates:
        try:
            embedder = factory()
            return embedder
        except Exception as exc:  # noqa: BLE001 - selection across many libs
            errors.append(f"{label}: {type(exc).__name__}: {exc}")

    raise EmbeddingNotReady(
        f"No embedding backend could be initialised ({context}): " + " | ".join(errors)
    )


# ---------------------------------------------------------------------------
# Retrieval result
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RetrievedChunk:
    """One vector-store hit, ready to become a citation."""

    file_id: int
    filename: str
    page: int | None
    chunk_id: int
    text: str
    distance: float


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------


class VectorStore:
    """Thin, idempotent wrapper around a persistent ChromaDB collection."""

    def __init__(self, settings: Settings | None = None, embedder: Embedder | None = None) -> None:
        self.settings = settings or get_settings()
        self._embedder = embedder
        self._collection: Any = None

    # -- embeddings ----------------------------------------------------------

    @property
    def embedder(self) -> Embedder:
        if self._embedder is None:
            self._embedder = build_embedder(self.settings)
        return self._embedder

    # -- collection ----------------------------------------------------------

    @property
    def collection(self) -> Any:
        if self._collection is None:
            import chromadb
            from chromadb.config import Settings as ChromaSettings

            # The library's own Settings (ours is app-level!), telemetry off.
            client = chromadb.PersistentClient(
                path=str(self.settings.chroma_path),
                settings=ChromaSettings(anonymized_telemetry=False, allow_reset=True),
            )
            self._collection = client.get_or_create_collection(
                name=self.settings.chroma_collection_name,
                metadata={"hnsw:space": "cosine"},
            )
        return self._collection

    def chunk_vector_id(self, source_file: SourceFile, chunk: DocumentChunk) -> str:
        """Deterministic id -> re-indexing the same chunk is an upsert."""

        return f"{source_file.id}:{chunk.chunk_index}"

    # -- writes --------------------------------------------------------------

    def index_file(
        self,
        source_file: SourceFile,
        chunks: Sequence[DocumentChunk] | None = None,
        *,
        purge: bool = True,
        db: Session | None = None,
    ) -> int:
        """Embed and store all chunks of one file. Returns the vector count.

        Purge-then-insert keeps re-indexing idempotent so stale vectors from a
        previous extraction can never linger behind fresh content. When ``db``
        is provided, the ``DocumentChunk.chroma_id`` sync is committed as part
        of the call -- otherwise the caller owns that write.
        """

        count = len(chunks) if chunks is not None else len(source_file.chunks)

        if purge:
            self.remove_file(source_file.id)

        chunks = list(chunks) if chunks is not None else list(source_file.chunks)
        chunks = [chunk for chunk in chunks if (chunk.content or "").strip()]
        if not chunks:
            return 0

        ids = [self.chunk_vector_id(source_file, chunk) for chunk in chunks]
        documents = [chunk.content for chunk in chunks]
        metadatas = [
            {
                "file_id": source_file.id,
                "filename": source_file.filename,
                "page_number": chunk.page_or_slide_number or 0,
                "chunk_id": chunk.id or 0,
            }
            for chunk in chunks
        ]

        self.collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
            embeddings=self.embedder.embed(documents),
        )

        # Keep the DB column in sync with the vector ids.
        for chunk, vector_id in zip(chunks, ids, strict=True):
            if chunk.chroma_id != vector_id:
                chunk.chroma_id = vector_id

        if db is not None:
            db.commit()

        return len(chunks)

    def remove_file(self, file_id: int) -> int:
        """Drop every vector belonging to a file (used on delete / re-extract)."""

        found = self.collection.get(where={"file_id": file_id})
        ids = list(found.get("ids") or [])
        if ids:
            self.collection.delete(ids=ids)
        return len(ids)

    # -- reads ---------------------------------------------------------------

    def count(self) -> int:
        """Total vectors in the collection."""

        return int(self.collection.count())

    def search(self, query: str, *, top_k: int | None = None) -> list[RetrievedChunk]:
        """Top-k most similar vectors for ``query`` (ordered, best first)."""

        limit = top_k or self.settings.rag_top_k
        total = self.count()
        if total == 0 or not query.strip():
            return []

        response = self.collection.query(
            query_embeddings=[self.embedder.embed([query])[0]],
            n_results=min(limit, total),
            include=["documents", "metadatas", "distances"],
        )

        hits: list[RetrievedChunk] = []
        documents = (response.get("documents") or [[]])[0]
        metadatas = (response.get("metadatas") or [[]])[0]
        distances = (response.get("distances") or [[]])[0]

        for text, metadata, distance in zip(documents, metadatas, distances, strict=False):
            page_number = int(metadata.get("page_number") or 0)
            hits.append(
                RetrievedChunk(
                    file_id=int(metadata.get("file_id", 0)),
                    filename=str(metadata.get("filename", "")),
                    page=page_number or None,
                    chunk_id=int(metadata.get("chunk_id", -1)),
                    text=str(text),
                    distance=float(distance),
                )
            )

        return hits

    def stats(self) -> dict:
        """Small health summary for logs and the health endpoint."""

        total = self.count()
        files = {int(m["file_id"]) for m in self.collection.get(include=["metadatas"])["metadatas"]}
        return {"total_vectors": total, "indexed_files": sorted(files), "embedder": self.embedder.name}


# ---------------------------------------------------------------------------
# Module-level factory
# ---------------------------------------------------------------------------

_cached_store: VectorStore | None = None


def get_vector_store() -> VectorStore:
    """Process-wide store (settings are cached, so this is process-stable)."""

    global _cached_store
    if _cached_store is None:
        _cached_store = VectorStore()
    return _cached_store


def reset_vector_store() -> None:
    """Drop the cached client -- used by tests."""

    global _cached_store
    _cached_store = None


def ensure_published_indexed() -> dict:
    """Index every ``published`` file that is not in the collection yet.

    Called at app startup so a restart never loses the RAG index. Embedding
    backends are optional -- when none is usable (e.g. no key in dev), this
    reports the skip instead of crashing the app.
    """

    summary: dict = {"indexed_files": 0, "indexed_chunks": 0, "skipped": None}

    try:
        store = get_vector_store()
    except EmbeddingNotReady as exc:
        summary["skipped"] = f"no embedder: {exc}"
        return summary

    db = SessionLocal()
    try:
        published = list(
            db.execute(
                select(SourceFile).where(SourceFile.status == SourceFileStatus.PUBLISHED.value)
            ).scalars()
        )

        for source_file in published:
            try:
                summary["indexed_chunks"] += store.index_file(source_file, db=db)
                summary["indexed_files"] += 1
            except Exception as exc:  # noqa: BLE001 - file-level, not app-level
                logger.warning("Could not index file %s: %s", source_file.id, exc)
    finally:
        db.close()

    return summary
