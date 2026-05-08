# Azure Blob Storage Upload Server

Azure Blob Storage에 파일을 업로드하기 위한 Web UI 서버입니다.

사용자는 브라우저에서 `.meta.toml` 파일과 원본 문서 파일을 선택하고 업로드합니다. 서버는 업로드 가능 여부를 판단한 뒤 짧은 시간만 유효한 SAS URL을 발급하고, 브라우저는 해당 SAS URL로 Azure Blob Storage에 직접 업로드합니다.

자세한 설치와 사용 방법은 [UPLOAD_GUIDE.md](UPLOAD_GUIDE.md)를 참고하세요.

## 주요 기능

- Web UI에서 파일 2개를 선택해 업로드
- `<name>.meta.toml`과 `<name>.<파일형식>` 파일명 규칙 검증
- 기존 메타데이터 내용과 비교해 `skip`, `upload`, `update` 자동 판단
- Azure Client Secret은 서버의 `.env`에만 보관
- 브라우저는 제한된 SAS URL로만 Blob Storage에 업로드

## 업로드 규칙

업로드 파일은 항상 2개입니다.

```text
<name>.meta.toml
<name>.<파일형식>
```

예:

```text
LiteLLM Workflow.meta.toml
LiteLLM Workflow.pdf
```

두 파일의 `<name>`이 다르면 업로드할 수 없습니다.

사용자 ID는 사내 이메일 계정명을 사용하는 것을 권장합니다.

```text
user01@example.com -> user01
```

처리 기준:

- 같은 이름의 메타 파일이 없으면 메타 파일과 원본 문서를 `upload`
- 같은 이름의 메타 파일이 있고 내용이 같으면 둘 다 `skip`
- 같은 이름의 메타 파일이 있지만 내용이 다르면 메타 파일과 원본 문서를 `update`

## 빠른 실행

의존성을 설치합니다.

```bash
uv sync
```

환경 변수 파일을 만듭니다.

```bash
cp .env.example .env
```

`.env`에 Azure Storage와 App Registration 값을 입력합니다.

```env
AZURE_STORAGE_ACCOUNT_NAME=your-storage-account
AZURE_STORAGE_CONTAINER_NAME=your-container
AZURE_TENANT_ID=your-tenant-id
AZURE_CLIENT_ID=your-client-id
AZURE_CLIENT_SECRET=your-client-secret
SAS_TTL_MINUTES=15
MAX_UPLOAD_BYTES=5368709120
```

Web UI 서버를 실행합니다.

```bash
uv run uvicorn azure_script.server:app --reload --port 9990
```

브라우저에서 접속합니다.

```text
http://127.0.0.1:9990/
```

clone부터 Web UI 업로드까지의 전체 절차는 [UPLOAD_GUIDE.md](UPLOAD_GUIDE.md)에 정리되어 있습니다.

## 문서

- [UPLOAD_GUIDE.md](UPLOAD_GUIDE.md): 사용자용 Web UI 업로드 가이드
- [ARCHITECTURE.md](ARCHITECTURE.md): SAS 발급 서버 구조와 Azure 권한 설명
- [.env.example](.env.example): 환경 변수 예시

## 개발

테스트 실행:

```bash
uv run pytest
```

보안 주의사항:

- `.env`는 Git에 커밋하지 않습니다.
- Azure Client Secret, SAS URL, 실제 업로드 파일은 공개 저장소에 올리지 않습니다.
- Web UI에서 직접 Blob Storage로 업로드하므로 Storage Account CORS 설정이 필요할 수 있습니다. 자세한 내용은 [UPLOAD_GUIDE.md](UPLOAD_GUIDE.md)의 CORS 섹션을 참고하세요.
