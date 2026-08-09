"""XML 한 건을 견적서 파일로 변환한다."""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from . import xml_reader
from .writer import ibm_writer

#: (진행률 0~100, 상태 메시지)
ProgressFn = Callable[[int, str], None]


@dataclass(frozen=True)
class Result:
    output: Path
    group_count: int
    elapsed: float


def _noop(percent: int, message: str) -> None:
    pass


def output_path_for(xml_path: Path) -> Path:
    """출력 파일 경로. **언제나 XML 과 같은 폴더**, 같은 이름, 확장자만 .xlsx."""
    xml_path = Path(xml_path)
    return xml_path.parent / f"{xml_path.stem}.xlsx"


def convert(xml_path: str | Path, *, template: str | Path | None = None,
            today: dt.date | None = None,
            progress: ProgressFn = _noop) -> Result:
    """XML -> 견적서 .xlsx. 저장 위치는 XML 과 같은 폴더로 고정이다.

    Raises:
        xml_reader.QuotationXmlError: XML 문제
        OSError: 파일 쓰기 실패 (대상 파일이 열려 있는 경우 등)
    """
    from .. import paths  # 지연 import (core 는 패키지 설정에 의존하지 않는다)

    started = dt.datetime.now()
    xml_path = Path(xml_path)
    template = Path(template) if template else paths.template_path()

    progress(5, "XML화일을 읽고 있습니다.")
    quote = xml_reader.parse(xml_path)

    progress(35, "XML화일 분석을 완료하였습니다.")
    out = output_path_for(xml_path)

    progress(45, "Excel화일을 생성하고 있습니다.")
    ibm_writer.write(quote, template, out, today=today)

    progress(100, "견적서작성을 완료하였습니다.")
    elapsed = (dt.datetime.now() - started).total_seconds()
    return Result(output=out, group_count=len(quote.groups), elapsed=elapsed)
