# Azure Blob Upload Architecture

이 프로젝트는 사내 사용자가 Python CLI 스크립트로 파일을 Azure Blob Storage에 업로드하도록 만든 구조입니다.

핵심 목표는 사용자가 Azure Portal을 쓰지 않고 파일을 올리되, 사용자에게 Storage Account Key, Connection String, Client Secret 같은 Azure 비밀 값을 전달하지 않는 것입니다.

## 전체 구조

```text
사용자 PC / 업로드 CLI
  |
  | 1. 파일명, 파일 크기, user_id로 SAS 발급 요청
  v
FastAPI SAS 발급 서버
  |
  | 2. App Registration / Service Principal로 Azure 인증
  v
Azure Blob Storage
  |
  | 3. 특정 blob 하나에 대한 짧은 업로드 SAS URL 생성
  v
FastAPI SAS 발급 서버
  |
  | 4. SAS URL 반환
  v
사용자 PC / 업로드 CLI
  |
  | 5. SAS URL로 Azure Blob Storage에 직접 PUT 업로드
  v
Azure Blob Storage Container
```

## 구성 요소

### 사용자 업로드 CLI

사용자가 직접 실행하는 명령줄 도구입니다.

사용자는 다음 정보만 알면 됩니다.

```text
- 업로드할 파일 경로
- SAS 발급 서버 URL
- 선택 사항: user_id
```

사용자 CLI는 Azure 비밀 값을 알 필요가 없습니다.

사용자에게 전달하면 안 되는 값:

```text
- AZURE_CLIENT_SECRET
- Storage Account Key
- Connection String
- .env 파일
```

### FastAPI SAS 발급 서버

서버는 사용자의 업로드 요청을 받아 Azure Blob Storage에 업로드 가능한 짧은 SAS URL을 발급합니다.

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

### Azure App Registration / Service Principal

SAS 발급 서버가 Azure에 본인 신원을 증명하기 위해 사용합니다.

Azure는 아무 서버에게나 SAS URL 생성 권한을 주지 않습니다. 따라서 SAS 발급 서버는 App Registration / Service Principal을 통해 Azure에 인증합니다.
```

## 업로드 동작

사용자가 CLI를 실행합니다.

```bash
uv run azure-upload upload ./report.meta.toml ./report.pdf \
  --server-url http://127.0.0.1:9990
```

CLI는 각 파일마다 다음 정보를 서버에 보냅니다.

```json
{
  "user_id": "parksh",
  "filename": "report.pdf",
  "content_type": "application/pdf",
  "size_bytes": 123456,
  "upload_id": "0f3a..."
}
```

`user_id`를 직접 지정하지 않으면 CLI는 OS 사용자명을 사용합니다.

서버는 blob 경로를 자동 생성합니다.

```text
uploads/{user_id}/{yyyy}/{mm}/{dd}/{upload_id}-{filename}
```

예:

```text
uploads/parksh/2026/05/07/0f3a...-report.meta.toml
uploads/parksh/2026/05/07/0f3a...-report.pdf
```

서버는 Azure에 User Delegation SAS를 요청하고, 특정 blob 하나에 대해서만 유효한 업로드 URL을 반환합니다.

SAS URL의 특징:

```text
- 특정 blob 하나에만 유효
- 짧은 시간 동안만 유효
- create/write 업로드만 허용
- read/list/delete 권한 없음
```

CLI는 서버가 반환한 SAS URL로 Azure Blob Storage에 직접 업로드합니다.

## 서버 실행 방법

서버 운영자는 먼저 `.env`를 설정합니다.

```bash
cp .env.example .env
```

`.env` 예:

```env
AZURE_STORAGE_ACCOUNT_NAME=your-storage-account
AZURE_STORAGE_CONTAINER_NAME=your-container
AZURE_TENANT_ID=your-tenant-id
AZURE_CLIENT_ID=your-client-id
AZURE_CLIENT_SECRET=your-client-secret-value
SAS_TTL_MINUTES=15
MAX_UPLOAD_BYTES=5368709120
```

의존성을 설치합니다.

```bash
uv sync
```

서버를 실행합니다.

```bash
uv run uvicorn azure_script.server:app --reload --port 9990
```

정상 동작 확인:

```bash
curl http://127.0.0.1:9990/healthz
```

응답:

```json
{"status":"ok"}
```

## 사용자가 스크립트로 업로드하는 방법

사용자는 프로젝트 또는 배포된 CLI를 받은 뒤 다음 명령으로 업로드합니다.
업로드는 항상 2개 파일을 한 묶음으로 처리합니다.

필수 파일 이름 규칙:

```text
<name>.meta.toml
<name>.<파일형식>
```

예를 들어 `report.meta.toml`과 `report.pdf`는 업로드 가능하지만,
`report.meta.toml`과 `invoice.pdf`는 `<name>`이 다르므로 업로드가 차단됩니다.

```bash
uv run azure-upload upload /path/to/report.meta.toml /path/to/report.pdf \
  --server-url http://127.0.0.1:9990
```

예:

```bash
uv run azure-upload upload \
  /Users/parksh/parksh/azure-script/files/DBSafer_접속_및_결재시스템_신청방법.meta.toml \
  /Users/parksh/parksh/azure-script/files/DBSafer_접속_및_결재시스템_신청방법.pdf \
  --server-url http://127.0.0.1:9990
```

사용자 ID를 명시하고 싶으면 `--user-id`를 추가합니다.

```bash
uv run azure-upload upload /path/to/report.meta.toml /path/to/report.pdf \
  --server-url http://127.0.0.1:9990 \
  --user-id alice
```

이 경우 blob 경로는 다음처럼 생성됩니다.

```text
uploads/alice/2026/05/07/{upload_id}-report.meta.toml
uploads/alice/2026/05/07/{upload_id}-report.pdf
```

`--user-id`를 생략하면 OS 사용자명이 자동으로 사용됩니다. 같은 명령으로 업로드되는
2개 파일은 동일한 `{upload_id}`를 공유하므로 Blob Storage 안에서도 한 묶음으로
식별할 수 있습니다.

## 에러 처리

### Address already in use

서버 실행 시 다음 에러가 나면 해당 포트가 이미 사용 중입니다.

```text
Address already in use
```

다른 포트로 실행합니다.

```bash
uv run uvicorn azure_script.server:app --reload --port 9991
```

업로드할 때도 같은 포트를 사용해야 합니다.

```bash
uv run azure-upload upload ./file.meta.toml ./file.pdf \
  --server-url http://127.0.0.1:9991
```

### AuthorizationPermissionMismatch

업로드 시 다음 에러가 나면 Service Principal에 Azure Storage 권한이 부족한 상태입니다.

```text
AuthorizationPermissionMismatch
```

관리자에게 아래 역할 부여를 요청해야 합니다.

```text
Storage Blob Delegator
Storage Blob Data Contributor
```

대상은 SAS 발급 서버가 사용하는 App Registration / Service Principal입니다.

## 보안 정리

이 구조에서 Azure secret은 서버에만 있습니다.

사용자에게 전달되는 것은 다음뿐입니다.

```text
- 업로드 CLI
- SAS 발급 서버 URL
- 선택 사항: user_id
```

사용자는 Azure 권한을 직접 갖지 않습니다. 사용자는 서버가 발급한 짧은 SAS URL로만 업로드합니다.

따라서 Storage Account Key나 Client Secret을 사용자 스크립트에 넣는 방식보다 안전합니다.
