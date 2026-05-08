from functools import lru_cache

from azure.core.exceptions import AzureError, HttpResponseError
from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import BaseModel, Field

from azure_script.azure_sas import AzureBlobSasIssuer
from azure_script.blob_names import build_blob_name
from azure_script.settings import Settings, get_settings


class UploadSasRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=120)
    filename: str = Field(..., min_length=1, max_length=255)
    content_type: str = Field("application/octet-stream", min_length=1, max_length=255)
    size_bytes: int = Field(..., ge=0)
    upload_id: str | None = Field(None, min_length=8, max_length=64)


class UploadSasResponse(BaseModel):
    blob_name: str
    upload_url: str
    method: str = "PUT"
    required_headers: dict[str, str]
    expires_at: str


app = FastAPI(title="Azure Blob Upload SAS Issuer")


@lru_cache
def get_sas_issuer() -> AzureBlobSasIssuer:
    return AzureBlobSasIssuer(get_settings())


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/uploads/sas", response_model=UploadSasResponse)
def create_upload_sas(
    request: UploadSasRequest,
    settings: Settings = Depends(get_settings),
    issuer: AzureBlobSasIssuer = Depends(get_sas_issuer),
) -> UploadSasResponse:
    if request.size_bytes > settings.max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File is larger than max_upload_bytes={settings.max_upload_bytes}",
        )

    try:
        # user_id와 파일명을 서버에서 안전한 blob 경로로 변환한다.
        # 사용자가 container나 전체 경로를 직접 지정하지 못하게 하기 위한 단계다.
        blob_name = build_blob_name(
            request.user_id,
            request.filename,
            upload_id=request.upload_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    try:
        # Azure Storage에 직접 업로드 가능한 짧은 SAS URL을 발급한다.
        # 서버는 파일 내용을 받지 않고, 업로드 권한 URL만 만들어서 CLI에 돌려준다.
        upload_sas = issuer.create_upload_sas(blob_name)
    except HttpResponseError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "message": "Azure Storage rejected the SAS request",
                "error_code": getattr(exc, "error_code", None),
            },
        ) from exc
    except AzureError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Azure credential or storage request failed: {exc.__class__.__name__}",
        ) from exc

    return UploadSasResponse(
        blob_name=upload_sas.blob_name,
        upload_url=upload_sas.upload_url,
        # CLI가 SAS URL로 PUT 업로드할 때 반드시 붙여야 하는 헤더다.
        required_headers={
            "x-ms-blob-type": "BlockBlob",
            "Content-Type": request.content_type,
        },
        expires_at=upload_sas.expires_at.isoformat(),
    )
