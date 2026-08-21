"""요청 검증과 응답 매핑 (계획서 §6).

Workers 런타임 객체를 모르는 순수 층이다. `worker.py` 가 JS Request 를 여기
자료형으로 바꿔 넘기고, 돌려받은 `ApiResponse` 를 JS Response 로 바꾼다.
덕분에 이 층은 CPython 에서 그대로 테스트할 수 있다.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import uuid
from dataclasses import dataclass, field
from urllib.parse import quote as urlquote
from urllib.parse import urlsplit

import conversion_adapter
import errors
import limits

XLSX_CONTENT_TYPE = ("application/vnd.openxmlformats-officedocument"
                     ".spreadsheetml.sheet")
JSON_CONTENT_TYPE = "application/json; charset=utf-8"

#: 계획서 §9. 정적 자산에는 web/frontend/public/_headers 가 같은 정책을 건다.
SECURITY_HEADERS = {
    "Cache-Control": "no-store",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
}

_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
_ASCII_UNSAFE = re.compile(r'[^A-Za-z0-9._ -]')

#: 브라우저가 붙일 수 있는 XML MIME. 확장자와 함께 참고만 하고 최종 판단은 파싱이다.
XML_CONTENT_TYPES = ("text/xml", "application/xml", "text/plain",
                     "application/octet-stream", "")


@dataclass(frozen=True)
class Upload:
    """업로드된 파일 하나."""

    filename: str
    content: bytes
    content_type: str = ""


@dataclass(frozen=True)
class ApiResponse:
    status: int
    headers: dict[str, str]
    body: bytes
    #: 구조화 로그로 남길 허용 필드 (계획서 §13). 원문·파일명·금액은 넣지 않는다.
    log: dict = field(default_factory=dict)

    def json(self) -> dict:
        return json.loads(self.body.decode("utf-8"))


# --- 파일명 -------------------------------------------------------------------

def safe_source_name(raw: str) -> str:
    """업로드 파일명에서 경로와 제어문자를 떼어 낸다.

    브라우저가 보내는 이름을 그대로 믿지 않는다. 한글·공백·`#`·괄호는 살린다.
    """
    name = _CONTROL.sub("", (raw or "").replace("\\", "/")).rsplit("/", 1)[-1]
    name = name.strip().lstrip(".")
    return name or "quotation.xml"


def content_disposition(filename: str) -> str:
    """RFC 5987 형식. 한글 파일명을 그대로 내려받게 한다."""
    fallback = _ASCII_UNSAFE.sub("_", filename).strip() or "quotation.xlsx"
    encoded = urlquote(filename, safe="")
    return f"attachment; filename=\"{fallback}\"; filename*=UTF-8''{encoded}"


# --- 응답 만들기 ---------------------------------------------------------------

def new_request_id() -> str:
    return str(uuid.uuid4())


def _headers(extra: dict[str, str] | None = None) -> dict[str, str]:
    headers = dict(SECURITY_HEADERS)
    headers.update(extra or {})
    return headers


def json_response(status: int, payload: dict, *, request_id: str,
                  extra: dict[str, str] | None = None,
                  log: dict | None = None) -> ApiResponse:
    headers = _headers({"Content-Type": JSON_CONTENT_TYPE,
                        "X-Request-Id": request_id})
    headers.update(extra or {})
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    return ApiResponse(status=status, headers=headers, body=body,
                       log=log or {})


def error_response(err: errors.ApiError, request_id: str,
                   log: dict | None = None) -> ApiResponse:
    fields = {"outcome": "error", "error_code": err.code, "status": err.status}
    fields.update(log or {})
    return json_response(err.status, err.payload(request_id),
                         request_id=request_id, log=fields)


def size_bucket(size: int) -> str:
    """로그에 남길 크기 구간. 정확한 크기는 남기지 않는다 (계획서 §13)."""
    for limit, label in ((64 * 1024, "<=64KiB"), (256 * 1024, "<=256KiB"),
                         (1 * limits.MiB, "<=1MiB"), (4 * limits.MiB, "<=4MiB"),
                         (limits.MAX_UPLOAD_BYTES, "<=10MiB")):
        if size <= limit:
            return label
    return ">10MiB"


# --- 엔드포인트 ---------------------------------------------------------------

def config_response(request_id: str) -> ApiResponse:
    """`GET /api/v1/config` — 클라이언트가 1차 검사에 쓸 공개 설정."""
    return json_response(200, limits.public_config(), request_id=request_id,
                         log={"outcome": "ok", "status": 200})


def status_response(request_id: str, *, deployment_version: str,
                    template_version: str) -> ApiResponse:
    """`GET /api/v1/status` — 배포 버전과 활성 템플릿 버전만."""
    return json_response(200, {"deployment_version": deployment_version,
                               "template_version": template_version},
                         request_id=request_id,
                         log={"outcome": "ok", "status": 200})


def pick_upload(uploads: list[Upload]) -> Upload:
    """한 요청에 파일 하나. 형식과 크기를 여기서 1차로 거른다."""
    if not uploads:
        raise errors.invalid_request("변환할 XML 화일을 첨부하십시오.")
    if len(uploads) > limits.MAX_FILE_COUNT:
        raise errors.invalid_request("한 번에 한 개의 XML 화일만 변환합니다.")

    upload = uploads[0]
    name = safe_source_name(upload.filename)
    if not name.lower().endswith(limits.ALLOWED_SUFFIXES):
        raise errors.unsupported_media_type()
    media = (upload.content_type or "").split(";")[0].strip().lower()
    if media not in XML_CONTENT_TYPES:
        raise errors.unsupported_media_type()
    if len(upload.content) > limits.MAX_UPLOAD_BYTES:
        raise errors.file_too_large(
            f"XML 화일은 {limits.MAX_UPLOAD_BYTES // limits.MiB} MiB 까지 올릴 수 있습니다.")
    return Upload(filename=name, content=upload.content,
                  content_type=upload.content_type)


def convert_response(uploads: list[Upload], *, template_bytes: bytes,
                     template_version: str, deployment_version: str,
                     request_id: str, today: dt.date) -> ApiResponse:
    """`POST /api/v1/convert` — 업로드 한 건을 견적서로 바꿔 바로 내려 준다.

    입력과 결과는 저장하지 않는다. 요청이 끝나면 함께 사라진다.

    IBM 문서인지 레노버 x86 문서인지는 화면이 고르지 않는다. 업로드된 XML
    내용으로 알아낸다 (`quotation.core.modes.detect`).
    """
    base_log = {"deployment_version": deployment_version,
                "template_version": template_version}
    try:
        upload = pick_upload(uploads)
        base_log["input_size_bucket"] = size_bucket(len(upload.content))

        result = conversion_adapter.convert_upload(
            xml_bytes=upload.content,
            template_bytes=template_bytes,
            today=today,
            source_name=upload.filename,
        )
    except errors.ApiError as err:
        return error_response(err, request_id, base_log)

    headers = _headers({
        "Content-Type": XLSX_CONTENT_TYPE,
        "Content-Disposition": content_disposition(result.filename),
        "Content-Length": str(len(result.xlsx)),
        "X-Request-Id": request_id,
        "X-Template-Version": template_version,
    })
    return ApiResponse(
        status=200, headers=headers, body=result.xlsx,
        log={**base_log, "outcome": "ok", "status": 200,
             "mode": result.mode,
             "line_count": result.line_count,
             "group_count": result.group_count,
             "output_size_bucket": size_bucket(len(result.xlsx)),
             "total_ms": result.elapsed_ms},
    )


# --- 동일 출처 검사 (계획서 §9) --------------------------------------------------

def check_same_origin(*, request_url: str, origin: str | None,
                      sec_fetch_site: str | None) -> None:
    """상태를 바꾸는 요청이 우리 화면에서 온 것인지 확인한다.

    API 와 정적 UI 를 같은 출처로 제공하므로 CORS 를 열지 않는다.

    Raises:
        errors.ApiError: INVALID_REQUEST
    """
    if sec_fetch_site and sec_fetch_site not in ("same-origin", "same-site"):
        raise errors.invalid_request("허용되지 않은 요청 출처입니다.")
    if origin:
        want = urlsplit(request_url)
        got = urlsplit(origin)
        if (got.scheme, got.netloc) != (want.scheme, want.netloc):
            raise errors.invalid_request("허용되지 않은 요청 출처입니다.")


def method_not_allowed(request_id: str, allowed: str) -> ApiResponse:
    err = errors.invalid_request("허용되지 않은 요청 방식입니다.")
    response = error_response(err, request_id)
    return ApiResponse(status=405, headers={**response.headers, "Allow": allowed},
                       body=response.body, log={**response.log, "status": 405})


def not_found(request_id: str) -> ApiResponse:
    err = errors.invalid_request("없는 API 경로입니다.")
    response = error_response(err, request_id)
    return ApiResponse(status=404, headers=response.headers, body=response.body,
                       log={**response.log, "status": 404})
