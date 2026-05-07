from pathlib import Path
from unittest.mock import patch

import respx
from httpx import Response
from typer.testing import CliRunner

from azure_script.cli import app


runner = CliRunner()


@respx.mock
def test_upload_cli_requests_sas_and_puts_file(tmp_path: Path) -> None:
    file = tmp_path / "hello.txt"
    file.write_text("hello", encoding="utf-8")

    respx.post("http://server.test/uploads/sas").mock(
        return_value=Response(
            200,
            json={
                "blob_name": "uploads/alice/hello.txt",
                "upload_url": "https://account.blob.core.windows.net/c/blob?sas",
                "method": "PUT",
                "required_headers": {
                    "x-ms-blob-type": "BlockBlob",
                    "Content-Type": "text/plain",
                },
                "expires_at": "2026-05-07T00:00:00+00:00",
            },
        )
    )
    upload_route = respx.put("https://account.blob.core.windows.net/c/blob?sas").mock(
        return_value=Response(201)
    )

    result = runner.invoke(
        app,
        [
            "upload",
            str(file),
            "--server-url",
            "http://server.test",
            "--user-id",
            "alice",
        ],
    )

    assert result.exit_code == 0, result.output
    assert upload_route.called
    assert "uploads/alice/hello.txt" in result.output


@respx.mock
def test_upload_cli_fails_when_sas_request_fails(tmp_path: Path) -> None:
    file = tmp_path / "hello.txt"
    file.write_text("hello", encoding="utf-8")
    respx.post("http://server.test/uploads/sas").mock(return_value=Response(401))

    result = runner.invoke(
        app,
        [
            "upload",
            str(file),
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
    file = tmp_path / "hello.txt"
    file.write_text("hello", encoding="utf-8")
    sas_route = respx.post("http://server.test/uploads/sas").mock(
        return_value=Response(
            200,
            json={
                "blob_name": "uploads/parksh/hello.txt",
                "upload_url": "https://account.blob.core.windows.net/c/blob?sas",
                "method": "PUT",
                "required_headers": {
                    "x-ms-blob-type": "BlockBlob",
                    "Content-Type": "text/plain",
                },
                "expires_at": "2026-05-07T00:00:00+00:00",
            },
        )
    )
    respx.put("https://account.blob.core.windows.net/c/blob?sas").mock(
        return_value=Response(201)
    )

    with patch("azure_script.cli.getpass.getuser", return_value="parksh"):
        result = runner.invoke(
            app,
            [
                "upload",
                str(file),
                "--server-url",
                "http://server.test",
            ],
        )

    assert result.exit_code == 0, result.output
    assert sas_route.calls.last.request.content
    assert b'"user_id":"parksh"' in sas_route.calls.last.request.content
