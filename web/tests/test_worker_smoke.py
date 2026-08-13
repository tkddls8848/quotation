"""Worker 층의 경계 검사.

`worker.py` 는 Workers 런타임(`workers` 모듈)이 있어야 import 되므로 CPython
에서는 소스를 정적으로 본다. 여기서 지키려는 것은 계획서 §5.1 의 한 줄이다.

    "Worker 모듈에서는 tkinter, config.py, paths.py, os.startfile,
     PyInstaller 코드를 import 하지 않는다."

이 경계가 깨지면 배포 시점이 아니라 첫 요청에서 터진다.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

#: Worker 번들에 절대 들어오면 안 되는 것들
FORBIDDEN_MODULES = {
    "tkinter", "quotation_desktop", "PyInstaller", "shutil", "webbrowser",
    "quotation.core.resources",  # 템플릿은 R2 에서 온다. 저장소 사본을 쓰지 않는다.
}
FORBIDDEN_CALLS = {"startfile", "system", "popen"}


def _module_names(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
            names.update(f"{node.module}.{a.name}" for a in node.names)
    return names


def _sources(web_src: Path) -> list[Path]:
    files = sorted(p for p in web_src.glob("*.py"))
    assert files, "web/src 에 Worker 모듈이 있어야 한다"
    return files


def test_worker_modules_do_not_import_desktop_code(web_src):
    for path in _sources(web_src):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for name in _module_names(tree):
            root = name.split(".")[0]
            assert root not in FORBIDDEN_MODULES and name not in FORBIDDEN_MODULES, (
                f"{path.name} 이 데스크톱 전용 모듈 {name} 을 import 한다")


def test_worker_modules_do_not_touch_the_filesystem(web_src):
    """요청 처리 중 파일을 읽거나 쓰지 않는다. 입력·결과는 메모리에만 있다."""
    for path in _sources(web_src):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                name = getattr(func, "attr", None) or getattr(func, "id", None)
                assert name not in FORBIDDEN_CALLS, f"{path.name}: {name}"
                assert name != "open", f"{path.name} 이 파일을 연다"


def test_core_stays_free_of_desktop_dependencies():
    """공용 코어도 마찬가지다. 웹과 데스크톱이 같은 코어를 쓴다."""
    core = Path(__file__).resolve().parents[2] / "quotation"
    for path in sorted(core.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for name in _module_names(tree):
            root = name.split(".")[0]
            assert root not in {"tkinter", "quotation_desktop"}, (
                f"코어 {path.name} 이 {name} 에 의존한다")


def test_tests_run_against_the_real_core_not_the_vendored_copy(web_src):
    """`web/src/quotation/` 은 배포용 사본이다. 테스트는 원본을 봐야 한다."""
    import quotation

    package = Path(quotation.__file__).resolve().parent
    assert package == web_src.parents[1] / "quotation", (
        f"코어 사본이 원본을 가리고 있다: {package}")


def test_worker_routes_cover_the_documented_api(web_src):
    body = (web_src / "worker.py").read_text(encoding="utf-8")
    for route in ("/convert", "/status", "/config"):
        assert route in body, f"{route} 경로가 없다"
    assert 'API_PREFIX = "/api/v1"' in body


def test_worker_hands_binary_bodies_back_unchanged(web_src):
    """응답 본문은 api 층이 만든 바이트 그대로여야 한다 (인코딩 손상 방지)."""
    body = (web_src / "worker.py").read_text(encoding="utf-8")
    assert "Response(result.body, status=result.status" in body


def test_worker_needs_the_workers_runtime(web_src):
    """CPython 에서는 import 되지 않는 것이 정상이다."""
    import sys

    sys.path.insert(0, str(web_src))
    with pytest.raises(ImportError):
        import worker  # noqa: F401
