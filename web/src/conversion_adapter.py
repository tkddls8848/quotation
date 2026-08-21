"""바이트 기반 코어 호출 (계획서 §5.1, §5.2).

여기서만 `quotation.core` 를 부른다. `tkinter`, `quotation_desktop.config`,
`quotation_desktop.paths`, `os.startfile`, PyInstaller 관련 코드는 import 하지
않는다. 코어 예외를 API 오류로 분류하는 일도 이 층이 맡는다.
"""
from __future__ import annotations

import datetime as dt
import re
import zipfile
from io import BytesIO

import errors
import limits
from quotation.core import convert as core_convert
from quotation.core.writer import ibm_writer
from quotation.core.xml_reader import QuotationXmlError, parse_bytes

#: 템플릿과 산출물에 반드시 있어야 하는 시트
REQUIRED_SHEETS = ("TOTAL", "template")

_SHEET_NAME_RE = re.compile(rb'<sheet\b[^>]*\bname="([^"]*)"')
_QUOTATION_ITEM_RE = re.compile(
    rb"<(?:ProductLineItem|ProductSubLineItem)[\s>]"
)


def _sheet_names(xlsx: bytes) -> list[str]:
    """xlsx(zip) 의 시트 이름. 워크북 전체를 열지 않고 목록만 읽는다."""
    with zipfile.ZipFile(BytesIO(xlsx)) as z:
        if "xl/workbook.xml" not in z.namelist():
            raise KeyError("xl/workbook.xml")
        workbook = z.read("xl/workbook.xml")
    return [m.decode("utf-8") for m in _SHEET_NAME_RE.findall(workbook)]


def validate_template(template_bytes: bytes) -> None:
    """활성 템플릿이 쓸 만한지 검사한다 (계획서 §5.2-7).

    Raises:
        errors.ApiError: TEMPLATE_UNAVAILABLE
    """
    if not template_bytes:
        raise errors.template_unavailable()
    try:
        names = _sheet_names(template_bytes)
    except (zipfile.BadZipFile, KeyError) as exc:
        raise errors.template_unavailable() from exc

    missing = [s for s in REQUIRED_SHEETS if s not in names]
    if missing:
        raise errors.template_unavailable()


def _guard_document_size(xml_bytes: bytes) -> None:
    """DOM 을 만들기 전에 싸게 걸러 낸다."""
    if len(xml_bytes) > limits.MAX_UPLOAD_BYTES:
        raise errors.file_too_large(
            f"XML 화일은 {limits.MAX_UPLOAD_BYTES // limits.MiB} MiB 까지 올릴 수 있습니다.")
    if not xml_bytes.strip():
        raise errors.invalid_request("빈 화일입니다.")
    if len(_QUOTATION_ITEM_RE.findall(xml_bytes)) > limits.MAX_LINE_ITEMS:
        raise errors.invalid_quotation_xml(
            f"구성 품목이 너무 많습니다. (최대 {limits.MAX_LINE_ITEMS:,}건)")


def _item_count(quote) -> int:
    """실제 견적에 포함될 상위·서브 품목의 합계."""
    return sum(1 + len(item.subs)
               for group in quote.groups for item in group.items)


def _guard_output(xlsx: bytes, group_count: int) -> None:
    if len(xlsx) > limits.MAX_OUTPUT_BYTES:
        raise errors.invalid_quotation_xml(
            f"생성된 견적서가 너무 큽니다. (최대 {limits.MAX_OUTPUT_BYTES // limits.MiB} MiB)")
    try:
        names = _sheet_names(xlsx)
    except (zipfile.BadZipFile, KeyError) as exc:
        raise errors.conversion_failed() from exc
    # TOTAL + 장비군별 상세 + 숨김 template
    if len(names) != group_count + 2 or any(s not in names for s in REQUIRED_SHEETS):
        raise errors.conversion_failed()


def convert_upload(*, xml_bytes: bytes, template_bytes: bytes,
                   today: dt.date,
                   source_name: str) -> core_convert.ConversionResult:
    """업로드된 XML 바이트 -> 견적서 바이트.

    IBM 문서인지 레노버 x86 문서인지는 고를 필요가 없다. 문서 내용으로 알아낸다
    (`quotation.core.modes.detect`).

    Raises:
        errors.ApiError: 입력·템플릿·내부 오류를 API 오류로 분류해 던진다.
    """
    import time

    started = time.perf_counter()

    _guard_document_size(xml_bytes)
    validate_template(template_bytes)

    try:
        quote = parse_bytes(xml_bytes)
    except QuotationXmlError as exc:
        # 원본 프로그램과 같은 문구를 그대로 사용자에게 보여 준다.
        raise errors.invalid_quotation_xml(str(exc)) from exc

    if len(quote.groups) > limits.MAX_GROUPS:
        raise errors.invalid_quotation_xml(
            f"장비군이 너무 많습니다. (최대 {limits.MAX_GROUPS}개)")
    if _item_count(quote) > limits.MAX_LINE_ITEMS:
        raise errors.invalid_quotation_xml(
            f"구성 품목이 너무 많습니다. (최대 {limits.MAX_LINE_ITEMS:,}건)")

    try:
        xlsx = ibm_writer.build_bytes(quote, template_bytes, today=today)
    except errors.ApiError:
        raise
    except Exception as exc:  # 예상하지 못한 실패는 내부 오류로 접는다
        raise errors.conversion_failed() from exc

    _guard_output(xlsx, len(quote.groups))

    return core_convert.ConversionResult(
        xlsx=xlsx,
        filename=core_convert.output_name_for(source_name),
        group_count=len(quote.groups),
        line_count=core_convert.line_count(quote),
        elapsed_ms=int((time.perf_counter() - started) * 1000),
        mode=quote.mode,
    )
