import re
import uuid
from datetime import datetime, timezone
from pathlib import Path


_SAFE_CHARS = re.compile(r"[^A-Za-z0-9._-]+")


def sanitize_filename(filename: str) -> str:
    basename = Path(filename).name.strip()
    if not basename:
        raise ValueError("filename must not be empty")

    sanitized = _SAFE_CHARS.sub("_", basename).strip("._-")
    if not sanitized:
        raise ValueError("filename must contain at least one safe character")
    return sanitized[:150]


def sanitize_user_id(user_id: str) -> str:
    user = user_id.strip()
    if not user:
        raise ValueError("user_id must not be empty")

    sanitized = _SAFE_CHARS.sub("_", user).strip("._-")
    if not sanitized:
        raise ValueError("user_id must contain at least one safe character")
    return sanitized[:80]


def build_blob_name(
    user_id: str,
    filename: str,
    now: datetime | None = None,
    upload_id: str | None = None,
) -> str:
    safe_user_id = sanitize_user_id(user_id)
    safe_name = sanitize_filename(filename)
    current = now or datetime.now(timezone.utc)
    safe_upload_id = upload_id or uuid.uuid4().hex
    if not re.fullmatch(r"[A-Za-z0-9_-]{8,64}", safe_upload_id):
        raise ValueError("upload_id must contain only letters, numbers, '_' or '-'")

    # 사용자별/날짜별 prefix와 UUID를 붙여 파일명이 충돌하지 않게 한다.
    return (
        f"uploads/{safe_user_id}/"
        f"{current:%Y/%m/%d}/"
        f"{safe_upload_id}-{safe_name}"
    )
