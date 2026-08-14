"""공용 기준 템플릿.

저장소에 담아 두는 **유일한** 기준 템플릿이다. 데스크톱은 이 파일을 EXE 옆으로
한 번 복사해 사용자 편집본으로 쓰고(`quotation_desktop.paths`), 웹은 배포 직전
`web/scripts/sync_core.py` 가 이 파일을 번들에 담는다
(`doc/decisions/0001-template-in-bundle.md`). 두 실행 환경 모두 자기 템플릿을
명시적으로 넘기므로, 여기 기본값은 개발과 테스트에서만 쓰인다.
"""
from __future__ import annotations

from pathlib import Path

TEMPLATE_NAME = "견적서_template.xlsx"

RESOURCE_DIR = Path(__file__).resolve().parents[1] / "resources"


def default_template_path() -> Path:
    return RESOURCE_DIR / TEMPLATE_NAME


def default_template_bytes() -> bytes:
    return default_template_path().read_bytes()
