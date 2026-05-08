# Azure Blob Upload Architecture

이 프로젝트는 사내 사용자가 Python CLI 또는 웹 UI로 파일을 Azure Blob Storage에 업로드하도록 만든 구조입니다.

핵심 목표는 사용자가 Azure Portal을 쓰지 않고 파일을 올리되, 사용자에게 Storage Account Key, Connection String, Client Secret 같은 Azure 비밀 값을 전달하지 않는 것입니다.

## 전체 구조

```text
사용자 PC / 업로드 CLI 또는 Web UI
  |
  | 1. meta 파일 해시, 파일명, 파일 크기, user_id로 업로드 계획 요청
  v
FastAPI SAS 발급 서버
  |
  | 2. 기존 meta blob 내용을 조회해 skip/upload/update 판단
  v
Azure Blob Storage
  |
  | 3. upload/update가 필요하면 두 blob에 대한 짧은 업로드 SAS URL 생성
  v
FastAPI SAS 발급 서버
  |
  | 4. skip/upload/update 결과와 SAS URL 반환
  v
사용자 PC / 업로드 CLI 또는 Web UI
  |
  | 5. upload/update일 때만 SAS URL로 Azure Blob Storage에 직접 PUT 업로드
  v
Azure Blob Storage Container
```

## 구성 요소

### 사용자 업로드 CLI / Web UI

사용자가 직접 실행하는 명령줄 도구 또는 브라우저 화면입니다.

사용자는 다음 정보만 알면 됩니다.

```text
- 업로드할 파일 경로
- SAS 발급 서버 URL
- 선택 사항: user_id
```

사용자 CLI와 Web UI는 Azure 비밀 값을 알 필요가 없습니다.

사용자에게 전달하면 안 되는 값:

```text
- AZURE_CLIENT_SECRET
- Storage Account Key
- Connection String
- .env 파일
```

### FastAPI SAS 발급 서버

서버는 사용자의 업로드 요청을 받아 기존 meta 파일의 바이트 해시와 비교하고, 필요한 경우 Azure Blob Storage에 업로드 가능한 짧은 SAS URL을 발급합니다.

서버만 다음 값을 가지고 있습니다.

```text
AZURE_STORAGE_ACCOUNT_NAME
AZURE_STORAGE_CONTAINER_NAME
AZURE_TENANT_ID
AZURE_CLIENT_ID
AZURE_CLIENT_SECRET
SAS_TTL_MINUTES
MAX_UPLOAD_BYTES
```

서버는 실제 파일 데이터를 받지 않습니다. 파일 데이터는 사용자 PC에서 Azure Blob Storage로 직접 업로드됩니다.