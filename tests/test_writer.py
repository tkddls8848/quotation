"""Phase 3 회귀 — 생성물이 골든 견적서와 셀 단위로 같은지 검증."""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from quotation.core import xml_reader  # noqa: E402
from quotation.core.writer import ibm_writer  # noqa: E402

import compare as cmp_mod  # noqa: E402

SAMPLES = ROOT / "samples"
CACHE = ROOT / "cache" if (ROOT / "cache").exists() else ROOT / ".cache"
TEMPLATE = CACHE / "견적서_template.xlsx"

CASES = [
    ("FS5045_260722", dt.date(2026, 7, 23)),
    ("X-ROIS 통합서버#2", dt.date(2026, 7, 23)),
]

pytestmark = pytest.mark.skipif(
    not TEMPLATE.exists(),
    reason="tools/xls2xlsx.ps1 로 .cache 를 먼저 생성하십시오",
)


def _build(name: str, today: dt.date, tmp_path: Path) -> Path:
    quote = xml_reader.parse(SAMPLES / f"{name}.xml")
    return ibm_writer.write(quote, TEMPLATE, tmp_path / f"{name}.xlsx", today=today)


def test_total_sheet_keeps_template_drawings(tmp_path):
    """TOTAL 시트 상단의 로고·머리글 도형이 남아 있어야 한다.

    openpyxl 은 저장 시 그림을 버린다. 이것이 빠지면 첫 장 상단이 비어 보인다.
    상세 시트와 숨김 template 시트에는 골든과 마찬가지로 그림이 없어야 한다.
    """
    import re
    import zipfile

    actual = _build("FS5045_260722", dt.date(2026, 7, 23), tmp_path)
    with zipfile.ZipFile(actual) as z:
        names = z.namelist()
        media = [n for n in names if n.startswith("xl/media/")]
        drawn = sorted(n for n in names
                       if n.startswith("xl/worksheets/sheet")
                       and re.search(rb"<drawing\s", z.read(n)))

    assert media, "템플릿의 로고 이미지가 옮겨지지 않았다"
    assert drawn == ["xl/worksheets/sheet1.xml"], (
        f"그림은 TOTAL(sheet1)에만 있어야 한다: {drawn}")


@pytest.mark.parametrize("name,today", CASES)
def test_matches_golden(name, today, tmp_path):
    golden = CACHE / f"{name}.xlsx"
    if not golden.exists():
        pytest.skip(f"골든 없음: {golden}")

    actual = _build(name, today, tmp_path)
    ignore = cmp_mod.load_ignore(ROOT / "tests" / "golden_ignore.txt")
    rep = cmp_mod.compare(golden, actual, ignore)

    if not rep.ok:
        lines = "\n".join("  " + str(d) for d in rep.diffs[:40])
        extra = "" if len(rep.diffs) <= 40 else f"\n  … 외 {len(rep.diffs) - 40}건"
        pytest.fail(f"{name}: 골든과 차이 {len(rep.diffs)}건\n{lines}{extra}")
