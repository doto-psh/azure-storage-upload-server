import pytest

from azure_script.blob_names import (
    build_pair_blob_names,
    sanitize_filename,
    sanitize_user_id,
    validate_upload_pair_names,
)


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


def test_build_pair_blob_names_scopes_to_user_and_stable_name() -> None:
    blob_names = build_pair_blob_names(
        "../alice",
        "report.meta.toml",
        "report.pdf",
    )

    assert blob_names.metadata == "uploads/alice/report/report.meta.toml"
    assert blob_names.data == "uploads/alice/report/report.pdf"


def test_build_pair_blob_names_preserves_korean_filename() -> None:
    blob_names = build_pair_blob_names(
        "alice",
        "신청방법.meta.toml",
        "신청방법.pdf",
    )

    assert blob_names.metadata == "uploads/alice/신청방법/신청방법.meta.toml"
    assert blob_names.data == "uploads/alice/신청방법/신청방법.pdf"


def test_validate_upload_pair_names_rejects_mismatched_names() -> None:
    with pytest.raises(ValueError):
        validate_upload_pair_names("invoice.meta.toml", "report.pdf")


def test_validate_upload_pair_names_rejects_missing_data_extension() -> None:
    with pytest.raises(ValueError):
        validate_upload_pair_names("report.meta.toml", "report")
