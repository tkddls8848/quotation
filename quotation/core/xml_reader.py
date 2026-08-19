"""eConfig XML 파서."""
from __future__ import annotations

import codecs
import re
from pathlib import Path

from lxml import etree

from . import integrated, modes
from .models import Group, LineItem, Quotation, SubLineItem
from .money import parse_amount
from .naming import item_key, safe_sheet_name, sheet_name, unique_sheet_names

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
XP_PRODUCT_NAME = "./ProductIdentification/PartnerProductIdentification/ProductName"
XP_TYPE_CODE = "./ProductIdentification/PartnerProductIdentification/ProductTypeCode"
XP_PART_NO = ("./ProductIdentification/PartnerProductIdentification"
              "/ProprietaryProductIdentifier")
XP_AMOUNT = "./UnitListPrice/FinancialAmount/MonetaryAmount"


class QuotationXmlError(Exception):
    """XML 이 견적서 생성 요건을 만족하지 않을 때. 메시지는 원본 프로그램과 동일하다."""


def _text(el, path: str) -> str:
    node = el.find(path)
    if node is None or node.text is None:
        return ""
    return node.text.strip()


def _int(el, path: str, default: int = 1) -> int:
    return int(_text(el, path) or default)


def _parse_sub(el) -> SubLineItem:
    return SubLineItem(
        txn_type=_text(el, XP_TXN_TYPE),
        quantity=_int(el, XP_QUANTITY),
        part_number=_text(el, XP_PART_NO),
        description=_text(el, XP_DESC),
        unit_price=parse_amount(_text(el, XP_AMOUNT) or None),
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
        product_name=_text(el, XP_PRODUCT_NAME),
        unit_price=parse_amount(_text(el, XP_AMOUNT) or None),
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


def _build_groups(items: list[LineItem], reference_names: list[str],
                  mode: str = modes.DEFAULT) -> tuple[Group, ...]:
    """ProprietaryGroupIdentifier 로 묶는다. 문서 등장 순서를 유지한다.

    증설 견적일 때만 두 가지 보정이 붙는다.
      - 본체 라인(CPUSIUvalue=1)이 없는 그룹을 앞 그룹에 합친다. 증설은 장비
        한 대에 대한 변경이라 UPGRADE/DISCO/NEW 가 한 장에 나온다.
      - 장비 이름을 BASE/PROPOSED 구성에서 가져온다.

    신규 견적에서는 합치지 않는다. TS4300 골든의 'No CPUSIU for the following
    products' 그룹은 본체 라인이 없어도 제 장을 갖는다.

    통합 모드는 여기서 두 가지가 갈린다 (근거는 `integrated.py`).
      - 장비 이름을 ProductName 에서 딴다.
      - 본체 LP 에 이미 들어 있는 소프트웨어·서비스 금액을 비운다.
      - 시트명의 금칙 문자를 걷어 내고 겹치는 이름을 갈라 준다.
    """
    is_upgrade = bool(reference_names)
    is_integrated = mode == modes.INTEGRATED

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

    keys: list[str] = []
    members_by_group: list[tuple[LineItem, ...]] = []
    for index, gid in enumerate(merged):
        members = tuple(buckets[gid])
        if is_integrated:
            members = integrated.fold_prices(members)
            key = integrated.group_key(members)
        elif index < len(reference_names):
            key = reference_names[index]
        else:
            key = item_key(members[0].description)
        keys.append(key)
        members_by_group.append(members)

    if is_integrated:
        titles = [sheet_name(k) for k in keys]
        names = unique_sheet_names([safe_sheet_name(k) for k in keys])
    else:
        titles = [""] * len(keys)
        names = [sheet_name(k) for k in keys]

    return tuple(
        Group(group_id=gid, item_key=key, sheet_name=name, title=title,
              items=members)
        for gid, key, name, title, members
        in zip(merged, keys, names, titles, members_by_group)
    )


def _parser() -> etree.XMLParser:
    """외부 참조를 하지 않는 파서.

    인라인 DTD 가 있는 2005년 형식 문서도 읽어야 하므로 문서를 거부하지는 않되,
    엔티티 확장과 네트워크 접근은 막는다.
    """
    return etree.XMLParser(
        load_dtd=False,          # 인라인 DTD 를 읽되 외부 참조는 하지 않는다
        resolve_entities=False,  # XXE 차단
        no_network=True,
        dtd_validation=False,
        huge_tree=False,         # 깊이·크기 폭주 문서 거부
        recover=False,
    )


#: XML 선언의 encoding 값. 선언은 규격상 문서 맨 앞에만 올 수 있다.
_DECLARED_ENCODING = re.compile(
    r'\A(<\?xml[^>]*?encoding\s*=\s*["\'])([A-Za-z0-9_.:+-]+)(["\'])')


def _utf8_equivalent(raw: bytes) -> bytes | None:
    """libxml2 가 모르는 인코딩의 문서를 뜻이 같은 UTF-8 문서로 옮긴다.

    libxml2 는 빌드에 iconv 가 없으면 EUC-KR 같은 인코딩을 거부한다. Pyodide
    (Cloudflare Python Worker, 브라우저 엔진)의 libxml2 가 그렇다.

        XMLSyntaxError: Unsupported encoding EUC-KR, line 1, column 38

    파이썬 표준 코덱은 그 인코딩들을 모두 안다. 그래서 **파싱이 아예 안 되는
    경우에 한해** 파이썬으로 디코딩해 UTF-8 로 다시 적는다. 문자는 하나도
    바뀌지 않으므로 파서가 보는 문서는 데스크톱(iconv 있는 libxml2)이 보는
    것과 같다. 이미 읽히는 문서에는 이 경로가 닿지 않는다.

    Returns:
        옮긴 바이트. 선언이 없거나 파이썬도 모르는 인코딩이면 None.
    """
    head = raw[:512].decode("ascii", "replace")
    match = _DECLARED_ENCODING.match(head)
    if not match:
        return None

    name = match.group(2)
    if name.lower().replace("-", "_") in ("utf_8", "utf8", "us_ascii", "ascii"):
        return None  # libxml2 가 이미 아는 인코딩이라면 다른 이유로 실패한 것이다
    try:
        codec = codecs.lookup(name)
    except LookupError:
        return None

    try:
        text = codec.decode(raw)[0]
    except (UnicodeDecodeError, ValueError):
        return None

    # 선언만 UTF-8 로 고친다. 본문은 손대지 않는다.
    return _DECLARED_ENCODING.sub(
        lambda m: f'{m.group(1)}UTF-8{m.group(3)}', text, count=1).encode("utf-8")


def parse(source: str | Path, *, mode: str = modes.DEFAULT) -> Quotation:
    """eConfig XML 파일 -> Quotation. (데스크톱 경로 입력)

    Args:
        mode: 문서를 읽는 방식. `modes.UNIX` 또는 `modes.INTEGRATED`.

    Raises:
        QuotationXmlError: 로드 실패 또는 필수 노드 누락.
    """
    try:
        tree = etree.parse(str(source), _parser())
    except etree.XMLSyntaxError as exc:
        try:
            raw = Path(source).read_bytes()
        except OSError:
            raw = b""  # 다시 읽을 수 없으면 처음 오류 그대로 알린다
        return _build(_retry_as_utf8(raw, exc), mode)
    return _build(tree.getroot(), mode)


def _retry_as_utf8(raw: bytes, original: "etree.XMLSyntaxError"):
    """인코딩 때문에 막힌 것이면 UTF-8 로 옮겨 한 번만 다시 읽는다.

    다시 읽어도 안 되면 **처음 오류 그대로** 알린다. 사용자가 보는 문구는
    원본 프로그램과 같아야 하고, 대체 경로가 있다는 사실이 드러나면 안 된다.
    """
    retry = _utf8_equivalent(raw)
    if retry is not None:
        try:
            return etree.fromstring(retry, _parser())
        except etree.XMLSyntaxError:
            pass
    raise QuotationXmlError(
        f"XML을 로드하는중 장애 발생. 장애코드: {original}") from original


def parse_bytes(data: bytes, *, mode: str = modes.DEFAULT) -> Quotation:
    """eConfig XML 바이트 -> Quotation. (웹 업로드 입력)

    파일시스템을 건드리지 않는다. 인코딩은 XML 선언을 따르므로 UTF-8 과
    EUC-KR 문서를 모두 그대로 받는다. 문자열이 아니라 **바이트** 를 넘겨야
    선언된 인코딩이 존중된다.

    Raises:
        QuotationXmlError: 로드 실패 또는 필수 노드 누락.
    """
    raw = bytes(data)
    if not raw.strip():
        raise QuotationXmlError("XML을 로드하는중 장애 발생. 장애코드: 빈 화일입니다.")
    try:
        root = etree.fromstring(raw, _parser())
    except etree.XMLSyntaxError as exc:
        root = _retry_as_utf8(raw, exc)
    return _build(root, mode)


def _build(root, mode: str = modes.DEFAULT) -> Quotation:
    """파싱된 문서 뿌리 -> Quotation. 경로 입력과 바이트 입력의 공통 경로다."""
    if etree.QName(root).localname != "CFXML":
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

    return Quotation(
        groups=_build_groups(quoted, _reference_names(all_items), mode))
