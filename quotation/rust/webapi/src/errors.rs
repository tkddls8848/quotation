//! API 오류. 파이썬 `web/src/errors.py`.
//!
//! 문구는 사용자에게 그대로 보인다. 스택 추적, XML 본문, 내부 경로, 고객
//! 정보는 절대 넣지 않는다. 원인 추적은 요청 ID 로 한다.

use crate::json;

pub const INVALID_REQUEST: &str = "INVALID_REQUEST";
pub const FILE_TOO_LARGE: &str = "FILE_TOO_LARGE";
pub const UNSUPPORTED_MEDIA_TYPE: &str = "UNSUPPORTED_MEDIA_TYPE";
pub const INVALID_QUOTATION_XML: &str = "INVALID_QUOTATION_XML";
pub const CONVERSION_FAILED: &str = "CONVERSION_FAILED";
pub const TEMPLATE_UNAVAILABLE: &str = "TEMPLATE_UNAVAILABLE";

/// 사용자에게 보여 줄 수 있는 오류.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ApiError {
    pub code: String,
    pub message: String,
}

impl ApiError {
    pub fn status(&self) -> u16 {
        match self.code.as_str() {
            INVALID_REQUEST => 400,
            FILE_TOO_LARGE => 413,
            UNSUPPORTED_MEDIA_TYPE => 415,
            INVALID_QUOTATION_XML => 422,
            TEMPLATE_UNAVAILABLE => 503,
            _ => 500,
        }
    }

    pub fn payload(&self, request_id: &str) -> String {
        format!(
            "{{\"error\": {{\"code\": {}, \"message\": {}, \"request_id\": {}}}}}",
            json::string(&self.code),
            json::string(&self.message),
            json::string(request_id),
        )
    }
}

impl std::fmt::Display for ApiError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(&self.message)
    }
}

impl std::error::Error for ApiError {}

fn error(code: &str, message: &str) -> ApiError {
    ApiError {
        code: code.to_owned(),
        message: message.to_owned(),
    }
}

pub fn invalid_request(message: &str) -> ApiError {
    error(INVALID_REQUEST, message)
}

pub fn file_too_large(message: &str) -> ApiError {
    error(FILE_TOO_LARGE, message)
}

pub fn unsupported_media_type() -> ApiError {
    error(UNSUPPORTED_MEDIA_TYPE, "XML 화일만 변환할 수 있습니다.")
}

pub fn invalid_quotation_xml(message: &str) -> ApiError {
    error(INVALID_QUOTATION_XML, message)
}

pub fn conversion_failed() -> ApiError {
    error(
        CONVERSION_FAILED,
        "견적서를 만들지 못했습니다. 잠시 후 다시 시도하십시오.",
    )
}

pub fn template_unavailable() -> ApiError {
    error(
        TEMPLATE_UNAVAILABLE,
        "견적서 템플릿을 사용할 수 없습니다. 관리자에게 알려 주십시오.",
    )
}
