//! 파이썬 `api.convert_response` 와 나란히 세워 두는 API 층 탐침.
//!
//! ```text
//! webapi-probe 파일이름 MIME 배포판본 요청ID YYYY-MM-DD 본문출력경로 < 업로드바이트
//! ```
//!
//! 상태·헤더·로그를 JSON 한 줄로 내고, 응답 본문은 파일로 적는다. 같은
//! 업로드를 파이썬에 넣은 결과와 `tools/rust_parity_webapi.py` 가 대조한다.

use std::io::{self, Read, Write};
use std::process::ExitCode;

use quotation_core::writer::Date;
use quotation_webapi::{LogValue, Upload, convert_response};
use serde_json::{Map, Value, json};

fn main() -> ExitCode {
    let arguments: Vec<String> = std::env::args().skip(1).collect();
    let [
        filename,
        content_type,
        deployment_version,
        request_id,
        day,
        body_path,
    ] = arguments.as_slice()
    else {
        eprintln!("usage: webapi-probe 이름 MIME 배포판본 요청ID YYYY-MM-DD 본문경로 < 업로드");
        return ExitCode::from(2);
    };

    let mut content = Vec::new();
    if let Err(error) = io::stdin().read_to_end(&mut content) {
        eprintln!("표준 입력을 읽을 수 없습니다: {error}");
        return ExitCode::from(2);
    }
    let Some(today) = parse_date(day) else {
        eprintln!("날짜는 YYYY-MM-DD 로 준다: {day}");
        return ExitCode::from(2);
    };

    let upload = Upload {
        filename: filename.clone(),
        content,
        content_type: content_type.clone(),
    };
    // 시간은 대조 대상이 아니다. 파이썬 쪽 total_ms 와 견줄 값이 아니므로 0.
    let response = convert_response(&upload, deployment_version, request_id, today, 0);

    if let Err(error) = std::fs::write(body_path, &response.body) {
        eprintln!("본문을 적을 수 없습니다: {error}");
        return ExitCode::from(2);
    }

    let mut headers = Map::new();
    for (name, value) in &response.headers {
        headers.insert(name.clone(), Value::String(value.clone()));
    }
    let mut log = Map::new();
    for (name, value) in &response.log {
        log.insert(
            name.clone(),
            match value {
                LogValue::Text(text) => Value::String(text.clone()),
                LogValue::Int(number) => Value::from(*number),
            },
        );
    }

    let answer = json!({
        "status": response.status,
        "headers": Value::Object(headers),
        "log": Value::Object(log),
        "body_len": response.body.len(),
    });
    let mut out = io::stdout().lock();
    let _ = writeln!(out, "{answer}");
    let _ = out.flush();
    ExitCode::SUCCESS
}

fn parse_date(text: &str) -> Option<Date> {
    let mut pieces = text.split('-');
    Some(Date {
        year: pieces.next()?.parse().ok()?,
        month: pieces.next()?.parse().ok()?,
        day: pieces.next()?.parse().ok()?,
    })
}
