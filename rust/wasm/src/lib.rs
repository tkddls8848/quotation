//! 브라우저 진입점. 변환 일꾼이 부르는 것은 여기 함수들이다.
//!
//! 파이썬 `web/browser/entry.py` 가 있던 자리다. 하는 일도 같다 — JS 가 넘긴
//! 바이트를 API 층에 넘기고, 돌려받은 응답을 JS 가 읽을 수 있는 형태로 바꾼다.
//! **변환 규칙도 검증 규칙도 여기 없다.**
//!
//! 파일시스템도, 네트워크도 쓰지 않는다. 업로드한 XML 은 브라우저 밖으로
//! 나가지 않는다 ([결정 0002](../../../doc/decisions/0002-convert-in-browser.md)).

use js_sys::{Object, Reflect, Uint8Array};
use quotation_core::modes;
use quotation_webapi::{
    ApiResponse, LogValue, Upload, config_response, convert_response, seoul_today, status_response,
    templates,
};
use wasm_bindgen::prelude::*;

/// 업로드 한 건을 견적서로 바꾼다. 서버의 `POST /api/v1/convert` 와 같다.
///
/// 실패해도 예외를 던지지 않고 서버와 같은 오류 응답을 돌려준다.
///
/// * `now_ms` — 에포크 밀리초. 견적 날짜는 브라우저의 지역 시간이 아니라
///   Asia/Seoul 기준으로 여기서 정한다.
#[wasm_bindgen]
pub fn convert(
    filename: &str,
    content: &[u8],
    content_type: &str,
    deployment_version: &str,
    request_id: &str,
    now_ms: f64,
) -> Object {
    let upload = Upload {
        filename: filename.to_owned(),
        content: content.to_vec(),
        content_type: content_type.to_owned(),
    };
    let started = js_sys::Date::now();
    let response = convert_response(
        &upload,
        deployment_version,
        request_id,
        seoul_today(now_ms as i64),
        0,
    );
    let elapsed = (js_sys::Date::now() - started) as i64;
    to_js(response, elapsed)
}

/// 이번 변환이 쓸 견적 날짜 (Asia/Seoul). 동일성 검증이 날짜를 맞추는 데 쓴다.
#[wasm_bindgen]
pub fn today(now_ms: f64) -> String {
    seoul_today(now_ms as i64).iso()
}

/// `GET /api/v1/config` 와 같은 응답.
#[wasm_bindgen]
pub fn config(request_id: &str) -> Object {
    to_js(config_response(request_id), 0)
}

/// `GET /api/v1/status` 와 같은 응답.
#[wasm_bindgen]
pub fn status(request_id: &str, deployment_version: &str) -> Object {
    to_js(status_response(request_id, deployment_version), 0)
}

/// 모드별 활성 템플릿 판본. 자산 목록(`engine.json`)을 만들 때 쓴다.
#[wasm_bindgen]
pub fn template_version(mode: &str) -> String {
    let mode = match mode {
        "integrated" => modes::Mode::Integrated,
        _ => modes::Mode::Unix,
    };
    templates::version(mode)
}

/// `{status, headers, body, log}` — 파이썬 `entry.convert` 가 돌려주던 모양.
fn to_js(response: ApiResponse, elapsed_ms: i64) -> Object {
    let headers = Object::new();
    for (name, value) in &response.headers {
        let _ = Reflect::set(
            &headers,
            &JsValue::from_str(name),
            &JsValue::from_str(value),
        );
    }

    let log = Object::new();
    for (name, value) in &response.log {
        let entry = match value {
            LogValue::Text(text) => JsValue::from_str(text),
            // 시간은 JS 쪽 시계로 잰다. 코어는 시계를 읽지 않는다.
            LogValue::Int(_) if name == "total_ms" => JsValue::from_f64(elapsed_ms as f64),
            LogValue::Int(number) => JsValue::from_f64(*number as f64),
        };
        let _ = Reflect::set(&log, &JsValue::from_str(name), &entry);
    }

    let out = Object::new();
    let _ = Reflect::set(
        &out,
        &JsValue::from_str("status"),
        &JsValue::from_f64(f64::from(response.status)),
    );
    let _ = Reflect::set(&out, &JsValue::from_str("headers"), &headers);
    let _ = Reflect::set(
        &out,
        &JsValue::from_str("body"),
        &Uint8Array::from(response.body.as_slice()),
    );
    let _ = Reflect::set(&out, &JsValue::from_str("log"), &log);
    out
}
