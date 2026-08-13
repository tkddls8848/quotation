"""바이트 I/O 코어 — 웹 Worker 가 쓰는 순수 경로.

계약은 하나다. **같은 XML 이면 경로 방식과 바이트 방식의 결과가 의미상 같다.**
데스크톱과 웹이 한동안 함께 운영되므로(계획서 §11 Phase 6) 이 동등성이 깨지면
두 경로의 견적서가 달라진다.
"""
from __future__ import annotations

import datetime as dt
import zipfile
from io import BytesIO

import pytest

import compare as cmp_mod
from quotation.core import convert, xml_reader
from quotation.core.writer import drawings, ibm_writer

TODAY = dt.date(2026, 7, 23)

FIXTURE_NAMES = ["new_quote.xml", "upgrade_quote.xml", "no_charge.xml",
                 "euckr_quote.xml"]


# --- 파싱 --------------------------------------------------------------------

@pytest.mark.parametrize("name", FIXTURE_NAMES)
def test_parse_bytes_matches_parse_path(name, fixtures):
    source = fixtures / name
    assert xml_reader.parse_bytes(source.read_bytes()) == xml_reader.parse(source)


def test_parse_bytes_rejects_empty_input():
    with pytest.raises(xml_reader.QuotationXmlError, match="빈 화일"):
        xml_reader.parse_bytes(b"   \n")


def test_parse_bytes_reports_malformed_xml():
    with pytest.raises(xml_reader.QuotationXmlError, match="장애 발생"):
        xml_reader.parse_bytes(b"<CFXML><CFData>")


def test_parse_bytes_blocks_external_entities(tmp_path):
    """외부 엔티티가 확장되면 안 된다 (XXE)."""
    secret = tmp_path / "secret.txt"
    secret.write_text("TOPSECRET", encoding="utf-8")
    payload = (
        '<?xml version="1.0"?>'
        f'<!DOCTYPE CFXML [<!ENTITY xxe SYSTEM "file:///{secret.as_posix()}">]>'
        "<CFXML><CFData><ProductLineItem>"
        "<ProductLineNumber>&xxe;</ProductLineNumber>"
        "<TransactionType>NEW</TransactionType>"
        "</ProductLineItem></CFData></CFXML>"
    ).encode("utf-8")
    try:
        quote = xml_reader.parse_bytes(payload)
    except xml_reader.QuotationXmlError:
        return  # 파싱 거부도 정상
    assert "TOPSECRET" not in str(quote.groups[0].items[0].line_number)


def test_parse_bytes_needs_bytes_not_text(fixtures):
    """str 로 넘기면 EUC-KR 선언을 존중할 수 없다. 바이트만 받는다."""
    text = (fixtures / "euckr_quote.xml").read_bytes().decode("euc-kr")
    with pytest.raises((ValueError, TypeError)):
        xml_reader.parse_bytes(text)  # type: ignore[arg-type]


# --- 생성 --------------------------------------------------------------------

@pytest.mark.parametrize("name", FIXTURE_NAMES)
def test_bytes_output_matches_path_output(name, tmp_path, fixtures, template_bytes,
                                          template_path):
    """두 경로의 산출물을 셀 단위로 대조한다 (tools/compare.py 와 같은 기준)."""
    source = fixtures / name

    xml = tmp_path / name
    xml.write_bytes(source.read_bytes())
    from_path = convert.convert(xml, template=template_path, today=TODAY).output

    result = convert.convert_bytes(source.read_bytes(), template_bytes,
                                   today=TODAY, source_name=name)
    from_bytes = tmp_path / "bytes.xlsx"
    from_bytes.write_bytes(result.xlsx)

    report = cmp_mod.compare(from_path, from_bytes, set())
    assert report.ok, "\n".join(str(d) for d in report.diffs[:20])


def test_convert_bytes_reports_names_and_counts(fixtures, template_bytes):
    result = convert.convert_bytes(
        (fixtures / "new_quote.xml").read_bytes(), template_bytes,
        today=TODAY, source_name="견적 (수정본)#2.xml")
    assert result.filename == "견적 (수정본)#2.xlsx"
    assert result.group_count == 2
    assert result.line_count == 3
    assert result.elapsed_ms >= 0


def test_convert_bytes_keeps_total_sheet_drawings(fixtures, template_bytes):
    """openpyxl 은 저장 시 그림을 버린다. TOTAL 시트의 로고가 남아야 한다."""
    import re

    result = convert.convert_bytes((fixtures / "new_quote.xml").read_bytes(),
                                   template_bytes, today=TODAY)
    with zipfile.ZipFile(BytesIO(result.xlsx)) as z:
        names = z.namelist()
        media = [n for n in names if n.startswith("xl/media/")]
        drawn = sorted(n for n in names
                       if n.startswith("xl/worksheets/sheet")
                       and re.search(rb"<drawing\s", z.read(n)))

    assert media, "템플릿의 로고 이미지가 옮겨지지 않았다"
    assert drawn == ["xl/worksheets/sheet1.xml"], (
        f"그림은 TOTAL(sheet1)에만 있어야 한다: {drawn}")


def test_carry_over_bytes_is_a_noop_without_drawings(fixtures, template_bytes):
    """그림이 없는 템플릿이면 손대지 않고 None 을 돌려준다."""
    quote = xml_reader.parse_bytes((fixtures / "new_quote.xml").read_bytes())
    plain = BytesIO()
    ibm_writer.build(quote, BytesIO(template_bytes), today=TODAY).save(plain)
    assert drawings.carry_over_bytes(plain.getvalue(), plain.getvalue()) is None


def test_build_bytes_produces_a_readable_workbook(fixtures, template_bytes):
    from openpyxl import load_workbook

    quote = xml_reader.parse_bytes((fixtures / "upgrade_quote.xml").read_bytes())
    data = ibm_writer.build_bytes(quote, template_bytes, today=TODAY)
    wb = load_workbook(BytesIO(data))
    assert wb.sheetnames == ["TOTAL", "SERVER 1", "template"]
    assert wb["TOTAL"]["C3"].value == TODAY.isoformat()
