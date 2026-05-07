from datetime import datetime, timezone

from azure.core.exceptions import HttpResponseError
from fastapi.testclient import TestClient

from azure_script.azure_sas import UploadSas
from azure_script.server import app, get_sas_issuer, get_settings


class FakeIssuer:
    def create_upload_sas(self, blob_name: str) -> UploadSas:
        return UploadSas(
            blob_name=blob_name,
            upload_url=f"https://example.blob.core.windows.net/uploads/{blob_name}?sas",
            expires_at=datetime(2026, 5, 7, tzinfo=timezone.utc),
        )


class FakeSettings:
    max_upload_bytes = 100


class FailingIssuer:
    def create_upload_sas(self, blob_name: str) -> UploadSas:
        raise HttpResponseError(message="not authorized")


def setup_function() -> None:
    app.dependency_overrides[get_sas_issuer] = lambda: FakeIssuer()
    app.dependency_overrides[get_settings] = lambda: FakeSettings()


def teardown_function() -> None:
    app.dependency_overrides.clear()


def test_create_upload_sas() -> None:
    client = TestClient(app)

    response = client.post(
        "/uploads/sas",
        json={
            "user_id": "alice",
            "filename": "report.pdf",
            "content_type": "application/pdf",
            "size_bytes": 10,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["method"] == "PUT"
    assert body["blob_name"].startswith("uploads/alice/")
    assert body["required_headers"] == {
        "x-ms-blob-type": "BlockBlob",
        "Content-Type": "application/pdf",
    }


def test_create_upload_sas_rejects_invalid_user_id() -> None:
    client = TestClient(app)

    response = client.post(
        "/uploads/sas",
        json={"user_id": "...", "filename": "report.pdf", "size_bytes": 10},
    )

    assert response.status_code == 400


def test_create_upload_sas_rejects_oversized_file() -> None:
    client = TestClient(app)

    response = client.post(
        "/uploads/sas",
        json={"user_id": "alice", "filename": "report.pdf", "size_bytes": 101},
    )

    assert response.status_code == 400


def test_create_upload_sas_reports_azure_permission_errors() -> None:
    app.dependency_overrides[get_sas_issuer] = lambda: FailingIssuer()
    client = TestClient(app)

    response = client.post(
        "/uploads/sas",
        json={"user_id": "alice", "filename": "report.pdf", "size_bytes": 10},
    )

    assert response.status_code == 502
    assert response.json()["detail"]["message"] == "Azure Storage rejected the SAS request"
