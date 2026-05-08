from pathlib import Path
from unittest.mock import patch

import respx
from httpx import Response
from typer.testing import CliRunner

from azure_script.cli import app


runner = CliRunner()


def _plan_response(action: str = "upload") -> dict[str, object]:
    uploads: list[dict[str, object]] = []
    if action != "skip":
        uploads = [
            {
                "kind": "metadata",
                "blob_name": "uploads/alice/report/report.meta.toml",
                "upload_url": "https://account.blob.core.windows.net/c/meta?sas",
                "method": "PUT",
                "required_headers": {
                    "x-ms-blob-type": "BlockBlob",
                    "Content-Type": "application/toml",
                },
                "expires_at": "2026-05-07T00:00:00+00:00",
            },
            {
                "kind": "data",
                "blob_name": "uploads/alice/report/report.pdf",
                "upload_url": "https://account.blob.core.windows.net/c/data?sas",
                "method": "PUT",
                "required_headers": {
                    "x-ms-blob-type": "BlockBlob",
                    "Content-Type": "application/pdf",
                },
                "expires_at": "2026-05-07T00:00:00+00:00",
            },
        ]

    return {
        "action": action,
        "metadata_blob_name": "uploads/alice/report/report.meta.toml",
        "data_blob_name": "uploads/alice/report/report.pdf",
        "uploads": uploads,
    }


def _write_pair(tmp_path: Path) -> tuple[Path, Path]:
    metadata_file = tmp_path / "report.meta.toml"
    data_file = tmp_path / "report.pdf"
    metadata_file.write_text('title = "Report"', encoding="utf-8")
    data_file.write_bytes(b"pdf")
    return metadata_file, data_file


@respx.mock
def test_upload_cli_uploads_metadata_and_data_files(tmp_path: Path) -> None:
    metadata_file, data_file = _write_pair(tmp_path)

    respx.post("http://server.test/uploads/plan").mock(
        return_value=Response(200, json=_plan_response("upload"))
    )
    metadata_upload_route = respx.put(
        "https://account.blob.core.windows.net/c/meta?sas"
    ).mock(return_value=Response(201))
    data_upload_route = respx.put("https://account.blob.core.windows.net/c/data?sas").mock(
        return_value=Response(201)
    )

    result = runner.invoke(
        app,
        [
            "upload",
            str(metadata_file),
            str(data_file),
            "--server-url",
            "http://server.test",
            "--user-id",
            "alice",
        ],
    )

    assert result.exit_code == 0, result.output
    assert metadata_upload_route.called
    assert data_upload_route.called
    assert "Uploaded" in result.output
    assert "uploads/alice/report/report.meta.toml" in result.output
    assert "uploads/alice/report/report.pdf" in result.output


@respx.mock
def test_upload_cli_updates_metadata_and_data_files(tmp_path: Path) -> None:
    metadata_file, data_file = _write_pair(tmp_path)

    respx.post("http://server.test/uploads/plan").mock(
        return_value=Response(200, json=_plan_response("update"))
    )
    respx.put("https://account.blob.core.windows.net/c/meta?sas").mock(
        return_value=Response(201)
    )
    respx.put("https://account.blob.core.windows.net/c/data?sas").mock(
        return_value=Response(201)
    )

    result = runner.invoke(
        app,
        [
            "upload",
            str(metadata_file),
            str(data_file),
            "--server-url",
            "http://server.test",
            "--user-id",
            "alice",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Updated" in result.output


@respx.mock
def test_upload_cli_skips_when_metadata_is_unchanged(tmp_path: Path) -> None:
    metadata_file, data_file = _write_pair(tmp_path)
    plan_route = respx.post("http://server.test/uploads/plan").mock(
        return_value=Response(200, json=_plan_response("skip"))
    )

    result = runner.invoke(
        app,
        [
            "upload",
            str(metadata_file),
            str(data_file),
            "--server-url",
            "http://server.test",
            "--user-id",
            "alice",
        ],
    )

    assert result.exit_code == 0, result.output
    assert plan_route.called
    assert "Skipped" in result.output


@respx.mock
def test_upload_cli_fails_when_upload_plan_request_fails(tmp_path: Path) -> None:
    metadata_file, data_file = _write_pair(tmp_path)
    respx.post("http://server.test/uploads/plan").mock(return_value=Response(401))

    result = runner.invoke(
        app,
        [
            "upload",
            str(metadata_file),
            str(data_file),
            "--server-url",
            "http://server.test",
            "--user-id",
            "alice",
        ],
    )

    assert result.exit_code != 0
    assert "Upload plan request failed" in result.output


@respx.mock
def test_upload_cli_uses_os_username_by_default(tmp_path: Path) -> None:
    metadata_file, data_file = _write_pair(tmp_path)
    plan_route = respx.post("http://server.test/uploads/plan").mock(
        return_value=Response(200, json=_plan_response("skip"))
    )

    with patch("azure_script.cli.getpass.getuser", return_value="parksh"):
        result = runner.invoke(
            app,
            [
                "upload",
                str(metadata_file),
                str(data_file),
                "--server-url",
                "http://server.test",
            ],
        )

    assert result.exit_code == 0, result.output
    assert plan_route.calls.last.request.content
    assert b'"user_id":"parksh"' in plan_route.calls.last.request.content


def test_upload_cli_rejects_mismatched_metadata_and_data_names(tmp_path: Path) -> None:
    metadata_file = tmp_path / "invoice.meta.toml"
    data_file = tmp_path / "report.pdf"
    metadata_file.write_text('title = "Invoice"', encoding="utf-8")
    data_file.write_bytes(b"pdf")

    result = runner.invoke(
        app,
        [
            "upload",
            str(metadata_file),
            str(data_file),
            "--server-url",
            "http://server.test",
        ],
    )

    assert result.exit_code != 0
    assert "must share the same <name>" in result.output


def test_upload_cli_rejects_two_data_files(tmp_path: Path) -> None:
    first_file = tmp_path / "report.pdf"
    second_file = tmp_path / "report.docx"
    first_file.write_bytes(b"pdf")
    second_file.write_bytes(b"docx")

    result = runner.invoke(
        app,
        [
            "upload",
            str(first_file),
            str(second_file),
            "--server-url",
            "http://server.test",
        ],
    )

    assert result.exit_code != 0
    assert "Exactly one file must be named <name>.meta.toml" in result.output
