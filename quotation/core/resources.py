"""공용 기준 템플릿.

저장소에 담아 두는 **유일한** 기준 템플릿이며, 문서 판별(`modes.py`)마다
한 벌씩 IBM 용·레노버 x86 용 두 개다. 데스크톱은 이 파일들을 EXE 옆으로
한 번씩 복사해 사용자 편집본으로 쓰고(`quotation_desktop.paths`), 웹은 배포
직전 `web/scripts/sync_core.py` 가 이 파일들을 번들에 담는다
(`doc/decisions/0001-template-in-bundle.md`). 두 실행 환경 모두 자기 템플릿을
명시적으로 넘기므로, 여기 기본값은 개발과 테스트에서만 쓰인다.
"""
from __future__ import annotations

from pathlib import Path

from . import modes

#: 모드별 기준 템플릿 파일 이름.
TEMPLATE_NAMES = {
    modes.UNIX: "견적서_template_IBM.xlsx",
    modes.INTEGRATED: "견적서_template_Lenovo.xlsx",
}

RESOURCE_DIR = Path(__file__).resolve().parents[1] / "resources"


def default_template_path(mode: str = modes.UNIX) -> Path:
    return RESOURCE_DIR / TEMPLATE_NAMES[mode]


def default_template_bytes(mode: str = modes.UNIX) -> bytes:
    return default_template_path(mode).read_bytes()
