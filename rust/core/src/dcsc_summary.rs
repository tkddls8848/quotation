//! 레노버 DCSC 요약표 — 구성 파일 안에 눌러 담긴 품목별 실금액.
//! 파이썬 `quotation/core/dcsc_summary.py`.
//!
//! `CFXML/SectionData/GroupData` 가 DCSC 화면의 요약표를 담고 있으며,
//! **base64 로 적은 gzip XML** 이다. 소프트웨어에도 제 금액이 붙어 있어서,
//! 본체 라인 LP 하나로만 세던 통합 모드가 품목별로 갈라진다.
//!
//! 성립하는 항등식은 이것이다.
//!
//! ```text
//! 본체 LP = 하드웨어 + Σ소프트웨어 + Σ서비스 - (소프트웨어 항목 수)
//! ```
//!
//! `GroupData` 는 eConfig 규격이 아니라 DCSC 가 제 상태를 담아 두는 자리다.
//! 문서화된 적이 없고 구성기 판올림에 형태가 바뀔 수 있으므로 **읽지 못하면
//! 조용히 포기** 한다. 요소 이름에 기대지 않고 자식 노드의 생김새로 항목을
//! 고르는 것도 같은 이유다.

use std::io::Read;

use base64::Engine;
use flate2::read::GzDecoder;

use crate::money::{self, Amount, Decimal, is_priced};
use crate::xmldom::{self, Element};

/// 요약표가 앉아 있는 자리.
const P_GROUP_DATA: [&str; 2] = ["SectionData", "GroupData"];

/// 풀어 놓은 요약표의 최대 크기. 실파일은 7 KiB 안팎이다. 압축 폭탄을 막는다.
const MAX_BLOB_BYTES: usize = 8 * 1024 * 1024;

/// 요약표의 `type`. 하드웨어만 H/W 구간이고 `hipo` 가 소프트웨어다.
const HARDWARE: &str = "hardware";

/// 본체 LP 와 요약표 합계가 어긋나도 같은 구성으로 보는 폭(원).
fn tolerance() -> Decimal {
    Decimal::from(10)
}

/// 소프트웨어 항목마다 붙어 있는 자리표. 실금액은 이만큼 뺀 값이다.
fn placeholder() -> Decimal {
    Decimal::ONE
}

/// 요약표의 구성 한 벌. 장비군 한 개에 대응한다.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Config {
    /// 하드웨어 항목의 품번. 짝짓기에 쓴다.
    pub body_part: String,
    /// 하드웨어 항목의 `SimplePrice`. 곧 XML 본체 라인의 UnitListPrice 다.
    pub total: Decimal,
    /// 하드웨어가 아닌 품목의 실금액. 등장 순서를 지킨다.
    pub prices: Vec<(String, Decimal)>,
}

impl Config {
    /// 품번에 붙은 금액을 꺼내고 목록에서 지운다 (파이썬 `dict.pop`).
    pub fn take_price(&mut self, part: &str) -> Option<Decimal> {
        let index = self.prices.iter().position(|(key, _)| key == part)?;
        Some(self.prices.remove(index).1)
    }
}

/// 문서 한 건의 요약표.
///
/// 구성은 장비군에 한 번씩만 짝지어야 하므로, 가져간 구성은 목록에서 뺀다.
#[derive(Clone, Debug, Default)]
pub struct Summary {
    left: Vec<Config>,
}

impl Summary {
    pub fn is_empty(&self) -> bool {
        self.left.is_empty()
    }

    pub fn len(&self) -> usize {
        self.left.len()
    }

    /// 본체 라인에 맞는 구성을 하나 꺼낸다. 없으면 `None`.
    pub fn take(&mut self, part_number: &str, total: &Amount) -> Option<Config> {
        if !is_priced(total) {
            return None;
        }
        let total = money::to_decimal(total);
        let key = part_key(part_number);
        let index = self.left.iter().position(|config| {
            config.body_part == key && (config.total - total).abs() <= tolerance()
        })?;
        Some(self.left.remove(index))
    }
}

/// 품번을 대조용으로 다듬는다. XML 은 `7DGD-CTO1WW`, 요약표는 `7DGDCTO1WW`.
pub fn part_key(part_number: &str) -> String {
    crate::text::strip(&part_number.replace('-', "")).to_uppercase()
}

/// 문서 뿌리 -> 요약표. 없거나 읽지 못하면 빈 요약표를 준다.
pub fn parse(root: &Element) -> Summary {
    match blob(root) {
        Some(blob) => Summary {
            left: configs(&blob),
        },
        None => Summary::default(),
    }
}

/// `SectionData/GroupData` 를 풀어 파싱한다. 조금이라도 어긋나면 `None`.
fn blob(root: &Element) -> Option<Element> {
    let node = root.find(&P_GROUP_DATA)?;
    // DCSC 는 한 줄로 적지만, 사람이 손으로 접어 둔 문서도 읽는다.
    let packed64: String = node.text.split_whitespace().collect();
    if packed64.is_empty() {
        return None;
    }
    let packed = base64::engine::general_purpose::STANDARD
        .decode(packed64.as_bytes())
        .ok()?;
    let mut raw = Vec::new();
    GzDecoder::new(packed.as_slice())
        .take(MAX_BLOB_BYTES as u64 + 1)
        .read_to_end(&mut raw)
        .ok()?;
    if raw.is_empty() || raw.len() > MAX_BLOB_BYTES {
        return None;
    }
    xmldom::parse(&raw).ok()
}

/// 풀어 놓은 요약표 -> 구성 목록. 문서 등장 순서를 지킨다.
fn configs(blob: &Element) -> Vec<Config> {
    struct Entry {
        code: String,
        kind: String,
        unit: Decimal,
        total: Option<Decimal>,
    }

    let mut ordered: Vec<String> = Vec::new();
    let mut buckets: Vec<(String, Vec<Entry>)> = Vec::new();
    for element in blob.iter() {
        let code = element.text_at(&["code"]);
        let Some(unit) = number(element, &["unitPrice"]) else {
            continue;
        };
        if code.is_empty() {
            continue;
        }
        let config_id = element.text_at(&["id"]).to_owned();
        let entry = Entry {
            code: part_key(code),
            kind: element.text_at(&["type"]).to_lowercase(),
            unit,
            total: number(element, &["prices", "SimplePrice", "price"]),
        };
        match buckets.iter_mut().find(|(id, _)| *id == config_id) {
            Some((_, entries)) => entries.push(entry),
            None => {
                ordered.push(config_id.clone());
                buckets.push((config_id, vec![entry]));
            }
        }
    }

    let mut configs = Vec::new();
    for id in &ordered {
        let entries = &buckets
            .iter()
            .find(|(key, _)| key == id)
            .expect("방금 넣은 자리")
            .1;
        let bodies: Vec<_> = entries
            .iter()
            .filter(|entry| entry.kind == HARDWARE)
            .collect();
        // 하드웨어가 없거나 둘 이상이면 어느 라인에 붙일지 알 수 없다.
        if bodies.len() != 1 {
            continue;
        }
        let Some(total) = bodies[0].total else {
            continue;
        };
        let body_part = bodies[0].code.clone();

        let mut prices: Vec<(String, Decimal)> = Vec::new();
        for entry in entries.iter().filter(|entry| entry.kind != HARDWARE) {
            // 소프트웨어(`hipo`)에만 자리표 1 원이 붙어 있다.
            let real = if is_software(&entry.kind) {
                entry.unit - placeholder()
            } else {
                entry.unit
            };
            match prices.iter_mut().find(|(key, _)| *key == entry.code) {
                Some(slot) => slot.1 += real,
                None => prices.push((entry.code.clone(), real)),
            }
        }
        configs.push(Config {
            body_part,
            total,
            prices,
        });
    }
    configs
}

/// 요약표의 소프트웨어 항목인가. 서비스는 `service` 로 시작한다.
fn is_software(kind: &str) -> bool {
    !kind.contains("service")
}

fn number(element: &Element, path: &[&str]) -> Option<Decimal> {
    let raw = element.text_at(path);
    if raw.is_empty() {
        return None;
    }
    money::parse_plain(raw)
}
