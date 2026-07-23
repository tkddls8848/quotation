"""eConfig XML 파서 — SPEC_CELLMAP.md §1.

원본 VB6 프로그램의 XPath 를 그대로 사용하되 다음을 현대화했다.
  - 인코딩: EUC-KR 하드코딩 -> 선언 인코딩 자동 판별 (UTF-8/EUC-KR 모두 수용)
  - DTD: 인라인 DTD 가 존재하므로 XXE 차단 설정으로 파싱
  - 금액: 콤마 포함 문자열과 "N/C" 리터럴 처리 (money.py)
"""
from __future__ import annotations

from pathlib import Path

from lxml import etree

from .models import Group, LineItem, Quotation, Shipping, SubLineItem
from .money import parse_amount
from .naming import item_key, unique_sheet_name

# --- 원본 프로그램의 XPath (변경 금지) ---------------------------------------
XP_CFDATA = "./CFData"
XP_LINE_ITEM = ".//ProductLineItem"
XP_SUB_LINE_ITEM = "./ProductSubLineItem"

XP_LINE_NUMBER = "./ProductLineNumber"
XP_TXN_TYPE = "./TransactionType"
XP_GROUP_ID = "./ProprietaryGroupIdentifier"
XP_QUANTITY = "./Quantity"
XP_DESC = "./ProductIdentification/PartnerProductIdentification/ProductDescription"
XP_TYPE_CODE = "./ProductIdentification/PartnerProductIdentification/ProductTypeCode"
XP_PART_NO = ("./ProductIdentification/PartnerProductIdentification"
              "/ProprietaryProductIdentifier")
XP_CURRENCY = "./UnitListPrice/FinancialAmount/GlobalCurrencyCode"
XP_AMOUNT = "./UnitListPrice/FinancialAmount/MonetaryAmount"
XP_PRICE_TERM = "./UnitListPrice/PriceTerm"
XP_MA_CURRENCY = "./MaintenanceUnitListPrice/FinancialAmount/GlobalCurrencyCode"
XP_MA_AMOUNT = "./MaintenanceUnitListPrice/FinancialAmount/MonetaryAmount"
XP_MA_TERM = "./MaintenanceUnitListPrice/PriceTerm"

XP_SUB_LINE_NUMBER = "./LineNumber"


class QuotationXmlError(Exception):
    """XML 이 견적서 생성 요건을 만족하지 않을 때. 메시지는 원본 프로그램과 동일하다."""


def _text(el, path: str) -> str:
    node = el.find(path)
    if node is None or node.text is None:
        return ""
    return node.text.strip()


def _int(el, path: str, default: int = 1) -> int:
    raw = _text(el, path).replace(",", "")
    if not raw:
        return default
    try:
        return int(float(raw))
    except ValueError:
        return default


def _parse_sub(el) -> SubLineItem:
    return SubLineItem(
        line_number=_text(el, XP_SUB_LINE_NUMBER),
        txn_type=_text(el, XP_TXN_TYPE),
        quantity=_int(el, XP_QUANTITY),
        part_number=_text(el, XP_PART_NO),
        description=_text(el, XP_DESC),
        unit_price=parse_amount(_text(el, XP_AMOUNT) or None),
        maintenance=parse_amount(_text(el, XP_MA_AMOUNT) or None),
    )


def _parse_line(el) -> LineItem:
    return LineItem(
        line_number=_text(el, XP_LINE_NUMBER),
        txn_type=_text(el, XP_TXN_TYPE),
        group_id=_text(el, XP_GROUP_ID),
        quantity=_int(el, XP_QUANTITY),
        part_number=_text(el, XP_PART_NO),
        description=_text(el, XP_DESC),
        product_type=_text(el, XP_TYPE_CODE),
        unit_price=parse_amount(_text(el, XP_AMOUNT) or None),
        price_term=_text(el, XP_PRICE_TERM),
        maintenance=parse_amount(_text(el, XP_MA_AMOUNT) or None),
        maintenance_term=_text(el, XP_MA_TERM),
        subs=tuple(_parse_sub(s) for s in el.findall(XP_SUB_LINE_ITEM)),
    )


def _build_groups(items: list[LineItem]) -> tuple[Group, ...]:
    """ProprietaryGroupIdentifier 로 묶는다. 문서 등장 순서를 유지한다."""
    ordered: list[str] = []
    buckets: dict[str, list[LineItem]] = {}
    for it in items:
        key = it.group_id or it.line_number
        if key not in buckets:
            buckets[key] = []
            ordered.append(key)
        buckets[key].append(it)

    groups: list[Group] = []
    taken: set[str] = set()
    for gid in ordered:
        members = buckets[gid]
        key = item_key(members[0].description)
        name = unique_sheet_name(key, taken)
        taken.add(name)
        groups.append(Group(group_id=gid, item_key=key, sheet_name=name,
                            items=tuple(members)))
    return tuple(groups)


def _parse_shipping(cfdata) -> Shipping | None:
    el = cfdata.find("./ProprietaryShippingInformation")
    if el is None:
        return None
    return Shipping(
        name=_text(el, "./Name"),
        currency=_text(el, "./FinancialAmount/GlobalCurrencyCode"),
        amount=parse_amount(_text(el, "./FinancialAmount/MonetaryAmount") or None),
    )


def _proprietary_info(cfdata) -> dict[str, str]:
    out: dict[str, str] = {}
    for el in cfdata.findall("./ProprietaryInformation"):
        out[_text(el, "./Name")] = _text(el, "./Value")
    return out


def parse(source: str | Path) -> Quotation:
    """eConfig XML 파일 -> Quotation.

    Raises:
        QuotationXmlError: 로드 실패 또는 필수 노드 누락.
    """
    parser = etree.XMLParser(
        load_dtd=False,        # 인라인 DTD 를 읽되 외부 참조는 하지 않는다
        resolve_entities=False,  # XXE 차단
        no_network=True,
        huge_tree=False,
        recover=False,
    )
    try:
        tree = etree.parse(str(source), parser)
    except etree.XMLSyntaxError as exc:
        raise QuotationXmlError(f"XML을 로드하는중 장애 발생. 장애코드: {exc}") from exc

    root = tree.getroot()
    if root is None or etree.QName(root).localname != "CFXML":
        raise QuotationXmlError("CFXML을 찾을수 없습니다.")

    cfdata = root.find(XP_CFDATA)
    if cfdata is None:
        raise QuotationXmlError("CFData을 찾을수 없습니다.")

    elements = cfdata.findall(XP_LINE_ITEM)
    if not elements:
        raise QuotationXmlError("견적서 작성을 위한 Item을 찾을 수 없습니다.")

    info = _proprietary_info(cfdata)
    return Quotation(
        document_id=_text(root, "./thisDocumentIdentifier"
                                "/ProprietaryDocumentIdentifier"),
        generated_time=_text(root, "./thisDocumentGenerationDateTime/DateTimeStamp"),
        price_file_date=info.get("Price File Date", ""),
        configurator_id=info.get("Configurator Identifier", ""),
        checksum=info.get("Checksum", ""),
        shipping=_parse_shipping(cfdata),
        groups=_build_groups([_parse_line(e) for e in elements]),
    )
