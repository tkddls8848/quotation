"""바이트 입력 경로 — 브라우저가 쓰는 것과 같은 계약.

계약은 하나다. **같은 XML 이면 경로 방식과 바이트 방식의 결과가 같다.**
데스크톱은 경로로, 브라우저는 바이트로 부르는데 그 둘이 갈리면 같은 문서에서
다른 견적서가 나온다.
"""
from __future__ import annotations

import datetime as dt
import zipfile
from io import BytesIO

import pytest

from quotation.core import convert
from quotation.core.xml_reader import QuotationXmlError

TODAY = dt.date(2026, 7, 23)

FIXTURE_NAMES = ["new_quote.xml", "upgrade_quote.xml", "no_charge.xml",
                 "euckr_quote.xml", "integrated_quote.xml"]


def _parts(xlsx: bytes) -> list[str]:
    with zipfile.ZipFile(BytesIO(xlsx)) as archive:
        return sorted(archive.namelist())


def _sheet(xlsx: bytes, part: str) -> str:
    with zipfile.ZipFile(BytesIO(xlsx)) as archive:
        return archive.read(part).decode("utf-8")


# --- 입력 거르기 ---------------------------------------------------------------

def test_empty_input_is_rejected():
    with pytest.raises(QuotationXmlError, match="빈 화일"):
        convert.convert_bytes(b"   \n", today=TODAY)


def test_malformed_xml_reports_the_original_message():
    with pytest.raises(QuotationXmlError, match="XML을 로드하는중 장애 발생"):
        convert.convert_bytes(b"<CFXML><CFData>", today=TODAY)


def test_missing_items_are_reported():
    with pytest.raises(QuotationXmlError, match="Item을 찾을 수 없습니다"):
        convert.convert_bytes(b"<CFXML><CFData/></CFXML>", today=TODAY)


def test_external_entities_are_not_expanded(tmp_path):
    """XXE 차단. 문서는 읽되 바깥 파일을 끌어오지 않는다."""
    secret = tmp_path / "secret.txt"
    secret.write_text("SECRET-TOKEN-42", encoding="utf-8")
    document = f"""<?xml version="1.0"?>
    <!DOCTYPE CFXML [<!ENTITY xxe SYSTEM "file:///{secret.as_posix()}">]>
    <CFXML><CFData><ProductLineItem>
        <ProductLineNumber>1</ProductLineNumber>
        <TransactionType>NEW</TransactionType>
        <ProprietaryGroupIdentifier>1000</ProprietaryGroupIdentifier>
        <Quantity>1</Quantity><CPUSIUvalue>1</CPUSIUvalue>
        <ProductIdentification><PartnerProductIdentification>
            <ProductDescription>비밀은&xxe;여기</ProductDescription>
            <ProprietaryProductIdentifier>1234-567</ProprietaryProductIdentifier>
            <ProductTypeCode>Hardware</ProductTypeCode>
        </PartnerProductIdentification></ProductIdentification>
        <UnitListPrice><FinancialAmount><MonetaryAmount>10</MonetaryAmount>
        </FinancialAmount></UnitListPrice>
    </ProductLineItem></CFData></CFXML>""".encode("utf-8")

    result = convert.convert_bytes(document, today=TODAY)
    body = _sheet(result.xlsx, "xl/sharedStrings.xml") \
        if "xl/sharedStrings.xml" in _parts(result.xlsx) \
        else _sheet(result.xlsx, "xl/worksheets/sheet2.xml")
    assert "비밀" not in body or "비밀은" in body, "엔티티가 펼쳐졌다"
    assert secret.read_text(encoding="utf-8") not in body


# --- 두 경로가 같은가 -----------------------------------------------------------

@pytest.mark.parametrize("name", FIXTURE_NAMES)
def test_bytes_output_matches_path_output(name, tmp_path, fixtures):
    """경로로 부르든 바이트로 부르든 같은 견적서가 나와야 한다."""
    source = fixtures / name
    xml = tmp_path / name
    xml.write_bytes(source.read_bytes())

    from_path = convert.convert(xml, today=TODAY)
    from_bytes = convert.convert_bytes(source.read_bytes(), today=TODAY,
                                       source_name=name)

    # 파일 전체 바이트는 같지 않다 (결정 0011). zip 은 부품마다 담은 시각을
    # 적고, 스타일표의 numFmt 나열 **순서**도 실행마다 달라진다 — 둘 다
    # 견적서 내용이 아니다. 시트와 문자열은 바이트가 같아야 한다.
    made = from_path.output.read_bytes()
    assert _parts(made) == _parts(from_bytes.xlsx)
    for part in _parts(made):
        if part.startswith(("xl/worksheets/", "xl/sharedStrings")):
            assert _sheet(made, part) == _sheet(from_bytes.xlsx, part), part
    assert from_path.group_count == from_bytes.group_count


def test_convert_bytes_reports_names_and_counts(fixtures):
    result = convert.convert_bytes(
        (fixtures / "new_quote.xml").read_bytes(), today=TODAY,
        source_name="견 적 (2).xml")
    assert result.filename == "견 적 (2).xlsx"
    assert result.group_count == 2
    assert result.line_count == 3
    assert result.mode == "unix"
    assert result.elapsed_ms >= 0


def test_document_mode_is_read_from_the_document(fixtures):
    """IBM 문서인지 레노버 x86 문서인지는 사람이 고르지 않는다."""
    assert convert.document_mode(
        (fixtures / "new_quote.xml").read_bytes()) == "unix"
    assert convert.document_mode(
        (fixtures / "integrated_quote.xml").read_bytes()) == "integrated"


def test_an_unknown_mode_is_refused(fixtures):
    # 모드를 강제로 주는 것은 시험용 경로다. 모르는 이름은 문서 오류로 돌려준다.
    with pytest.raises(QuotationXmlError, match="모르는 변환 모드"):
        convert.convert_bytes((fixtures / "new_quote.xml").read_bytes(),
                              today=TODAY, mode="x86")


# --- 그림 ---------------------------------------------------------------------

def test_the_total_sheet_keeps_the_template_drawings(fixtures, template_bytes):
    """첫 페이지의 로고·머리글 도형은 템플릿 원본 그대로 실려 나온다."""
    result = convert.convert_bytes((fixtures / "new_quote.xml").read_bytes(),
                                   today=TODAY)
    made = _parts(result.xlsx)
    assert "xl/drawings/drawing1.xml" in made
    assert [name for name in made if name.startswith("xl/media/")]

    with zipfile.ZipFile(BytesIO(result.xlsx)) as produced, \
            zipfile.ZipFile(BytesIO(template_bytes)) as template:
        for part in made:
            if part.startswith(("xl/drawings/", "xl/media/")):
                assert produced.read(part) == template.read(part), part


def test_only_the_total_sheet_draws(fixtures):
    """상세 시트와 잔존 template 시트에는 그림을 남기지 않는다."""
    result = convert.convert_bytes((fixtures / "new_quote.xml").read_bytes(),
                                   today=TODAY)
    assert "<drawing r:id=" in _sheet(result.xlsx, "xl/worksheets/sheet1.xml")
    for part in ("xl/worksheets/sheet2.xml", "xl/worksheets/sheet4.xml"):
        assert "<drawing r:id=" not in _sheet(result.xlsx, part)
