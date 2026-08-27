//! 파이썬 `xml_reader.parse_bytes` 와 나란히 세워 두는 견적 탐침.
//!
//! 표준 입력으로 XML 바이트를 받아, 만들어진 견적서 한 부(그룹·시트명·금액)를
//! JSON 으로 돌려준다. 같은 바이트를 파이썬에 넣은 결과와
//! `tools/rust_parity_quotation.py` 가 대조한다.

use std::io::{self, Read, Write};

use quotation_core::models::{Group, LineItem, Quotation};
use quotation_core::money::Amount;
use quotation_core::xml_reader;
use serde_json::{Value, json};

fn main() -> io::Result<()> {
    let mut data = Vec::new();
    io::stdin().read_to_end(&mut data)?;
    let answer = match xml_reader::parse_bytes(&data, None) {
        Ok(quotation) => quotation_json(&quotation),
        Err(error) => json!({"ok": false, "error": error.to_string()}),
    };
    let mut out = io::stdout().lock();
    writeln!(out, "{answer}")?;
    out.flush()
}

fn quotation_json(quotation: &Quotation) -> Value {
    json!({
        "ok": true,
        "mode": quotation.mode.as_str(),
        "groups": quotation.groups.iter().map(group).collect::<Vec<_>>(),
    })
}

fn group(group: &Group) -> Value {
    json!({
        "group_id": group.group_id,
        "item_key": group.item_key,
        "sheet_name": group.sheet_name,
        "title": group.title,
        "amount": group.amount().to_string(),
        "sections": group
            .sections()
            .iter()
            .map(|(kind, items)| json!([kind, items.len()]))
            .collect::<Vec<_>>(),
        "items": group.items.iter().map(line).collect::<Vec<_>>(),
    })
}

/// 금액을 파이썬 쪽과 같은 글로 적는다 (결정 0006).
fn amount(value: &Amount) -> Value {
    match value {
        Amount::Priced(number) => json!(format!("priced:{number}")),
        Amount::NoCharge => json!("nocharge"),
        Amount::Missing => json!("missing"),
    }
}

fn line(item: &LineItem) -> Value {
    json!({
        "line_number": item.line_number,
        "txn_type": item.txn_type,
        "part_number": item.part_number,
        "description": item.description,
        "product_type": item.product_type,
        "quantity": item.quantity,
        "siu": item.siu,
        "unit_price": amount(&item.unit_price),
        "amount": item.amount().to_string(),
        "is_hardware": item.is_hardware(),
        "subs": item
            .subs
            .iter()
            .map(|sub| json!({
                "txn_type": sub.txn_type,
                "part_number": sub.part_number,
                "quantity": sub.quantity,
                "unit_price": amount(&sub.unit_price),
                "amount": sub.amount(item.quantity).to_string(),
                "is_removal": sub.is_removal(),
            }))
            .collect::<Vec<_>>(),
    })
}
