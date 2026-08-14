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


async def _read_bytes(blob) -> bytes:
    """JS Blob/File 본문 -> bytes."""
    buffer = await blob.arrayBuffer()
    data = buffer.to_py()
    return data.tobytes() if hasattr(data, "tobytes") else bytes(data)


async def _uploads(request) -> list[api.Upload]:
    """multipart/form-data 의 파일 필드를 읽는다."""
    content_type = (request.headers.get("content-type") or "").lower()
    if "multipart/form-data" not in content_type:
        raise errors.invalid_request("multipart/form-data 로 보내야 합니다.")

    try:
        form = await request.formData()
    except Exception as exc:  # 깨진 multipart
        raise errors.invalid_request("첨부 화일을 읽지 못했습니다.") from exc

    found: list[api.Upload] = []
    for entry in form.getAll("file"):
        if isinstance(entry, str) or not hasattr(entry, "arrayBuffer"):
            raise errors.invalid_request("첨부 화일을 읽지 못했습니다.")
        found.append(api.Upload(
            filename=getattr(entry, "name", "") or "",
            content=await _read_bytes(entry),
            content_type=getattr(entry, "type", "") or "",
        ))
    return found


def _js_response(result: api.ApiResponse, request_id: str) -> Response:
    _log(result, request_id)
    return Response(result.body, status=result.status, headers=result.headers)


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
            uploads = await _uploads(request)
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
