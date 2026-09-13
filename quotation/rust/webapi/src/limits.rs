//! 애플리케이션 자체 제한. 파이썬 `web/src/limits.py`.

use crate::json;

pub const MIB: usize = 1024 * 1024;

/// 업로드 XML 한 개의 최대 크기.
pub const MAX_UPLOAD_BYTES: usize = 10 * MIB;

/// 한 번에 골라 변환할 수 있는 파일 수 (브라우저에서 되풀이하는 횟수).
pub const MAX_BATCH_FILES: usize = 50;

/// **한 요청**에 담을 수 있는 파일 수.
pub const MAX_FILE_COUNT: usize = 1;

/// 파싱 전 싸게 걸러 낼 품목 합계 상한.
pub const MAX_LINE_ITEMS: usize = quotation_core::xml_reader::MAX_QUOTATION_ITEMS;

/// 장비군(=상세 시트) 수. Excel 시트 폭증을 막는다.
pub const MAX_GROUPS: usize = 200;

/// 생성 결과 크기.
pub const MAX_OUTPUT_BYTES: usize = 20 * MIB;

/// 받아들일 확장자. 확장자만 믿지 않고 내용도 파싱해서 확인한다.
pub const ALLOWED_SUFFIX: &str = ".xml";

/// 클라이언트에 알려 줄 공개 설정 (`GET /api/v1/config`).
pub fn public_config() -> String {
    format!(
        "{{\"max_upload_bytes\": {}, \"max_file_count\": {}, \"max_batch_files\": {}, \
         \"allowed_suffixes\": [{}], \"output_suffix\": {}}}",
        MAX_UPLOAD_BYTES,
        MAX_FILE_COUNT,
        MAX_BATCH_FILES,
        json::string(ALLOWED_SUFFIX),
        json::string(".xlsx"),
    )
}
