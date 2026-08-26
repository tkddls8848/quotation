"""파이썬 순수 규칙과 Rust 이식본을 같은 입력으로 대조한다.

계획 §Phase 1 의 동등성 판정 — `money` · `naming` · `modes` 에 **같은 입력을
넣어 출력 문자열을 비교**한다. 파이썬 `quotation.core` 가 기준이고, Rust 쪽은
`rust/parity` 탐침이 답한다. 한 건이라도 다르면 0 이 아닌 값으로 끝난다.

    python tools/rust_parity_pure_rules.py

입력 자료는 지어내지 않는다. 골든 fixture 6종과 저장소에 있는 실제 구성
XML 에서 ProductDescription · ProductName · MonetaryAmount 를 그대로 뽑아
쓰고, 여기에 경계값(빈 문자열·금칙 문자·31자 초과·중복 시트명)을 더한다.
"""
from __future__ import annotations

import json
import subprocess
import sys
from decimal import InvalidOperation
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from quotation.core import modes, naming  # noqa: E402
from quotation.core.money import NO_CHARGE, is_priced, parse_amount, to_decimal  # noqa: E402

PROBE = ("cargo", "run", "--quiet", "--package", "quotation-parity",
         "--bin", "pure-rules-probe")

#: 구성 XML 에서 값을 뽑아 오는 곳.
XML_SOURCES = (
    *sorted((ROOT / "tests" / "fixtures" / "public").glob("*.xml")),
    *sorted(ROOT.glob("*.xml")),
)


def plain(value) -> str:
    """자릿수 표기 — 지수 없이, 소수 자릿수는 그대로.

    파이썬 `str(Decimal("4.0172E7"))` 은 `4.0172E+7` 이지만 셀에 적히는 것은
    openpyxl 이 만드는 자릿수 표기다. 두 구현이 같은 **값**을 들고 있는지를
    묻는 자리이므로 지수 형태 차이는 여기서 걷어 낸다.
    """
    return format(value, "f")


def amount_repr(amount) -> str:
    """탐침과 같은 글로 금액을 적는다."""
    if amount is NO_CHARGE:
        return "nocharge"
    if amount is None:
        return "missing"
    return f"priced:{plain(amount)}"


def cell_text(amount) -> str:
    """셀에 적히는 표현."""
    if amount is NO_CHARGE:
        return "N/C"
    if amount is None:
        return ""
    return plain(amount)


class _Named:
    """`modes.detect` 가 보는 것은 `product_name` 뿐이다."""

    __slots__ = ("product_name",)

    def __init__(self, product_name: str) -> None:
        self.product_name = product_name


def _fake_items(names):
    return [_Named(name) for name in names]


PYTHON_RULES = {
    "money.parse_amount": lambda raw: amount_repr(parse_amount(raw)),
    "money.to_decimal": lambda raw: plain(to_decimal(parse_amount(raw))),
    "money.is_priced": lambda raw: is_priced(parse_amount(raw)),
    "money.cell_text": lambda raw: cell_text(parse_amount(raw)),
    "naming.item_key": naming.item_key,
    "naming.sheet_name": naming.sheet_name,
    "naming.product_key": naming.product_key,
    "naming.safe_sheet_name": naming.safe_sheet_name,
    "naming.unique_sheet_names": naming.unique_sheet_names,
    "modes.detect": lambda names: modes.detect(_fake_items(names)),
    "modes.normalize": modes.normalize,
    "modes.resolve": lambda raw, names: modes.resolve(raw, _fake_items(names)),
}


def harvested_texts() -> tuple[list[str], list[str], list[str]]:
    """구성 XML 에서 설명·이름·금액 텍스트를 있는 그대로 뽑는다."""
    from lxml import etree

    parser = etree.XMLParser(resolve_entities=False, no_network=True, recover=True)
    descriptions: list[str] = []
    names: list[str] = []
    amounts: list[str] = []
    for path in XML_SOURCES:
        try:
            tree = etree.fromstring(path.read_bytes(), parser)
        except etree.XMLSyntaxError:
            continue
        if tree is None:
            continue
        for element in tree.iter():
            if not isinstance(element.tag, str):
                continue
            tag = etree.QName(element).localname
            text = element.text or ""
            if tag == "ProductDescription":
                descriptions.append(text)
            elif tag == "ProductName":
                names.append(text)
            elif tag == "MonetaryAmount":
                amounts.append(text)
    return descriptions, names, amounts


#: 실제 문서에는 잘 나오지 않지만 규칙이 갈릴 수 있는 자리.
EDGE_DESCRIPTIONS = [
    "",
    "   ",
    "IBM ",
    "IBM  Power",
    "IBM Expert Labs Project Unit for IBM Power Systems",
    "4680-3P4 #1:IBM Storage FlashSystem 5045 SFF Control Enclosure",
    "Server 1:Server 1:9080 Model HEX",
    ":뒤에만 있는 설명",
    "가" * 40,
    "  앞뒤 공백  :설명",
    "ß straße",
]

EDGE_NAMES = [
    "",
    "   ",
    "백업서버_1식",
    "메일/스펨_1식",
    "'따옴표'",
    "history",
    "HISTORY",
    "a:b" + chr(92) + "c/d?e*f[g]h",
    "백" * 40,
    "A" * 31,
]

EDGE_AMOUNTS = [
    None,
    "",
    "   ",
    "N/C",
    "n/c",
    "0",
    "309",
    "88,971.5",
    "88,971.50",
    "796275.83",
    "-1,024.00",
    "1,196,000.79",
    "0.000001",
    "무상",
    "12 34",
]

EDGE_MODES = [None, "", "  ", "unix", "UNIX", " Integrated ", "integrated", "x86", "통합"]


def build_cases() -> list[dict]:
    descriptions, names, amounts = harvested_texts()
    descriptions = list(dict.fromkeys(descriptions + EDGE_DESCRIPTIONS))
    names = list(dict.fromkeys(names + EDGE_NAMES))
    amounts = list(dict.fromkeys(amounts)) + EDGE_AMOUNTS

    cases: list[dict] = []
    for raw in amounts:
        for rule in ("money.parse_amount", "money.to_decimal",
                     "money.is_priced", "money.cell_text"):
            cases.append({"fn": rule, "args": [raw]})
    for description in descriptions:
        cases.append({"fn": "naming.item_key", "args": [description]})
        cases.append({"fn": "naming.sheet_name", "args": [naming.item_key(description)]})
        cases.append({"fn": "naming.safe_sheet_name", "args": [naming.item_key(description)]})
    for name in names:
        for description in descriptions[:20]:
            cases.append({"fn": "naming.product_key", "args": [name, description]})
        cases.append({"fn": "naming.safe_sheet_name", "args": [name]})
        cases.append({"fn": "naming.sheet_name", "args": [name]})

    sheet_names = [naming.safe_sheet_name(naming.item_key(d)) for d in descriptions]
    cases.append({"fn": "naming.unique_sheet_names", "args": [sheet_names]})
    cases.append({"fn": "naming.unique_sheet_names",
                  "args": [[naming.safe_sheet_name(n) for n in names]]})
    for size in (0, 1, 2, 5):
        cases.append({"fn": "naming.unique_sheet_names", "args": [sheet_names[:size]]})

    for group in ([], [""], ["  "], ["", "백업서버_1식"], names[:10]):
        cases.append({"fn": "modes.detect", "args": [group]})
        for raw in EDGE_MODES:
            cases.append({"fn": "modes.resolve", "args": [raw, group]})
    for raw in EDGE_MODES:
        if raw is not None:
            cases.append({"fn": "modes.normalize", "args": [raw]})
    return cases


def python_answer(case: dict) -> dict:
    rule = PYTHON_RULES[case["fn"]]
    try:
        return {"ok": True, "value": rule(*case["args"])}
    except (InvalidOperation, ValueError, ArithmeticError):
        # 오류 문구는 두 구현이 다를 수 있다. 대조하는 것은 '거절했는가' 다.
        return {"ok": False}


def rust_answers(cases: list[dict]) -> list[dict]:
    payload = "".join(json.dumps(case, ensure_ascii=False) + "\n" for case in cases)
    result = subprocess.run(
        PROBE, cwd=ROOT, input=payload.encode("utf-8"),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    if result.returncode != 0:
        sys.stderr.write(result.stderr.decode("utf-8", "replace"))
        raise SystemExit(f"Rust 탐침이 {result.returncode} 로 끝났습니다.")
    lines = result.stdout.decode("utf-8").splitlines()
    if len(lines) != len(cases):
        raise SystemExit(f"탐침 응답 {len(lines)}건, 보낸 호출 {len(cases)}건.")
    answers = []
    for line in lines:
        answer = json.loads(line)
        answers.append({"ok": True, "value": answer["value"]} if answer["ok"]
                       else {"ok": False})
    return answers


def compare(cases: list[dict]) -> list[tuple[dict, dict, dict]]:
    """다른 결과만 돌려준다."""
    expected = [python_answer(case) for case in cases]
    actual = rust_answers(cases)
    return [(case, want, got)
            for case, want, got in zip(cases, expected, actual)
            if want != got]


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    cases = build_cases()
    mismatches = compare(cases)
    print(f"대조한 호출 {len(cases)}건 — 규칙 {len(PYTHON_RULES)}종, "
          f"입력 자료 {len(XML_SOURCES)}개 XML")
    if not mismatches:
        print("파이썬과 Rust 의 출력이 모두 같습니다.")
        return 0
    print(f"다른 결과 {len(mismatches)}건:")
    for case, want, got in mismatches[:20]:
        print(f"  {case['fn']}{case['args']!r}")
        print(f"    파이썬: {want!r}")
        print(f"    Rust  : {got!r}")
    if len(mismatches) > 20:
        print(f"  ... 그리고 {len(mismatches) - 20}건 더")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
