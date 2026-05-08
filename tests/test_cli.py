from pathlib import Path
from unittest.mock import patch

import respx
from httpx import Response
from typer.testing import CliRunner

from azure_script.cli import app


runner = CliRunner()


@respx.mock
def test_upload_cli_requests_sas_and_puts_metadata_and_data_files(
    tmp_path: Path,
) -> None:
    metadata_file = tmp_path / "report.meta.toml"
    data_file = tmp_path / "report.pdf"
    metadata_file.write_text("title = \"Report\"", encoding="utf-8")
    data_file.write_bytes(b"pdf")

    respx.post("http://server.test/uploads/sas").mock(
        side_effect=[
            Response(
                200,
                json={
                    "blob_name": "uploads/alice/id-report.meta.toml",
                    "upload_url": "https://account.blob.core.windows.net/c/meta?sas",
                    "method": "PUT",
                    "required_headers": {
                        "x-ms-blob-type": "BlockBlob",
                        "Content-Type": "application/toml",
                    },
                    "expires_at": "2026-05-07T00:00:00+00:00",
                },
            ),
            Response(
                200,
                json={
                    "blob_name": "uploads/alice/id-report.pdf",
                    "upload_url": "https://account.blob.core.windows.net/c/data?sas",
                    "method": "PUT",
                    "required_headers": {
                        "x-ms-blob-type": "BlockBlob",
                        "Content-Type": "application/pdf",
                    },
                    "expires_at": "2026-05-07T00:00:00+00:00",
                },
            ),
        ]
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
    assert "uploads/alice/id-report.meta.toml" in result.output
    assert "uploads/alice/id-report.pdf" in result.output


@respx.mock
def test_upload_cli_fails_when_sas_request_fails(tmp_path: Path) -> None:
    metadata_file = tmp_path / "report.meta.toml"
    data_file = tmp_path / "report.pdf"
    metadata_file.write_text("title = \"Report\"", encoding="utf-8")
    data_file.write_bytes(b"pdf")
    respx.post("http://server.test/uploads/sas").mock(return_value=Response(401))

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
    assert "SAS request failed" in result.output


@respx.mock
def test_upload_cli_uses_os_username_by_default(tmp_path: Path) -> None:
    metadata_file = tmp_path / "report.meta.toml"
    data_file = tmp_path / "report.pdf"
    metadata_file.write_text("title = \"Report\"", encoding="utf-8")
    data_file.write_bytes(b"pdf")
    sas_route = respx.post("http://server.test/uploads/sas").mock(
        side_effect=[
            Response(
                200,
                json={
                    "blob_name": "uploads/parksh/id-report.meta.toml",
                    "upload_url": "https://account.blob.core.windows.net/c/meta?sas",
                    "method": "PUT",
                    "required_headers": {
                        "x-ms-blob-type": "BlockBlob",
                        "Content-Type": "application/toml",
                    },
                    "expires_at": "2026-05-07T00:00:00+00:00",
                },
            ),
            Response(
                200,
                json={
                    "blob_name": "uploads/parksh/id-report.pdf",
                    "upload_url": "https://account.blob.core.windows.net/c/data?sas",
                    "method": "PUT",
                    "required_headers": {
                        "x-ms-blob-type": "BlockBlob",
                        "Content-Type": "application/pdf",
                    },
                    "expires_at": "2026-05-07T00:00:00+00:00",
                },
            ),
        ]
    )
    respx.put("https://account.blob.core.windows.net/c/meta?sas").mock(
        return_value=Response(201)
    )
    respx.put("https://account.blob.core.windows.net/c/data?sas").mock(
        return_value=Response(201)
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
    assert sas_route.calls.last.request.content
    assert b'"user_id":"parksh"' in sas_route.calls.last.request.content


def test_upload_cli_rejects_mismatched_metadata_and_data_names(tmp_path: Path) -> None:
    metadata_file = tmp_path / "invoice.meta.toml"
    data_file = tmp_path / "report.pdf"
    metadata_file.write_text("title = \"Invoice\"", encoding="utf-8")
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
