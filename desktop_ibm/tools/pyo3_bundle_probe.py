"""PyInstaller 단일 EXE 안에서 Rust 확장이 도는지 확인하는 진입점.

계획 §5 관문 3 — 데스크톱은 무설치 단일 EXE 로 나간다. PyO3 확장은 파이썬
소스가 아니라 네이티브 .pyd 라 번들에 실리는지, 실려서 실제로 도는지를 따로
확인해야 한다. 이 파일은 그 확인만 한다.

    .venv\\Scripts\\pyinstaller.exe --onefile --console ^
        --name pyo3-bundle-probe desktop_ibm\\tools\\pyo3_bundle_probe.py
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

    print("확장이 EXE 안에서 정상 동작합니다." if not failed else f"{failed}건 다릅니다.")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
