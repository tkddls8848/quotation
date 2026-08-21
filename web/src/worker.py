"""Cloudflare Python Worker 진입점 (계획서 §4, §5.2).

역할은 셋뿐이다.

    1. JS Request 를 `api` 층의 순수 자료형으로 바꾼다
    2. 번들에 담긴 활성 템플릿을 넘긴다 (`template.py`)
    3. `api` 층이 돌려준 응답을 JS Response 로 바꾸고 구조화 로그를 남긴다

변환 규칙은 여기 없다. 전부 `quotation.core` 와 `conversion_adapter` 에 있다.
데스크톱 전용 모듈(`quotation_desktop.*`, `tkinter`, `os.startfile`)은 절대
import 하지 않는다.
"""
from __future__ import annotations

import json

from workers import Response, WorkerEntrypoint  # Workers 런타임이 제공한다

import api
import clock
import errors
import template

API_PREFIX = "/api/v1"


async def _read_bytes(entry) -> bytes:
    """업로드된 File 의 본문 -> bytes.

    `workers` SDK 의 `File` 은 `bytes()` 를 준다. JS 쪽 `arrayBuffer()` 를 부르면
    안 된다 — SDK 가 감싼 파이썬 객체에는 그 이름이 없다.
    """
    return bytes(await entry.bytes())


async def _uploads(request, request_id: str) -> list[api.Upload]:
    """multipart/form-data 의 파일 필드를 읽는다.

    **여기 이름은 `workers` SDK 의 파이썬 API 다.** SDK 는 JS Request 를 파이썬
    `Request` 로, FormData 를 `FormData` 로, 파일을 `File` 로 감싸서 넘긴다.
    그래서 JS 이름(`formData`, `getAll`, `arrayBuffer`, `type`)을 부르면
    `AttributeError` 가 나고, 그것이 아래 `except` 에 걸려 사용자에게는
    "첨부 화일을 읽지 못했습니다" 로만 보인다. 실제로 그렇게 죽은 적이 있다.

        JS               workers SDK
        formData()   ->  form_data()
        getAll()     ->  get_all()
        arrayBuffer() -> bytes()
        .type        ->  .content_type

    이 대응이 어긋나지 않는지는 `web/tests/test_worker_runtime.py` 가 지킨다.
    """
    content_type = (request.headers.get("content-type") or "").lower()
    if "multipart/form-data" not in content_type:
        raise errors.invalid_request("multipart/form-data 로 보내야 합니다.")

    try:
        form = await request.form_data()
        entries = form.get_all("file")
    except Exception as exc:  # 깨진 multipart
        # 무엇 때문에 막혔는지는 로그에 남긴다. 예전에는 이 자리에서 삼킨
        # AttributeError 가 사용자 문구 하나로만 보여, 모든 변환이 실패하는데도
        # 배포 로그에 아무 단서가 없었다. 예외 **종류만** 남기므로 견적 내용이
        # 새지 않는다 (계획서 §13).
        _note(request_id, "upload_read_failed", type(exc).__name__)
        raise errors.invalid_request("첨부 화일을 읽지 못했습니다.") from exc

    found: list[api.Upload] = []
    for entry in entries:
        if isinstance(entry, str) or not hasattr(entry, "bytes"):
            _note(request_id, "upload_not_a_file", type(entry).__name__)
            raise errors.invalid_request("첨부 화일을 읽지 못했습니다.")
        found.append(api.Upload(
            filename=getattr(entry, "name", "") or "",
            content=await _read_bytes(entry),
            content_type=getattr(entry, "content_type", "") or "",
        ))

    return found


def _js_response(result: api.ApiResponse, request_id: str) -> Response:
    _log(result, request_id)
    return Response(result.body, status=result.status, headers=result.headers)


def _note(request_id: str, event: str, detail: str) -> None:
    """진단용 한 줄. 견적 내용이 아니라 **무엇이 막았는지** 만 남긴다.

    사용자에게 보이는 문구는 바뀌지 않는다. 운영자가 로그만 보고도 원인을
    좁힐 수 있게 하려는 것이다 (사고 기록 incidents/0001).
    """
    print(json.dumps({"request_id": request_id, "event": event,
                      "detail": detail}, ensure_ascii=False))


def _log(result: api.ApiResponse, request_id: str) -> None:
    """허용 필드만 구조화해 남긴다 (계획서 §13).

    XML 본문, 파일명, 금액, 고객 정보는 남기지 않는다.
    """
    print(json.dumps({"request_id": request_id, **result.log},
                     ensure_ascii=False))


class Default(WorkerEntrypoint):
    async def fetch(self, request):
        url = request.url
        path = _path_of(url)
        request_id = api.new_request_id()

        if not path.startswith(API_PREFIX):
            # 정적 자산. wrangler.jsonc 의 run_worker_first 설정상 보통 여기 오지 않는다.
            return await self.env.ASSETS.fetch(request)

        try:
            return await self._api(request, url, path, request_id)
        except errors.ApiError as err:
            return _js_response(api.error_response(err, request_id), request_id)
        except Exception:  # noqa: BLE001 — 사용자에게 내부 사정을 노출하지 않는다
            return _js_response(
                api.error_response(errors.conversion_failed(), request_id),
                request_id)

    async def _api(self, request, url: str, path: str, request_id: str):
        method = request.method.upper()
        deployment_version = getattr(self.env, "DEPLOYMENT_VERSION", "") or "dev"

        if path == f"{API_PREFIX}/config":
            if method not in ("GET", "HEAD"):
                return _js_response(api.method_not_allowed(request_id, "GET"),
                                    request_id)
            return _js_response(api.config_response(request_id), request_id)

        if path == f"{API_PREFIX}/status":
            if method not in ("GET", "HEAD"):
                return _js_response(api.method_not_allowed(request_id, "GET"),
                                    request_id)
            return _js_response(
                api.status_response(
                    request_id,
                    deployment_version=deployment_version,
                    template_version=template.template_version()),
                request_id)

        if path == f"{API_PREFIX}/convert":
            if method != "POST":
                return _js_response(api.method_not_allowed(request_id, "POST"),
                                    request_id)
            api.check_same_origin(
                request_url=url,
                origin=request.headers.get("origin"),
                sec_fetch_site=request.headers.get("sec-fetch-site"),
            )
            uploads = await _uploads(request, request_id)
            result = api.convert_response(
                uploads,
                template_bytes=template.template_bytes(),
                template_version=template.template_version(),
                deployment_version=deployment_version,
                request_id=request_id,
                # 견적 날짜는 Worker 의 UTC 가 아니라 Asia/Seoul 기준으로 한 번만 정한다
                today=clock.seoul_today(),
            )
            return _js_response(result, request_id)

        return _js_response(api.not_found(request_id), request_id)


def _path_of(url: str) -> str:
    """전체 URL 에서 경로만. urlsplit 은 Pyodide 표준 라이브러리에 있다."""
    from urllib.parse import urlsplit

    return urlsplit(url).path or "/"
