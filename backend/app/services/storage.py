"""Secure local storage for uploaded course files.

Responsibilities:
  * stream an :class:`fastapi.UploadFile` to disk without loading it all in RAM
  * compute SHA-256 while streaming (single pass -> no double I/O)
  * neutralise path traversal and hostile file names

Stored layout::

    <UPLOAD_DIR>/
        <sha256[:16]>-<sanitized-original-name>
        <sha256[:16]>-<sanitized-original-name>
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from app.core.config import get_settings

# 1 MiB -- large enough to keep syscalls low, small enough for low-memory hosts.
_BUFFER_SIZE = 1024 * 1024

# Characters that are unsafe on Windows *and* POSIX filesystems.
_UNSAFE_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f\x7f]')
_WHITESPACE = re.compile(r"\s+")

MAX_FILENAME_LEN = 120


class StorageError(Exception):
    """Raised when a file cannot be safely written to disk."""


@dataclass(frozen=True, slots=True)
class StoredFile:
    """Result of persisting one upload."""

    path: Path
    file_hash: str
    size: int
    stored_name: str
    original_name: str
    file_type: str


def sha256_bytes(payload: bytes) -> str:
    """SHA-256 hex digest of an in-memory payload."""

    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    """Compute the SHA-256 hex digest of a file on disk (streamed)."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(_BUFFER_SIZE):
            digest.update(block)
    return digest.hexdigest()


def sanitize_filename(name: str) -> str:
    """Return a filesystem-safe, human-readable version of ``name``.

    Keeps Arabic letters and digits (so the original name stays legible),
    strips directory components, collapses unsafe characters, and truncates.
    """

    # Drop any directory component -- never trust a client-supplied path.
    base = Path(name.replace("\\", "/")).name

    # Normalise unicode so visually identical names map to one stored file.
    base = unicodedata.normalize("NFC", base)

    base = _UNSAFE_CHARS.sub("_", base)
    base = _WHITESPACE.sub(" ", base).strip(" .")

    if not base:
        base = "unnamed"

    if len(base) > MAX_FILENAME_LEN:
        stem, dot, suffix = base.rpartition(".")
        # Keep the extension when truncating.
        if dot and 0 < len(suffix) <= 10:
            keep = MAX_FILENAME_LEN - len(suffix) - 1
            base = f"{stem[:keep]}.{suffix}"
        else:
            base = base[:MAX_FILENAME_LEN]

    return base


def build_stored_name(file_hash: str, original_name: str) -> str:
    """Deterministic on-disk name: same content => same stored name."""

    return f"{file_hash[:16]}-{sanitize_filename(original_name)}"


async def save_upload(
    upload: UploadFile,
    directory: Path | None = None,
    *,
    buffer_size: int = _BUFFER_SIZE,
) -> StoredFile:
    """Stream ``upload`` to disk, returning its hash and size.

    The payload is written to a hidden temporary sibling first and renamed on
    success, so a crashed upload never leaves a half-written file behind.
    """

    original_name = sanitize_filename(upload.filename or "unnamed")
    digest = hashlib.sha256()
    size = 0
    tmp_path = _temp_path()

    try:
        with tmp_path.open("wb") as out:
            while block := await upload.read(buffer_size):
                digest.update(block)
                size += len(block)
                out.write(block)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise

    return _persist(
        tmp_path,
        directory=directory,
        original_name=original_name,
        file_hash=digest.hexdigest(),
        size=size,
    )


def save_bytes(
    payload: bytes,
    original_name: str,
    *,
    directory: Path | None = None,
) -> StoredFile:
    """Synchronous equivalent of :func:`save_upload` for in-memory payloads."""

    safe_name = sanitize_filename(original_name)
    file_hash = sha256_bytes(payload)

    if not payload:
        raise StorageError("The uploaded file is empty.")

    tmp_path = _temp_path()
    tmp_path.write_bytes(payload)

    return _persist(
        tmp_path,
        directory=directory,
        original_name=safe_name,
        file_hash=file_hash,
        size=len(payload),
    )


def _temp_path() -> Path:
    """A unique hidden scratch file inside the upload directory."""

    settings = get_settings()
    settings.upload_path.mkdir(parents=True, exist_ok=True)
    return settings.upload_path / f".upload-{uuid4().hex}.part"


def _persist(
    tmp_path: Path,
    *,
    directory: Path | None,
    original_name: str,
    file_hash: str,
    size: int,
) -> StoredFile:
    """Validate a temp file and move it to its final, hash-addressed name."""

    if size == 0:
        tmp_path.unlink(missing_ok=True)
        raise StorageError("The uploaded file is empty.")

    target_dir = Path(directory) if directory is not None else get_settings().upload_path
    target_dir.mkdir(parents=True, exist_ok=True)

    stored_name = build_stored_name(file_hash, original_name)
    final_path = target_dir / stored_name

    if final_path.exists():
        # Same bytes are already on disk -- drop the duplicate copy.
        tmp_path.unlink(missing_ok=True)
    else:
        tmp_path.replace(final_path)

    return StoredFile(
        path=final_path,
        file_hash=file_hash,
        size=size,
        stored_name=stored_name,
        original_name=original_name,
        file_type=Path(original_name).suffix.lstrip(".").lower(),
    )
