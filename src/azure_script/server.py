from functools import lru_cache
from typing import Literal

from azure.core.exceptions import AzureError, HttpResponseError
from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import BaseModel, Field

from azure_script.azure_sas import AzureBlobSasIssuer
from azure_script.blob_names import PairBlobNames, build_pair_blob_names
from azure_script.settings import Settings, get_settings


class UploadPlanRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=120)
    metadata_filename: str = Field(..., min_length=1, max_length=255)
    metadata_content: str
    metadata_content_type: str = Field(
        "application/toml",
        min_length=1,
        max_length=255,
    )
    metadata_size_bytes: int = Field(..., ge=0)
    data_filename: str = Field(..., min_length=1, max_length=255)
    data_content_type: str = Field(
        "application/octet-stream",
        min_length=1,
        max_length=255,
    )
    data_size_bytes: int = Field(..., ge=0)


class UploadTarget(BaseModel):
    kind: Literal["metadata", "data"]
    blob_name: str
    upload_url: str
    method: str = "PUT"
    required_headers: dict[str, str]
    expires_at: str


class UploadPlanResponse(BaseModel):
    action: Literal["skip", "upload", "update"]
    metadata_blob_name: str
    data_blob_name: str
    uploads: list[UploadTarget] = Field(default_factory=list)


app = FastAPI(title="Azure Blob Upload SAS Issuer")


@lru_cache
def get_sas_issuer() -> AzureBlobSasIssuer:
    return AzureBlobSasIssuer(get_settings())


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/uploads/plan", response_model=UploadPlanResponse)
def create_upload_plan(
    request: UploadPlanRequest,
    settings: Settings = Depends(get_settings),
    issuer: AzureBlobSasIssuer = Depends(get_sas_issuer),
) -> UploadPlanResponse:
    _check_file_size(
        "metadata file",
        request.metadata_size_bytes,
        settings.max_upload_bytes,
    )
    _check_file_size("data file", request.data_size_bytes, settings.max_upload_bytes)

    try:
        # user_id와 파일명을 서버에서 안전한 고정 blob 경로로 변환한다.
        # 사용자가 container나 전체 경로를 직접 지정하지 못하게 하기 위한 단계다.
        blob_names = build_pair_blob_names(
            request.user_id,
            request.metadata_filename,
            request.data_filename,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    try:
        existing_metadata = issuer.download_blob_bytes(blob_names.metadata)
        metadata_bytes = request.metadata_content.encode("utf-8")

        if existing_metadata == metadata_bytes:
            # 기존 meta 내용이 완전히 같으면 원본 문서는 비교하지 않고 전체 업로드를 건너뛴다.
            return _build_plan_response("skip", blob_names)

        action: Literal["upload", "update"] = (
            "upload" if existing_metadata is None else "update"
        )

        # upload/update가 필요할 때만 Azure Storage에 직접 업로드 가능한 SAS URL을 발급한다.
        # 서버는 원본 문서 파일 내용을 받지 않고, 업로드 권한 URL만 만들어서 CLI에 돌려준다.
        return _build_plan_response(
            action,
            blob_names,
            uploads=[
                _build_upload_target(
                    kind="metadata",
                    blob_name=blob_names.metadata,
                    content_type=request.metadata_content_type,
                    issuer=issuer,
                ),
                _build_upload_target(
                    kind="data",
                    blob_name=blob_names.data,
                    content_type=request.data_content_type,
                    issuer=issuer,
                ),
            ],
        )
    except HttpResponseError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "message": "Azure Storage rejected the upload planning request",
                "error_code": getattr(exc, "error_code", None),
            },
        ) from exc
    except AzureError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Azure credential or storage request failed: {exc.__class__.__name__}",
        ) from exc


def _check_file_size(label: str, size_bytes: int, max_upload_bytes: int) -> None:
    if size_bytes > max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{label} is larger than max_upload_bytes={max_upload_bytes}",
        )


def _build_upload_target(
    *,
    kind: Literal["metadata", "data"],
    blob_name: str,
    content_type: str,
    issuer: AzureBlobSasIssuer,
) -> UploadTarget:
    upload_sas = issuer.create_upload_sas(blob_name)
    return UploadTarget(
        kind=kind,
        blob_name=upload_sas.blob_name,
        upload_url=upload_sas.upload_url,
        # CLI가 SAS URL로 PUT 업로드할 때 반드시 붙여야 하는 헤더다.
        required_headers={
            "x-ms-blob-type": "BlockBlob",
            "Content-Type": content_type,
        },
        expires_at=upload_sas.expires_at.isoformat(),
    )


def _build_plan_response(
    action: Literal["skip", "upload", "update"],
    blob_names: PairBlobNames,
    uploads: list[UploadTarget] | None = None,
) -> UploadPlanResponse:
    return UploadPlanResponse(
        action=action,
        metadata_blob_name=blob_names.metadata,
        data_blob_name=blob_names.data,
        uploads=uploads or [],
    )
