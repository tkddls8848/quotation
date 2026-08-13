"""API 오류 (계획서 §6.1).

메시지는 사용자에게 그대로 보인다. 스택 추적, XML 본문, R2/로컬 경로,
고객 정보는 절대 넣지 않는다. 원인 추적은 요청 ID 로 한다.
"""
from __future__ import annotations

INVALID_REQUEST = "INVALID_REQUEST"
FILE_TOO_LARGE = "FILE_TOO_LARGE"
UNSUPPORTED_MEDIA_TYPE = "UNSUPPORTED_MEDIA_TYPE"
INVALID_QUOTATION_XML = "INVALID_QUOTATION_XML"
CONVERSION_FAILED = "CONVERSION_FAILED"
TEMPLATE_UNAVAILABLE = "TEMPLATE_UNAVAILABLE"

STATUS = {
    INVALID_REQUEST: 400,
    FILE_TOO_LARGE: 413,
    UNSUPPORTED_MEDIA_TYPE: 415,
    INVALID_QUOTATION_XML: 422,
    CONVERSION_FAILED: 500,
    TEMPLATE_UNAVAILABLE: 503,
}


class ApiError(Exception):
    """사용자에게 보여 줄 수 있는 오류."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = STATUS[code]

    def payload(self, request_id: str) -> dict:
        return {"error": {"code": self.code, "message": self.message,
                          "request_id": request_id}}


def invalid_request(message: str = "요청 형식이 올바르지 않습니다.") -> ApiError:
    return ApiError(INVALID_REQUEST, message)


def file_too_large(message: str = "화일이 너무 큽니다.") -> ApiError:
    return ApiError(FILE_TOO_LARGE, message)


def unsupported_media_type(
        message: str = "XML 화일만 변환할 수 있습니다.") -> ApiError:
    return ApiError(UNSUPPORTED_MEDIA_TYPE, message)


def invalid_quotation_xml(
        message: str = "견적서 작성에 필요한 XML 항목을 찾을 수 없습니다.") -> ApiError:
    return ApiError(INVALID_QUOTATION_XML, message)


def conversion_failed(
        message: str = "견적서를 만들지 못했습니다. 잠시 후 다시 시도하십시오.") -> ApiError:
    return ApiError(CONVERSION_FAILED, message)


def template_unavailable(
        message: str = "견적서 템플릿을 사용할 수 없습니다. 관리자에게 알려 주십시오.") -> ApiError:
    return ApiError(TEMPLATE_UNAVAILABLE, message)
