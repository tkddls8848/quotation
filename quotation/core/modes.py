"""변환 모드.

같은 eConfig 형식이라도 문서를 만든 구성기가 다르면 값의 뜻이 달라진다.
모드는 **문서를 어떻게 읽을지** 를 고르는 것이며 견적서 양식은 하나뿐이다.

    UNIX        IBM eServer / TotalStorage eConfig Export (지금까지의 동작)
    INTEGRATED  레노버 x86 (Lenovo DCSC) 구성 파일 — 통합 견적

레노버 구성기만 본체 라인에 ProductName 을 적어 넣는다
(`models.LineItem.product_name` 머리말). 그래서 문서 자체가 어느 쪽인지
알려 주며, 사람이 고를 필요가 없다 — `detect()` 하나로 정한다.

두 모드가 갈리는 지점은 `integrated.py` 에 한 곳으로 모아 두었다. UNIX 모드는
한 줄도 바뀌지 않는다.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Iterable

if TYPE_CHECKING:
    from .models import LineItem

UNIX = "unix"
INTEGRATED = "integrated"

MODES = (UNIX, INTEGRATED)

#: 진단 로그·안내문에 쓸 이름.
LABELS = {UNIX: "IBM 제품", INTEGRATED: "통합"}


def detect(items: "Iterable[LineItem]") -> str:
    """문서 내용으로 읽는 방식을 고른다.

    본체 라인에 ProductName 이 있으면 레노버 x86(통합) 구성이고, 없으면 IBM
    문서다. IBM eConfig 는 이 항목을 쓰지 않는다.
    """
    return INTEGRATED if any(i.product_name.strip() for i in items) else UNIX


def normalize(raw: str) -> str:
    """모드 문자열을 정규화한다. 자동 판정을 강제로 덮어쓸 때만 쓴다 (테스트용).

    Raises:
        ValueError: 모르는 모드.
    """
    text = raw.strip().lower()
    if text not in MODES:
        raise ValueError(f"모르는 변환 모드입니다: {raw}")
    return text


def resolve(raw: str | None, items: "Iterable[LineItem]") -> str:
    """명시로 준 모드가 있으면 그대로 쓰고, 없으면 문서에서 알아낸다."""
    text = (raw or "").strip()
    return normalize(text) if text else detect(items)
