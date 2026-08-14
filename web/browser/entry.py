"""브라우저(Pyodide) 안에서 도는 변환 진입점.

Cloudflare Workers Free 플랜의 CPU 한도(요청당 10 ms)로는 XLSX 생성을 할 수
없다(계획서 §18.3 실측: 가장 작은 견적서도 73 ms). 그래서 무료 계정에서는
변환을 **브라우저에서** 돌리고 Cloudflare 는 정적 자산만 내려 준다.

여기서 하는 일은 JS 가 넘긴 바이트를 `api` 층 자료형으로 바꾸고, 돌려받은
응답을 JS 가 읽을 수 있는 형태로 바꾸는 것뿐이다. **변환 규칙은 한 줄도 여기
없다.** `worker.py` 가 Workers 런타임에 대해 하는 일과 정확히 같은 역할이며,
부르는 함수(`api.convert_response`)도 같다. 그래서 서버로 돌리든 브라우저로
돌리든 같은 입력은 같은 바이트를 낸다.

    worker.py   JS Request  -> api.convert_response -> JS Response
    entry.py    JS Uint8Array -> api.convert_response -> JS Uint8Array

같은 것을 쓴다는 사실은 테스트가 지킨다
(`web/tests/test_browser_engine.py`, `web/tests/test_browser_parity.py`).
"""
from __future__ import annotations

import api
import clock
import errors
import template


def _as_dict(response: "api.ApiResponse") -> dict:
    """JS 로 넘길 형태. 본문은 bytes 그대로 둔다 (인코딩 손상 방지)."""
    return {
        "status": response.status,
        "headers": dict(response.headers),
        "body": response.body,
        "log": dict(response.log),
    }


def convert(filename: str, content, content_type: str = "",
            deployment_version: str = "browser",
            request_id: str | None = None) -> dict:
    """업로드 한 건을 견적서로 바꾼다. 서버의 `POST /api/v1/convert` 와 같다.

    Args:
        filename: 사용자가 고른 파일 이름.
        content: XML 바이트 (JS `Uint8Array` 가 넘어온다).
        content_type: 브라우저가 붙인 MIME.

    Returns:
        status / headers / body / log. 실패해도 예외를 던지지 않고 서버와 같은
        오류 응답을 돌려준다.
    """
    request_id = request_id or api.new_request_id()

    try:
        template_bytes = template.template_bytes()
    except errors.ApiError as err:
        return _as_dict(api.error_response(err, request_id))

    upload = api.Upload(filename=filename, content=bytes(content),
                        content_type=content_type or "")
    response = api.convert_response(
        [upload],
        template_bytes=template_bytes,
        template_version=template.template_version(),
        deployment_version=deployment_version,
        request_id=request_id,
        # 견적 날짜는 브라우저의 지역 시간이 아니라 Asia/Seoul 기준이다.
        # 서버 경로와 같은 함수를 쓴다.
        today=clock.seoul_today(),
    )
    return _as_dict(response)


def template_version() -> str:
    """화면 아래에 표시할 활성 템플릿 판본."""
    return template.template_version()


def today() -> str:
    """이번 변환이 쓸 견적 날짜 (Asia/Seoul). 동일성 검증이 날짜를 맞추는 데 쓴다."""
    return clock.seoul_today().isoformat()
