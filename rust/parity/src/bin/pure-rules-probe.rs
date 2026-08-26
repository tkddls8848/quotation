//! 파이썬 구현과 나란히 세워 두는 순수 규칙 탐침.
//!
//! 표준 입력으로 JSON 한 줄에 호출 하나(`{"fn": ..., "args": [...]}`)를 받고,
//! 표준 출력으로 결과 한 줄(`{"ok": true, "value": ...}`)을 돌려준다. 같은
//! 호출을 파이썬 `quotation.core` 에 넣은 결과와 `tools/rust_parity_pure_rules.py`
//! 가 대조한다. 이 프로그램은 규칙을 새로 정하지 않는다 — 크레이트를 부르기만 한다.

use std::io::{self, BufRead, Write};

use quotation_core::{modes, money, naming};
use serde_json::{Value, json};

fn main() -> io::Result<()> {
    let stdin = io::stdin();
    let stdout = io::stdout();
    let mut out = stdout.lock();
    for line in stdin.lock().lines() {
        let line = line?;
        if line.trim().is_empty() {
            continue;
        }
        let call: Value = serde_json::from_str(&line).expect("탐침 입력은 JSON 한 줄이다");
        let answer = match dispatch(&call) {
            Ok(value) => json!({"ok": true, "value": value}),
            Err(message) => json!({"ok": false, "error": message}),
        };
        writeln!(out, "{answer}")?;
    }
    out.flush()
}

/// 선택 인자. JSON `null` 은 파이썬 `None` 이다.
fn text(call: &Value, index: usize) -> Option<&str> {
    match &call["args"][index] {
        Value::Null => None,
        value => Some(value.as_str().expect("문자열 인자")),
    }
}

fn required(call: &Value, index: usize) -> &str {
    text(call, index).expect("필수 인자")
}

fn list(call: &Value, index: usize) -> Vec<&str> {
    call["args"][index]
        .as_array()
        .expect("문자열 배열 인자")
        .iter()
        .map(|value| value.as_str().expect("문자열"))
        .collect()
}

/// 금액을 파이썬 쪽과 같은 글로 적는다 (`Decimal` 인지 N/C 인지 없음인지).
fn amount_repr(amount: &money::Amount) -> String {
    match amount {
        money::Amount::Priced(value) => format!("priced:{value}"),
        money::Amount::NoCharge => "nocharge".to_owned(),
        money::Amount::Missing => "missing".to_owned(),
    }
}

fn dispatch(call: &Value) -> Result<Value, String> {
    let name = call["fn"].as_str().expect("호출 이름");
    match name {
        "money.parse_amount" => money::parse_amount(text(call, 0))
            .map(|amount| json!(amount_repr(&amount)))
            .map_err(|error| error.to_string()),
        "money.to_decimal" => money::parse_amount(text(call, 0))
            .map(|amount| json!(money::to_decimal(&amount).to_string()))
            .map_err(|error| error.to_string()),
        "money.is_priced" => money::parse_amount(text(call, 0))
            .map(|amount| json!(money::is_priced(&amount)))
            .map_err(|error| error.to_string()),
        "money.cell_text" => money::parse_amount(text(call, 0))
            .map(|amount| json!(amount.to_string()))
            .map_err(|error| error.to_string()),
        "naming.item_key" => Ok(json!(naming::item_key(required(call, 0)))),
        "naming.sheet_name" => Ok(json!(naming::sheet_name(required(call, 0)))),
        "naming.product_key" => Ok(json!(naming::product_key(
            required(call, 0),
            required(call, 1)
        ))),
        "naming.safe_sheet_name" => Ok(json!(naming::safe_sheet_name(required(call, 0)))),
        "naming.unique_sheet_names" => Ok(json!(naming::unique_sheet_names(list(call, 0)))),
        "modes.detect" => Ok(json!(modes::detect(list(call, 0)).as_str())),
        "modes.normalize" => modes::normalize(required(call, 0))
            .map(|mode| json!(mode.as_str()))
            .map_err(|error| error.to_string()),
        "modes.resolve" => modes::resolve(text(call, 0), list(call, 1))
            .map(|mode| json!(mode.as_str()))
            .map_err(|error| error.to_string()),
        other => panic!("모르는 호출: {other}"),
    }
}
