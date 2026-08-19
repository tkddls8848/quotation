"""종목 키와 Excel 시트명 생성."""
from __future__ import annotations

from typing import Iterable

# Excel 시트명 제한에 맞춰 자른 뒤 IBM 접두사를 제거한다.
ITEM_KEY_MAX = 31
SHEET_NAME_MAX = 31

#: Excel 이 시트명에 허용하지 않는 글자. 대신 하이픈을 넣는다.
#: '메일/스펨_1식' -> '메일-스펨_1식'
SHEET_FORBIDDEN = ":\\/?*[]"
SHEET_REPLACEMENT = "-"

#: Excel 이 예약해 둔 시트명 (대소문자 무관).
SHEET_RESERVED = "history"

#: 금칙 문자를 다 걷어 내고도 이름이 남지 않을 때 쓸 이름.
SHEET_FALLBACK = "SHEET"


def item_key(description: str) -> str:
    """ProductDescription -> 종목 키 (원본 대소문자 유지)."""
    text = description.partition(":")[0].strip()[:ITEM_KEY_MAX]
    return text.removeprefix("IBM ").strip()


def sheet_name(key: str) -> str:
    """종목 키 -> 시트명 (대문자)."""
    return key.upper()[:SHEET_NAME_MAX]


def product_key(product_name: str, description: str) -> str:
    """레노버 구성의 종목 키.

    한 파일에 같은 기종을 여러 대 담으면 ProductDescription 이 전부 같다
    ('ThinkSystem SR650 V4-3yr Base Warranty' x 10). 장비를 구분하는 이름은
    구성기에서 사람이 적어 넣은 ProductName 에 있다 ('백업서버_1식', '웹서버_1식').
    그래서 그쪽을 먼저 쓰고, 없으면 지금까지 하던 대로 설명에서 딴다.
    """
    text = (product_name or "").strip()[:ITEM_KEY_MAX].strip()
    return text or item_key(description)


def safe_sheet_name(key: str) -> str:
    """종목 키 -> **Excel 이 받아 주는** 시트명.

    `sheet_name` 과 달리 금칙 문자를 걷어 낸다. IBM 문서의 종목 키에는 금칙
    문자가 나오지 않지만 사람이 적어 넣은 이름에는 나온다 ('메일/스펨_1식').
    """
    text = "".join(SHEET_REPLACEMENT if ch in SHEET_FORBIDDEN else ch
                   for ch in key.upper())
    text = text[:SHEET_NAME_MAX].strip().strip("'").strip()
    if not text or text.lower() == SHEET_RESERVED:
        return SHEET_FALLBACK
    return text


def unique_sheet_names(names: Iterable[str]) -> list[str]:
    """겹치는 시트명을 갈라 준다. 순서와 길이 제한을 지킨다.

    Excel 은 한 통합 문서에 같은 이름의 시트를 둘 수 없고 이름은 31자까지다.
    openpyxl 에 맡기면 뒤에 숫자를 이어 붙여 32자짜리 이름을 만들어 내므로
    (`...BASE W1`) 여기서 먼저 정리한다.

        ['백업서버', '백업서버', '웹서버'] -> ['백업서버', '백업서버 (2)', '웹서버']
    """
    taken: set[str] = set()
    result: list[str] = []
    for name in names:
        candidate = name
        ordinal = 2
        while candidate.upper() in taken:
            suffix = f" ({ordinal})"
            base = name[:SHEET_NAME_MAX - len(suffix)].strip() or SHEET_FALLBACK
            candidate = f"{base}{suffix}"
            ordinal += 1
        taken.add(candidate.upper())
        result.append(candidate)
    return result
