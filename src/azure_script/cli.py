import getpass
import mimetypes
from pathlib import Path

import httpx
import typer


app = typer.Typer(help="Upload files to Azure Blob Storage via a short-lived SAS URL.")


@app.command()
def upload(
    file: Path = typer.Argument(..., exists=True, file_okay=True, dir_okay=False),
    server_url: str = typer.Option(..., help="SAS issuer base URL."),
    user_id: str | None = typer.Option(
        None,
        help="User identifier for the blob path. Defaults to the OS username.",
    ),
) -> None:
    size_bytes = file.stat().st_size
    content_type = mimetypes.guess_type(file.name)[0] or "application/octet-stream"
    base_url = server_url.rstrip("/")
    # user_id를 지정하지 않으면 현재 OS 사용자명을 blob 경로 식별자로 사용한다.
    effective_user_id = user_id or getpass.getuser()

    # 서버에는 파일 자체가 아니라 SAS 발급에 필요한 메타데이터만 보낸다.
    payload = {
        "user_id": effective_user_id,
        "filename": file.name,
        "content_type": content_type,
        "size_bytes": size_bytes,
    }

    with httpx.Client(timeout=None) as client:
        # 1단계: 내부 SAS 발급 서버에 단일 blob 업로드용 SAS URL을 요청한다.
        sas_response = client.post(
            f"{base_url}/uploads/sas",
            json=payload,
        )
        if sas_response.status_code >= 400:
            raise typer.BadParameter(
                f"SAS request failed: {sas_response.status_code} {sas_response.text}"
            )

        sas_payload = sas_response.json()
        headers = sas_payload["required_headers"]
        with file.open("rb") as handle:
            # 2단계: 서버가 발급한 SAS URL로 Azure Blob Storage에 직접 PUT 업로드한다.
            # 이 요청은 FastAPI 서버를 거치지 않으므로 대용량 파일 트래픽이 서버에 실리지 않는다.
            upload_response = client.put(
                sas_payload["upload_url"],
                headers=headers,
                content=handle,
            )

        if upload_response.status_code not in {201, 202}:
            raise typer.BadParameter(
                "Azure upload failed: "
                f"{upload_response.status_code} {upload_response.text}"
            )

    typer.echo(f"Uploaded {file} to {sas_payload['blob_name']}")


@app.command(hidden=True)
def version() -> None:
    typer.echo("azure-script 0.1.0")


if __name__ == "__main__":
    app()
