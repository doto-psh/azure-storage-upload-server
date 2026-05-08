from datetime import datetime, timezone

import pytest

from azure_script.blob_names import build_blob_name, sanitize_filename, sanitize_user_id


def test_sanitize_filename_uses_basename_and_safe_chars() -> None:
    assert sanitize_filename("../my report.pdf") == "my_report.pdf"


def test_sanitize_filename_rejects_empty_names() -> None:
    with pytest.raises(ValueError):
        sanitize_filename("...")


def test_sanitize_user_id_uses_safe_chars() -> None:
    assert sanitize_user_id("../Park Sh") == "Park_Sh"


def test_sanitize_user_id_rejects_empty_names() -> None:
    with pytest.raises(ValueError):
        sanitize_user_id("...")


def test_build_blob_name_scopes_to_user_and_date() -> None:
    now = datetime(2026, 5, 7, tzinfo=timezone.utc)
    blob_name = build_blob_name(
        "../alice",
        "report.pdf",
        now=now,
        upload_id="upload123",
    )

    assert blob_name.startswith("uploads/alice/2026/05/07/")
    assert blob_name.endswith("upload123-report.pdf")


def test_build_blob_name_rejects_unsafe_upload_id() -> None:
    now = datetime(2026, 5, 7, tzinfo=timezone.utc)

    with pytest.raises(ValueError):
        build_blob_name("alice", "report.pdf", now=now, upload_id="../bad")
