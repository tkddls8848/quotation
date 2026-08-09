"""종목 키와 Excel 시트명 생성."""
from __future__ import annotations

# Excel 시트명 제한에 맞춰 자른 뒤 IBM 접두사를 제거한다.
ITEM_KEY_MAX = 31
SHEET_NAME_MAX = 31


def item_key(description: str) -> str:
    """ProductDescription -> 종목 키 (원본 대소문자 유지)."""
    text = description.partition(":")[0].strip()[:ITEM_KEY_MAX]
    return text.removeprefix("IBM ").strip()


def sheet_name(key: str) -> str:
    """종목 키 -> 시트명 (대문자)."""
    return key.upper()[:SHEET_NAME_MAX]
