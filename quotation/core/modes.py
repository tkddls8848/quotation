"""변환 모드 — 문서를 읽는 방식.

같은 eConfig 형식이라도 문서를 만든 구성기가 다르면 값의 뜻이 달라진다.

    UNIX        IBM eServer / TotalStorage eConfig Export
    INTEGRATED  레노버 x86 (Lenovo DCSC) 구성 파일 — 통합 견적

**어느 쪽인지는 사람이 고르지 않는다.** 본체 라인에 ProductName 이 있으면
레노버 문서다. 그 판단은 Rust 코어가 하고, 결과는
`quotation.core.convert.document_mode()` 가 알려 준다.

여기 남은 것은 그 결과를 가리키는 이름뿐이다 — 화면이 템플릿을 고르고 라벨을
붙이는 데 쓴다.
"""
from __future__ import annotations

UNIX = "unix"
INTEGRATED = "integrated"

MODES = (UNIX, INTEGRATED)

#: 진단 로그·안내문에 쓸 이름.
LABELS = {UNIX: "IBM 제품", INTEGRATED: "통합"}

__all__ = ["INTEGRATED", "LABELS", "MODES", "UNIX"]
