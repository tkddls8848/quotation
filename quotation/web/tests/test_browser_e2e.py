"""실제 브라우저가 만든 견적서가 CPython 산출물과 같은지 확인한다.

`test_browser_parity.py` 는 파이썬이 같은 결과를 내는지를 본다. 여기서는 그것이
**빌드된 화면을 거쳐 사용자 손에 닿을 때까지** 그대로 남는지를 본다. 운영과 같은
CSP 를 건 서버에서 dist 를 내려 주고, Chromium 으로 파일을 골라 변환 버튼을 눌러
실제로 내려받은 파일을 대조한다.

돌리려면 세 가지가 있어야 한다. 없으면 건너뛴다.

    python quotation/web/scripts/build_browser_engine.py
    npm --prefix web ci && npm --prefix web run build
    npm --prefix web install --no-save playwright   (브라우저 구동)
"""
from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import subprocess
import sys
from io import BytesIO
from pathlib import Path

import pytest
from openpyxl import load_workbook

import xlsx_content
from quotation.core import convert

FEATURE = Path(__file__).resolve().parents[2]   # quotation/
ROOT = FEATURE.parent
#: 화면 셸. 빌드 산출물(dist)이 여기 있다.
FRONTEND = ROOT / "web"
DIST = FRONTEND / "dist"
#: 브라우저 구동 도구는 이 기능이 갖는다. Node 의 패키지 해석은 **부르는 위치가
#: 아니라 스크립트가 놓인 자리**를 따라 올라가므로, playwright 도 여기 있어야
#: 한다 (셸의 node_modules 는 이 스크립트에서 보이지 않는다).
E2E = FEATURE / "web"
SMOKE = E2E / "e2e" / "browser_smoke.mjs"

CASES = ("new_quote.xml", "euckr_quote.xml", "upgrade_quote.xml")


def _browser_dirs() -> list[Path]:
    """이 운영체제에서 playwright 가 브라우저를 놓아 두는 자리."""
    override = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    if override and override != "0":
        return [Path(override)]
    if sys.platform == "win32":
        return [Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright"]
    if sys.platform == "darwin":
        return [Path.home() / "Library" / "Caches" / "ms-playwright"]
    # 리눅스. /opt/pw-browsers 는 미리 깔아 두는 CI 이미지들이 쓰는 자리다.
    return [Path.home() / ".cache" / "ms-playwright", Path("/opt/pw-browsers")]


def _reason() -> str | None:
    if shutil.which("node") is None:
        return "node 가 없습니다"
    if not (DIST / "engine" / "engine.json").is_file():
        return "빌드된 dist 에 변환 엔진이 없습니다 (build_browser_engine.py + vite build)"
    if not (E2E / "node_modules" / "playwright").is_dir():
        return "playwright 가 없습니다 (npm --prefix quotation/web install)"
    # 꾸러미만 있고 **이 운영체제용 브라우저**가 없을 수 있다. WSL 에서 /mnt/c 의
    # Windows 설치본을 그대로 보는 경우가 그렇다. 그때 붉히면 진짜 고장과
    # 구분이 되지 않으므로, 없으면 없다고 밝히고 건너뛴다.
    if not any(d.is_dir() and any(d.glob("chromium*")) for d in _browser_dirs()):
        return "이 운영체제용 playwright 브라우저가 없습니다 (npx playwright install chromium)"
    return None


pytestmark = pytest.mark.skipif(_reason() is not None, reason=_reason() or "")


@pytest.fixture(scope="module")
def downloads(tmp_path_factory, fixtures) -> Path:
    out = tmp_path_factory.mktemp("e2e")
    env = dict(os.environ)
    # 이 환경에는 브라우저가 미리 깔려 있다. 있으면 내려받지 않고 그것을 쓴다.
    preinstalled = sorted(Path("/opt/pw-browsers").glob("chromium-*/chrome-linux/chrome")) \
        if Path("/opt/pw-browsers").is_dir() else []
    if preinstalled and "CHROMIUM_PATH" not in env:
        env["CHROMIUM_PATH"] = str(preinstalled[-1])

    proc = subprocess.run(
        ["node", str(SMOKE), str(DIST), str(out),
         *[str(fixtures / name) for name in CASES]],
        capture_output=True, text=True, timeout=900, cwd=str(E2E), env=env)
    assert proc.returncode == 0, \
        f"브라우저 스모크 실패:\n{proc.stdout[-2000:]}\n{proc.stderr[-4000:]}"
    return out


def test_browser_downloads_match_the_desktop_conversion(downloads, fixtures):
    """받은 파일이 데스크톱이 만드는 것과 같은 견적서여야 한다."""
    # 견적 날짜는 브라우저도 여기도 Asia/Seoul 기준으로 정한다.
    # 받은 파일이 실제로 그 날짜를 담았는지 먼저 확인하고, 그 날짜로 대조한다.
    today = dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date()

    for name in CASES:
        got = (downloads / f"{Path(name).stem}.xlsx").read_bytes()

        stamped = load_workbook(BytesIO(got))["TOTAL"]["C3"].value
        assert stamped == today.isoformat(), (
            f"{name}: 견적 날짜가 Asia/Seoul 기준이 아닙니다 "
            f"(문서 {stamped!r}, 기대 {today.isoformat()!r})")

        expected = convert.convert_bytes(
            (fixtures / name).read_bytes(), today=today, source_name=name).xlsx

        # 무엇을 같게 볼지는 결정 0005·0009 가 정한다 — ZIP 바이트가 아니라
        # Excel 이 읽는 내용이다. 두 경로 모두 같은 Rust 코어를 부르지만
        # wasm 과 네이티브 확장이라 압축·색 표기가 다를 수 있다.
        want = load_workbook(BytesIO(expected))
        have = load_workbook(BytesIO(got))
        assert want.sheetnames == have.sheetnames, name
        problems = []
        for sheet in want.sheetnames:
            problems.extend(xlsx_content.sheet_problems(name, sheet, want[sheet], have[sheet]))
        assert not problems, name + ":" + chr(10) + chr(10).join(problems[:20])


def test_browser_names_the_download_after_the_source(downloads):
    report = json.loads((downloads / "result.json").read_text(encoding="utf-8"))
    for name in CASES:
        assert report[name]["downloaded_as"] == f"{Path(name).stem}.xlsx"
        assert report[name]["bytes"] > 0
        assert not report[name]["error_shown"], report[name]["status_text"]


def test_one_batch_yields_one_file_per_input(downloads):
    """여러 건을 한 번에 골라도 건마다 한 개씩, 제 이름으로 내려와야 한다."""
    report = json.loads((downloads / "result.json").read_text(encoding="utf-8"))
    batch = report["#batch"]
    assert batch["selected"] == len(CASES)
    assert batch["downloaded"] == len(CASES), batch["status_text"]
    assert "실패" not in batch["status_text"], batch["status_text"]


def test_the_page_reports_the_active_template(downloads):
    """어떤 양식으로 만든 견적서인지 화면에 남아야 한다."""
    report = json.loads((downloads / "result.json").read_text(encoding="utf-8"))
    assert report["#page"]["template_version"].startswith("sha256-")
    assert not report["#page"]["problems"]
