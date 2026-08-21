"""`worker.py` 가 Workers 런타임 객체를 제대로 다루는지 확인한다.

`test_worker_smoke.py` 는 소스를 정적으로만 본다. 그것으로는 못 잡는 사고가
실제로 났다. 배포된 Worker 가 **모든** 변환을 이 한 줄로 거절했다.

    {"error": {"code": "INVALID_REQUEST",
               "message": "첨부 화일을 읽지 못했습니다.", ...}}

원인은 이름이었다. `workers` SDK 는 JS 객체를 그대로 넘기지 않고 파이썬
클래스로 감싸서 준다. 그런데 코드가 JS 이름을 불렀다.

    await request.formData()   -> AttributeError -> except 에 걸려 위 메시지
    form.getAll("file")        -> AttributeError
    entry.arrayBuffer()        -> AttributeError
    entry.type                 -> None

`except Exception` 이 그것을 전부 "첨부 화일을 읽지 못했습니다" 로 접어 버려
배포 전에는 아무 신호도 없었다. 그래서 여기서는 SDK 와 같은 모양의 가짜 런타임을
만들어 `fetch()` 를 실제로 돌린다. 이름이 어긋나면 이 테스트가 먼저 죽는다.

가짜가 진짜와 어긋나지 않는지는 `test_worker_uses_only_real_sdk_names` 가
`pywrangler sync` 로 받아 둔 실제 SDK 소스를 읽어 대조한다.
"""
from __future__ import annotations

import ast
import asyncio
import json
import sys
from http import HTTPMethod
from http.client import HTTPMessage
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "web"
#: pywrangler sync 가 Pyodide 대상 의존성을 풀어 두는 자리.
VENDORED_SDK = WEB / "python_modules" / "workers"


# --- SDK 와 같은 모양의 가짜 런타임 ---------------------------------------------
#
# 이름과 반환형은 workers-runtime-sdk 를 그대로 따른다.
#   Request.form_data() -> FormData        (request.py)
#   FormData.get_all()  -> list            (formdata.py)
#   File.bytes()        -> bytes           (blob.py)
#   File.content_type   -> str             (blob.py, Blob.content_type)
#   Response(body, status=, headers=)      (response.py)

class FakeFile:
    """`workers.File`. JS 의 `arrayBuffer()`·`type` 은 **일부러 없다.**"""

    def __init__(self, name: str, content: bytes, content_type: str = "text/xml"):
        self.name = name
        self.content_type = content_type
        self._content = content

    @property
    def size(self) -> int:
        return len(self._content)

    async def bytes(self) -> bytes:
        return self._content

    async def text(self) -> str:
        return self._content.decode("utf-8")


class FakeFormData:
    """`workers.FormData`. JS 의 `getAll` 은 **일부러 없다.**"""

    def __init__(self, fields: dict[str, list]):
        self._fields = fields

    def get_all(self, key: str) -> list:
        return list(self._fields.get(key, []))

    def keys(self):
        return self._fields.keys()


class FakeRequest:
    """`workers.Request`. JS 의 `formData` 는 **일부러 없다.**"""

    def __init__(self, url: str, method: str = "GET", headers: dict | None = None,
                 form: FakeFormData | None = None, broken_body: bool = False):
        self.url = url
        self.method = HTTPMethod[method]          # SDK 와 같이 열거형이다
        self.headers = HTTPMessage()
        for key, value in (headers or {}).items():
            self.headers[key] = value
        self._form = form
        self._broken = broken_body

    async def form_data(self) -> FakeFormData:
        if self._broken:
            raise ValueError("깨진 multipart")
        assert self._form is not None
        return self._form


class FakeResponse:
    def __init__(self, body=None, status=200, headers=None, **_):
        assert isinstance(body, (bytes, str)) or body is None, type(body)
        self.body = body
        self.status = status
        self.headers = dict(headers or {})

    def json(self) -> dict:
        return json.loads(self.body.decode("utf-8"))


class FakeWorkerEntrypoint:
    def __init__(self, env):
        self.env = env


class FakeAssets:
    def __init__(self):
        self.calls = []

    async def fetch(self, request):
        self.calls.append(request)
        return FakeResponse(b"<html>", 200)


class FakeEnv:
    def __init__(self, **values):
        self.ASSETS = FakeAssets()
        for key, value in values.items():
            setattr(self, key, value)


@pytest.fixture()
def worker(monkeypatch):
    """가짜 런타임을 끼워 `worker.py` 를 불러온다."""
    import types

    module = types.ModuleType("workers")
    module.Response = FakeResponse
    module.WorkerEntrypoint = FakeWorkerEntrypoint
    monkeypatch.setitem(sys.modules, "workers", module)
    # 다른 테스트가 보는 상태를 더럽히지 않는다
    # (test_worker_smoke.py 는 worker 가 import 되지 않는 것을 확인한다).
    monkeypatch.delitem(sys.modules, "worker", raising=False)

    import worker as loaded

    yield loaded
    sys.modules.pop("worker", None)


def _run(coro):
    return asyncio.run(coro)


def _entry(worker, **env):
    return worker.Default(FakeEnv(DEPLOYMENT_VERSION="d-test", **env))


def _post(fixtures, name: str, *, field: str = "file",
          content_type: str = "text/xml") -> FakeRequest:
    return FakeRequest(
        "https://quotation.example/api/v1/convert",
        method="POST",
        headers={"content-type": "multipart/form-data; boundary=x",
                 "sec-fetch-site": "same-origin"},
        form=FakeFormData({field: [
            FakeFile(name, (fixtures / name).read_bytes(), content_type)]}))


# --- 변환 ---------------------------------------------------------------------

def test_convert_reads_the_upload_and_returns_the_xlsx(worker, fixtures):
    """배포에서 깨졌던 바로 그 경로. 여기가 붉으면 내보내면 안 된다."""
    response = _run(_entry(worker).fetch(_post(fixtures, "new_quote.xml")))

    assert response.status == 200, getattr(response, "body", b"")[:400]
    assert response.headers["Content-Type"].endswith("spreadsheetml.sheet")
    assert response.body[:2] == b"PK"          # xlsx 는 zip 이다
    assert "new_quote.xlsx" in response.headers["Content-Disposition"]
    assert response.headers["X-Template-Version"].startswith("sha256-")


def test_convert_reads_a_euckr_upload(worker, fixtures):
    response = _run(_entry(worker).fetch(_post(fixtures, "euckr_quote.xml")))
    assert response.status == 200, getattr(response, "body", b"")[:400]


def test_missing_file_field_is_a_plain_bad_request(worker, fixtures):
    response = _run(_entry(worker).fetch(
        _post(fixtures, "new_quote.xml", field="attachment")))
    assert response.status == 400
    assert response.json()["error"]["code"] == "INVALID_REQUEST"


def test_broken_multipart_is_reported_as_such(worker):
    request = FakeRequest(
        "https://quotation.example/api/v1/convert", method="POST",
        headers={"content-type": "multipart/form-data; boundary=x",
                 "sec-fetch-site": "same-origin"},
        broken_body=True)
    response = _run(_entry(worker).fetch(request))
    assert response.status == 400
    assert response.json()["error"]["message"] == "첨부 화일을 읽지 못했습니다."


def test_text_field_instead_of_a_file_is_rejected(worker):
    request = FakeRequest(
        "https://quotation.example/api/v1/convert", method="POST",
        headers={"content-type": "multipart/form-data; boundary=x",
                 "sec-fetch-site": "same-origin"},
        form=FakeFormData({"file": ["그냥 글자"]}))
    response = _run(_entry(worker).fetch(request))
    assert response.status == 400


def test_non_multipart_post_is_rejected(worker):
    request = FakeRequest(
        "https://quotation.example/api/v1/convert", method="POST",
        headers={"content-type": "application/json",
                 "sec-fetch-site": "same-origin"})
    response = _run(_entry(worker).fetch(request))
    assert response.status == 400
    assert "multipart/form-data" in response.json()["error"]["message"]


# --- 그 밖의 경로 ---------------------------------------------------------------

def test_status_and_config_answer(worker):
    entry = _entry(worker)
    for path, key in (("/api/v1/status", "template_versions"),
                      ("/api/v1/config", "max_upload_bytes")):
        response = _run(entry.fetch(
            FakeRequest(f"https://quotation.example{path}")))
        assert response.status == 200
        assert key in response.json()


def test_unknown_api_path_is_404(worker):
    response = _run(_entry(worker).fetch(
        FakeRequest("https://quotation.example/api/v1/nope")))
    assert response.status == 404


def test_static_paths_go_to_the_assets_binding(worker):
    entry = _entry(worker)
    response = _run(entry.fetch(FakeRequest("https://quotation.example/")))
    assert response.status == 200
    assert entry.env.ASSETS.calls, "정적 자산은 ASSETS 바인딩이 처리해야 한다"


def test_cross_origin_post_is_refused(worker, fixtures):
    request = _post(fixtures, "new_quote.xml")
    request.headers.replace_header("sec-fetch-site", "cross-site")
    response = _run(_entry(worker).fetch(request))
    assert response.status == 400


# --- 가짜가 진짜와 어긋나지 않는지 ------------------------------------------------

def _class_members(path: Path) -> dict[str, set[str]]:
    """소스를 파싱해 클래스별 메서드·프로퍼티 이름을 모은다.

    SDK 는 `import js` 로 시작해 Pyodide 밖에서는 import 되지 않는다. 그래서
    실행하지 않고 읽기만 한다.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    members: dict[str, set[str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            members[node.name] = {
                child.name for child in node.body
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))}
    return members


@pytest.mark.skipif(not (VENDORED_SDK / "request.py").is_file(),
                    reason="workers SDK 가 없습니다 (python3 -m pywrangler sync)")
def test_worker_uses_only_real_sdk_names():
    """`worker.py` 가 부르는 이름이 실제 SDK 에 있어야 한다.

    반대쪽도 함께 못박는다 — JS 이름은 SDK 에 **없어야** 한다. 있다면 SDK 가
    양쪽을 다 받아 주게 바뀐 것이고, 그때는 이 테스트를 고쳐야 한다.
    """
    request = _class_members(VENDORED_SDK / "request.py")["Request"]
    form = _class_members(VENDORED_SDK / "formdata.py")["FormData"]
    blob = _class_members(VENDORED_SDK / "blob.py")
    file_members = blob["File"] | blob["Blob"]

    assert "form_data" in request and "formData" not in request
    assert "get_all" in form and "getAll" not in form
    assert "bytes" in file_members and "arrayBuffer" not in file_members

    source = (WEB / "src" / "worker.py").read_text(encoding="utf-8")
    for js_name in ("formData(", "getAll(", "arrayBuffer("):
        assert js_name not in source, (
            f"worker.py 가 JS 이름 {js_name!r} 을 부릅니다. "
            "workers SDK 는 파이썬 이름을 씁니다")
