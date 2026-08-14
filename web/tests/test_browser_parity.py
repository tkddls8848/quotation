"""브라우저 변환과 CPython 변환이 같은 결과를 내는지 대조한다.

무료 계정에서는 변환이 브라우저(Pyodide)에서 돈다. **결과가 조금이라도 달라지면
안 된다** — 금액 한 자리, 품목 한 줄, 서식 한 칸도. 그래서 화면이 쓰는 엔진
(`web/frontend/src/engine.js`)을 Node 에서 **같은 파일 그대로** 돌려 나온 바이트를
CPython 산출물과 대조한다.

대조 방식은 둘이다.

    1. .xlsx(zip) 안의 모든 부품을 바이트 단위로 비교한다. 시트, 스타일,
       그림·도형, 관계 파일까지 전부 들어간다.
    2. openpyxl 로 열어 셀 단위(값·수식·서식·정렬·글꼴·병합·열너비·시트순서)로
       비교한다 — 골든 회귀와 같은 비교기(`tools/compare.py`)를 쓴다.

바이트 비교에서 딱 두 가지만 정규화한다. 둘 다 견적서 내용이 아니다.

    docProps/core.xml 의 <dcterms:modified>   파일을 만든 **시각**
    <mergeCell> 의 나열 순서                  병합 **집합** 은 같다. 순서는
                                              openpyxl 이 집합을 순회한 순서일
                                              뿐이고 Excel 은 순서를 보지 않는다.

엔진 자산이 없거나 node 가 없으면 건너뛴다.

    python web/scripts/sync_core.py
    python web/scripts/build_browser_engine.py
"""
from __future__ import annotations

import datetime as dt
import json
import shutil
import subprocess
import zipfile
from io import BytesIO
from pathlib import Path

import pytest

import api
from xlsx_parity import differences

ROOT = Path(__file__).resolve().parents[2]
ENGINE_DIR = ROOT / "web" / "frontend" / "public" / "py"
DRIVER = ROOT / "web" / "scripts" / "browser_convert.mjs"

CASES = ("new_quote.xml", "upgrade_quote.xml", "no_charge.xml", "euckr_quote.xml")

#: 실패도 서버와 같아야 한다. (이름, 내용, 기대 상태)
ERROR_CASES = (
    ("broken.xml", b"<CFXML><CFData><ProductLineItem>", 422),
    ("empty.xml", b"   \n", 400),
    ("notes.txt", "XML 이 아닙니다".encode("utf-8"), 415),
)

pytestmark = pytest.mark.skipif(
    not (ENGINE_DIR / "engine.json").is_file() or shutil.which("node") is None,
    reason="브라우저 엔진 자산이 없습니다. "
           "python web/scripts/build_browser_engine.py 를 먼저 실행하십시오",
)


@pytest.fixture(scope="module")
def browser_results(tmp_path_factory, fixtures) -> dict[str, dict]:
    """엔진을 한 번 띄워 모든 사례를 변환한다 (Pyodide 기동이 느리다)."""
    out = tmp_path_factory.mktemp("browser")
    bad = tmp_path_factory.mktemp("bad")
    for name, content, _ in ERROR_CASES:
        (bad / name).write_bytes(content)

    inputs = [str(fixtures / name) for name in CASES]
    inputs += [str(bad / name) for name, _, _ in ERROR_CASES]

    proc = subprocess.run(
        ["node", str(DRIVER), str(ENGINE_DIR), str(out), *inputs],
        capture_output=True, text=True, timeout=600)
    assert proc.returncode == 0, f"브라우저 엔진 실행 실패:\n{proc.stderr[-4000:]}"

    results = {}
    for name in [*CASES, *(n for n, _, _ in ERROR_CASES)]:
        stem = Path(name).stem
        meta = json.loads((out / f"{stem}.json").read_text(encoding="utf-8"))
        xlsx = out / f"{stem}.xlsx"
        meta["xlsx"] = xlsx.read_bytes() if xlsx.is_file() else b""
        results[name] = meta
    return results


def _cpython(fixtures, name: str, today: dt.date, template_bytes: bytes) -> api.ApiResponse:
    """서버(그리고 데스크톱)와 같은 경로. 브라우저가 부르는 함수와 같은 함수다."""
    return api.convert_response(
        [api.Upload(filename=name,
                    content=(fixtures / name).read_bytes(),
                    content_type="text/xml")],
        template_bytes=template_bytes,
        template_version="parity",
        deployment_version="parity",
        request_id="parity",
        today=today)


# --- 바이트 대조 ---------------------------------------------------------------

@pytest.mark.parametrize("name", CASES)
def test_browser_xlsx_is_byte_identical(name, browser_results, fixtures,
                                        template_bytes):
    result = browser_results[name]
    assert result["status"] == 200, result.get("body_utf8")

    expected = _cpython(fixtures, name, dt.date.fromisoformat(result["today"]),
                        template_bytes)
    assert expected.status == 200

    problems = differences(expected.body, result["xlsx"])
    assert not problems, "\n".join(problems)


def test_browser_keeps_the_template_drawings(browser_results):
    """로고와 머리말 도형이 그대로 실려 나오는지 (양식 뒤틀림 방지)."""
    with zipfile.ZipFile(BytesIO(browser_results["new_quote.xml"]["xlsx"])) as z:
        names = z.namelist()
    assert [n for n in names if n.startswith("xl/media/")]
    assert [n for n in names if n.startswith("xl/drawings/")]


# --- 셀 단위 대조 --------------------------------------------------------------

@pytest.mark.parametrize("name", CASES)
def test_browser_xlsx_matches_cell_by_cell(name, browser_results, fixtures,
                                           template_bytes, tmp_path):
    """골든 회귀와 같은 비교기로 한 번 더 본다. 값·수식·서식·병합·열너비."""
    import compare

    result = browser_results[name]
    expected = _cpython(fixtures, name, dt.date.fromisoformat(result["today"]),
                        template_bytes)

    want = tmp_path / "cpython.xlsx"
    got = tmp_path / "browser.xlsx"
    want.write_bytes(expected.body)
    got.write_bytes(result["xlsx"])

    report = compare.compare(want, got, ignore=set())
    assert report.ok, "\n".join(str(d) for d in report.diffs[:20])


# --- 계약 대조 -----------------------------------------------------------------

@pytest.mark.parametrize("name", CASES)
def test_browser_returns_the_same_headers_and_log(name, browser_results,
                                                  fixtures, template_bytes):
    """상태 코드·다운로드 이름·로그 항목이 서버 응답과 같아야 한다."""
    result = browser_results[name]
    expected = _cpython(fixtures, name, dt.date.fromisoformat(result["today"]),
                        template_bytes)

    assert result["status"] == expected.status
    assert result["headers"]["Content-Disposition"] == \
        expected.headers["Content-Disposition"]
    assert result["headers"]["Content-Type"] == expected.headers["Content-Type"]
    for field in ("outcome", "status", "line_count", "group_count",
                  "input_size_bucket", "output_size_bucket"):
        assert result["log"][field] == expected.log[field], field


@pytest.mark.parametrize("name,content,status", ERROR_CASES)
def test_browser_rejects_what_the_server_rejects(name, content, status,
                                                 browser_results,
                                                 template_bytes):
    """거절도 같아야 한다. 같은 상태 코드, 같은 오류 코드, 같은 문구."""
    result = browser_results[name]
    assert result["status"] == status

    expected = api.convert_response(
        [api.Upload(filename=name, content=content, content_type="text/xml")],
        template_bytes=template_bytes, template_version="parity",
        deployment_version="parity", request_id="parity",
        today=dt.date.fromisoformat(result["today"]))

    assert expected.status == status
    got = json.loads(result["body_utf8"])["error"]
    want = expected.json()["error"]
    assert got["code"] == want["code"]

    # 문구는 원본 프로그램과 같은 접두사까지 대조한다. 그 뒤에 붙는 libxml2 의
    # 진단 문장은 lxml 판본마다 말이 달라진다 (여기 CPython 은 6.1.1, Pyodide
    # 는 6.0.0 — 계획서 §18.2). 운영에서는 Worker 도 브라우저도 6.0.0 이라
    # 같은 문장이 나온다. 변환 결과와는 무관하다.
    prefix = "XML을 로드하는중 장애 발생. 장애코드: "
    if want["message"].startswith(prefix):
        assert got["message"].startswith(prefix)
    else:
        assert got["message"] == want["message"]
