"""개발 실행과 PyInstaller 단일 EXE의 파일 경로를 제공한다."""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

APP_NAME = "QuotationTool"
TEMPLATE_NAME = "견적서_template.xlsx"


def resource_dir() -> Path:
    """번들된 리소스 폴더. PyInstaller 는 임시 폴더에 풀어 놓는다."""
    bundled = getattr(sys, "_MEIPASS", None)
    if bundled:
        return Path(bundled) / "resources"
    return Path(__file__).resolve().parent / "resources"


def app_dir() -> Path:
    """EXE 가 놓인 폴더. 개발 중에는 저장소 루트."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def template_path() -> Path:
    """EXE 옆에 사용자 편집용 템플릿을 한 번 생성하고 그 경로를 반환한다."""
    external = app_dir() / TEMPLATE_NAME
    if not external.exists():
        shutil.copyfile(resource_dir() / TEMPLATE_NAME, external)
    return external


def app_data_dir() -> Path:
    path = Path(os.environ["LOCALAPPDATA"]) / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def config_path() -> Path:
    return app_data_dir() / "config.json"
