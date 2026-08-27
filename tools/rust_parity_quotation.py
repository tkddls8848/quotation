"""파이썬과 Rust 가 만든 **견적서 한 부**를 대조한다.

계획 §Phase 3 의 동등성 판정 — 같은 fixture 로 중간 모델을 비교한다. 그룹
구성, 장비군 이름, 시트명, 제목, H/W·S/W 구간, 그리고 **금액**이 대상이다.
셀에 적히는 값이 여기서 정해지므로, 여기가 같으면 남는 것은 Excel 작성뿐이다.

    python tools/rust_parity_quotation.py
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
         "--bin", "quotation-probe")

FIXTURES = ROOT / "tests" / "fixtures" / "public"


def documents() -> dict[str, bytes]:
    found = {path.name: path.read_bytes() for path in sorted(FIXTURES.glob("*.xml"))}
    for path in sorted(ROOT.glob("*.xml")):
        found[path.name] = path.read_bytes()
    return found


def amount_repr(amount) -> str:
    """[결정 0006] 금액은 지수 없는 자릿수 표기로 비교한다."""
    if amount is NO_CHARGE:
        return "nocharge"
    if amount is None:
        return "missing"
    return f"priced:{format(amount, 'f')}"


def python_quotation(data: bytes) -> dict:
    try:
        quotation = xml_reader.parse_bytes(data)
    except xml_reader.QuotationXmlError as error:
        return {"ok": False, "error": str(error)}
    return {
        "ok": True,
        "mode": quotation.mode,
        "groups": [{
            "group_id": group.group_id,
            "item_key": group.item_key,
            "sheet_name": group.sheet_name,
            "title": group.title,
            "amount": format(group.amount(), "f"),
            "sections": [[kind, len(items)] for kind, items in group.sections()],
            "items": [{
                "line_number": item.line_number,
                "txn_type": item.txn_type,
                "part_number": item.part_number,
                "description": item.description,
                "product_type": item.product_type,
                "quantity": item.quantity,
                "siu": item.siu,
                "unit_price": amount_repr(item.unit_price),
                "amount": format(item.amount(), "f"),
                "is_hardware": item.is_hardware,
                "subs": [{
                    "txn_type": sub.txn_type,
                    "part_number": sub.part_number,
                    "quantity": sub.quantity,
                    "unit_price": amount_repr(sub.unit_price),
                    "amount": format(sub.amount(item.quantity), "f"),
                    "is_removal": sub.is_removal,
                } for sub in item.subs],
            } for item in group.items],
        } for group in quotation.groups],
    }


def rust_quotation(data: bytes) -> dict:
    result = subprocess.run(PROBE, cwd=ROOT, input=data,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if result.returncode != 0:
        sys.stderr.write(result.stderr.decode("utf-8", "replace"))
        raise SystemExit(f"Rust 탐침이 {result.returncode} 로 끝났습니다.")
    return json.loads(result.stdout.decode("utf-8"))


def differences(name: str, want, got, path: str = "") -> list[str]:
    """두 구조에서 다른 자리만 짚어 준다."""
    where = f"{name}{path}"
    if isinstance(want, dict) and isinstance(got, dict):
        problems = []
        for key in want:
            if key not in got:
                problems.append(f"{where}.{key}: Rust 쪽에 없습니다")
            else:
                problems.extend(differences(name, want[key], got[key], f"{path}.{key}"))
        return problems
    if isinstance(want, list) and isinstance(got, list):
        if len(want) != len(got):
            return [f"{where}: 개수 {len(want)} vs {len(got)}"]
        problems = []
        for index, (left, right) in enumerate(zip(want, got)):
            problems.extend(differences(name, left, right, f"{path}[{index}]"))
        return problems
    if want != got:
        return [f"{where}: 파이썬 {want!r} / Rust {got!r}"]
    return []


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    problems: list[str] = []
    documents_ = documents()
    for name, data in documents_.items():
        problems.extend(differences(name, python_quotation(data), rust_quotation(data)))

    print(f"대조한 문서 {len(documents_)}건 — 그룹 구성 · 시트명 · 구간 · 금액")
    if not problems:
        print("파이썬과 Rust 의 견적 내용이 모두 같습니다.")
        return 0
    print(f"다른 곳 {len(problems)}건:")
    for line in problems[:30]:
        print(f"  {line}")
    if len(problems) > 30:
        print(f"  ... 그리고 {len(problems) - 30}건 더")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
