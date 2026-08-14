"""브라우저 엔진에 담기는 것이 저장소 원본과 같은지 확인한다.

무료 계정에서는 변환이 브라우저에서 돈다. 결과가 서버·데스크톱과 같으려면
**돌아가는 코드와 양식이 같은 파일** 이어야 한다. 여기서는 그 포장을 본다.
실제로 돌려서 결과를 대조하는 것은 `test_browser_parity.py` 가 한다.

이 테스트는 Pyodide 도 node 도 필요 없다. 엔진 자산이 없어도 zip 내용을
그 자리에서 만들어 비교하므로 항상 돈다.
"""
from __future__ import annotations

import hashlib
import json
import zipfile
from io import BytesIO
from pathlib import Path

import pytest

import build_browser_engine as engine

ROOT = Path(__file__).resolve().parents[2]
WEB_SRC = ROOT / "web" / "src"
CORE = ROOT / "quotation"
TEMPLATE = CORE / "resources" / "견적서_template.xlsx"

pytestmark = pytest.mark.skipif(
    not (WEB_SRC / "template_data.py").is_file(),
    reason="python web/scripts/sync_core.py 를 먼저 실행하십시오")


@pytest.fixture(scope="module")
def members() -> dict[str, bytes]:
    return dict(engine.core_members())


# --- 담기는 것 ----------------------------------------------------------------

def test_core_zip_carries_the_repository_core_untouched(members):
    """`quotation/` 코어는 저장소 원본과 바이트가 같아야 한다."""
    packed = {name: data for name, data in members.items()
              if name.startswith("quotation/")}
    assert packed, "코어가 담기지 않았습니다"

    for name, data in packed.items():
        original = CORE / name[len("quotation/"):]
        assert original.is_file(), f"저장소에 없는 파일이 담겼습니다: {name}"
        assert data == original.read_bytes(), f"{name} 이 원본과 다릅니다"

    expected = {f"quotation/{p.relative_to(CORE).as_posix()}"
                for p in CORE.rglob("*.py")}
    assert set(packed) == expected, "코어 모듈이 빠지거나 더 담겼습니다"


def test_core_zip_carries_the_same_api_layer_the_worker_runs(members):
    """브라우저와 Worker 가 같은 `api`·가드 코드를 쓴다는 사실을 못박는다."""
    for name in ("api.py", "conversion_adapter.py", "errors.py", "limits.py",
                 "clock.py", "template.py", "template_data.py"):
        assert members[name] == (WEB_SRC / name).read_bytes(), \
            f"{name} 이 Worker 가 쓰는 것과 다릅니다"


def test_worker_only_module_stays_out(members):
    """`worker.py` 는 Workers 런타임이 있어야 import 된다. 담으면 안 된다."""
    assert "worker.py" not in members
    assert "entry.py" in members


def test_template_travels_as_the_repository_original(members):
    """양식은 저장소의 그 파일 하나뿐이다 (양식 뒤틀림 방지의 출발점)."""
    digest = hashlib.sha256(TEMPLATE.read_bytes()).hexdigest()
    text = members["template_data.py"].decode("utf-8")
    assert f'TEMPLATE_SHA256 = "{digest}"' in text
    assert f'TEMPLATE_VERSION = "sha256-{digest[:12]}"' in text


def test_packing_is_reproducible(members):
    """같은 입력이면 같은 zip 바이트. 배포마다 해시가 흔들리지 않는다."""
    once = engine.zip_bytes(list(members.items()))
    twice = engine.zip_bytes(list(members.items()))
    assert once == twice
    with zipfile.ZipFile(BytesIO(once)) as archive:
        assert sorted(archive.namelist()) == sorted(members)


# --- 판본 ---------------------------------------------------------------------

def _pinned_versions() -> dict[str, str]:
    """`web/pyproject.toml` 의 Worker 런타임 의존성 판본."""
    text = (ROOT / "web" / "pyproject.toml").read_text(encoding="utf-8")
    pins = {}
    for line in text.splitlines():
        line = line.strip().strip(",").strip('"')
        if "==" in line and not line.startswith("#"):
            name, _, version = line.partition("==")
            pins[name.strip()] = version.strip()
    return pins


def test_browser_uses_the_same_library_versions_as_the_worker():
    """lxml·openpyxl 판본이 갈리면 결과가 갈릴 수 있다. 한 곳에서 고정한다."""
    pins = _pinned_versions()
    assert f"lxml-{pins['lxml']}-" in engine.LXML.name
    files = [wheel.name for wheel in engine.PURE_WHEELS]
    assert any(name.startswith(f"openpyxl-{pins['openpyxl']}-") for name in files)


def test_every_download_is_pinned_by_content_hash():
    """받아 오는 것은 모두 sha256 으로 고정되어 있어야 한다."""
    for asset in (*engine.RUNTIME, engine.LXML, *engine.PURE_WHEELS):
        assert len(asset.sha256) == 64, asset.name
        assert asset.url.startswith("https://"), asset.name


# --- 산출물이 있을 때 ----------------------------------------------------------

def test_built_assets_are_up_to_date():
    """엔진 자산이 있다면 저장소 상태와 어긋나 있으면 안 된다."""
    if not (engine.OUT / "engine.json").is_file():
        pytest.skip("엔진 자산이 없습니다 (build_browser_engine.py 미실행)")

    problems = engine.stale()
    assert not problems, (
        "엔진 자산이 낡았습니다. python web/scripts/build_browser_engine.py "
        "를 다시 실행하십시오:\n  " + "\n  ".join(problems))


def test_manifest_describes_what_it_ships():
    if not (engine.OUT / "engine.json").is_file():
        pytest.skip("엔진 자산이 없습니다")

    manifest = json.loads((engine.OUT / "engine.json").read_text(encoding="utf-8"))
    core = (engine.OUT / manifest["core"]["file"]).read_bytes()
    assert hashlib.sha256(core).hexdigest() == manifest["core"]["sha256"]
    assert "entry.py" in manifest["core"]["modules"]
    assert "worker.py" not in manifest["core"]["modules"]
