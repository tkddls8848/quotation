//! 파이썬 `xml_reader` 와 나란히 세워 두는 파서 탐침.
//!
//! 표준 입력으로 XML 바이트를 받아, 읽어 낸 라인을 JSON 한 덩어리로 돌려준다.
//! 거절할 문서면 `{"ok": false, "error": ...}` 를 돌려준다. 같은 바이트를
//! 파이썬에 넣은 결과와 `tools/rust_parity_xml_reader.py` 가 대조한다.

use std::io::{self, Read, Write};

use quotation_core::money::Amount;
use quotation_core::xml_reader;
use serde_json::{Value, json};

fn main() -> io::Result<()> {
    let mut data = Vec::new();
    io::stdin().read_to_end(&mut data)?;
    let answer = match xml_reader::parse_items(&data) {
        Ok(items) => json!({"ok": true, "items": items.iter().map(line).collect::<Vec<_>>()}),
        Err(error) => json!({"ok": false, "error": error.to_string()}),
    };
    let mut out = io::stdout().lock();
    writeln!(out, "{answer}")?;
    out.flush()
}

/// 금액을 파이썬 쪽과 같은 글로 적는다 ([결정 0006](../../../doc/decisions)).
fn amount(value: &Amount) -> Value {
    match value {
        Amount::Priced(number) => json!(format!("priced:{number}")),
        Amount::NoCharge => json!("nocharge"),
        Amount::Missing => json!("missing"),
    }
}

fn line(item: &quotation_core::models::LineItem) -> Value {
    json!({
        "line_number": item.line_number,
        "txn_type": item.txn_type,
        "group_id": item.group_id,
        "quantity": item.quantity,
        "part_number": item.part_number,
        "description": item.description,
        "product_type": item.product_type,
        "product_name": item.product_name,
        "unit_price": amount(&item.unit_price),
        "siu": item.siu,
        "subs": item.subs.iter().map(sub).collect::<Vec<_>>(),
    })
}

fn sub(item: &quotation_core::models::SubLineItem) -> Value {
    json!({
        "txn_type": item.txn_type,
        "quantity": item.quantity,
        "part_number": item.part_number,
        "description": item.description,
        "unit_price": amount(&item.unit_price),
    })
}
