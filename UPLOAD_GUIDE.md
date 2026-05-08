# Web UI 파일 업로드 가이드

이 문서는 사용자가 이 저장소를 clone한 뒤 Web UI를 실행하고, 브라우저에서 Azure Blob Storage로 파일을 업로드하는 방법을 설명합니다.

업로드는 항상 아래 2개 파일을 한 묶음으로 처리합니다.

```text
<name>.meta.toml
<name>.<파일형식>
```

예:

```text
보고서.meta.toml
보고서.pdf
```

두 파일의 `<name>`이 다르면 업로드할 수 없습니다.

## 1. 사전 준비

필요한 것:

```text
- Git
- uv
- 저장소 접근 권한
- UI 서버 실행에 필요한 .env 설정값
```

주의:

```text
.env 파일에는 Azure Client Secret이 들어갑니다.
이 파일은 Git에 올리거나 다른 사람에게 임의로 공유하면 안 됩니다.
```

일반 업로드 사용자에게 Azure secret을 배포하지 않는 운영 방식이 더 안전합니다. 사내 공용 UI 서버가 이미 떠 있다면 사용자는 clone이나 uv 설치 없이 서버 URL에 접속해서 업로드하면 됩니다.

이 문서는 사용자가 직접 로컬 또는 사내 PC에서 UI 서버를 실행해야 하는 경우를 기준으로 합니다.

## 2. uv 설치

uv가 설치되어 있는지 확인합니다.

```bash
uv --version
```

명령어가 없다고 나오면 설치합니다.

macOS / Linux:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Windows PowerShell:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

설치 후 터미널을 새로 열고 다시 확인합니다.

```bash
uv --version
```

공식 설치 문서:

```text
https://docs.astral.sh/uv/getting-started/installation/
```

## 3. 저장소 clone

저장소를 clone합니다.

```bash
git clone <repository-url>
cd azure-script
```

예:

```bash
git clone https://github.com/<org>/<repo>.git
cd azure-script
```

## 4. 의존성 설치

프로젝트 의존성을 설치합니다.

```bash
uv sync
```

`.python-version`에 지정된 Python 3.11 환경을 uv가 준비합니다.

## 5. 환경 변수 설정

`.env.example`을 복사해서 `.env`를 만듭니다.

```bash
cp .env.example .env
```

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

`.env` 파일에 Azure Storage와 App Registration 값을 입력합니다.

```env
AZURE_STORAGE_ACCOUNT_NAME=your-storage-account
AZURE_STORAGE_CONTAINER_NAME=your-container
AZURE_TENANT_ID=your-tenant-id
AZURE_CLIENT_ID=your-client-id
AZURE_CLIENT_SECRET=your-client-secret
SAS_TTL_MINUTES=15
MAX_UPLOAD_BYTES=5368709120
```


## 6. Web UI 서버 실행

로컬에서 실행합니다.

```bash
uv run uvicorn azure_script.server:app --reload --port 9990
```

정상 실행되면 다음과 비슷한 로그가 표시됩니다.

```text
Uvicorn running on http://127.0.0.1:9990
```

브라우저에서 접속합니다.

```text
http://127.0.0.1:9990/
```

사내 다른 사용자가 접근해야 하는 서버로 실행할 경우:

```bash
uv run uvicorn azure_script.server:app --host 0.0.0.0 --port 9990
```

이 경우 사용자는 `127.0.0.1`이 아니라 서버의 사내 주소로 접속해야 합니다.

```text
http://<server-host>:9990/
```

## 7. Azure Storage CORS 및 권한 설정

> 중요: 이 섹션은 **관리자가 지정한 Storage Account와 Storage Container를 사용하지 않을 때만** 확인합니다.
>
> 관리자가 이미 제공한 Storage Account / Container / App Registration 값을 그대로 사용한다면, 일반 사용자가 이 설정을 직접 변경하지 않습니다.

Web UI는 브라우저에서 Azure Blob Storage SAS URL로 직접 `PUT` 업로드합니다.

따라서 직접 만든 Storage Account 또는 관리자가 지정하지 않은 별도 Storage Account를 사용할 경우, Azure Storage Account의 Blob service CORS 설정에 Web UI 주소를 추가해야 합니다.

Azure Portal:

```text
Storage Account
-> Settings
-> Resource sharing (CORS)
-> Blob service
```

로컬 실행 예:

```text
Allowed origins: http://127.0.0.1:9990
Allowed methods: PUT, OPTIONS
Allowed headers: x-ms-blob-type, content-type, x-ms-*
Exposed headers: *
Max age: 3600
```

사내 서버 실행 예:

```text
Allowed origins: http://<server-host>:9990
Allowed methods: PUT, OPTIONS
Allowed headers: x-ms-blob-type, content-type, x-ms-*
Exposed headers: *
Max age: 3600
```

브라우저 주소창의 origin과 CORS의 Allowed origins가 정확히 같아야 합니다.

예를 들어 아래 값들은 서로 다른 origin입니다.

```text
http://127.0.0.1:9990
http://localhost:9990
http://127.0.0.1:9992
```

관리자가 지정하지 않은 별도 Storage Account를 사용할 경우, `.env`의 `AZURE_CLIENT_ID`에 해당하는 App Registration / Service Principal에 아래 권한도 필요합니다.

```text
Storage Blob Delegator
Storage Blob Data Contributor
```

권한 범위:

```text
Storage Blob Delegator: Storage Account 범위
Storage Blob Data Contributor: Storage Account 또는 대상 Container 범위
```

다시 한 번 강조하면, **관리자가 지정한 Storage Account와 Container를 그대로 사용하는 경우에는 이 섹션의 CORS/권한 설정을 새로 하지 않습니다.**

## 8. Web UI에서 업로드

브라우저에서 Web UI를 엽니다.

```text
http://127.0.0.1:9990/
```
![화면](images/image.png)

화면에서 다음 값을 입력합니다.

```text
사용자 ID
메타데이터 파일
원본 문서
```

파일명 규칙:

```text
메타데이터 파일: <name>.meta.toml
원본 문서: <name>.<파일형식>
```

정상 예:

```text
LiteLLM Workflow.meta.toml
LiteLLM Workflow.pdf
```

잘못된 예:

```text
LiteLLM Workflow.meta.toml
Other Workflow.pdf
```

두 파일을 선택하면 UI의 `파일명 확인` 영역에서 규칙 검사 결과가 표시됩니다.

규칙에 맞으면 `업로드` 버튼을 누릅니다.

## 9. 처리 결과 확인

업로드 결과는 세 가지 중 하나입니다.

### Uploaded

Blob Storage에 같은 meta 파일 이름이 없어서 새로 업로드된 상태입니다.

```text
업로드가 완료되었습니다.
```

### Skipped

Blob Storage에 같은 meta 파일이 있고, meta 파일 내용도 동일해서 업로드하지 않은 상태입니다.

```text
기존 메타데이터 파일 내용과 동일하여 업로드하지 않았습니다.
```

### Updated

Blob Storage에 같은 meta 파일 이름은 있지만 내용이 달라서 meta 파일과 원본 문서를 함께 갱신한 상태입니다.

```text
수정이 완료되었습니다.
```

결과 화면의 `Blob Storage 내 저장 경로`에서 실제 저장 경로를 확인할 수 있습니다.
![Blob Storage 내 저장 경로 예시](images/image-1.png)

예:

```text
uploads/parksh/LiteLLM_Workflow/LiteLLM_Workflow.meta.toml
uploads/parksh/LiteLLM_Workflow/LiteLLM_Workflow.pdf
```

## 10. 문제 해결

### uv 명령어를 찾을 수 없음

```text
uv: command not found
```

해결:

```text
1. uv 설치가 완료되었는지 확인
2. 터미널을 새로 열기
3. uv --version 다시 실행
```

### 포트가 이미 사용 중

```text
Address already in use
```

다른 포트로 실행합니다.

```bash
uv run uvicorn azure_script.server:app --reload --port 9991
```

브라우저도 같은 포트로 접속합니다.

```text
http://127.0.0.1:9991/
```

CORS 설정도 해당 origin으로 맞춰야 합니다.

```text
http://127.0.0.1:9991
```

### CORS 오류

UI에 다음과 비슷한 메시지가 나오면 CORS 설정 문제입니다.

```text
브라우저에서 Azure Blob Storage 업로드가 차단되었습니다.
Storage Account의 Blob service CORS 설정에 현재 UI 주소를 허용하세요.
```

해결:

```text
Azure Storage Account -> Resource sharing (CORS) -> Blob service
Allowed origins에 현재 UI 주소 추가
```

### Azure 권한 오류

```text
Azure Storage가 업로드 계획 요청을 거부했습니다.
```

해결:

```text
App Registration / Service Principal에 아래 권한이 있는지 확인
- Storage Blob Delegator
- Storage Blob Data Contributor
```

### 파일명 불일치

UI에 다음 메시지가 나오면 두 파일의 `<name>`이 다른 상태입니다.

```text
파일명이 일치하지 않습니다.
```

예를 들어 원본 문서가 `report.pdf`라면 메타데이터 파일은 반드시 다음 이름이어야 합니다.

```text
report.meta.toml
```

## 11. 보안 주의사항

아래 파일과 값은 Git에 올리면 안 됩니다.

```text
.env
.venv/
files/
AZURE_CLIENT_SECRET
Storage Account Key
Connection String
```

Web UI 서버만 Azure 자격 증명을 가지고 있고, 브라우저는 서버가 발급한 짧은 SAS URL로만 업로드합니다.
