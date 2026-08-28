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

ROOT = Path(__file__).resolve().parents[2]
ENGINE_DIR = ROOT / "web" / "frontend" / "public" / "engine"
DRIVER = ROOT / "web" / "scripts" / "browser_convert.mjs"

#: 대조할 파일. 어느 쪽 문서(IBM/레노버)든 사람이 고르지 않고 내용으로
#: 갈린다(`quotation.core.modes.detect`) — 브라우저와 CPython 이 같은 판단을
#: 내려야 한다.
CASES = (
    "new_quote.xml",
    "upgrade_quote.xml",
    "no_charge.xml",
    "euckr_quote.xml",
    # 통합(레노버) 문서도 브라우저와 CPython 이 같은 바이트를 내야 한다.
    "integrated_quote.xml",
    # 요약표를 푸는 길(base64+gzip)도 브라우저에서 같아야 한다.
    "integrated_summary_quote.xml",
)

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


def _cpython(fixtures, name: str, today: dt.date) -> api.ApiResponse:
    """서버(그리고 데스크톱)와 같은 경로. 브라우저가 부르는 함수와 같은 함수다.

    템플릿은 고정 바이트가 아니라 `template.template_bytes` 함수를 그대로
    준다 — IBM 문서와 레노버 문서가 템플릿이 서로 달라서, 브라우저와 똑같이
    알아낸 모드로 골라야 바이트가 맞아떨어진다.
    """
    import template

    return api.convert_response(
        [api.Upload(filename=name,
                    content=(fixtures / name).read_bytes(),
                    content_type="text/xml")],
        template_bytes=template.template_bytes,
        template_version=template.template_version,
        deployment_version="parity",
        request_id="parity",
        today=today)


# --- 내용 대조 -----------------------------------------------------------------
#
# 브라우저는 Rust→WASM 엔진으로, CPython 은 openpyxl 로 같은 견적서를 만든다.
# OOXML 을 적는 라이브러리가 서로 달라 ZIP 바이트는 같지 않다 — 부품 순서,
# 압축, 색을 적는 방식(팔레트 색인 27 = ARGB FFCCFFFF)이 다르다. 무엇을 같게
# 볼지는 [결정 0005](../../doc/decisions/0005-accept-meaningful-xlsx-parity.md)
# 가 정한다: **Excel 이 읽는 내용**과 **첫 페이지 도형**이다.

@pytest.mark.parametrize("name", CASES)
def test_browser_xlsx_matches_cell_by_cell(name, browser_results, fixtures):
    """값·수식·서식·글꼴·채우기·테두리·정렬·병합·인쇄영역·행높이."""
    import openpyxl
    import rust_parity_workbook as judge

    result = browser_results[name]
    assert result["status"] == 200, result.get("body_utf8")
    expected = _cpython(fixtures, name, dt.date.fromisoformat(result["today"]))
    assert expected.status == 200

    want = openpyxl.load_workbook(BytesIO(expected.body))
    got = openpyxl.load_workbook(BytesIO(result["xlsx"]))
    assert want.sheetnames == got.sheetnames

    problems = []
    for sheet in want.sheetnames:
        problems.extend(judge.sheet_problems(name, sheet, want[sheet], got[sheet]))
    assert not problems, "\n".join(problems[:20])


@pytest.mark.parametrize("name", CASES)
def test_browser_xlsx_keeps_every_part_the_server_ships(name, browser_results,
                                                        fixtures):
    """서버 산출물에 있는 부품은 하나도 빠지면 안 된다.

    더 실리는 것은 막지 않는다. umya 는 템플릿의 프린터 설정을 그대로 들고
    가고 문자열을 `sharedStrings.xml` 로 모으는데, openpyxl 은 프린터 설정을
    버리고 문자열을 셀 안에 적는다. 둘 다 Excel 이 읽는 내용은 같다
    (결정 0005). 빠지는 부품은 다르다 — 그림이 사라지는 것이 그런 경우다.
    """
    result = browser_results[name]
    expected = _cpython(fixtures, name, dt.date.fromisoformat(result["today"]))

    server = zipfile.ZipFile(BytesIO(expected.body))
    browser = zipfile.ZipFile(BytesIO(result["xlsx"]))
    with server, browser:
        missing = sorted(set(server.namelist()) - set(browser.namelist()))
        extra = sorted(set(browser.namelist()) - set(server.namelist()))
    assert not missing, f"브라우저 산출물에 없는 부품: {missing}"
    if extra:
        print(f"[{name}] 브라우저에만 있는 부품(진단): {extra}")


def test_browser_keeps_the_template_drawings(browser_results, template_bytes):
    """로고와 머리말 도형이 템플릿 원본 그대로 실려 나오는지 (양식 뒤틀림 방지)."""
    produced = zipfile.ZipFile(BytesIO(browser_results["new_quote.xml"]["xlsx"]))
    template = zipfile.ZipFile(BytesIO(template_bytes))
    with produced, template:
        parts = [name for name in produced.namelist()
                 if name.startswith(("xl/media/", "xl/drawings/"))]
        assert parts
        for part in parts:
            assert produced.read(part) == template.read(part), part


# --- 계약 대조 -----------------------------------------------------------------

@pytest.mark.parametrize("name", CASES)
def test_browser_returns_the_same_headers_and_log(name, browser_results,
                                                  fixtures):
    """상태 코드·다운로드 이름·로그 항목이 서버 응답과 같아야 한다."""
    result = browser_results[name]
    expected = _cpython(fixtures, name, dt.date.fromisoformat(result["today"]))

    assert result["status"] == expected.status
    assert result["headers"]["Content-Disposition"] == \
        expected.headers["Content-Disposition"]
    assert result["headers"]["Content-Type"] == expected.headers["Content-Type"]
    assert result["headers"]["X-Template-Version"] == \
        expected.headers["X-Template-Version"]
    for field in ("outcome", "status", "mode", "template_version", "line_count",
                  "group_count", "input_size_bucket", "output_size_bucket"):
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
    # 는 6.0.0 — 실측 measurements/runtime.md). 운영에서는 Worker 도 브라우저도 6.0.0 이라
    # 같은 문장이 나온다. 변환 결과와는 무관하다.
    prefix = "XML을 로드하는중 장애 발생. 장애코드: "
    if want["message"].startswith(prefix):
        assert got["message"].startswith(prefix)
    else:
        assert got["message"] == want["message"]
