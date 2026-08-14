"""템플릿 검증과 교체 (계획서 §8.2 - 2단계).

필수 시트·도형 관계를 보고, 공개 fixture 로 실제 변환까지 해 본 뒤 해시를 찍는다.

    # 검증만 (지금 저장소의 원본이 성한지)
    python web/scripts/verify_template.py quotation/resources/견적서_template.xlsx

    # 쓰고 계신 양식을 저장소 원본으로 삼기 (검증을 통과해야만 바꾼다)
    python web/scripts/verify_template.py "<EXE 옆>/견적서_template.xlsx" --adopt

`--adopt` 는 검증에 합격한 경우에만 `quotation/resources/견적서_template.xlsx`
를 덮고, 파생물(Worker 번들·브라우저 엔진)까지 다시 만든다. 데스크톱과 웹이
같은 양식을 쓰게 하는 유일한 방법이며, 되돌리려면 그 커밋을 되돌린다.

종료 코드: 0 = 합격, 1 = 불합격
"""
from __future__ import annotations

import argparse
import hashlib
import sys
import zipfile
from io import BytesIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "web" / "src")]

import conversion_adapter  # noqa: E402
import errors  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "public"


def _fail(message: str) -> int:
    print(f"불합격: {message}")
    return 1


def verify(path: Path) -> int:
    import datetime as dt

    template = path.read_bytes()
    print(f"대상: {path}")
    print(f"크기: {len(template):,} bytes")
    print(f"SHA-256: {hashlib.sha256(template).hexdigest()}")

    try:
        conversion_adapter.validate_template(template)
    except errors.ApiError as exc:
        return _fail(f"{exc.code} — 필수 시트({', '.join(conversion_adapter.REQUIRED_SHEETS)})를 확인하십시오.")
    print(f"필수 시트: {', '.join(conversion_adapter.REQUIRED_SHEETS)} 확인")

    with zipfile.ZipFile(BytesIO(template)) as z:
        media = [n for n in z.namelist() if n.startswith("xl/media/")]
        drawings = [n for n in z.namelist() if n.startswith("xl/drawings/drawing")]
    if not media or not drawings:
        return _fail("TOTAL 시트의 로고·머리글 도형을 찾지 못했습니다.")
    print(f"도형: drawing {len(drawings)}개 / media {len(media)}개")

    for fixture in sorted(FIXTURES.glob("*.xml")):
        try:
            result = conversion_adapter.convert_upload(
                xml_bytes=fixture.read_bytes(),
                template_bytes=template,
                today=dt.date(2026, 7, 23),
                source_name=fixture.name,
            )
        except errors.ApiError as exc:
            return _fail(f"{fixture.name}: {exc.code} — {exc.message}")
        print(f"변환 {fixture.name}: 장비군 {result.group_count}개 · "
              f"{len(result.xlsx):,} bytes · {result.elapsed_ms} ms")

    print("합격. 골든 회귀 테스트(python -m pytest tests -q)도 함께 통과시키십시오.")
    return 0


TEMPLATE_ORIGINAL = ROOT / "quotation" / "resources" / "견적서_template.xlsx"


def adopt(source: Path) -> int:
    """검증을 통과한 템플릿을 저장소 원본으로 삼고 파생물을 다시 만든다."""
    import subprocess

    incoming = source.read_bytes()
    current = TEMPLATE_ORIGINAL.read_bytes() if TEMPLATE_ORIGINAL.is_file() else b""
    if incoming == current:
        print(f"\n이미 같은 양식입니다. 바꿀 것이 없습니다 ({TEMPLATE_ORIGINAL}).")
        return 0

    print(f"\n저장소 원본 교체: {TEMPLATE_ORIGINAL}")
    print(f"  이전 sha256: {hashlib.sha256(current).hexdigest() if current else '(없음)'}")
    print(f"  이후 sha256: {hashlib.sha256(incoming).hexdigest()}")
    TEMPLATE_ORIGINAL.write_bytes(incoming)

    # 파생물을 다시 만들지 않으면 Worker 번들과 브라우저 엔진이 옛 양식을 쥔다.
    for script in ("sync_core.py", "build_browser_engine.py"):
        path = ROOT / "web" / "scripts" / script
        if not path.is_file():
            continue
        print(f"\n=== {script}")
        completed = subprocess.run([sys.executable, str(path)])
        if completed.returncode != 0:
            return _fail(f"{script} 실패. 원본은 이미 바뀌었으니 다시 실행하십시오.")

    print("\n교체 완료. 이어서 확인하십시오:")
    print("  python -m pytest -q")
    print("  git add quotation/resources/견적서_template.xlsx && git commit")
    print("\n주의: .xls 편집 원본은 그대로입니다. 그쪽도 함께 고쳐 두십시오")
    print("      (quotation/resources/견적서_template.xls, tools/xls2xlsx.ps1).")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("template", type=Path, help="검증할 .xlsx 템플릿")
    parser.add_argument("--adopt", action="store_true",
                        help="합격하면 저장소 원본으로 삼고 파생물을 다시 만든다")
    args = parser.parse_args()
    if not args.template.is_file():
        return _fail(f"화일이 없습니다: {args.template}")

    code = verify(args.template)
    if code != 0 or not args.adopt:
        return code
    return adopt(args.template.resolve())


if __name__ == "__main__":
    sys.exit(main())
