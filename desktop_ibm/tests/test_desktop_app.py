"""데스크톱 전용 — 템플릿 위치, 사용자 설정, GUI 진입 인수.

변환 자체의 계약은 공용 코어 테스트(`tests/`)가 지킨다. 여기서는 EXE 로
배포될 때만 의미가 있는 것들만 본다.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from quotation_desktop import paths


# --- 템플릿 ------------------------------------------------------------------

def test_desktop_uses_the_one_shared_template():
    """양식은 하나뿐이다. 데스크톱이 웹과 같은 원본을 쓰는지 확인한다."""
    from quotation.core import resources

    bundled = paths.resource_dir() / paths.TEMPLATE_NAME
    assert bundled.is_file()
    assert bundled.resolve() == resources.default_template_path().resolve()


def test_template_lives_outside_the_exe(tmp_path, monkeypatch):
    """템플릿은 EXE 옆의 고칠 수 있는 파일이어야 한다.

    없으면 번들 사본으로 한 번 만들어 준다. 안에 묻어 두면 견적서 번호와
    담당자 이름을 고칠 수 없다.
    """
    monkeypatch.setattr(paths, "app_dir", lambda: tmp_path)

    target = tmp_path / paths.TEMPLATE_NAME
    assert not target.exists()
    assert paths.template_path() == target
    assert target.exists(), "번들 사본으로 자동 생성되어야 한다"

    # 이미 있으면 덮어쓰지 않는다 (사용자 편집 보존)
    target.write_bytes(b"edited")
    assert paths.template_path().read_bytes() == b"edited"


# --- 설정 --------------------------------------------------------------------

def test_config_roundtrip(tmp_path, monkeypatch):
    from quotation_desktop import config as config_mod

    monkeypatch.setattr(paths, "app_data_dir", lambda: tmp_path)
    monkeypatch.setattr(paths, "config_path", lambda: tmp_path / "config.json")

    cfg = config_mod.load()
    cfg.open_result_when_done = False
    cfg.remember(tmp_path / "입력" / "a.xml")
    config_mod.save(cfg)

    again = config_mod.load()
    assert again.open_result_when_done is False
    assert again.last_input_dir == str(tmp_path / "입력")


def test_config_defaults_when_file_is_absent(tmp_path, monkeypatch):
    from quotation_desktop import config as config_mod

    monkeypatch.setattr(paths, "config_path", lambda: tmp_path / "none.json")
    cfg = config_mod.load()
    assert cfg.open_result_when_done is True
    assert cfg.last_input_dir == ""


# --- 진입점 ------------------------------------------------------------------

def test_main_opens_gui_with_first_file_argument(monkeypatch):
    pytest.importorskip("tkinter", reason="Tk 없는 환경")

    from quotation_desktop import __main__
    from quotation_desktop.ui import main_window

    seen: list[str | None] = []
    monkeypatch.setattr(main_window, "run",
                        lambda prefill: seen.append(prefill) or 0)

    assert __main__.main(["sample.xml", "ignored.xml"]) == 0
    assert seen == ["sample.xml"]


def test_launcher_entrypoint_is_importable():
    """PyInstaller 진입점이 저장소 어디서 실행되든 코어를 찾아야 한다."""
    launcher = Path(__file__).resolve().parents[1] / "launcher.py"
    body = launcher.read_text(encoding="utf-8")
    assert "quotation_desktop.__main__" in body
