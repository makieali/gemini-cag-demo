"""File validation and upload to the Gemini Files API."""
from __future__ import annotations

import mimetypes
import os
from typing import Iterable

from .models import UploadedFile

# Map extensions to the MIME types Gemini expects.
_MIME_BY_EXT = {
    ".pdf": "application/pdf",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".csv": "text/csv",
    ".json": "application/json",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".ppt": "application/vnd.ms-powerpoint",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}


class ValidationError(ValueError):
    """Raised when an uploaded file fails validation."""


def content_type_for(path: str) -> str:
    """Best-effort MIME type for a local file path."""
    ext = os.path.splitext(path)[1].lower()
    if ext in _MIME_BY_EXT:
        return _MIME_BY_EXT[ext]
    guessed, _ = mimetypes.guess_type(path)
    return guessed or "application/octet-stream"


def validate_filename(filename: str, allowed_extensions: Iterable[str]) -> None:
    """Raise ValidationError if the filename is empty or has a disallowed type."""
    if not filename:
        raise ValidationError("Empty filename")
    ext = os.path.splitext(filename)[1].lower().lstrip(".")
    allowed = {e.lower().lstrip(".") for e in allowed_extensions}
    if ext not in allowed:
        raise ValidationError(
            f"Unsupported file type '.{ext}'. Allowed: {', '.join(sorted(allowed))}"
        )


def upload_file(client, path: str, original_filename: str) -> UploadedFile:
    """Upload a single local file to the Gemini Files API.

    ``client`` is a ``google.genai.Client``. The Files API stores the document
    server-side and returns a handle we can later put into a context cache.
    """
    mime_type = content_type_for(path)
    size_bytes = os.path.getsize(path)
    gemini_file = client.files.upload(
        file=path,
        config={"mime_type": mime_type, "display_name": original_filename},
    )
    return UploadedFile(
        name=gemini_file.name,
        uri=gemini_file.uri,
        mime_type=mime_type,
        original_filename=original_filename,
        size_bytes=size_bytes,
    )
