"""PyInstaller 단일 EXE 안에서 Rust 확장이 도는지 확인하는 진입점.

계획 §5 관문 3 — 데스크톱은 무설치 단일 EXE 로 나간다. PyO3 확장은 파이썬
소스가 아니라 네이티브 .pyd 라 번들에 실리는지, 실려서 실제로 도는지를 따로
확인해야 한다. 이 파일은 그 확인만 한다.

    .venv\\Scripts\\pyinstaller.exe --onefile --console ^
        --name pyo3-bundle-probe quotation\\desktop\\tools\\pyo3_bundle_probe.py
    dist\\pyo3-bundle-probe.exe

기대값은 파이썬 코어가 내는 값이다. 다르면 0 이 아닌 값으로 끝난다.
"""
from __future__ import annotations

import sys


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    try:
        import quotation_rust as rust
    except ImportError as error:
        print(f"확장을 부를 수 없습니다: {error}")
        return 2

    bundled = getattr(sys, "frozen", False)
    print(f"실행 형태: {'단일 EXE' if bundled else '파이썬'}")
    print(f"확장 위치: {getattr(rust, '__file__', '(없음)')}")

    checks = [
        ("parse_amount('88,971.50')", rust.parse_amount("88,971.50"), ("priced", "88971.50")),
        ("parse_amount('N/C')", rust.parse_amount("N/C"), ("nocharge", "")),
        ("parse_amount('4.0172E7')", rust.parse_amount("4.0172E7"), ("priced", "40172000")),
        ("item_key('Server 1:Server 1:9080 Model HEX')",
         rust.item_key("Server 1:Server 1:9080 Model HEX"), "Server 1"),
        ("safe_sheet_name('메일/스펨_1식')",
         rust.safe_sheet_name("메일/스펨_1식"), "메일-스펨_1식"),
        ("unique_sheet_names(['백업서버', '백업서버'])",
         rust.unique_sheet_names(["백업서버", "백업서버"]), ["백업서버", "백업서버 (2)"]),
        ("detect_mode(['', '백업서버_1식'])",
         rust.detect_mode(["", "백업서버_1식"]), "integrated"),
    ]

    failed = 0
    for label, got, want in checks:
        ok = got == want
        failed += 0 if ok else 1
        print(f"  {'OK  ' if ok else 'FAIL'} {label} -> {got!r}" + ("" if ok else f" (기대 {want!r})"))

    failed += _convert_check()
    print("확장이 EXE 안에서 정상 동작합니다." if not failed else f"{failed}건 다릅니다.")
    return 0 if not failed else 1


def _convert_check() -> int:
    """번들 안에서 **실제 변환**까지 도는가.

    확장을 부를 수 있다는 것과 견적서가 나온다는 것은 다른 문제다. 템플릿을
    찾고, XML 을 읽고, xlsx 바이트를 만드는 데까지 가 본다.
    """
    import datetime as dt
    import tempfile
    from pathlib import Path

    try:
        from quotation.core import convert
    except ImportError as error:
        print(f"  FAIL 코어를 부를 수 없습니다: {error}")
        return 1

    sample = (b"<CFXML><CFData><ProductLineItem>"
              b"<ProductLineNumber>1000</ProductLineNumber>"
              b"<TransactionType>NEW</TransactionType>"
              b"<ProprietaryGroupIdentifier>1000</ProprietaryGroupIdentifier>"
              b"<Quantity>1</Quantity><CPUSIUvalue>1</CPUSIUvalue>"
              b"<ProductIdentification><PartnerProductIdentification>"
              b"<ProductDescription>Server 1:probe</ProductDescription>"
              b"<ProprietaryProductIdentifier>1234-567</ProprietaryProductIdentifier>"
              b"<ProductTypeCode>Hardware</ProductTypeCode>"
              b"</PartnerProductIdentification></ProductIdentification>"
              b"<UnitListPrice><FinancialAmount><MonetaryAmount>1,000.5</MonetaryAmount>"
              b"</FinancialAmount></UnitListPrice>"
              b"</ProductLineItem></CFData></CFXML>")

    with tempfile.TemporaryDirectory() as folder:
        source = Path(folder) / "probe.xml"
        source.write_bytes(sample)
        try:
            result = convert.convert(source, today=dt.date(2026, 8, 28))
        except Exception as error:  # noqa: BLE001 - 무엇이든 실패면 보고한다
            print(f"  FAIL 변환이 되지 않습니다: {type(error).__name__}: {error}")
            return 1
        made = result.output.read_bytes()

    ok = made[:2] == b"PK" and len(made) > 10_000 and result.group_count == 1
    print(f"  {'OK  ' if ok else 'FAIL'} 변환 1건 -> {len(made):,} bytes, "
          f"장비군 {result.group_count}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
