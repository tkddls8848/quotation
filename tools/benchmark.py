"""변환 성능 측정. Excel 프로세스를 쓰지 않는 경로의 실제 소요 시간."""
from __future__ import annotations

import datetime as dt
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from quotation.core import xml_reader  # noqa: E402
from quotation.core.writer import ibm_writer  # noqa: E402

TEMPLATE = ROOT / ".cache" / "견적서_template.xlsx"
OUT = ROOT / "out"
ROUNDS = 5


def main():
    for xml in sorted((ROOT / "samples").glob("*.xml")):
        times = []
        for _ in range(ROUNDS):
            t0 = time.perf_counter()
            quote = xml_reader.parse(xml)
            ibm_writer.write(quote, TEMPLATE, OUT / f"{xml.stem}.xlsx",
                             today=dt.date(2026, 7, 23))
            times.append(time.perf_counter() - t0)
        items = sum(len(g.items) for g in quote.groups)
        subs = sum(len(i.subs) for g in quote.groups for i in g.items)
        print(f"{xml.name:<28} 최소 {min(times):.3f}s  중앙 "
              f"{sorted(times)[len(times) // 2]:.3f}s  "
              f"(시트 {len(quote.groups) + 2}, 라인 {items}, 서브 {subs})")


if __name__ == "__main__":
    main()
