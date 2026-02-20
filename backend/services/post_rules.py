from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class PostValidationResult:
    ok: bool
    error: str | None = None

def normalize_caption(value: str | None, max_length: int = 250) -> str:
    if value is None:
        return ""
    cleaned = value.strip()
    if len(cleaned) > max_length:
        return cleaned[:max_length]
    return cleaned

def validate_create_payload(media_public_id: str | None, media_url: str | None) -> PostValidationResult:
    if not media_public_id or not media_url:
        return PostValidationResult(False, "media_public_id and media_url are required")
    return PostValidationResult(True)

def can_user_modify_post(current_user_id: int | str | None, row_author_id: int | str | None, role: str | None) -> bool:
    if role == "admin":
        return True
    if current_user_id is None or row_author_id is None:
        return False
    return str(current_user_id) == str(row_author_id)

def normalize_id_list(values) -> list[int]:
    result: list[int] = []
    for value in values or []:
        try:
            result.append(int(value))
        except (TypeError, ValueError):
            continue
    return result