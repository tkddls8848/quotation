//! XML 과 Excel 사이에서 쓰는 견적 데이터 모델. 파이썬 `quotation/core/models.py`.

use crate::money::Amount;

pub const HARDWARE: &str = "Hardware";
pub const SOFTWARE: &str = "Software";
pub const SERVICES: &str = "Services";

/// 증설 견적에서 견적 대상이 아닌 TransactionType.
pub const REFERENCE_TXN: [&str; 2] = ["BASE", "PROPOSED"];

/// 제거되는 부품. 수량을 음수로 적고 붉게 표시한다.
pub const REMOVE_TXN: &str = "REMOVE";

/// ProductSubLineItem — 상위 라인의 구성 부품.
#[derive(Clone, Debug, PartialEq, Eq, Default)]
pub struct SubLineItem {
    pub txn_type: String,
    pub quantity: i64,
    pub part_number: String,
    pub description: String,
    pub unit_price: Amount,
}

/// ProductLineItem — 견적의 한 줄.
#[derive(Clone, Debug, PartialEq, Eq, Default)]
pub struct LineItem {
    pub line_number: String,
    pub txn_type: String,
    pub group_id: String,
    pub quantity: i64,
    pub part_number: String,
    pub description: String,
    pub product_type: String,
    /// ProductName. 구성기에서 사람이 붙인 장비 이름 (`백업서버_1식`).
    pub product_name: String,
    pub unit_price: Amount,
    pub subs: Vec<SubLineItem>,
    /// CPUSIUvalue. 1 이면 장비 본체 라인이다.
    pub siu: i64,
}

impl LineItem {
    /// 기존(BASE)·증설후(PROPOSED) 구성. 견적서에 넣지 않는다.
    pub fn is_reference(&self) -> bool {
        REFERENCE_TXN.contains(&self.txn_type.as_str())
    }
}
