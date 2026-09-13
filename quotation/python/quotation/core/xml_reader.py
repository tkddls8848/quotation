"""XML 을 읽다가 나는 오류.

파서 자체는 Rust 코어에 있다 (`rust/core/src/xml_reader.rs`). 여기 남은 것은
**예외 하나** 뿐이다 — 데스크톱 화면과 웹 API 가 그것을 잡아 사용자에게
보여 준다. 클래스는 확장 모듈이 정의한 것을 그대로 쓴다. 변환이 어느 경로로
돌든(브라우저의 wasm, 데스크톱의 확장) 호출자가 같은 예외를 잡게 하려는 것이다.

메시지는 원본 프로그램과 같다.

    XML을 로드하는중 장애 발생. 장애코드: …
    CFXML을 찾을수 없습니다.
    CFData을 찾을수 없습니다.
    견적서 작성을 위한 Item을 찾을 수 없습니다.
"""
from __future__ import annotations

from quotation_rust import QuotationXmlError

__all__ = ["QuotationXmlError"]
