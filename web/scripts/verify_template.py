"""템플릿 검증 (계획서 §8.2 - 2단계).

R2 에 새 템플릿을 올리기 전에 로컬에서 돌린다. 필수 시트·도형 관계를 보고,
공개 fixture 로 실제 변환까지 해 본 뒤 파일 해시를 찍는다.

    python web/scripts/verify_template.py quotation/resources/견적서_template.xlsx

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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("template", type=Path, help="검증할 .xlsx 템플릿")
    args = parser.parse_args()
    if not args.template.is_file():
        return _fail(f"화일이 없습니다: {args.template}")
    return verify(args.template)


if __name__ == "__main__":
    sys.exit(main())
