//! eConfig XML 파서. 파이썬 `quotation/core/xml_reader.py`.
//!
//! 파이썬은 lxml(libxml2)을 쓰고 여기서는 `quick-xml` 을 쓴다. 문서를 읽는
//! **규칙**은 같다.
//!
//! - 외부 참조를 하지 않는다. 인라인 DTD 가 있는 2005년 형식 문서는 읽되
//!   엔티티는 펼치지 않는다 (XXE 차단). 그래서 `before&xxe;after` 는 파이썬과
//!   똑같이 `before` 로 읽힌다.
//!   ([사고 0002](../../../doc/incidents/0002-pyodide-lxml-euckr.md) 도 참고)
//! - 인코딩은 XML 선언을 따른다. `encoding_rs` 가 EUC-KR 을 기본으로 알기
//!   때문에 파이썬 쪽 우회책(`_utf8_equivalent`)에 해당하는 코드가 없다.
//! - 이름공간이 붙은 원소는 파이썬 `find()` 와 같이 **찾지 않는다.** 뿌리
//!   이름만 `QName(root).localname` 처럼 접두사를 떼고 본다.
//!
//! 한 곳이 다르다. 파이썬은 수량이나 금액이 숫자가 아니면 `ValueError` /
//! `InvalidOperation` 으로 죽는다(사용자에게는 추적 정보가 그대로 나간다).
//! 여기서는 같은 자리에서 문서 오류로 알린다. 통과하던 문서의 결과는 달라지지
//! 않고, 죽던 자리에서만 문구가 생긴다.

use quick_xml::NsReader;
use quick_xml::events::Event;
use quick_xml::name::ResolveResult;

use crate::models::{LineItem, SubLineItem};
use crate::money;
use crate::text;

/// 상위 라인과 서브라인을 합친 문서 전체 품목 수 상한.
pub const MAX_QUOTATION_ITEMS: usize = 5_000;

const LOAD_FAILURE: &str = "XML을 로드하는중 장애 발생. 장애코드: ";

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

/// 파싱한 원소 하나. 파이썬이 lxml 노드에서 쓰는 만큼만 담는다.
#[derive(Debug, Default)]
struct Element {
    /// 접두사를 뗀 이름.
    name: String,
    /// 이름공간이 붙어 있는가. 붙어 있으면 파이썬 `find()` 가 찾지 못한다.
    namespaced: bool,
    /// 첫 자식(또는 엔티티 참조) 앞까지의 글. lxml `.text` 와 같다.
    text: String,
    /// 글 모으기를 끝냈는가.
    closed_text: bool,
    children: Vec<Element>,
}

impl Element {
    /// 파이썬 `el.find(path)` — 이름공간 없는 자식만 따라간다.
    fn find(&self, path: &[&str]) -> Option<&Element> {
        let mut node = self;
        for step in path {
            node = node
                .children
                .iter()
                .find(|child| !child.namespaced && child.name == *step)?;
        }
        Some(node)
    }

    /// 파이썬 `el.findall("./name")`.
    fn children_named<'a>(&'a self, name: &'a str) -> impl Iterator<Item = &'a Element> {
        self.children
            .iter()
            .filter(move |child| !child.namespaced && child.name == name)
    }

    /// 파이썬 `el.findall(".//name")` — 문서 순서로 모든 자손.
    fn descendants_named<'a>(&'a self, name: &'a str, found: &mut Vec<&'a Element>) {
        for child in &self.children {
            if !child.namespaced && child.name == name {
                found.push(child);
            }
            child.descendants_named(name, found);
        }
    }

    /// 파이썬 `_text` — 없으면 빈 글, 있으면 앞뒤를 다듬는다.
    fn text_at(&self, path: &[&str]) -> &str {
        self.find(path).map_or("", |node| text::strip(&node.text))
    }

    /// 파이썬 `_int` — 비어 있으면 기본값.
    fn int_at(&self, path: &[&str], default: i64) -> Result<i64> {
        let raw = self.text_at(path);
        if raw.is_empty() {
            return Ok(default);
        }
        raw.parse::<i64>()
            .map_err(|_| QuotationXmlError::load(format!("숫자가 아닙니다: {raw}")))
    }

    fn amount_at(&self, path: &[&str]) -> Result<money::Amount> {
        money::parse_amount(Some(self.text_at(path)))
            .map_err(|error| QuotationXmlError::load(error.to_string()))
    }
}

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

/// eConfig XML 바이트 -> 문서에 적힌 모든 라인 (참조용 구성까지 그대로).
///
/// 그룹으로 묶는 일은 여기서 하지 않는다. 파이썬 `_build_groups` 에 해당하는
/// 부분은 Phase 3 에서 옮긴다.
pub fn parse_items(data: &[u8]) -> Result<Vec<LineItem>> {
    if data.iter().all(u8::is_ascii_whitespace) {
        return Err(QuotationXmlError::load("빈 화일입니다."));
    }

    let root = read_document(data)?;
    if root.name != "CFXML" {
        return Err(QuotationXmlError::new("CFXML을 찾을수 없습니다."));
    }
    let cfdata = root
        .find(&P_CFDATA)
        .ok_or_else(|| QuotationXmlError::new("CFData을 찾을수 없습니다."))?;

    let mut elements = Vec::new();
    cfdata.descendants_named(LINE_ITEM, &mut elements);
    if elements.is_empty() {
        return Err(QuotationXmlError::new(
            "견적서 작성을 위한 Item을 찾을 수 없습니다.",
        ));
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

    // 증설 견적은 기존(BASE)·증설후(PROPOSED) 구성을 참조용으로 함께 담는다.
    // 견적 대상이 하나도 없으면 견적서를 만들 수 없다.
    if items.iter().all(LineItem::is_reference) {
        return Err(QuotationXmlError::new(
            "견적서 작성을 위한 Item을 찾을 수 없습니다.",
        ));
    }
    Ok(items)
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
        quantity: element.int_at(&P_QUANTITY, 1)?,
        part_number: element.text_at(&P_PART_NO).to_owned(),
        description: element.text_at(&P_DESC).to_owned(),
        product_type: element.text_at(&P_TYPE_CODE).to_owned(),
        product_name: element.text_at(&P_PRODUCT_NAME).to_owned(),
        unit_price: element.amount_at(&P_AMOUNT)?,
        subs,
        siu: element.int_at(&P_SIU, 0)?,
    })
}

fn read_sub(element: &Element) -> Result<SubLineItem> {
    Ok(SubLineItem {
        txn_type: element.text_at(&P_TXN_TYPE).to_owned(),
        quantity: element.int_at(&P_QUANTITY, 1)?,
        part_number: element.text_at(&P_PART_NO).to_owned(),
        description: element.text_at(&P_DESC).to_owned(),
        unit_price: element.amount_at(&P_AMOUNT)?,
    })
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

/// 바이트 -> 원소 나무. 선언된 인코딩을 따르고 외부 참조는 하지 않는다.
fn read_document(data: &[u8]) -> Result<Element> {
    let mut reader = NsReader::from_reader(data);
    reader.config_mut().check_end_names = true;
    let mut buffer = Vec::new();
    let mut stack: Vec<Element> = Vec::new();
    let mut root: Option<Element> = None;

    loop {
        let (namespace, event) = reader
            .read_resolved_event_into(&mut buffer)
            .map_err(QuotationXmlError::load)?;
        match event {
            Event::Start(tag) => {
                let element = open(tag.name().local_name().as_ref(), &namespace);
                mark_child(&mut stack);
                stack.push(element);
            }
            Event::Empty(tag) => {
                let element = open(tag.name().local_name().as_ref(), &namespace);
                mark_child(&mut stack);
                close(&mut stack, &mut root, element)?;
            }
            Event::End(_) => {
                let element = stack
                    .pop()
                    .ok_or_else(|| QuotationXmlError::load("닫는 태그가 남습니다."))?;
                close(&mut stack, &mut root, element)?;
            }
            Event::Text(body) => {
                let decoded = body.decode().map_err(QuotationXmlError::load)?.into_owned();
                push_text(&mut stack, &decoded);
            }
            Event::CData(body) => {
                // CDATA 도 lxml 에서는 그냥 글이다.
                let decoded = reader
                    .decoder()
                    .decode(&body)
                    .map_err(QuotationXmlError::load)?
                    .into_owned();
                push_text(&mut stack, &decoded);
            }
            // 규격이 정한 엔티티와 숫자 참조는 lxml 과 같이 펼친다. 문서가 스스로
            // 정의한 엔티티만 펼치지 않고, 거기서 `.text` 가 끝난다 (XXE 차단).
            Event::GeneralRef(reference) => match predefined(&reference) {
                Some(character) => push_text(&mut stack, &character.to_string()),
                None => mark_child(&mut stack),
            },
            Event::Eof => break,
            _ => {}
        }
        buffer.clear();
    }

    if !stack.is_empty() {
        return Err(QuotationXmlError::load("닫히지 않은 태그가 있습니다."));
    }
    root.ok_or_else(|| QuotationXmlError::load("빈 화일입니다."))
}

fn open(name: &[u8], namespace: &ResolveResult) -> Element {
    Element {
        name: String::from_utf8_lossy(name).into_owned(),
        namespaced: matches!(namespace, ResolveResult::Bound(_)),
        ..Element::default()
    }
}

/// 규격이 정한 엔티티(`&amp;` 등)와 숫자 참조를 글자로 바꾼다.
///
/// 문서가 `<!ENTITY ...>` 로 정의한 것은 여기서 `None` 이 되어 펼쳐지지 않는다.
fn predefined(reference: &quick_xml::events::BytesRef<'_>) -> Option<char> {
    if let Ok(Some(character)) = reference.resolve_char_ref() {
        return Some(character);
    }
    match reference.as_ref() {
        b"amp" => Some('&'),
        b"lt" => Some('<'),
        b"gt" => Some('>'),
        b"quot" => Some('"'),
        b"apos" => Some('\''),
        _ => None,
    }
}

/// 첫 자식 앞까지의 글만 모은다.
fn push_text(stack: &mut [Element], body: &str) {
    if let Some(current) = stack.last_mut() {
        if !current.closed_text {
            current.text.push_str(body);
        }
    }
}

/// 자식이 하나라도 생기면 그 원소의 `.text` 는 더 자라지 않는다 (lxml 과 같다).
fn mark_child(stack: &mut [Element]) {
    if let Some(current) = stack.last_mut() {
        current.closed_text = true;
    }
}

fn close(stack: &mut [Element], root: &mut Option<Element>, element: Element) -> Result<()> {
    match stack.last_mut() {
        Some(parent) => parent.children.push(element),
        None => {
            if root.is_some() {
                return Err(QuotationXmlError::load("뿌리 원소가 둘입니다."));
            }
            *root = Some(element);
        }
    }
    Ok(())
}
