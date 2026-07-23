"""GUI 스모크 — 창이 실제로 구성되는지. mainloop 는 돌리지 않는다."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

tk = pytest.importorskip("tkinter")


@pytest.fixture
def root(tmp_path, monkeypatch):
    from quotation import paths
    monkeypatch.setattr(paths, "app_data_dir", lambda: tmp_path)
    monkeypatch.setattr(paths, "config_path", lambda: tmp_path / "config.json")
    monkeypatch.setattr(paths, "legacy_ini_candidates", lambda: [])
    try:
        r = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"화면 없음: {exc}")
    r.withdraw()
    yield r
    r.destroy()


def test_window_builds(root):
    from quotation.ui.main_window import MainWindow
    win = MainWindow(root)
    assert win.convert_btn.cget("text") == "변환"
    assert "선택" in win.status.get()
    # 견적번호·담당자를 고칠 수 있도록 템플릿 경로를 보여 준다
    assert win.template_label.get().endswith(".xlsx")


def test_convert_without_file_warns(root, monkeypatch):
    from quotation.ui import main_window
    shown: list[tuple[str, str]] = []
    monkeypatch.setattr(main_window.messagebox, "showinfo",
                        lambda t, m: shown.append((t, m)))
    win = main_window.MainWindow(root)
    win._start()
    assert shown == [(main_window.TITLE, "작업할 화일을 선택하세요.")]


def test_missing_file_reports_error(root, monkeypatch, tmp_path):
    from quotation.ui import main_window
    errors: list[str] = []
    monkeypatch.setattr(main_window.messagebox, "showerror",
                        lambda t, m: errors.append(m))
    win = main_window.MainWindow(root)
    win.xml_path.set(str(tmp_path / "없는화일.xml"))
    win._start()
    assert errors and "찾을 수 없습니다" in errors[0]
