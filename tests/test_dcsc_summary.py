"""요약표(SectionData/GroupData) 읽기와 금액 가르기.

규칙과 근거는 `quotation/core/dcsc_summary.py` 머리말에 있다. 여기서 지키려는
것은 셋이다.

  1. 소프트웨어 실금액을 자리표 1 원을 뺀 값으로 읽는다
  2. 장비군과 구성을 본체 품번·본체 LP 로 짝짓고, 한 구성은 한 번만 쓴다
  3. 요약표가 없거나 깨졌으면 조용히 포기하고 지금까지의 규칙으로 돌아간다
"""
from __future__ import annotations

import base64
import gzip
from decimal import Decimal

import pytest
from lxml import etree

from quotation.core import dcsc_summary, integrated, modes, xml_reader
from quotation.core.models import HARDWARE, SERVICES, SOFTWARE, LineItem

BODY_PART = "7XXX-CTO1WW"


def line(part: str, price, *, kind: str = HARDWARE, siu: int = 0,
         quantity: int = 1) -> LineItem:
    return LineItem(
        line_number=part, txn_type="NEW", group_id="1000", quantity=quantity,
        part_number=part, description=part, product_type=kind,
        unit_price=None if price is None else Decimal(price), siu=siu)


def body(price="40172000") -> LineItem:
    return line(BODY_PART, price, kind=HARDWARE, siu=1)


def summary_of(prices: dict[str, str], total="40172000") -> dcsc_summary.Summary:
    return dcsc_summary.Summary((dcsc_summary.Config(
        body_part=dcsc_summary.part_key(BODY_PART), total=Decimal(total),
        prices={k: Decimal(v) for k, v in prices.items()}),))


# --- 읽기 ---------------------------------------------------------------------

@pytest.fixture  # 구성은 꺼내 쓰면 없어진다. 시험마다 새로 읽는다.
def parsed(fixtures) -> dcsc_summary.Summary:
    root = etree.fromstring(
        (fixtures / "integrated_summary_quote.xml").read_bytes())
    return dcsc_summary.parse(root)


def test_parse_reads_one_config_per_server(parsed):
    assert len(parsed) == 2


def test_parse_drops_the_placeholder_from_the_software_price(parsed):
    """요약표의 5,440,001 은 실금액 5,440,000 에 자리표 1 원이 붙은 값이다."""
    config = parsed.take(BODY_PART, Decimal("40172000"))
    assert config.prices["7SXXCTOBWW"] == Decimal("5440000")


def test_parse_keeps_the_service_price_as_it_is(parsed):
    """서비스에는 자리표가 붙지 않는다. XML 라인 값과 같아야 한다."""
    config = parsed.take(BODY_PART, Decimal("40172000"))
    assert config.prices["5WS7C00001"] == Decimal("5691000")


def test_parse_takes_the_body_total_from_the_simple_price(parsed):
    """하드웨어 항목의 SimplePrice 가 XML 본체 라인 UnitListPrice 다."""
    assert sorted(c.total for c in [parsed.take(BODY_PART, Decimal("40172000")),
                                    parsed.take(BODY_PART, Decimal("42812000"))]
                  ) == [Decimal("40172000"), Decimal("42812000")]


# --- 짝짓기 -------------------------------------------------------------------

def test_take_matches_a_hyphenated_part_number(parsed):
    """XML 은 `7XXX-CTO1WW`, 요약표는 `7XXXCTO1WW` 로 적는다."""
    assert parsed.take("7XXX-CTO1WW", Decimal("40172000")) is not None


def test_take_allows_a_few_won_of_drift(parsed):
    """자리표 개수와 소수 넷째 자리 반올림 때문에 몇 원이 어긋난다."""
    assert parsed.take(BODY_PART, Decimal("40172005")) is not None


def test_take_refuses_a_different_price(parsed):
    assert parsed.take(BODY_PART, Decimal("40172011")) is None


def test_take_refuses_an_unknown_part(parsed):
    assert parsed.take("9999-CTO1WW", Decimal("40172000")) is None


def test_take_hands_out_each_config_once(parsed):
    """같은 기종 두 대면 구성도 두 벌이다. 한 벌을 두 장비군이 쓰면 안 된다."""
    assert parsed.take(BODY_PART, Decimal("40172000")) is not None
    assert parsed.take(BODY_PART, Decimal("40172000")) is None
    assert parsed.take(BODY_PART, Decimal("42812000")) is not None
    assert not parsed


def test_take_refuses_a_line_without_a_price(parsed):
    assert parsed.take(BODY_PART, None) is None


# --- 못 읽는 문서 --------------------------------------------------------------

@pytest.mark.parametrize("packed", [
    None,                                                   # 요소가 없다
    "",                                                     # 비어 있다
    "!!!not base64!!!",                                     # base64 가 아니다
    base64.b64encode(b"not gzip").decode(),                 # gzip 이 아니다
    base64.b64encode(gzip.compress(b"<hi>")).decode(),      # XML 이 아니다
    base64.b64encode(gzip.compress(b"<x><code>A</code></x>")).decode(),  # 금액이 없다
])
def test_unreadable_group_data_gives_an_empty_summary(packed):
    section = "" if packed is None else f"<SectionData><GroupData>{packed}</GroupData></SectionData>"
    root = etree.fromstring(f"<CFXML><CFData/>{section}</CFXML>".encode())
    assert not dcsc_summary.parse(root)


def test_a_document_without_a_summary_still_converts(fixtures):
    """요약표가 없는 레노버 문서는 지금까지대로 본체 LP 한 줄만 센다."""
    quote = xml_reader.parse_bytes(
        (fixtures / "integrated_quote.xml").read_bytes(), mode=modes.INTEGRATED)
    assert quote.groups[0].amount() == Decimal("40172000")
    assert [i.unit_price for i in quote.groups[0].items] == [
        Decimal("40172000"), None, None]


# --- 금액 가르기 ---------------------------------------------------------------

def test_hardware_takes_what_is_left_over():
    items = (body(), line("7SXX-CTOBWW", "1", kind=SOFTWARE),
             line("5WS7C00001", "5691000", kind=SERVICES))
    folded = integrated.fold_prices(items, summary_of(
        {"7SXXCTOBWW": "5440000", "5WS7C00001": "5691000"}))
    assert [i.unit_price for i in folded] == [
        Decimal("29041000"), Decimal("5440000"), Decimal("5691000")]
    assert sum(i.unit_price for i in folded) == Decimal("40172000")


def test_a_placeholder_only_line_keeps_an_empty_price():
    """Configuration Instruction 처럼 실금액이 0 인 라인은 칸을 비운다."""
    items = (body(), line("5374-CM1", "1", kind=SOFTWARE))
    folded = integrated.fold_prices(items, summary_of({"5374CM1": "0"}))
    assert [i.unit_price for i in folded] == [Decimal("40172000"), None]


def test_a_line_missing_from_the_summary_keeps_an_empty_price():
    """요약표에 없는 라인은 실금액을 알 수 없다. 두 번 세지 않도록 비운다."""
    items = (body(), line("7SXX-CTOBWW", "1", kind=SOFTWARE),
             line("5PS7C00002", "841000", kind=SERVICES))
    folded = integrated.fold_prices(items, summary_of({"7SXXCTOBWW": "5440000"}))
    assert [i.unit_price for i in folded] == [
        Decimal("34732000"), Decimal("5440000"), None]


def test_the_same_part_twice_is_counted_once():
    """앞선 라인이 금액을 가져가고 뒤는 비운다. 장비군 합계는 그대로다."""
    items = (body(), line("5372-SWX", "1", kind=SOFTWARE),
             line("5372-SWX", "1", kind=SOFTWARE))
    folded = integrated.fold_prices(items, summary_of({"5372SWX": "440000"}))
    assert [i.unit_price for i in folded] == [
        Decimal("39732000"), Decimal("440000"), None]


def test_a_negative_remainder_falls_back_to_the_old_rule():
    """남는 값이 음수면 짝을 잘못 지은 것이다. 본체 LP 한 줄만 센다."""
    items = (body(), line("7SXX-CTOBWW", "1", kind=SOFTWARE))
    folded = integrated.fold_prices(items, summary_of({"7SXXCTOBWW": "99999999"}))
    assert [i.unit_price for i in folded] == [Decimal("40172000"), None]


def test_a_group_without_a_body_is_left_alone():
    """랙·PDU 처럼 부품만 있는 그룹은 요약표에도 없고 제 금액을 갖는다."""
    items = (line("90000PX", "8960000", kind=HARDWARE),)
    assert integrated.fold_prices(items, summary_of({})) == items
