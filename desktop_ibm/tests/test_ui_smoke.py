"""GUI 스모크 — 창이 실제로 구성되는지. mainloop 는 돌리지 않는다."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures" / "public"


def _point_at_tcl() -> None:
    """한 프로세스에서 Tk 를 두 번 만들면 tk.tcl 을 못 찾는 일이 있다.

    venv 에서 실행할 때 TCL_LIBRARY/TK_LIBRARY 가 비어 있어 생기는 문제라,
    기본 Python 설치의 경로를 직접 알려 준다.
    """
    import os

    base = Path(sys.base_prefix) / "tcl"
    if not base.is_dir():
        return
    for var, pattern in (("TCL_LIBRARY", "tcl8.*"), ("TK_LIBRARY", "tk8.*")):
        if os.environ.get(var):
            continue
        found = sorted(p for p in base.glob(pattern) if p.is_dir())
        if found:
            os.environ[var] = str(found[-1])


_point_at_tcl()
tk = pytest.importorskip("tkinter")


@pytest.fixture
def root(tmp_path, monkeypatch):
    from quotation_desktop import paths
    monkeypatch.setattr(paths, "app_data_dir", lambda: tmp_path)
    monkeypatch.setattr(paths, "config_path", lambda: tmp_path / "config.json")
    try:
        r = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"화면 없음: {exc}")
    r.withdraw()
    yield r
    r.destroy()


def test_window_builds(root):
    from quotation_desktop.ui.main_window import MainWindow
    win = MainWindow(root)
    assert win.convert_btn.cget("text") == "변환"
    assert "선택" in win.status.get()
    # 견적번호·담당자를 고칠 수 있도록 템플릿 경로를 보여 준다
    assert win.template_label.get().endswith(".xlsx")
    assert win.open_result.get() is True


def test_success_opens_the_quote_without_a_popup(root, monkeypatch, tmp_path):
    """완료 시 알림창을 띄우지 않고 만든 견적서를 연다."""
    import datetime as dt

    from quotation.core import convert
    from quotation_desktop.ui import main_window

    popups: list[str] = []
    opened: list = []
    monkeypatch.setattr(main_window.messagebox, "showinfo",
                        lambda t, m: popups.append(m))
    monkeypatch.setattr(main_window, "_open", opened.append)

    source = FIXTURES / "new_quote.xml"
    xml = tmp_path / source.name
    xml.write_bytes(source.read_bytes())

    win = main_window.MainWindow(root)
    result = convert.convert(xml, today=dt.date(2026, 7, 23))
    win.xml_path.set(str(xml))
    win._on_done(result)

    assert popups == [], "알림창이 떴다"
    assert opened == [result.output], "만든 견적서를 열지 않았다"


def test_convert_uses_the_user_editable_template(root, monkeypatch, tmp_path):
    """변환은 EXE 옆 편집본을 쓴다. 코어의 기준 템플릿을 쓰면 안 된다.

    견적서 번호와 담당자 도형을 고칠 수 있는 유일한 통로다.
    """
    from quotation_desktop import paths
    from quotation_desktop.ui import main_window

    monkeypatch.setattr(paths, "app_dir", lambda: tmp_path)

    seen: dict = {}
    monkeypatch.setattr(main_window.convert, "convert",
                        lambda xml, **kw: seen.update(xml=xml, **kw))

    win = main_window.MainWindow(root)
    win._worker(FIXTURES / "new_quote.xml")

    assert seen["template"] == tmp_path / paths.TEMPLATE_NAME


def test_convert_without_file_warns(root, monkeypatch):
    from quotation_desktop.ui import main_window
    shown: list[tuple[str, str]] = []
    monkeypatch.setattr(main_window.messagebox, "showinfo",
                        lambda t, m: shown.append((t, m)))
    win = main_window.MainWindow(root)
    win._start()
    assert shown == [(main_window.TITLE, "작업할 화일을 선택하세요.")]


def test_missing_file_reports_error(root, monkeypatch, tmp_path):
    from quotation_desktop.ui import main_window
    errors: list[str] = []
    monkeypatch.setattr(main_window.messagebox, "showerror",
                        lambda t, m: errors.append(m))
    win = main_window.MainWindow(root)
    win.xml_path.set(str(tmp_path / "없는화일.xml"))
    win._start()
    assert errors and "찾을 수 없습니다" in errors[0]
