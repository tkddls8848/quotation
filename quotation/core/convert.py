"""XML 한 건을 견적서로 변환한다.

두 진입점이 같은 순수 로직을 쓴다.

    convert_bytes()   바이트 입력 -> 바이트 출력 (웹 Worker)
    convert()         경로 입력 -> 파일 저장     (데스크톱)

코어는 사용자 설정과 실행 경로 정책을 모른다. 템플릿을 어디서 가져올지는
호출자(데스크톱은 EXE 옆 편집본, 웹은 빌드 시점에 번들에 담긴 것)가 정한다.
IBM 문서인지 레노버 x86 문서인지는 파싱 후에야 알 수 있으므로(`modes.detect`),
템플릿을 고정 값이 아니라 `mode -> 템플릿` 함수로 줄 수도 있다 — 문서를 읽어
모드를 알아낸 **다음** 그 함수를 불러 템플릿을 고른다.
"""
from __future__ import annotations

import datetime as dt
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Union

from . import resources, xml_reader
from .models import Quotation
from .writer import ibm_writer

#: (진행률 0~100, 상태 메시지)
ProgressFn = Callable[[int, str], None]

#: 고정 경로/바이트를 주거나, 알아낸 모드로 고르는 함수를 줄 수 있다.
TemplatePath = Union[str, Path, Callable[[str], Union[str, Path]]]
TemplateBytes = Union[bytes, Callable[[str], bytes]]

OUTPUT_SUFFIX = ".xlsx"


def _resolve(value, mode: str):
    """고정 값이면 그대로, 함수면 알아낸 모드로 불러 쓴다."""
    return value(mode) if callable(value) else value


@dataclass(frozen=True)
class Result:
    """데스크톱 변환 결과."""

    output: Path
    group_count: int
    elapsed: float


@dataclass(frozen=True)
class ConversionResult:
    """웹 변환 결과. 파일로 남기지 않고 응답 본문으로 바로 나간다."""

    xlsx: bytes
    filename: str
    group_count: int
    line_count: int
    elapsed_ms: int
    #: 문서에서 알아낸 읽기 방식 (`modes.UNIX` 또는 `modes.INTEGRATED`). 진단 로그용.
    mode: str = ""
    #: 실제로 쓴 템플릿의 판본. 호출자가 안 줬으면 빈 문자열.
    template_version: str = ""


def _noop(percent: int, message: str) -> None:
    pass


def output_name_for(xml_name: str) -> str:
    """입력 파일의 기본 이름을 유지하고 확장자만 .xlsx 로 바꾼다."""
    stem = Path(xml_name).stem or "quotation"
    return f"{stem}{OUTPUT_SUFFIX}"


def output_path_for(xml_path: str | Path) -> Path:
    """출력 파일 경로. **언제나 XML 과 같은 폴더**, 같은 이름, 확장자만 .xlsx."""
    xml_path = Path(xml_path)
    return xml_path.parent / output_name_for(xml_path.name)


def line_count(quote: Quotation) -> int:
    return sum(len(g.items) for g in quote.groups)


def convert_bytes(xml_bytes: bytes, template_bytes: TemplateBytes | None = None, *,
                  today: dt.date | None = None,
                  source_name: str = "quotation.xml",
                  mode: str = "") -> ConversionResult:
    """XML 바이트 -> 견적서 .xlsx 바이트.

    Args:
        template_bytes: 쓸 템플릿 바이트, 또는 `mode -> bytes` 함수. 생략하면
            저장소의 기준 템플릿을 문서의 읽기 방식(IBM/레노버)에 맞춰 쓴다.
        mode: 문서를 읽는 방식을 강제로 지정한다 (`quotation.core.modes`).
            비워 두면 문서 내용(IBM/레노버)으로 알아낸다 — 보통은 이쪽을 쓴다.

    Raises:
        xml_reader.QuotationXmlError: XML 문제
    """
    started = time.perf_counter()
    quote = xml_reader.parse_bytes(xml_bytes, mode=mode)
    resolved = (_resolve(template_bytes, quote.mode) if template_bytes is not None
               else resources.default_template_bytes(quote.mode))
    xlsx = ibm_writer.build_bytes(quote, resolved, today=today)
    return ConversionResult(
        xlsx=xlsx,
        filename=output_name_for(source_name),
        group_count=len(quote.groups),
        line_count=line_count(quote),
        elapsed_ms=int((time.perf_counter() - started) * 1000),
        mode=quote.mode,
    )


def convert(xml_path: str | Path, *, template: TemplatePath | None = None,
            today: dt.date | None = None,
            progress: ProgressFn = _noop,
            mode: str = "") -> Result:
    """XML -> 견적서 .xlsx. 저장 위치는 XML 과 같은 폴더로 고정이다.

    Args:
        template: 쓸 템플릿 경로, 또는 `mode -> 경로` 함수. 생략하면 저장소의
            기준 템플릿을 문서의 읽기 방식(IBM/레노버)에 맞춰 쓴다.
        mode: 문서를 읽는 방식을 강제로 지정한다 (`quotation.core.modes`).
            비워 두면 문서 내용(IBM/레노버)으로 알아낸다 — 보통은 이쪽을 쓴다.

    Raises:
        xml_reader.QuotationXmlError: XML 문제
        OSError: 파일 쓰기 실패 (대상 파일이 열려 있는 경우 등)
    """
    started = dt.datetime.now()
    xml_path = Path(xml_path)

    progress(5, "XML화일을 읽고 있습니다.")
    quote = xml_reader.parse(xml_path, mode=mode)

    resolved_template = Path(_resolve(template, quote.mode)) if template is not None \
        else resources.default_template_path(quote.mode)

    progress(35, "XML화일 분석을 완료하였습니다.")
    out = output_path_for(xml_path)

    progress(45, "Excel화일을 생성하고 있습니다.")
    ibm_writer.write(quote, resolved_template, out, today=today)

    progress(100, "견적서작성을 완료하였습니다.")
    elapsed = (dt.datetime.now() - started).total_seconds()
    return Result(output=out, group_count=len(quote.groups), elapsed=elapsed)
