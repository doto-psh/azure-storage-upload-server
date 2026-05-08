import getpass
import mimetypes
from pathlib import Path

import httpx
import typer

from azure_script.blob_names import metadata_base_name


app = typer.Typer(help="Upload files to Azure Blob Storage via a short-lived SAS URL.")


def _metadata_base_name(path: Path) -> str | None:
    return metadata_base_name(path.name)


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


def _guess_content_type(file: Path) -> str:
    return mimetypes.guess_type(file.name)[0] or "application/octet-stream"


def _build_upload_plan_payload(
    metadata_file: Path,
    data_file: Path,
    user_id: str,
) -> dict[str, object]:
    # 서버는 meta 파일 내용만 받아 기존 meta blob과 비교한다.
    # 원본 문서 내용은 서버로 보내지 않고, 필요할 때만 SAS URL로 Azure에 직접 업로드한다.
    return {
        "user_id": user_id,
        "metadata_filename": metadata_file.name,
        "metadata_content": metadata_file.read_text(encoding="utf-8"),
        "metadata_content_type": _guess_content_type(metadata_file),
        "metadata_size_bytes": metadata_file.stat().st_size,
        "data_filename": data_file.name,
        "data_content_type": _guess_content_type(data_file),
        "data_size_bytes": data_file.stat().st_size,
    }


def _request_upload_plan(
    client: httpx.Client,
    base_url: str,
    payload: dict[str, object],
) -> dict[str, object]:
    # 1단계: 내부 서버에 skip/upload/update 판단과 필요한 SAS URL 생성을 요청한다.
    plan_response = client.post(
        f"{base_url}/uploads/plan",
        json=payload,
    )
    if plan_response.status_code >= 400:
        raise typer.BadParameter(
            "Upload plan request failed: "
            f"{plan_response.status_code} {plan_response.text}"
        )

    return dict(plan_response.json())


def _upload_with_sas(
    client: httpx.Client,
    file: Path,
    upload_target: dict[str, object],
) -> str:
    headers = upload_target["required_headers"]
    with file.open("rb") as handle:
        # 2단계: 서버가 발급한 SAS URL로 Azure Blob Storage에 직접 PUT 업로드한다.
        # 이 요청은 FastAPI 서버를 거치지 않으므로 대용량 파일 트래픽이 서버에 실리지 않는다.
        upload_response = client.put(
            str(upload_target["upload_url"]),
            headers=headers,
            content=handle,
        )

    if upload_response.status_code not in {201, 202}:
        raise typer.BadParameter(
            "Azure upload failed for "
            f"{file.name}: {upload_response.status_code} {upload_response.text}"
        )

    return str(upload_target["blob_name"])


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

    with httpx.Client(timeout=None) as client:
        plan = _request_upload_plan(
            client,
            base_url,
            _build_upload_plan_payload(metadata_file, data_file, effective_user_id),
        )
        action = str(plan["action"])

        if action == "skip":
            typer.echo(
                "Skipped "
                f"{metadata_file} and {data_file}; metadata is unchanged at "
                f"{plan['metadata_blob_name']}"
            )
            return

        files_by_kind = {
            "metadata": metadata_file,
            "data": data_file,
        }
        uploaded_blob_names: list[tuple[Path, str]] = []
        for upload_target in plan["uploads"]:
            kind = str(upload_target["kind"])
            upload_file = files_by_kind[kind]
            blob_name = _upload_with_sas(client, upload_file, upload_target)
            uploaded_blob_names.append((upload_file, blob_name))

    verb = "Updated" if action == "update" else "Uploaded"
    for uploaded_file, blob_name in uploaded_blob_names:
        typer.echo(f"{verb} {uploaded_file} to {blob_name}")


@app.command(hidden=True)
def version() -> None:
    typer.echo("azure-script 0.1.0")


if __name__ == "__main__":
    app()
