//! eConfig XML 파서. 파이썬 `quotation/core/xml_reader.py`.
//!
//! 문서를 읽는 **규칙**은 파이썬과 같다. 파서만 lxml(libxml2)에서
//! `quick-xml` 로 바뀌었고, 그 차이는 [`crate::xmldom`] 에 모아 두었다.
//!
//! 파이썬 쪽 EUC-KR 우회책(`_utf8_equivalent`)에 해당하는 코드는 없다.
//! `encoding_rs` 가 EUC-KR 을 기본으로 알기 때문에 선언만 보면 된다. 우회책이
//! 왜 있었는지는 [사고 0002](../../../doc/incidents/0002-pyodide-lxml-euckr.md)
//! 에 남아 있다.
//!
//! 한 곳이 다르다. 파이썬은 수량이나 금액이 숫자가 아니면 `ValueError` /
//! `InvalidOperation` 으로 죽는다. 여기서는 같은 자리에서 문서 오류로 알린다.
//! 통과하던 문서의 결과는 달라지지 않고, 죽던 자리에서만 문구가 생긴다.

use crate::dcsc_summary::{self, Summary};
use crate::integrated;
use crate::models::{Group, LineItem, Quotation, SubLineItem};
use crate::modes::{self, Mode};
use crate::money;
use crate::naming::{item_key, safe_sheet_name, sheet_name, unique_sheet_names};
use crate::xmldom::{self, Element};

/// 상위 라인과 서브라인을 합친 문서 전체 품목 수 상한.
pub const MAX_QUOTATION_ITEMS: usize = 5_000;

const LOAD_FAILURE: &str = "XML을 로드하는중 장애 발생. 장애코드: ";
const NO_ITEMS: &str = "견적서 작성을 위한 Item을 찾을 수 없습니다.";

/// XML 이 견적서 생성 요건을 만족하지 않을 때. 문구는 원본 프로그램과 같다.
#[derive(Debug, PartialEq, Eq)]
pub struct QuotationXmlError {
    pub message: String,
}

impl QuotationXmlError {
    fn new(message: impl Into<String>) -> Self {
        Self {
            message: message.into(),
        }
    }

    fn load(detail: impl std::fmt::Display) -> Self {
        Self::new(format!("{LOAD_FAILURE}{detail}"))
    }
}

impl std::fmt::Display for QuotationXmlError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(&self.message)
    }
}

impl std::error::Error for QuotationXmlError {}

type Result<T> = std::result::Result<T, QuotationXmlError>;

// --- 원본 프로그램의 경로 (변경 금지) -----------------------------------------

const P_CFDATA: [&str; 1] = ["CFData"];
const P_LINE_NUMBER: [&str; 1] = ["ProductLineNumber"];
const P_SIU: [&str; 1] = ["CPUSIUvalue"];
const P_TXN_TYPE: [&str; 1] = ["TransactionType"];
const P_GROUP_ID: [&str; 1] = ["ProprietaryGroupIdentifier"];
const P_QUANTITY: [&str; 1] = ["Quantity"];
const P_DESC: [&str; 3] = [
    "ProductIdentification",
    "PartnerProductIdentification",
    "ProductDescription",
];
const P_PRODUCT_NAME: [&str; 3] = [
    "ProductIdentification",
    "PartnerProductIdentification",
    "ProductName",
];
const P_TYPE_CODE: [&str; 3] = [
    "ProductIdentification",
    "PartnerProductIdentification",
    "ProductTypeCode",
];
const P_PART_NO: [&str; 3] = [
    "ProductIdentification",
    "PartnerProductIdentification",
    "ProprietaryProductIdentifier",
];
const P_AMOUNT: [&str; 3] = ["UnitListPrice", "FinancialAmount", "MonetaryAmount"];
const LINE_ITEM: &str = "ProductLineItem";
const SUB_LINE_ITEM: &str = "ProductSubLineItem";

/// eConfig XML 바이트 -> 견적서 한 부.
///
/// `mode` 를 주면 문서를 읽는 방식을 강제한다 (`"unix"` / `"integrated"`).
/// 비워 두면 문서 내용으로 알아낸다 — 보통은 이쪽을 쓴다.
pub fn parse_bytes(data: &[u8], mode: Option<&str>) -> Result<Quotation> {
    let (root, items) = read(data)?;

    // 증설 견적은 기존(BASE)·증설후(PROPOSED) 구성을 참조용으로 함께 담는다.
    // 견적서에는 실제 증설분만 넣는다.
    let names = reference_names(&items);
    let quoted: Vec<LineItem> = items
        .into_iter()
        .filter(|item| !item.is_reference())
        .collect();
    if quoted.is_empty() {
        return Err(QuotationXmlError::new(NO_ITEMS));
    }

    // IBM 문서인지 레노버 x86 문서인지는 사람이 고르지 않는다. 본체 라인에
    // ProductName 이 있으면 통합, 없으면 UNIX 다.
    let resolved = modes::resolve(mode, quoted.iter().map(|item| item.product_name.as_str()))
        .map_err(|error| QuotationXmlError::new(error.to_string()))?;

    // 요약표는 문서 하나에 한 벌이고 장비군에 한 번씩 짝지어 쓴다. 통합 모드가
    // 아니면 읽지 않는다 — UNIX 경로는 한 줄도 달라지지 않는다.
    let mut summary = match resolved {
        Mode::Integrated => Some(dcsc_summary::parse(&root)),
        Mode::Unix => None,
    };

    Ok(Quotation {
        mode: resolved,
        groups: build_groups(quoted, &names, resolved, summary.as_mut()),
    })
}

/// eConfig XML 바이트 -> 문서에 적힌 모든 라인 (참조용 구성까지 그대로).
pub fn parse_items(data: &[u8]) -> Result<Vec<LineItem>> {
    let (_, items) = read(data)?;
    if items.iter().all(LineItem::is_reference) {
        return Err(QuotationXmlError::new(NO_ITEMS));
    }
    Ok(items)
}

/// 문서를 읽어 뿌리와 라인을 함께 돌려준다. 요약표가 뿌리를 다시 본다.
fn read(data: &[u8]) -> Result<(Element, Vec<LineItem>)> {
    if data.iter().all(u8::is_ascii_whitespace) {
        return Err(QuotationXmlError::load("빈 화일입니다."));
    }

    let root = xmldom::parse(data).map_err(QuotationXmlError::load)?;
    if root.name != "CFXML" {
        return Err(QuotationXmlError::new("CFXML을 찾을수 없습니다."));
    }
    let cfdata = root
        .find(&P_CFDATA)
        .ok_or_else(|| QuotationXmlError::new("CFData을 찾을수 없습니다."))?;

    let mut elements = Vec::new();
    cfdata.descendants_named(LINE_ITEM, &mut elements);
    if elements.is_empty() {
        return Err(QuotationXmlError::new(NO_ITEMS));
    }

    let count = elements.len()
        + elements
            .iter()
            .map(|element| element.children_named(SUB_LINE_ITEM).count())
            .sum::<usize>();
    if count > MAX_QUOTATION_ITEMS {
        return Err(QuotationXmlError::new(format!(
            "구성 품목이 너무 많습니다. (최대 {}건)",
            with_thousands(MAX_QUOTATION_ITEMS)
        )));
    }

    let items = elements
        .iter()
        .map(|element| read_line(element))
        .collect::<Result<Vec<_>>>()?;
    Ok((root, items))
}

fn read_line(element: &Element) -> Result<LineItem> {
    let subs = element
        .children_named(SUB_LINE_ITEM)
        .map(read_sub)
        .collect::<Result<Vec<_>>>()?;
    Ok(LineItem {
        line_number: element.text_at(&P_LINE_NUMBER).to_owned(),
        txn_type: element.text_at(&P_TXN_TYPE).to_owned(),
        group_id: element.text_at(&P_GROUP_ID).to_owned(),
        quantity: int_at(element, &P_QUANTITY, 1)?,
        part_number: element.text_at(&P_PART_NO).to_owned(),
        description: element.text_at(&P_DESC).to_owned(),
        product_type: element.text_at(&P_TYPE_CODE).to_owned(),
        product_name: element.text_at(&P_PRODUCT_NAME).to_owned(),
        unit_price: amount_at(element, &P_AMOUNT)?,
        subs,
        siu: int_at(element, &P_SIU, 0)?,
    })
}

fn read_sub(element: &Element) -> Result<SubLineItem> {
    Ok(SubLineItem {
        txn_type: element.text_at(&P_TXN_TYPE).to_owned(),
        quantity: int_at(element, &P_QUANTITY, 1)?,
        part_number: element.text_at(&P_PART_NO).to_owned(),
        description: element.text_at(&P_DESC).to_owned(),
        unit_price: amount_at(element, &P_AMOUNT)?,
    })
}

/// 파이썬 `_int` — 비어 있으면 기본값.
fn int_at(element: &Element, path: &[&str], default: i64) -> Result<i64> {
    let raw = element.text_at(path);
    if raw.is_empty() {
        return Ok(default);
    }
    raw.parse::<i64>()
        .map_err(|_| QuotationXmlError::load(format!("숫자가 아닙니다: {raw}")))
}

fn amount_at(element: &Element, path: &[&str]) -> Result<money::Amount> {
    money::parse_amount(Some(element.text_at(path)))
        .map_err(|error| QuotationXmlError::load(error.to_string()))
}

/// 증설 견적의 장비 이름. 기존(BASE)/증설후(PROPOSED) 구성의 본체 라인에서 딴다.
///
/// 증설 라인(UPGRADE)의 Description 은 `9080 Model HEU` 처럼 장비 이름이 없다.
/// 골든은 시트를 `SERVER 1` 로 부르는데, 그 이름은 BASE 구성의 본체 라인
/// `Server 1:Server 1:IBM Power E1080` 에서 온다.
fn reference_names(items: &[LineItem]) -> Vec<String> {
    let mut names: Vec<String> = Vec::new();
    for item in items {
        if item.is_reference() && item.siu == 1 {
            let key = item_key(&item.description);
            if !names.contains(&key) {
                names.push(key);
            }
        }
    }
    names
}

/// ProprietaryGroupIdentifier 로 묶는다. 문서 등장 순서를 유지한다.
///
/// 증설 견적일 때만 두 가지 보정이 붙는다.
///   - 본체 라인(CPUSIUvalue=1)이 없는 그룹을 앞 그룹에 합친다. 증설은 장비
///     한 대에 대한 변경이라 UPGRADE/DISCO/NEW 가 한 장에 나온다.
///   - 장비 이름을 BASE/PROPOSED 구성에서 가져온다.
///
/// 신규 견적에서는 합치지 않는다. 본체 라인이 없어도 제 장을 갖는다.
///
/// 통합 모드는 장비 이름을 ProductName 에서 따고, 본체 LP 에 들어 있는
/// 소프트웨어·서비스 금액을 갈라 놓으며, 시트명의 금칙 문자를 걷어 낸다.
fn build_groups(
    items: Vec<LineItem>,
    reference_names: &[String],
    mode: Mode,
    mut summary: Option<&mut Summary>,
) -> Vec<Group> {
    let is_upgrade = !reference_names.is_empty();
    let is_integrated = mode == Mode::Integrated;

    let mut buckets: Vec<(String, Vec<LineItem>)> = Vec::new();
    for item in items {
        let key = if item.group_id.is_empty() {
            item.line_number.clone()
        } else {
            item.group_id.clone()
        };
        match buckets.iter_mut().find(|(id, _)| *id == key) {
            Some((_, members)) => members.push(item),
            None => buckets.push((key, vec![item])),
        }
    }

    let mut merged: Vec<(String, Vec<LineItem>)> = Vec::new();
    for (id, members) in buckets {
        let has_body = members.iter().any(|item| item.siu == 1);
        match merged.last_mut() {
            Some((_, previous)) if is_upgrade && !has_body => previous.extend(members),
            _ => merged.push((id, members)),
        }
    }

    let mut ids: Vec<String> = Vec::with_capacity(merged.len());
    let mut keys: Vec<String> = Vec::with_capacity(merged.len());
    let mut members_by_group: Vec<Vec<LineItem>> = Vec::with_capacity(merged.len());
    for (index, (id, members)) in merged.into_iter().enumerate() {
        let (key, members) = if is_integrated {
            let members = integrated::fold_prices(members, summary.as_deref_mut());
            let key = integrated::group_key(&members);
            (key, members)
        } else if index < reference_names.len() {
            (reference_names[index].clone(), members)
        } else {
            (item_key(&members[0].description), members)
        };
        ids.push(id);
        keys.push(key);
        members_by_group.push(members);
    }

    let (titles, names): (Vec<String>, Vec<String>) = if is_integrated {
        (
            keys.iter().map(|key| sheet_name(key)).collect(),
            unique_sheet_names(keys.iter().map(|key| safe_sheet_name(key))),
        )
    } else {
        (
            vec![String::new(); keys.len()],
            keys.iter().map(|key| sheet_name(key)).collect(),
        )
    };

    ids.into_iter()
        .zip(keys)
        .zip(names)
        .zip(titles)
        .zip(members_by_group)
        .map(
            |((((group_id, item_key), sheet_name), title), items)| Group {
                group_id,
                item_key,
                sheet_name,
                title,
                items,
            },
        )
        .collect()
}

/// 파이썬 `f"{n:,}"`.
fn with_thousands(value: usize) -> String {
    let digits = value.to_string();
    let mut out = String::with_capacity(digits.len() + digits.len() / 3);
    for (index, digit) in digits.chars().enumerate() {
        if index > 0 && (digits.len() - index) % 3 == 0 {
            out.push(',');
        }
        out.push(digit);
    }
    out
}
