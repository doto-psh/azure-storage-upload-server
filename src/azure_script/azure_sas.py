from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from azure.identity import ClientSecretCredential, DefaultAzureCredential
from azure.storage.blob import (
    BlobSasPermissions,
    BlobServiceClient,
    UserDelegationKey,
    generate_blob_sas,
)

from azure_script.settings import Settings


@dataclass(frozen=True)
class UploadSas:
    blob_name: str
    upload_url: str
    expires_at: datetime


class AzureBlobSasIssuer:
    def __init__(
        self,
        settings: Settings,
        blob_service_client: BlobServiceClient | None = None,
    ) -> None:
        self._settings = settings
        account_url = (
            f"https://{settings.azure_storage_account_name}.blob.core.windows.net"
        )
        credential = self._build_credential(settings)
        # 서버만 가진 Azure 자격 증명으로 BlobServiceClient를 만든다.
        # 사용자가 실행하는 업로드 CLI에는 이 자격 증명이 전달되지 않는다.
        self._client = blob_service_client or BlobServiceClient(
            account_url=account_url,
            credential=credential,
        )

    def _build_credential(
        self,
        settings: Settings,
    ) -> ClientSecretCredential | DefaultAzureCredential:
        if (
            settings.azure_tenant_id
            and settings.azure_client_id
            and settings.azure_client_secret
        ):
            # 로컬/외부 서버 실행에서는 .env의 Service Principal 값을 직접 사용한다.
            return ClientSecretCredential(
                tenant_id=settings.azure_tenant_id,
                client_id=settings.azure_client_id,
                client_secret=settings.azure_client_secret,
            )
        # Azure App Service, Functions, VM 등에 배포하면 Managed Identity나
        # Azure CLI 로그인 같은 DefaultAzureCredential 체인을 사용할 수 있다.
        return DefaultAzureCredential()

    def create_upload_sas(self, blob_name: str) -> UploadSas:
        now = datetime.now(timezone.utc)
        starts_at = now - timedelta(minutes=1)
        expires_at = now + timedelta(minutes=self._settings.sas_ttl_minutes)

        # User Delegation SAS는 먼저 Azure Storage에서 delegation key를 받아야 한다.
        # 이 호출에는 Service Principal의 Storage Blob Delegator 권한이 필요하다.
        delegation_key = self._client.get_user_delegation_key(
            key_start_time=starts_at,
            key_expiry_time=expires_at,
        )

        # delegation key로 특정 blob 하나에만 유효한 SAS token을 만든다.
        token = self._generate_sas(blob_name, delegation_key, starts_at, expires_at)
        account = self._settings.azure_storage_account_name
        container = self._settings.azure_storage_container_name
        
        # CLI는 이 URL에 PUT 요청을 보내 실제 파일을 Azure Blob Storage에 업로드한다.
        upload_url = (
            f"https://{account}.blob.core.windows.net/"
            f"{container}/{blob_name}?{token}"
        )
        return UploadSas(blob_name=blob_name, upload_url=upload_url, expires_at=expires_at)

    def _generate_sas(
        self,
        blob_name: str,
        delegation_key: UserDelegationKey,
        starts_at: datetime,
        expires_at: datetime,
    ) -> str:
        return generate_blob_sas(
            account_name=self._settings.azure_storage_account_name,
            container_name=self._settings.azure_storage_container_name,
            blob_name=blob_name,
            user_delegation_key=delegation_key,
            # create/write만 허용한다. read/list/delete 권한은 주지 않는다.
            permission=BlobSasPermissions(create=True, write=True),
            start=starts_at,
            expiry=expires_at,
            protocol="https",
        )
