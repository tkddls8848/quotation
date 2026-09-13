//! XML 과 Excel 사이에서 쓰는 견적 데이터 모델. 파이썬 `quotation/core/models.py`.

use crate::modes::Mode;
use crate::money::{Amount, Decimal, to_decimal};

pub const HARDWARE: &str = "Hardware";
pub const SOFTWARE: &str = "Software";
pub const SERVICES: &str = "Services";

/// 증설 견적에서 견적 대상이 아닌 TransactionType.
/// BASE 는 기존 구성, PROPOSED 는 증설 후 구성이다. 둘 다 참조용이다.
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

impl SubLineItem {
    /// 제거되는 부품인가. XML 의 수량은 양수이고 표시할 때 음수로 바꾼다.
    pub fn is_removal(&self) -> bool {
        self.txn_type == REMOVE_TXN
    }

    /// 금액 = (서브수량 x 부모수량) x 단가.
    ///
    /// 셀 수식 `=8*E8` 이 뜻하는 바와 같다. 서브 수량은 부모 1대당 수량이다.
    pub fn amount(&self, parent_quantity: i64) -> Decimal {
        to_decimal(&self.unit_price) * Decimal::from(self.quantity) * Decimal::from(parent_quantity)
    }
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
    /// IBM 문서에는 없거나 비어 있고, 레노버 문서에서 장비군 이름으로 쓴다.
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

    /// Hardware 만 H/W 구간이다. Services 는 S/W 로 간다
    /// (골든 X-ROIS `EXPERT LABS` 시트 B8 = "S/W", 6911-301 은 Services).
    pub fn is_hardware(&self) -> bool {
        self.product_type == HARDWARE
    }

    /// 자기 금액 + 모든 서브라인 금액.
    pub fn amount(&self) -> Decimal {
        let own = to_decimal(&self.unit_price) * Decimal::from(self.quantity);
        self.subs
            .iter()
            .fold(own, |total, sub| total + sub.amount(self.quantity))
    }
}

/// ProprietaryGroupIdentifier 로 묶인 장비군. 상세 시트 1장에 대응한다.
#[derive(Clone, Debug, PartialEq, Eq, Default)]
pub struct Group {
    pub group_id: String,
    pub item_key: String,
    pub sheet_name: String,
    /// 상세 시트 C1 에 적을 이름. 시트명과 달리 Excel 금칙 문자를 그대로 둔다
    /// (`메일/스펨_1식`). 비어 있으면 시트명을 쓴다.
    pub title: String,
    pub items: Vec<LineItem>,
}

impl Group {
    /// TOTAL 시트의 금액 병합 단위. H/W 구간과 S/W 구간이 각각 소계를 가진다.
    ///
    /// SPEC_CELLMAP.md §3.2 — 비어 있는 구간은 내놓지 않는다.
    pub fn sections(&self) -> Vec<(&'static str, Vec<&LineItem>)> {
        let hardware: Vec<_> = self
            .items
            .iter()
            .filter(|item| item.is_hardware())
            .collect();
        let software: Vec<_> = self
            .items
            .iter()
            .filter(|item| !item.is_hardware())
            .collect();
        [(HARDWARE, hardware), (SOFTWARE, software)]
            .into_iter()
            .filter(|(_, items)| !items.is_empty())
            .collect()
    }

    pub fn amount(&self) -> Decimal {
        self.items
            .iter()
            .fold(Decimal::ZERO, |total, item| total + item.amount())
    }
}

/// XML 한 건 = 견적서 한 부.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Quotation {
    pub groups: Vec<Group>,
    /// 문서에서 알아낸 읽기 방식. 견적 내용에는 쓰지 않고 진단에만 남긴다.
    pub mode: Mode,
}
