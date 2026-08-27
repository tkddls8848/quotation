//! 브라우저 진입점. 변환 일꾼이 부르는 것은 이 함수 하나다.
//!
//! 파이썬 쪽 `web/browser/entry.py` 와 같은 자리다. 파일시스템도, 네트워크도
//! 쓰지 않는다 — 업로드한 XML 은 브라우저 밖으로 나가지 않는다
//! ([결정 0002](../../../doc/decisions/0002-convert-in-browser.md)).

use quotation_core::writer::{self, Date};
use quotation_core::xml_reader;
use wasm_bindgen::prelude::*;

/// eConfig XML 바이트 -> 견적서 `.xlsx` 바이트.
///
/// 날짜는 부르는 쪽이 준다. 브라우저의 시계를 코어가 읽지 않으므로 같은
/// 입력이 언제나 같은 파일을 낸다.
#[wasm_bindgen]
pub fn convert(
    xml: &[u8],
    template: &[u8],
    year: i32,
    month: u32,
    day: u32,
) -> Result<Vec<u8>, JsError> {
    let quotation =
        xml_reader::parse_bytes(xml, None).map_err(|error| JsError::new(&error.to_string()))?;
    writer::build_bytes(&quotation, template, Date { year, month, day })
        .map_err(|error| JsError::new(&error.to_string()))
}

/// 문서를 읽는 방식을 강제로 지정해 변환한다 (진단·시험용).
#[wasm_bindgen]
pub fn convert_with_mode(
    xml: &[u8],
    template: &[u8],
    year: i32,
    month: u32,
    day: u32,
    mode: &str,
) -> Result<Vec<u8>, JsError> {
    let quotation = xml_reader::parse_bytes(xml, Some(mode))
        .map_err(|error| JsError::new(&error.to_string()))?;
    writer::build_bytes(&quotation, template, Date { year, month, day })
        .map_err(|error| JsError::new(&error.to_string()))
}
