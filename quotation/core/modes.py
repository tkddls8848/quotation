"""변환 모드.

같은 eConfig 형식이라도 문서를 만든 구성기가 다르면 값의 뜻이 달라진다.
모드는 **문서를 어떻게 읽을지** 를 고르는 것이며 견적서 양식은 하나뿐이다.

    UNIX        IBM eServer / TotalStorage eConfig Export (지금까지의 동작)
    INTEGRATED  레노버 x86 (Lenovo DCSC) 구성 파일 — 통합 견적

두 모드가 갈리는 지점은 `integrated.py` 에 한 곳으로 모아 두었다. UNIX 모드는
한 줄도 바뀌지 않는다.
"""
from __future__ import annotations

UNIX = "unix"
INTEGRATED = "integrated"

MODES = (UNIX, INTEGRATED)
DEFAULT = UNIX

#: 화면에 보여 줄 이름.
LABELS = {UNIX: "IBM 제품", INTEGRATED: "통합"}


def normalize(raw: str | None) -> str:
    """사용자·요청이 준 모드 값을 정규화한다.

    Args:
        raw: 모드 문자열. 비어 있으면 기본값(UNIX)으로 본다.

    Raises:
        ValueError: 모르는 모드.
    """
    text = (raw or "").strip().lower()
    if not text:
        return DEFAULT
    if text not in MODES:
        raise ValueError(f"모르는 변환 모드입니다: {raw}")
    return text
