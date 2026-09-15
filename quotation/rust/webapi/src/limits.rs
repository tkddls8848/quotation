//! 애플리케이션 자체 제한. 여기가 기준이고 화면의 1차 검사는 사본이다.

pub const MIB: usize = 1024 * 1024;

/// 업로드 XML 한 개의 최대 크기.
pub const MAX_UPLOAD_BYTES: usize = 10 * MIB;

/// 파싱 전 싸게 걸러 낼 품목 합계 상한.
pub const MAX_LINE_ITEMS: usize = quotation_core::xml_reader::MAX_QUOTATION_ITEMS;

/// 장비군(=상세 시트) 수. Excel 시트 폭증을 막는다.
pub const MAX_GROUPS: usize = 200;

/// 생성 결과 크기.
pub const MAX_OUTPUT_BYTES: usize = 20 * MIB;

/// 받아들일 확장자. 확장자만 믿지 않고 내용도 파싱해서 확인한다.
pub const ALLOWED_SUFFIX: &str = ".xml";
