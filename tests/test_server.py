import hashlib
from datetime import datetime, timezone

from azure.core.exceptions import HttpResponseError
from fastapi.testclient import TestClient

from azure_script.azure_sas import UploadSas
from azure_script.server import app, get_sas_issuer, get_settings


class FakeIssuer:
    def __init__(self, existing_metadata: bytes | None = None) -> None:
        self.existing_metadata = existing_metadata

    def download_blob_bytes(self, blob_name: str) -> bytes | None:
        return self.existing_metadata

    def create_upload_sas(self, blob_name: str) -> UploadSas:
        return UploadSas(
            blob_name=blob_name,
            upload_url=f"https://example.blob.core.windows.net/uploads/{blob_name}?sas",
            expires_at=datetime(2026, 5, 7, tzinfo=timezone.utc),
        )


class FakeSettings:
    max_upload_bytes = 100


class FailingIssuer:
    def download_blob_bytes(self, blob_name: str) -> bytes | None:
        raise HttpResponseError(message="not authorized")

    def create_upload_sas(self, blob_name: str) -> UploadSas:
        raise HttpResponseError(message="not authorized")


def _request_payload(metadata_bytes: bytes = b'title = "Report"') -> dict[str, object]:
    return {
        "user_id": "alice",
        "metadata_filename": "report.meta.toml",
        "metadata_sha256": hashlib.sha256(metadata_bytes).hexdigest(),
        "metadata_content_type": "application/toml",
        "metadata_size_bytes": len(metadata_bytes),
        "data_filename": "report.pdf",
        "data_content_type": "application/pdf",
        "data_size_bytes": 10,
    }


def setup_function() -> None:
    app.dependency_overrides[get_sas_issuer] = lambda: FakeIssuer()
    app.dependency_overrides[get_settings] = lambda: FakeSettings()


def teardown_function() -> None:
    app.dependency_overrides.clear()


def test_upload_ui_is_served() -> None:
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert "메타데이터 파일 업로드" in response.text
    assert "파일명 확인" in response.text
    assert "보고서.meta.toml" in response.text
    assert "Blob Storage 내 저장 경로" in response.text
    assert "/static/app.js" in response.text


def test_upload_ui_static_assets_are_served() -> None:
    client = TestClient(app)

    response = client.get("/static/app.js")

    assert response.status_code == 200
    assert "requestUploadPlan" in response.text


def test_create_upload_plan_uploads_when_metadata_is_missing() -> None:
    client = TestClient(app)

    response = client.post("/uploads/plan", json=_request_payload())

    assert response.status_code == 200
    body = response.json()
    assert body["action"] == "upload"
    assert body["metadata_blob_name"] == "uploads/alice/report/report.meta.toml"
    assert body["data_blob_name"] == "uploads/alice/report/report.pdf"
    assert [upload["kind"] for upload in body["uploads"]] == ["metadata", "data"]
    assert body["uploads"][0]["required_headers"] == {
        "x-ms-blob-type": "BlockBlob",
        "Content-Type": "application/toml",
    }
    assert body["uploads"][1]["required_headers"] == {
        "x-ms-blob-type": "BlockBlob",
        "Content-Type": "application/pdf",
    }


def test_create_upload_plan_skips_when_metadata_is_unchanged() -> None:
    metadata_bytes = b'title = "Report"'
    app.dependency_overrides[get_sas_issuer] = lambda: FakeIssuer(
        existing_metadata=metadata_bytes
    )
    client = TestClient(app)

    response = client.post("/uploads/plan", json=_request_payload(metadata_bytes))

    assert response.status_code == 200
    body = response.json()
    assert body["action"] == "skip"
    assert body["uploads"] == []


def test_create_upload_plan_skips_when_crlf_metadata_bytes_match() -> None:
    metadata_bytes = b'title = "Report"\r\n'
    app.dependency_overrides[get_sas_issuer] = lambda: FakeIssuer(
        existing_metadata=metadata_bytes
    )
    client = TestClient(app)

    response = client.post("/uploads/plan", json=_request_payload(metadata_bytes))

    assert response.status_code == 200
    assert response.json()["action"] == "skip"


def test_create_upload_plan_updates_when_metadata_changed() -> None:
    app.dependency_overrides[get_sas_issuer] = lambda: FakeIssuer(
        existing_metadata=b'title = "Old"'
    )
    client = TestClient(app)

    response = client.post("/uploads/plan", json=_request_payload(b'title = "New"'))

    assert response.status_code == 200
    body = response.json()
    assert body["action"] == "update"
    assert [upload["kind"] for upload in body["uploads"]] == ["metadata", "data"]


def test_create_upload_plan_rejects_invalid_pair() -> None:
    client = TestClient(app)
    payload = _request_payload()
    payload["metadata_filename"] = "invoice.meta.toml"

    response = client.post("/uploads/plan", json=payload)

    assert response.status_code == 400


def test_create_upload_plan_rejects_oversized_file() -> None:
    client = TestClient(app)
    payload = _request_payload()
    payload["data_size_bytes"] = 101

    response = client.post("/uploads/plan", json=payload)

    assert response.status_code == 400


def test_create_upload_plan_reports_azure_permission_errors() -> None:
    app.dependency_overrides[get_sas_issuer] = lambda: FailingIssuer()
    client = TestClient(app)

    response = client.post("/uploads/plan", json=_request_payload())

    assert response.status_code == 502
    assert (
        response.json()["detail"]["message"]
        == "Azure Storage rejected the upload planning request"
    )
