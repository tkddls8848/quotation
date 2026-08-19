"""테스트 임포트 경로.

저장소가 세 갈래로 나뉘어 있어 각각의 임포트 뿌리를 잡아 준다.

    <root>              공용 코어 패키지  ``quotation``
    <root>/desktop_ibm  데스크톱 패키지    ``quotation_desktop``
    <root>/web/src      Worker 모듈        ``api``, ``conversion_adapter`` 등
    <root>/web/scripts  포장 스크립트      ``build_browser_engine``
    <root>/tools        골든 비교기 ``compare``

순서가 중요하다. 저장소 루트가 `web/src` 보다 앞서야 한다. 배포용으로 복사해 둔
`web/src/quotation/` 사본이 원본 코어를 가리면 테스트가 낡은 사본을 검사하게 된다.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

IMPORT_ROOTS = (ROOT, ROOT / "desktop_ibm", ROOT / "web" / "src",
                ROOT / "web" / "scripts", ROOT / "tools")

for path in reversed(IMPORT_ROOTS):
    entry = str(path)
    if entry in sys.path:
        sys.path.remove(entry)
    sys.path.insert(0, entry)
