"""테스트 임포트 경로.

저장소가 세 갈래로 나뉘어 있어 각각의 임포트 뿌리를 잡아 준다.

    <root>/quotation/python       공용 코어 패키지  ``quotation``
    <root>/quotation/desktop      데스크톱 패키지   ``quotation_desktop``
    <root>/quotation/web/scripts  엔진 포장 스크립트 ``build_browser_engine``
    <root>/quotation/tools        비교기 ``compare``, ``xlsx_content``

기능마다 제 폴더를 갖는다. 견적기는 ``quotation/`` 한 덩어리이고, 다른 기능이
그 안을 들여다보지 않는다.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

QUOTATION = ROOT / "quotation"

IMPORT_ROOTS = (QUOTATION / "python", QUOTATION / "desktop",
                QUOTATION / "web" / "scripts", QUOTATION / "tools")

for path in reversed(IMPORT_ROOTS):
    entry = str(path)
    if entry in sys.path:
        sys.path.remove(entry)
    sys.path.insert(0, entry)
