"""종목 키 / 시트명 생성 — SPEC_CELLMAP.md §2.1.

    "4680-3P4 #1:IBM Storage FlashSystem 5045 SFF Control Enclosure"
        -> 종목키 "4680-3P4 #1"      시트명 "4680-3P4 #1"
    "Server 1:Server 1:9080 Model HEX"
        -> 종목키 "Server 1"          시트명 "SERVER 1"
    "IBM Expert Labs Project Unit for IBM Power Systems"
        -> 종목키 "Expert Labs Project Unit fo"
           시트명 "EXPERT LABS PROJECT UNIT FO"
"""
from __future__ import annotations

import re

#: 종목 키 최대 길이. 두 골든 샘플에서 27자로 확인됨 (SPEC_CELLMAP.md §7-3).
ITEM_KEY_MAX = 27

#: Excel 시트명 제한
SHEET_NAME_MAX = 31
_INVALID_SHEET_CHARS = re.compile(r"[\[\]:*?/\\]")

_IBM_PREFIX = re.compile(r"^IBM\s+", re.IGNORECASE)


def item_key(description: str) -> str:
    """ProductDescription -> 종목 키 (원본 대소문자 유지)."""
    text = (description or "").strip()
    if ":" in text:
        text = text.split(":", 1)[0].strip()
    else:
        text = _IBM_PREFIX.sub("", text).strip()
    return text[:ITEM_KEY_MAX]


def sheet_name(key: str) -> str:
    """종목 키 -> 시트명 (대문자)."""
    name = _INVALID_SHEET_CHARS.sub(" ", key.upper()).strip()
    return name[:SHEET_NAME_MAX] or "SHEET"


def unique_sheet_name(key: str, taken: set[str]) -> str:
    """시트명 충돌 회피. 원본에는 없던 방어 로직이다.

    골든 샘플에서는 충돌이 없었으나, 같은 종목 키를 가진 그룹이 둘 이상이면
    Excel 이 시트 생성 자체를 거부하므로 접미사를 붙인다.
    """
    base = sheet_name(key)
    if base not in taken:
        return base
    for n in range(2, 100):
        suffix = f" ({n})"
        candidate = base[: SHEET_NAME_MAX - len(suffix)] + suffix
        if candidate not in taken:
            return candidate
    raise ValueError(f"시트명을 확정할 수 없습니다: {key!r}")
