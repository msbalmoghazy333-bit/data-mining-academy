"""Engine, session factory and FastAPI dependency for database access."""

from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.db.base import Base

settings = get_settings()

# `check_same_thread=False` is required by FastAPI: each request thread
# (including threadpool workers) reuses the same connection pool.
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    pool_pre_ping=True,
    future=True,
)


if settings.database_url.startswith("sqlite"):
    # SQLite ships with foreign-key enforcement DISABLED. Without this pragma,
    # `ON DELETE CASCADE` silently does nothing and deleting a SourceFile
    # (or Topic) would orphan its children.
    @event.listens_for(engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
    class_=Session,
)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a transactional session per request."""

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create every table declared on :class:`Base` (dev convenience).

    In production, prefer Alembic migrations: `alembic upgrade head`.
    """

    # Importing the package registers every model on Base.metadata.
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
