//! 관문 2 측정용 브라우저 진입점.
//!
//! 아직 견적서를 만들지 않는다. 최종 코어가 지고 갈 **의존성 무게를 그대로**
//! 태워서 전송 크기와 기동 시간을 재는 것이 목적이다. 그래서 zip 열기,
//! XML 파싱, 셀 쓰기, zip 저장을 모두 한 번씩 지나간다.

use quick_xml::{Reader, events::Event};
use quotation_core::{money, naming};
use std::io::Cursor;
use wasm_bindgen::prelude::*;

/// 템플릿을 열어 XML 에서 읽은 값을 한 셀에 적고 다시 저장한다.
#[wasm_bindgen]
pub fn probe(template: &[u8], xml: &[u8]) -> Result<Vec<u8>, JsError> {
    let (items, total) = scan(xml)?;
    let mut book = umya_spreadsheet::reader::xlsx::read_reader(Cursor::new(template), true)
        .map_err(|error| JsError::new(&error.to_string()))?;
    let sheet = book
        .sheet_mut(0)
        .map_err(|error| JsError::new(&error.to_string()))?;
    sheet.cell_mut("C3").set_value_string(items);
    sheet.cell_mut("C4").set_value_string(total);
    let mut out = Cursor::new(Vec::new());
    umya_spreadsheet::writer::xlsx::write_writer(&book, &mut out)
        .map_err(|error| JsError::new(&error.to_string()))?;
    Ok(out.into_inner())
}

/// XML 을 한 번 훑어 종목 키와 금액 합을 만든다. 규칙은 코어의 것을 쓴다.
fn scan(xml: &[u8]) -> Result<(String, String), JsError> {
    let mut reader = Reader::from_reader(xml);
    reader.config_mut().trim_text(true);
    let mut buffer = Vec::new();
    let mut field = String::new();
    let mut keys: Vec<String> = Vec::new();
    let mut total = money::Decimal::ZERO;
    loop {
        match reader.read_event_into(&mut buffer) {
            Ok(Event::Start(tag)) => {
                field = String::from_utf8_lossy(tag.name().as_ref()).into_owned();
            }
            Ok(Event::Text(text)) => {
                let body = text.decode().map_err(|e| JsError::new(&e.to_string()))?;
                match field.as_str() {
                    "ProductDescription" => keys.push(naming::item_key(&body)),
                    "MonetaryAmount" => {
                        if let Ok(amount) = money::parse_amount(Some(&body)) {
                            total += money::to_decimal(&amount);
                        }
                    }
                    _ => {}
                }
            }
            Ok(Event::Eof) => break,
            Ok(_) => {}
            Err(error) => return Err(JsError::new(&error.to_string())),
        }
        buffer.clear();
    }
    let names = naming::unique_sheet_names(keys.iter().map(|key| naming::safe_sheet_name(key)));
    Ok((names.len().to_string(), total.to_string()))
}
