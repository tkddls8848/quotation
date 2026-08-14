"""실제 브라우저가 만든 견적서가 CPython 산출물과 같은지 확인한다.

`test_browser_parity.py` 는 파이썬이 같은 결과를 내는지를 본다. 여기서는 그것이
**빌드된 화면을 거쳐 사용자 손에 닿을 때까지** 그대로 남는지를 본다. 운영과 같은
CSP 를 건 서버에서 dist 를 내려 주고, Chromium 으로 파일을 골라 변환 버튼을 눌러
실제로 내려받은 파일을 대조한다.

돌리려면 세 가지가 있어야 한다. 없으면 건너뛴다.

    python web/scripts/sync_core.py
    python web/scripts/build_browser_engine.py
    npm --prefix web/frontend ci && npm --prefix web/frontend run build
    npm --prefix web/frontend install --no-save playwright   (브라우저 구동)
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from io import BytesIO
from pathlib import Path

import pytest
from openpyxl import load_workbook

import api
import clock
from xlsx_parity import differences

ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "web" / "frontend"
DIST = FRONTEND / "dist"
SMOKE = FRONTEND / "e2e" / "browser_smoke.mjs"

CASES = ("new_quote.xml", "euckr_quote.xml")


def _reason() -> str | None:
    if shutil.which("node") is None:
        return "node 가 없습니다"
    if not (DIST / "py" / "engine.json").is_file():
        return "빌드된 dist 에 변환 엔진이 없습니다 (build_browser_engine.py + vite build)"
    if not (FRONTEND / "node_modules" / "playwright").is_dir():
        return "playwright 가 없습니다"
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
        capture_output=True, text=True, timeout=900, cwd=str(FRONTEND), env=env)
    assert proc.returncode == 0, \
        f"브라우저 스모크 실패:\n{proc.stdout[-2000:]}\n{proc.stderr[-4000:]}"
    return out


def test_browser_downloads_match_the_cpython_conversion(downloads, fixtures,
                                                        template_bytes):
    """받은 파일이 서버·데스크톱이 만드는 것과 같은 견적서여야 한다."""
    # 견적 날짜는 브라우저도 여기도 Asia/Seoul 기준으로 정한다 (clock.py).
    # 받은 파일이 실제로 그 날짜를 담았는지 먼저 확인하고, 그 날짜로 대조한다.
    today = clock.seoul_today()

    for name in CASES:
        got = (downloads / f"{Path(name).stem}.xlsx").read_bytes()

        stamped = load_workbook(BytesIO(got))["TOTAL"]["C3"].value
        assert stamped == today.isoformat(), (
            f"{name}: 견적 날짜가 Asia/Seoul 기준이 아닙니다 "
            f"(문서 {stamped!r}, 기대 {today.isoformat()!r})")

        expected = api.convert_response(
            [api.Upload(filename=name,
                        content=(fixtures / name).read_bytes(),
                        content_type="text/xml")],
            template_bytes=template_bytes, template_version="e2e",
            deployment_version="e2e", request_id="e2e", today=today)
        assert expected.status == 200

        problems = differences(expected.body, got)
        assert not problems, f"{name}:\n" + "\n".join(problems)


def test_browser_names_the_download_after_the_source(downloads):
    report = json.loads((downloads / "result.json").read_text(encoding="utf-8"))
    for name in CASES:
        assert report[name]["downloaded_as"] == f"{Path(name).stem}.xlsx"
        assert report[name]["bytes"] > 0
        assert not report[name]["error_shown"], report[name]["status_text"]


def test_the_page_reports_the_active_template(downloads):
    """어떤 양식으로 만든 견적서인지 화면에 남아야 한다."""
    report = json.loads((downloads / "result.json").read_text(encoding="utf-8"))
    assert report["#page"]["template_version"].startswith("sha256-")
    assert not report["#page"]["problems"]
