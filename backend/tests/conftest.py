"""Shared pytest fixtures.

The environment is redirected to a throw-away SQLite database and upload
folder **before** any ``app.*`` module is imported, so the module-level engine
in ``app.db.session`` never points at the developer's real database.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

# --- make `app` importable when pytest is launched from the repo root -------
BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

# --- redirect persistence BEFORE importing the application ------------------
_TMP_ROOT = Path(tempfile.mkdtemp(prefix="dmacademy-tests-"))

os.environ["DATABASE_URL"] = f"sqlite:///{_TMP_ROOT / 'test.db'}"
os.environ["UPLOAD_DIR"] = str(_TMP_ROOT / "uploads")
os.environ["CHROMA_PERSIST_DIRECTORY"] = str(_TMP_ROOT / "chroma")
os.environ["ENVIRONMENT"] = "development"
os.environ["ALLOWED_UPLOAD_TYPES"] = ".pdf,.docx,.pptx,.txt,.md"
# Keep the strict per-page citation behaviour under test; the slide-merging
# default is covered by its own dedicated tests.
os.environ["CHUNK_MERGE_SHORT_PAGES"] = "false"
# Never let a developer's real key leak into the test run.
os.environ["OPENROUTER_API_KEY"] = ""

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402

# Clear any settings cached during import so they pick up the env above.
get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _fresh_database():
    """Give every test an empty schema **and** an empty upload folder."""

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    upload_path = get_settings().upload_path
    if upload_path.is_dir():
        for stale in upload_path.iterdir():
            stale.unlink(missing_ok=True)
    else:
        upload_path.mkdir(parents=True, exist_ok=True)

    yield


@pytest.fixture()
def db_session() -> Session:
    """A direct ORM session, for service-level tests."""

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client() -> TestClient:
    """ASGI test client with the lifespan (startup) hooks executed."""

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def upload_dir() -> Path:
    """The temp folder the application is configured to store uploads in."""

    path = get_settings().upload_path
    path.mkdir(parents=True, exist_ok=True)
    return path
