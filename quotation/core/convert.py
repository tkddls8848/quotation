"""변환 오케스트레이션 — XML 한 건을 견적서 파일로.

UI 와 CLI 가 공유한다. GUI 에 의존하지 않는다.
"""
from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from . import xml_reader
from .models import Quotation
from .writer import ibm_writer

log = logging.getLogger(__name__)

#: (진행률 0~100, 상태 메시지)
ProgressFn = Callable[[int, str], None]


@dataclass(frozen=True)
class Result:
    output: Path
    quote: Quotation
    elapsed: float

    @property
    def group_count(self) -> int:
        """장비군 수 = 상세 시트 수."""
        return len(self.quote.groups)

    @property
    def sheet_count(self) -> int:
        """실제 시트 수. TOTAL + 상세 + 숨김 template."""
        return len(self.quote.groups) + 2


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
    log.info("파싱 완료: 그룹 %d, 라인 %d", len(quote.groups),
             sum(len(g.items) for g in quote.groups))

    progress(35, "XML화일 분석을 완료하였습니다.")
    out = output_path_for(xml_path)

    progress(45, "Excel화일을 생성하고 있습니다.")
    ibm_writer.write(quote, template, out, today=today)

    progress(100, "견적서작성을 완료하였습니다.")
    elapsed = (dt.datetime.now() - started).total_seconds()
    log.info("변환 완료: %s (%.2f초)", out, elapsed)
    return Result(output=out, quote=quote, elapsed=elapsed)
