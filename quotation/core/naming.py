"""종목 키와 Excel 시트명 생성."""
from __future__ import annotations

import re

# Excel 시트명 제한에 맞춰 자른 뒤 IBM 접두사를 제거한다.
ITEM_KEY_MAX = 31

SHEET_NAME_MAX = 31
_INVALID_SHEET_CHARS = re.compile(r"[\[\]:*?/\\]")

_IBM_PREFIX = re.compile(r"^IBM\s+", re.IGNORECASE)


def item_key(description: str) -> str:
    """ProductDescription -> 종목 키 (원본 대소문자 유지)."""
    text = (description or "").strip()
    if ":" in text:
        text = text.split(":", 1)[0].strip()
    return _IBM_PREFIX.sub("", text[:ITEM_KEY_MAX]).strip()


def sheet_name(key: str) -> str:
    """종목 키 -> 시트명 (대문자)."""
    name = _INVALID_SHEET_CHARS.sub(" ", key.upper()).strip()
    return name[:SHEET_NAME_MAX] or "SHEET"


def unique_sheet_name(key: str, taken: set[str]) -> str:
    """중복 시트명에 번호 접미사를 붙인다."""
    base = sheet_name(key)
    if base not in taken:
        return base
    for n in range(2, 100):
        suffix = f" ({n})"
        candidate = base[: SHEET_NAME_MAX - len(suffix)] + suffix
        if candidate not in taken:
            return candidate
    raise ValueError(f"시트명을 확정할 수 없습니다: {key!r}")
