import re
from dataclasses import dataclass
from pathlib import Path


_SAFE_CHARS = re.compile(r"[^\w.-]+", re.UNICODE)


@dataclass(frozen=True)
class PairBlobNames:
    metadata: str
    data: str


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


def metadata_base_name(filename: str) -> str | None:
    basename = Path(filename).name.strip()
    if basename.endswith(".meta.toml"):
        base = basename.removesuffix(".meta.toml")
        return base or None
    return None


def validate_upload_pair_names(metadata_filename: str, data_filename: str) -> None:
    metadata_name = Path(metadata_filename).name.strip()
    data_name = Path(data_filename).name.strip()
    metadata_base = metadata_base_name(metadata_name)

    if metadata_base is None:
        raise ValueError("metadata file must be named <name>.meta.toml")

    if not data_name:
        raise ValueError("data filename must not be empty")

    if data_name.endswith(".meta.toml"):
        raise ValueError("data file must not be a .meta.toml file")

    if not Path(data_name).suffix:
        raise ValueError("data file must have an extension, such as .pdf or .docx")

    if metadata_base != Path(data_name).stem:
        raise ValueError(
            "metadata and data filenames must share the same <name>: "
            f"expected {Path(data_name).stem}.meta.toml, got {metadata_name}"
        )


def build_pair_blob_names(
    user_id: str,
    metadata_filename: str,
    data_filename: str,
) -> PairBlobNames:
    validate_upload_pair_names(metadata_filename, data_filename)

    safe_user_id = sanitize_user_id(user_id)
    metadata_name = Path(metadata_filename).name.strip()
    data_name = Path(data_filename).name.strip()
    base = metadata_base_name(metadata_name)
    if base is None:
        raise ValueError("metadata file must be named <name>.meta.toml")

    safe_base = sanitize_filename(base)
    safe_metadata_name = sanitize_filename(metadata_name)
    safe_data_name = sanitize_filename(data_name)
    prefix = f"uploads/{safe_user_id}/{safe_base}"

    # 같은 user_id와 같은 <name>은 항상 같은 blob 경로를 사용한다.
    # 이 고정 경로 덕분에 서버가 기존 meta 파일을 찾아 skip/update를 판단할 수 있다.
    return PairBlobNames(
        metadata=f"{prefix}/{safe_metadata_name}",
        data=f"{prefix}/{safe_data_name}",
    )
