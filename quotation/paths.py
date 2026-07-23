"""경로 해석 — 개발 실행과 PyInstaller 단일 EXE 를 모두 지원한다.

설정과 로그는 %LOCALAPPDATA% 에 둔다. 원본은 Program Files 아래에 INI 를 썼는데,
Windows 11 에서는 쓰기가 차단되어 VirtualStore 로 우회되고 설정이 유실된다.
"""
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
    """사용자가 고칠 수 있는 템플릿 파일.

    템플릿은 EXE 안에 묻어 두면 안 된다. 견적서 번호(`NO : Trialinfo-YY-`)와
    머리말 도형의 `담당 : 시스템사업부 ...` 를 사용자가 직접 고쳐야 하기 때문이다.
    EXE 옆에 두고, 없으면 번들 사본으로 한 번만 만들어 준다.

    `QUOTATION_TEMPLATE` 환경 변수로 다른 경로를 지정할 수 있다.
    """
    override = os.environ.get("QUOTATION_TEMPLATE")
    if override:
        return Path(override)

    external = app_dir() / TEMPLATE_NAME
    if not external.exists():
        bundled = resource_dir() / TEMPLATE_NAME
        if bundled.exists():
            try:
                external.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(bundled, external)
            except OSError:
                return bundled  # 쓰기 불가한 위치면 번들본을 그대로 쓴다
    return external


def app_data_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local"
    path = Path(base) / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def config_path() -> Path:
    return app_data_dir() / "config.json"


def log_dir() -> Path:
    path = app_data_dir() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def legacy_ini_candidates() -> list[Path]:
    """구버전이 INI 를 남겼을 만한 위치들."""
    names = ["견적서생성기.ini"]
    roots = [
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Quotation",
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Quotation",
    ]
    # Program Files 쓰기 차단 시 Windows 가 리다이렉트하는 위치
    local = os.environ.get("LOCALAPPDATA")
    if local:
        roots += [
            Path(local) / "VirtualStore" / "Program Files" / "Quotation",
            Path(local) / "VirtualStore" / "Program Files (x86)" / "Quotation",
        ]
    return [root / name for root in roots for name in names]
