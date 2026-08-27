"""파이썬 `xml_reader` 와 Rust 이식본을 같은 문서로 대조한다.

계획 §Phase 2 의 동등성 판정 — **fixture 의 파싱 결과가 파이썬 모델과 같은가.**
그룹으로 묶기 전, 문서에서 읽어 낸 라인 하나하나를 필드 단위로 비교한다.

    python tools/rust_parity_xml_reader.py

대조 자료는 세 갈래다.

1. `tests/fixtures/public/` 의 골든 fixture 6종 (신규·증설·N/C·EUC-KR·통합 둘).
2. 저장소에 실제 구성 XML 이 놓여 있으면 그것도 함께 (있을 때만).
3. 거절해야 하는 문서 — 빈 파일, 뿌리 없음, CFData 없음, 품목 없음, 참조뿐,
   구문 오류, 외부 엔티티. **거절 문구까지 비교한다.**
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from quotation.core import xml_reader  # noqa: E402
from quotation.core.money import NO_CHARGE  # noqa: E402

PROBE = ("cargo", "run", "--quiet", "--package", "quotation-parity",
         "--bin", "xml-reader-probe")

FIXTURES = ROOT / "tests" / "fixtures" / "public"

#: 파서가 거절해야 하는 문서. 이름은 보고용이다.
REJECTED = {
    "빈 파일": b"",
    "공백뿐": b"  \n\t ",
    "뿌리가 CFXML 이 아님": b"<Other><CFData/></Other>",
    "CFData 없음": b"<CFXML></CFXML>",
    "품목 없음": b"<CFXML><CFData/></CFXML>",
    "참조 구성뿐": (b"<CFXML><CFData>"
                b"<ProductLineItem><TransactionType>BASE</TransactionType></ProductLineItem>"
                b"<ProductLineItem><TransactionType>PROPOSED</TransactionType></ProductLineItem>"
                b"</CFData></CFXML>"),
    "닫히지 않은 태그": b"<CFXML><CFData>",
    "품목 상한 초과": (b"<CFXML><CFData>"
                 + b"<ProductLineItem><TransactionType>NEW</TransactionType></ProductLineItem>"
                 * (xml_reader.MAX_QUOTATION_ITEMS + 1)
                 + b"</CFData></CFXML>"),
}

#: 외부 엔티티를 펼치지 않는지 본다. 문서 자체는 거절하지 않는다.
XXE = ("""<?xml version="1.0"?>
<!DOCTYPE CFXML [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>
<CFXML><CFData><ProductLineItem>
    <TransactionType>NEW</TransactionType>
    <ProductIdentification><PartnerProductIdentification>
        <ProductDescription>before&xxe;after</ProductDescription>
    </PartnerProductIdentification></ProductIdentification>
</ProductLineItem></CFData></CFXML>""").encode("utf-8")


def documents() -> dict[str, bytes]:
    """읽혀야 하는 문서."""
    found = {path.name: path.read_bytes() for path in sorted(FIXTURES.glob("*.xml"))}
    for path in sorted(ROOT.glob("*.xml")):
        found[path.name] = path.read_bytes()
    found["외부 엔티티"] = XXE
    return found


def amount_repr(amount) -> str:
    """[결정 0006] 금액은 지수 없는 자릿수 표기로 비교한다."""
    if amount is NO_CHARGE:
        return "nocharge"
    if amount is None:
        return "missing"
    return f"priced:{format(amount, 'f')}"


def python_items(data: bytes) -> dict:
    """파이썬으로 읽은 라인. 그룹으로 묶기 전 상태다."""
    try:
        root = _root(data)
        cfdata = root.find(xml_reader.XP_CFDATA)
        if cfdata is None:
            raise xml_reader.QuotationXmlError("CFData을 찾을수 없습니다.")
        elements = cfdata.findall(xml_reader.XP_LINE_ITEM)
        if not elements:
            raise xml_reader.QuotationXmlError("견적서 작성을 위한 Item을 찾을 수 없습니다.")
        count = len(elements) + sum(
            len(element.findall(xml_reader.XP_SUB_LINE_ITEM)) for element in elements)
        if count > xml_reader.MAX_QUOTATION_ITEMS:
            raise xml_reader.QuotationXmlError(
                f"구성 품목이 너무 많습니다. (최대 {xml_reader.MAX_QUOTATION_ITEMS:,}건)")
        items = [xml_reader._parse_line(element) for element in elements]
        if all(item.is_reference for item in items):
            raise xml_reader.QuotationXmlError("견적서 작성을 위한 Item을 찾을 수 없습니다.")
    except xml_reader.QuotationXmlError as error:
        return {"ok": False, "error": str(error)}
    return {"ok": True, "items": [_line(item) for item in items]}


def _root(data: bytes):
    """`xml_reader` 와 같은 순서로 읽는다 (EUC-KR 재시도 포함)."""
    from lxml import etree

    if not data.strip():
        raise xml_reader.QuotationXmlError(
            "XML을 로드하는중 장애 발생. 장애코드: 빈 화일입니다.")
    try:
        root = etree.fromstring(data, xml_reader._parser())
    except etree.XMLSyntaxError as exc:
        root = xml_reader._retry_as_utf8(data, exc)
    if etree.QName(root).localname != "CFXML":
        raise xml_reader.QuotationXmlError("CFXML을 찾을수 없습니다.")
    return root


def _line(item) -> dict:
    return {
        "line_number": item.line_number,
        "txn_type": item.txn_type,
        "group_id": item.group_id,
        "quantity": item.quantity,
        "part_number": item.part_number,
        "description": item.description,
        "product_type": item.product_type,
        "product_name": item.product_name,
        "unit_price": amount_repr(item.unit_price),
        "siu": item.siu,
        "subs": [{
            "txn_type": sub.txn_type,
            "quantity": sub.quantity,
            "part_number": sub.part_number,
            "description": sub.description,
            "unit_price": amount_repr(sub.unit_price),
        } for sub in item.subs],
    }


def rust_items(data: bytes) -> dict:
    result = subprocess.run(PROBE, cwd=ROOT, input=data,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if result.returncode != 0:
        sys.stderr.write(result.stderr.decode("utf-8", "replace"))
        raise SystemExit(f"Rust 탐침이 {result.returncode} 로 끝났습니다.")
    return json.loads(result.stdout.decode("utf-8"))


def compare(name: str, data: bytes, *, expect_error: bool) -> list[str]:
    """다른 곳만 사람이 읽을 수 있는 줄로 돌려준다."""
    want = python_items(data)
    got = rust_items(data)
    if want["ok"] != got["ok"]:
        return [f"{name}: 파이썬 {'통과' if want['ok'] else '거절'}, "
                f"Rust {'통과' if got['ok'] else '거절'} "
                f"({want.get('error') or got.get('error')})"]
    if not want["ok"]:
        # 구문 오류의 뒷부분(파서가 내는 설명)은 구현마다 다르다. 그 앞은 같아야 한다.
        prefix = "XML을 로드하는중 장애 발생. 장애코드: "
        if want["error"].startswith(prefix) and got["error"].startswith(prefix):
            return []
        if want["error"] != got["error"]:
            return [f"{name}: 거절 문구가 다릅니다\n"
                    f"    파이썬: {want['error']}\n    Rust  : {got['error']}"]
        return []
    if not expect_error and len(want["items"]) != len(got["items"]):
        return [f"{name}: 라인 수 {len(want['items'])} vs {len(got['items'])}"]

    problems: list[str] = []
    for index, (left, right) in enumerate(zip(want["items"], got["items"])):
        for field in left:
            if left[field] != right.get(field):
                problems.append(
                    f"{name}[{index}].{field}: 파이썬 {left[field]!r} / Rust {right.get(field)!r}")
    return problems


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    cases = [(name, data, False) for name, data in documents().items()]
    cases += [(name, data, True) for name, data in REJECTED.items()]

    problems: list[str] = []
    for name, data, expect_error in cases:
        problems.extend(compare(name, data, expect_error=expect_error))

    print(f"대조한 문서 {len(cases)}건 "
          f"(읽는 문서 {len(cases) - len(REJECTED)}, 거절하는 문서 {len(REJECTED)})")
    if not problems:
        print("파이썬과 Rust 의 파싱 결과가 모두 같습니다.")
        return 0
    print(f"다른 곳 {len(problems)}건:")
    for line in problems[:30]:
        print(f"  {line}")
    if len(problems) > 30:
        print(f"  ... 그리고 {len(problems) - 30}건 더")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
