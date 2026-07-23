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
XP_SIU = "./CPUSIUvalue"
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
        siu=_int(el, XP_SIU, default=0),
    )


def _reference_names(items: list[LineItem]) -> list[str]:
    """증설 견적의 장비 이름. 기존(BASE)/증설후(PROPOSED) 구성의 본체 라인에서 딴다.

    증설 라인(UPGRADE)의 Description 은 '9080 Model HEU' 처럼 장비 이름이 없다.
    골든은 시트를 'SERVER 1' 로 부르는데, 그 이름은 BASE 구성의 본체 라인
    'Server 1:Server 1:IBM Power E1080' 에서 온다.
    """
    seen: set[str] = set()
    names: list[str] = []
    for it in items:
        if it.is_reference and it.siu == 1:
            key = item_key(it.description)
            if key not in seen:
                seen.add(key)
                names.append(key)
    return names


def _build_groups(items: list[LineItem],
                  reference_names: list[str]) -> tuple[Group, ...]:
    """ProprietaryGroupIdentifier 로 묶는다. 문서 등장 순서를 유지한다.

    증설 견적일 때만 두 가지 보정이 붙는다.
      - 본체 라인(CPUSIUvalue=1)이 없는 그룹을 앞 그룹에 합친다. 증설은 장비
        한 대에 대한 변경이라 UPGRADE/DISCO/NEW 가 한 장에 나온다.
      - 장비 이름을 BASE/PROPOSED 구성에서 가져온다.

    신규 견적에서는 합치지 않는다. TS4300 골든의 'No CPUSIU for the following
    products' 그룹은 본체 라인이 없어도 제 장을 갖는다.
    """
    is_upgrade = bool(reference_names)

    ordered: list[str] = []
    buckets: dict[str, list[LineItem]] = {}
    for it in items:
        key = it.group_id or it.line_number
        if key not in buckets:
            buckets[key] = []
            ordered.append(key)
        buckets[key].append(it)

    merged: list[str] = []
    for gid in ordered:
        has_body = any(i.siu == 1 for i in buckets[gid])
        if is_upgrade and merged and not has_body:
            buckets[merged[-1]].extend(buckets[gid])
        else:
            merged.append(gid)

    groups: list[Group] = []
    taken: set[str] = set()
    for index, gid in enumerate(merged):
        members = buckets[gid]
        if index < len(reference_names):
            key = reference_names[index]
        else:
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

    all_items = [_parse_line(e) for e in elements]
    # 증설 견적은 기존(BASE)·증설후(PROPOSED) 구성을 참조용으로 함께 담는다.
    # 견적서에는 실제 증설분만 넣는다.
    quoted = [i for i in all_items if not i.is_reference]
    if not quoted:
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
        groups=_build_groups(quoted, _reference_names(all_items)),
    )
