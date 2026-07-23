"""골든의 셀 종류별 글꼴 실측. writer 의 글꼴 규칙을 확정하기 위한 조사용."""
import sys

from openpyxl import load_workbook

CASES = {
    ".cache/FS5045_260722.xlsx": {
        "TOTAL": {
            "B2 표제": "B2", "C3 날짜": "C3",
            "데이터 B(종목)": "B8", "데이터 C": "C8", "데이터 D": "D8",
            "데이터 E": "E8", "데이터 F": "F8", "데이터 G": "G8",
            "합계 C": "C11", "합계 G": "G11", "합계 H": "H11",
            "총합계 B": "B20", "총합계 G": "G20", "총합계 H": "H20",
            "공급가 B": "B21",
        },
        "4680-3P4 #1": {
            "C1 제목": "C1", "C3 날짜": "C3",
            "섹션라벨 B": "B8", "데이터 C": "C8", "데이터 D": "D8",
            "데이터 E": "E8", "데이터 F": "F8", "데이터 G": "G8",
            "서브 C": "C9", "서브 E": "E9", "서브 F": "F9", "서브 G": "G9",
            "N/C F": "F11", "N/C G": "G11",
            "블록합계 C": "C20", "블록합계 G": "G20", "블록합계 H": "H20",
            "섹션합계 C": "C24", "섹션합계 G": "G24", "섹션합계 H": "H24",
            "SW섹션합계 C": "C27", "SW섹션합계 G": "G27",
            "총합계 B": "B28", "총합계 G": "G28", "총합계 H": "H28",
            "공급가 B": "B29",
        },
    },
    ".cache/X-ROIS 통합서버#2.xlsx": {
        "SERVER 1": {"MA H": "H51", "MA I": "I51", "S/W 라벨 B": "B68",
                     "S/W 데이터 E": "E69"},
        "TOTAL": {"MA H": "H10"},
    },
}

for path, sheets in CASES.items():
    print(f"########## {path}")
    wb = load_workbook(path)
    for sheet, cells in sheets.items():
        print(f"=== [{sheet}]")
        for label, addr in cells.items():
            c = wb[sheet][addr]
            f = c.font
            print(f"  {label:<16} {addr:<5} {f.name}/{f.size} bold={bool(f.b)} "
                  f"al={c.alignment.horizontal} fmt={c.number_format!r}")
