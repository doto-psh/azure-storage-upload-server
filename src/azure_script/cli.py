import getpass
import mimetypes
import uuid
from pathlib import Path

import httpx
import typer


app = typer.Typer(help="Upload files to Azure Blob Storage via a short-lived SAS URL.")


def _metadata_base_name(path: Path) -> str | None:
    if path.name.endswith(".meta.toml"):
        return path.name.removesuffix(".meta.toml")
    return None


def _split_upload_pair(first_file: Path, second_file: Path) -> tuple[Path, Path]:
    first_meta_base = _metadata_base_name(first_file)
    second_meta_base = _metadata_base_name(second_file)

    if bool(first_meta_base) == bool(second_meta_base):
        raise typer.BadParameter(
            "Exactly one file must be named <name>.meta.toml, and the other must be <name>.<extension>."
        )

    metadata_file = first_file if first_meta_base else second_file
    data_file = second_file if first_meta_base else first_file
    metadata_base = first_meta_base or second_meta_base

    if not data_file.suffix:
        raise typer.BadParameter("Data file must have an extension, such as .pdf or .docx.")

    if data_file.name.endswith(".meta.toml"):
        raise typer.BadParameter("Data file must not be a .meta.toml file.")

    if metadata_base != data_file.stem:
        raise typer.BadParameter(
            "Metadata and data filenames must share the same <name>: "
            f"expected {data_file.stem}.meta.toml, got {metadata_file.name}."
        )

    return metadata_file, data_file


def _build_sas_payload(file: Path, user_id: str, upload_id: str) -> dict[str, object]:
    content_type = mimetypes.guess_type(file.name)[0] or "application/octet-stream"
    # 서버에는 파일 자체가 아니라 SAS 발급에 필요한 메타데이터만 보낸다.
    return {
        "user_id": user_id,
        "filename": file.name,
        "content_type": content_type,
        "size_bytes": file.stat().st_size,
        "upload_id": upload_id,
    }


def _request_sas_and_upload(
    client: httpx.Client,
    base_url: str,
    file: Path,
    payload: dict[str, object],
) -> str:
    # 1단계: 내부 SAS 발급 서버에 단일 blob 업로드용 SAS URL을 요청한다.
    sas_response = client.post(
        f"{base_url}/uploads/sas",
        json=payload,
    )
    if sas_response.status_code >= 400:
        raise typer.BadParameter(
            f"SAS request failed for {file.name}: {sas_response.status_code} {sas_response.text}"
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
            "Azure upload failed for "
            f"{file.name}: {upload_response.status_code} {upload_response.text}"
        )

    return str(sas_payload["blob_name"])


@app.command()
def upload(
    first_file: Path = typer.Argument(..., exists=True, file_okay=True, dir_okay=False),
    second_file: Path = typer.Argument(..., exists=True, file_okay=True, dir_okay=False),
    server_url: str = typer.Option(..., help="SAS issuer base URL."),
    user_id: str | None = typer.Option(
        None,
        help="User identifier for the blob path. Defaults to the OS username.",
    ),
) -> None:
    metadata_file, data_file = _split_upload_pair(first_file, second_file)
    base_url = server_url.rstrip("/")
    # user_id를 지정하지 않으면 현재 OS 사용자명을 blob 경로 식별자로 사용한다.
    effective_user_id = user_id or getpass.getuser()
    # 한 번의 실행에서 올라가는 meta/data 파일이 blob 경로에서도 같은 묶음으로 보이게 한다.
    upload_id = uuid.uuid4().hex

    with httpx.Client(timeout=None) as client:
        metadata_blob_name = _request_sas_and_upload(
            client,
            base_url,
            metadata_file,
            _build_sas_payload(metadata_file, effective_user_id, upload_id),
        )
        data_blob_name = _request_sas_and_upload(
            client,
            base_url,
            data_file,
            _build_sas_payload(data_file, effective_user_id, upload_id),
        )

    typer.echo(f"Uploaded {metadata_file} to {metadata_blob_name}")
    typer.echo(f"Uploaded {data_file} to {data_blob_name}")


@app.command(hidden=True)
def version() -> None:
    typer.echo("azure-script 0.1.0")


if __name__ == "__main__":
    app()
