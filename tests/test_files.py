"""Tests for file validation and upload."""
import pytest

from cag import files as cag_files
from cag.models import UploadedFile


ALLOWED = {"pdf", "txt", "md", "csv"}


def test_validate_accepts_allowed_extension():
    cag_files.validate_filename("notes.pdf", ALLOWED)  # no raise


def test_validate_rejects_disallowed_extension():
    with pytest.raises(cag_files.ValidationError):
        cag_files.validate_filename("malware.exe", ALLOWED)


def test_validate_rejects_empty_name():
    with pytest.raises(cag_files.ValidationError):
        cag_files.validate_filename("", ALLOWED)


def test_validate_is_case_insensitive():
    cag_files.validate_filename("REPORT.PDF", ALLOWED)  # no raise


def test_content_type_known_and_unknown():
    assert cag_files.content_type_for("a.pdf") == "application/pdf"
    assert cag_files.content_type_for("a.unknownext") == "application/octet-stream"


def test_upload_file_returns_uploaded_model(tmp_path, client):
    p = tmp_path / "doc.txt"
    p.write_text("hello")
    result = cag_files.upload_file(client, str(p), "doc.txt")
    assert isinstance(result, UploadedFile)
    assert result.uri.startswith("https://")
    assert result.mime_type == "text/plain"
    assert result.size_bytes == 5
