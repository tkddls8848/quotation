"""경로 해석 — 개발 실행과 PyInstaller 단일 EXE 를 모두 지원한다.

설정과 로그는 %LOCALAPPDATA% 에 둔다. 원본은 Program Files 아래에 INI 를 썼는데,
Windows 11 에서는 쓰기가 차단되어 VirtualStore 로 우회되고 설정이 유실된다.
"""
from __future__ import annotations

import os
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


def template_path() -> Path:
    return resource_dir() / TEMPLATE_NAME


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
