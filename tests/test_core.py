"""Phase 2 코어 검증. 기대값은 전부 골든 견적서 실측값이다."""
from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from quotation.core import xml_reader  # noqa: E402
from quotation.core.money import NO_CHARGE, parse_amount, to_decimal  # noqa: E402
from quotation.core.naming import item_key, sheet_name  # noqa: E402
from quotation.core.pricing import (  # noqa: E402
    DiscountError, apply_discount, parse_discount,
)

SAMPLES = ROOT / "samples"
FS5045 = SAMPLES / "FS5045_260722.xml"
XROIS = SAMPLES / "X-ROIS 통합서버#2.xml"


@pytest.fixture(scope="module")
def fs5045():
    return xml_reader.parse(FS5045)


@pytest.fixture(scope="module")
def xrois():
    return xml_reader.parse(XROIS)


# --- money -------------------------------------------------------------------

@pytest.mark.parametrize("raw,expected", [
    ("88,971.5", Decimal("88971.5")),
    ("796275.83", Decimal("796275.83")),
    ("0", Decimal("0")),
    ("N/C", NO_CHARGE),
    ("n/c", NO_CHARGE),
    ("", None),
    (None, None),
])
def test_parse_amount(raw, expected):
    assert parse_amount(raw) == expected


def test_parse_amount_preserves_scale():
    # 소수 자릿수가 바뀌면 골든 셀 값과 어긋난다.
    assert str(parse_amount("88,971.50")) == "88971.50"
    assert str(parse_amount("309")) == "309"


def test_no_charge_folds_to_zero_in_sums():
    assert to_decimal(NO_CHARGE) == 0
    assert to_decimal(None) == 0


def test_parse_amount_rejects_garbage():
    with pytest.raises(ValueError):
        parse_amount("가격미정")


# --- naming (SPEC_CELLMAP.md §2.1) -------------------------------------------

@pytest.mark.parametrize("desc,key,sheet", [
    ("4680-3P4 #1:IBM Storage FlashSystem 5045 SFF Control Enclosure",
     "4680-3P4 #1", "4680-3P4 #1"),
    ("Server 1:Server 1:9080 Model HEX", "Server 1", "SERVER 1"),
    ("IBM Expert Labs Project Unit for IBM Power Systems",
     "Expert Labs Project Unit fo", "EXPERT LABS PROJECT UNIT FO"),
])
def test_item_key_and_sheet_name(desc, key, sheet):
    assert item_key(desc) == key
    assert sheet_name(item_key(desc)) == sheet


def test_item_key_truncates_at_27():
    assert len(item_key("IBM Expert Labs Project Unit for IBM Power Systems")) == 27


# --- 파싱 --------------------------------------------------------------------

def test_fs5045_structure(fs5045):
    assert fs5045.document_id == "CFXML.FS5045.2026-07-22T00:00:00+00:00"
    assert fs5045.price_file_date == "2026-07-22"
    assert [g.group_id for g in fs5045.groups] == ["1000", "4000", "7000"]
    assert [g.sheet_name for g in fs5045.groups] == [
        "4680-3P4 #1", "4680-3P4 #3", "4680-3P2 #5",
    ]
    assert sum(len(g.items) for g in fs5045.groups) == 9


def test_xrois_structure(xrois):
    assert [g.group_id for g in xrois.groups] == ["1000", "2000"]
    assert [g.sheet_name for g in xrois.groups] == [
        "EXPERT LABS PROJECT UNIT FO", "SERVER 1",
    ]
    assert sum(len(g.items) for g in xrois.groups) == 14


def test_transaction_types_are_new_and_add(fs5045):
    assert {i.txn_type for g in fs5045.groups for i in g.items} == {"NEW"}
    assert {s.txn_type
            for g in fs5045.groups for i in g.items for s in i.subs} == {"ADD"}


def test_shipping_is_parsed_but_unused(fs5045):
    # 견적서에는 반영되지 않는다 (SPEC_CELLMAP.md §7-6). 파싱만 해 둔다.
    assert fs5045.shipping is not None
    assert fs5045.shipping.amount == Decimal("1826.9")
    assert fs5045.shipping.currency == "KWON"


# --- 금액 계산: 골든 TOTAL 시트 G열 대조 ---------------------------------------

def test_fs5045_group_amounts_match_golden(fs5045):
    """골든 TOTAL 시트 G8 / G12 / G16."""
    expected = [Decimal("796275.83"), Decimal("209054.67"), Decimal("190670.29")]
    assert [g.amount() for g in fs5045.groups] == expected


def test_fs5045_grand_total_matches_golden(fs5045):
    """골든 TOTAL!G20 = 1,196,001 (표시값). 원값은 세 그룹 합."""
    assert fs5045.total_amount() == Decimal("1196000.79")


def test_fs5045_first_group_hardware_block_matches_golden(fs5045):
    """골든 '4680-3P4 #1' 시트 G20 = SUM(G8:G19) = 718,661 (표시값)."""
    first = fs5045.groups[0].items[0]
    assert first.amount() == Decimal("718660.5")


def test_xrois_group_amounts_match_golden(xrois):
    """골든 TOTAL 시트: G8(그룹1) / G23(그룹2 합계행)."""
    assert xrois.groups[0].amount() == Decimal("11800")
    assert xrois.groups[1].amount() == Decimal("5979442.0")


def test_xrois_total_sheet_section_subtotals_match_golden(xrois):
    """TOTAL 은 그룹을 H/W·S/W 구간으로 나눠 각각 병합 셀에 소계를 넣는다.

    골든: G10:G12 = 5,378,973.5 (H/W) / G13:G22 = 600,468.5 (S/W)
    """
    server = xrois.groups[1]
    assert server.hardware_amount() == Decimal("5378973.5")
    assert server.software_amount() == Decimal("600468.5")
    assert server.hardware_amount() + server.software_amount() == server.amount()
    assert [kind for kind, _ in server.sections()] == ["Hardware", "Software"]


def test_fs5045_software_section_is_all_no_charge(fs5045):
    """FS5045 는 S/W 소계가 0 이라 골든에서 해당 병합 셀이 비어 있다."""
    for g in fs5045.groups:
        assert g.software_amount() == 0
        assert g.hardware_amount() == g.amount()


def test_subline_quantity_multiplies_parent(fs5045):
    """서브 수량은 부모 1대당 수량. 셀 수식 '=12*E8' 과 같은 의미."""
    parent = fs5045.groups[0].items[0]
    al80 = next(s for s in parent.subs if s.part_number == "AL80")
    assert al80.quantity == 12
    assert al80.amount(parent_quantity=1) == Decimal("592548")
    assert al80.amount(parent_quantity=3) == Decimal("1777644")


# --- MA (SPEC_CELLMAP.md §4.3) -----------------------------------------------

def test_xrois_maintenance_matches_golden(xrois):
    """골든 TOTAL!H10 = 309, SERVER 1!H51 = 309."""
    server = xrois.groups[1]
    assert server.maintenance_amount() == Decimal("309")
    assert server.has_maintenance()

    line3000 = next(i for i in server.items if i.line_number == "3000")
    assert line3000.maintenance == Decimal("309")
    assert line3000.maintenance_term == "Y"


def test_maintenance_is_not_multiplied_by_quantity(xrois):
    """MA 는 수량을 곱하지 않는다."""
    line3000 = next(i for i in xrois.groups[1].items if i.line_number == "3000")
    object.__setattr__(line3000, "quantity", 5)  # 수량만 바꿔도
    assert line3000.maintenance_amount() == Decimal("309")  # MA 는 그대로


def test_fs5045_has_no_maintenance(fs5045):
    """MA 가 없는 그룹은 H 셀을 비운다."""
    assert fs5045.total_maintenance() == 0
    assert not any(g.has_maintenance() for g in fs5045.groups)


# --- 하드웨어/소프트웨어 분류 ---------------------------------------------------

def test_services_are_grouped_with_software(xrois):
    """X-ROIS 6911-301 은 Services 이고 골든 'EXPERT LABS' 시트 B8 = "S/W"."""
    expert = xrois.groups[0]
    assert expert.items[0].product_type == "Services"
    assert not expert.items[0].is_hardware
    assert len(expert.hardware) == 0
    assert [kind for kind, _ in expert.sections()] == ["Software"]


def test_xrois_server_hw_sw_split(xrois):
    """골든 SERVER 1 시트: H/W 섹션 B8:B67, S/W 섹션 B68:B104."""
    server = xrois.groups[1]
    assert [i.part_number for i in server.hardware] == [
        "9080-HEX", "7226-1U3", "5313-HPO",
    ]
    assert len(server.software) == 10


# --- 오류 처리 ----------------------------------------------------------------

def test_missing_cfxml_root(tmp_path):
    p = tmp_path / "bad.xml"
    p.write_text("<Other><CFData/></Other>", encoding="utf-8")
    with pytest.raises(xml_reader.QuotationXmlError, match="CFXML을 찾을수 없습니다"):
        xml_reader.parse(p)


def test_missing_cfdata(tmp_path):
    p = tmp_path / "bad.xml"
    p.write_text("<CFXML></CFXML>", encoding="utf-8")
    with pytest.raises(xml_reader.QuotationXmlError, match="CFData을 찾을수 없습니다"):
        xml_reader.parse(p)


def test_missing_line_items(tmp_path):
    p = tmp_path / "bad.xml"
    p.write_text("<CFXML><CFData/></CFXML>", encoding="utf-8")
    with pytest.raises(xml_reader.QuotationXmlError, match="Item을 찾을 수 없습니다"):
        xml_reader.parse(p)


def test_reference_only_document_is_rejected(tmp_path):
    """BASE/PROPOSED 뿐이면 견적할 것이 없다."""
    p = tmp_path / "ref.xml"
    p.write_text(
        "<CFXML><CFData>"
        "<ProductLineItem><ProductLineNumber>1000</ProductLineNumber>"
        "<TransactionType>BASE</TransactionType></ProductLineItem>"
        "<ProductLineItem><ProductLineNumber>2000</ProductLineNumber>"
        "<TransactionType>PROPOSED</TransactionType></ProductLineItem>"
        "</CFData></CFXML>", encoding="utf-8")
    with pytest.raises(xml_reader.QuotationXmlError, match="Item을 찾을 수 없습니다"):
        xml_reader.parse(p)


def test_malformed_xml(tmp_path):
    p = tmp_path / "bad.xml"
    p.write_text("<CFXML><CFData>", encoding="utf-8")
    with pytest.raises(xml_reader.QuotationXmlError, match="장애 발생"):
        xml_reader.parse(p)


def test_euckr_xml_is_accepted(tmp_path):
    """2005년 형식(EUC-KR) 도 계속 읽혀야 한다."""
    p = tmp_path / "euckr.xml"
    body = (
        '<?xml version="1.0" encoding="EUC-KR"?>'
        "<CFXML><CFData><ProductLineItem>"
        "<ProductLineNumber>1000</ProductLineNumber>"
        "<TransactionType>NEW</TransactionType>"
        "<ProprietaryGroupIdentifier>1000</ProprietaryGroupIdentifier>"
        "<Quantity>1</Quantity>"
        "<ProductIdentification><PartnerProductIdentification>"
        "<ProprietaryProductIdentifier>1234-567</ProprietaryProductIdentifier>"
        "<ProductDescription>서버 1:한글 설명</ProductDescription>"
        "<ProductTypeCode>Hardware</ProductTypeCode>"
        "</PartnerProductIdentification></ProductIdentification>"
        "<UnitListPrice><FinancialAmount>"
        "<GlobalCurrencyCode>KWON</GlobalCurrencyCode>"
        "<MonetaryAmount>1,000.5</MonetaryAmount>"
        "</FinancialAmount><PriceTerm>0</PriceTerm></UnitListPrice>"
        "</ProductLineItem></CFData></CFXML>"
    )
    p.write_bytes(body.encode("euc-kr"))
    q = xml_reader.parse(p)
    assert q.groups[0].items[0].description == "서버 1:한글 설명"
    assert q.groups[0].item_key == "서버 1"
    assert q.total_amount() == Decimal("1000.5")


def test_xxe_is_blocked(tmp_path):
    """외부 엔티티가 확장되면 안 된다."""
    secret = tmp_path / "secret.txt"
    secret.write_text("TOPSECRET", encoding="utf-8")
    p = tmp_path / "xxe.xml"
    p.write_text(
        '<?xml version="1.0"?>'
        f'<!DOCTYPE CFXML [<!ENTITY xxe SYSTEM "file:///{secret.as_posix()}">]>'
        "<CFXML><CFData><ProductLineItem>"
        "<ProductLineNumber>&xxe;</ProductLineNumber>"
        "</ProductLineItem></CFData></CFXML>",
        encoding="utf-8",
    )
    try:
        q = xml_reader.parse(p)
    except xml_reader.QuotationXmlError:
        return  # 파싱 거부도 정상
    assert "TOPSECRET" not in str(q.groups[0].items[0].line_number)


# --- 할인율 ------------------------------------------------------------------

@pytest.mark.parametrize("raw,expected", [
    ("", Decimal(0)), (None, Decimal(0)),
    ("10", Decimal("10")), ("25.5", Decimal("25.5")),
    ("99", Decimal("99")), ("0.1", Decimal("0.1")), ("15%", Decimal("15")),
])
def test_parse_discount_ok(raw, expected):
    assert parse_discount(raw) == expected


def test_discount_over_99_rejected():
    with pytest.raises(DiscountError, match="99보다 클수 없습니다"):
        parse_discount("99.1")


def test_discount_two_decimals_rejected():
    with pytest.raises(DiscountError, match="소숫점 1자리만"):
        parse_discount("10.25")


def test_apply_discount():
    assert apply_discount(Decimal("1000"), Decimal("25.5")) == Decimal("745.000")
    assert apply_discount(Decimal("1000"), Decimal(0)) == Decimal("1000")
