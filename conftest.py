"""테스트 임포트 경로.

저장소가 세 갈래로 나뉘어 있어 각각의 임포트 뿌리를 잡아 준다.

    <root>              공용 코어 패키지  ``quotation``
    <root>/desktop_ibm  데스크톱 패키지    ``quotation_desktop``
    <root>/web/scripts  엔진 포장 스크립트 ``build_browser_engine``
    <root>/tools        비교기 ``compare``, ``xlsx_content``
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

IMPORT_ROOTS = (ROOT, ROOT / "desktop_ibm", ROOT / "web" / "scripts",
                ROOT / "tools")

for path in reversed(IMPORT_ROOTS):
    entry = str(path)
    if entry in sys.path:
        sys.path.remove(entry)
    sys.path.insert(0, entry)
