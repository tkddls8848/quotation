"""XML 한 건을 견적서로 변환한다.

두 진입점이 같은 순수 로직을 쓴다.

    convert_bytes()   바이트 입력 -> 바이트 출력 (웹 Worker)
    convert()         경로 입력 -> 파일 저장     (데스크톱)

코어는 사용자 설정과 실행 경로 정책을 모른다. 템플릿을 어디서 가져올지는
호출자(데스크톱은 EXE 옆 편집본, Worker 는 R2 객체)가 정한다.
"""
from __future__ import annotations

import datetime as dt
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from . import modes, resources, xml_reader
from .models import Quotation
from .writer import ibm_writer

#: (진행률 0~100, 상태 메시지)
ProgressFn = Callable[[int, str], None]

OUTPUT_SUFFIX = ".xlsx"


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


def convert_bytes(xml_bytes: bytes, template_bytes: bytes, *,
                  today: dt.date | None = None,
                  source_name: str = "quotation.xml",
                  mode: str = modes.DEFAULT) -> ConversionResult:
    """XML 바이트 -> 견적서 .xlsx 바이트.

    Args:
        mode: 문서를 읽는 방식 (`quotation.core.modes`).

    Raises:
        xml_reader.QuotationXmlError: XML 문제
    """
    started = time.perf_counter()
    quote = xml_reader.parse_bytes(xml_bytes, mode=mode)
    xlsx = ibm_writer.build_bytes(quote, template_bytes, today=today)
    return ConversionResult(
        xlsx=xlsx,
        filename=output_name_for(source_name),
        group_count=len(quote.groups),
        line_count=line_count(quote),
        elapsed_ms=int((time.perf_counter() - started) * 1000),
    )


def convert(xml_path: str | Path, *, template: str | Path | None = None,
            today: dt.date | None = None,
            progress: ProgressFn = _noop,
            mode: str = modes.DEFAULT) -> Result:
    """XML -> 견적서 .xlsx. 저장 위치는 XML 과 같은 폴더로 고정이다.

    Args:
        template: 쓸 템플릿 경로. 생략하면 저장소의 기준 템플릿을 쓴다.
        mode: 문서를 읽는 방식 (`quotation.core.modes`).

    Raises:
        xml_reader.QuotationXmlError: XML 문제
        OSError: 파일 쓰기 실패 (대상 파일이 열려 있는 경우 등)
    """
    started = dt.datetime.now()
    xml_path = Path(xml_path)
    template = Path(template) if template else resources.default_template_path()

    progress(5, "XML화일을 읽고 있습니다.")
    quote = xml_reader.parse(xml_path, mode=mode)

    progress(35, "XML화일 분석을 완료하였습니다.")
    out = output_path_for(xml_path)

    progress(45, "Excel화일을 생성하고 있습니다.")
    ibm_writer.write(quote, template, out, today=today)

    progress(100, "견적서작성을 완료하였습니다.")
    elapsed = (dt.datetime.now() - started).total_seconds()
    return Result(output=out, group_count=len(quote.groups), elapsed=elapsed)
