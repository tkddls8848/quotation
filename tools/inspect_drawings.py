"""워크북의 그림/도형이 어느 시트에 붙어 있는지 조사."""
from __future__ import annotations

import re
import sys
import zipfile
from pathlib import Path


def sheet_map(z: zipfile.ZipFile) -> dict[str, str]:
    """시트 이름 -> xl/worksheets/sheetN.xml"""
    wb = z.read("xl/workbook.xml").decode("utf-8")
    rels = z.read("xl/_rels/workbook.xml.rels").decode("utf-8")
    rid_to_target = dict(re.findall(r'Id="([^"]+)"[^>]*Target="([^"]+)"', rels))
    out = {}
    for name, rid in re.findall(
            r'<sheet[^>]*name="([^"]*)"[^>]*r:id="([^"]+)"', wb):
        target = rid_to_target.get(rid, "")
        out[name] = "xl/" + target.lstrip("/")
    return out


def main(path: str):
    print(f"=== {Path(path).name}")
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        for sheet, part in sheet_map(z).items():
            rel = part.replace("worksheets/", "worksheets/_rels/") + ".rels"
            drawings = []
            if rel in names:
                body = z.read(rel).decode("utf-8")
                drawings = re.findall(r'Target="([^"]*drawing[^"]*)"', body)
            has_tag = b"<drawing " in z.read(part)
            print(f"  [{sheet:<28}] {part:<28} drawing태그={has_tag} "
                  f"rels={drawings}")
        media = [n for n in names if n.startswith("xl/media/")]
        print(f"  media: {media}")


if __name__ == "__main__":
    for p in sys.argv[1:]:
        main(p)
        print()
