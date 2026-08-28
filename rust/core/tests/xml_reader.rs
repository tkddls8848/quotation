//! Phase 2 — eConfig XML 파서의 이식 검증.
//!
//! 기대값은 전부 파이썬 `quotation.core.xml_reader` 가 같은 fixture 에서 내는
//! 값이다. 파이썬이 기준이고, 여기서 다르면 이식이 틀린 것이다.

use std::path::PathBuf;

use quotation_core::money::Amount;
use quotation_core::xml_reader::{self, MAX_QUOTATION_ITEMS};

fn fixture(name: &str) -> Vec<u8> {
    let path: PathBuf = [
        env!("CARGO_MANIFEST_DIR"),
        "..",
        "..",
        "tests",
        "fixtures",
        "public",
    ]
    .iter()
    .collect::<PathBuf>()
    .join(name);
    std::fs::read(&path).unwrap_or_else(|error| panic!("fixture {path:?}: {error}"))
}

fn message(bytes: &[u8]) -> String {
    xml_reader::parse_items(bytes)
        .expect_err("거절해야 한다")
        .to_string()
}

// --- 골든 fixture ------------------------------------------------------------

#[test]
fn reads_every_public_fixture() {
    // (파일, 상위 라인, 서브라인) — 파이썬이 같은 파일에서 세는 값이다.
    let cases = [
        ("euckr_quote.xml", 1, 0),
        ("integrated_quote.xml", 6, 1),
        ("integrated_summary_quote.xml", 6, 1),
        ("new_quote.xml", 3, 2),
        ("no_charge.xml", 1, 1),
        ("upgrade_quote.xml", 4, 3),
    ];
    for (name, lines, subs) in cases {
        let items = xml_reader::parse_items(&fixture(name)).unwrap_or_else(|error| {
            panic!("{name}: {error}");
        });
        assert_eq!(items.len(), lines, "{name} 상위 라인 수");
        assert_eq!(
            items.iter().map(|item| item.subs.len()).sum::<usize>(),
            subs,
            "{name} 서브라인 수"
        );
    }
}

#[test]
fn reads_euckr_declaration_and_inline_dtd() {
    // 이 fixture 는 EUC-KR 이고 인라인 DTD 를 달고 있다. 둘 다 그대로 읽어야 한다.
    let items = xml_reader::parse_items(&fixture("euckr_quote.xml")).expect("읽혀야 한다");
    let first = &items[0];
    assert_eq!(first.description, "서버 1:표본 한글 설명 장비");
    assert_eq!(first.part_number, "1234-567");
    assert_eq!(first.quantity, 1);
    assert_eq!(first.product_type, "Hardware");
    assert_eq!(first.unit_price, Amount::Priced("1000.5".parse().unwrap()));
}

#[test]
fn reads_line_and_sub_fields() {
    let items = xml_reader::parse_items(&fixture("new_quote.xml")).expect("읽혀야 한다");
    let first = &items[0];
    assert_eq!(first.txn_type, "NEW");
    assert!(!first.group_id.is_empty());
    assert!(!first.line_number.is_empty());
    let sub = items
        .iter()
        .flat_map(|item| item.subs.iter())
        .next()
        .expect("서브라인이 있어야 한다");
    assert_eq!(sub.txn_type, "ADD");
    assert!(!sub.part_number.is_empty());
}

// --- 오류 문구 ---------------------------------------------------------------
//
// 사용자가 보는 문구는 원본 프로그램과 같아야 한다. 구문 오류의 뒷부분(파서가
// 내는 설명)만 구현마다 다르고, 그 앞의 문구는 같다.

#[test]
fn rejects_empty_document() {
    assert!(message(b"").contains("빈 화일입니다."));
    assert!(message(b"   \n\t ").contains("빈 화일입니다."));
}

#[test]
fn rejects_document_without_cfxml_root() {
    assert_eq!(
        message(b"<Other><CFData/></Other>"),
        "CFXML을 찾을수 없습니다."
    );
}

#[test]
fn rejects_document_without_cfdata() {
    assert_eq!(message(b"<CFXML></CFXML>"), "CFData을 찾을수 없습니다.");
}

#[test]
fn rejects_document_without_line_items() {
    assert_eq!(
        message(b"<CFXML><CFData/></CFXML>"),
        "견적서 작성을 위한 Item을 찾을 수 없습니다."
    );
}

#[test]
fn rejects_reference_only_document() {
    // BASE / PROPOSED 는 증설 견적의 참조용 구성이다. 그것만 있으면 견적이 없다.
    let document = r#"<CFXML><CFData>
        <ProductLineItem><TransactionType>BASE</TransactionType></ProductLineItem>
        <ProductLineItem><TransactionType>PROPOSED</TransactionType></ProductLineItem>
    </CFData></CFXML>"#;
    assert_eq!(
        message(document.as_bytes()),
        "견적서 작성을 위한 Item을 찾을 수 없습니다."
    );
}

#[test]
fn reports_syntax_errors_with_the_python_prefix() {
    let message = message(b"<CFXML><CFData>");
    assert!(
        message.starts_with("XML을 로드하는중 장애 발생. 장애코드: "),
        "{message}"
    );
}

#[test]
fn rejects_documents_with_too_many_items() {
    let mut document = String::from("<CFXML><CFData>");
    for _ in 0..=MAX_QUOTATION_ITEMS {
        document
            .push_str("<ProductLineItem><TransactionType>NEW</TransactionType></ProductLineItem>");
    }
    document.push_str("</CFData></CFXML>");
    assert_eq!(
        message(document.as_bytes()),
        "구성 품목이 너무 많습니다. (최대 5,000건)"
    );
}

// --- 외부 참조 차단 ------------------------------------------------------------

#[test]
fn does_not_expand_external_entities() {
    // 파이썬 파서는 엔티티를 펼치지 않는다. 그래서 설명은 엔티티 앞까지만 남는다.
    let document = r#"<?xml version="1.0"?>
    <!DOCTYPE CFXML [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>
    <CFXML><CFData><ProductLineItem>
        <TransactionType>NEW</TransactionType>
        <ProductIdentification><PartnerProductIdentification>
            <ProductDescription>before&xxe;after</ProductDescription>
        </PartnerProductIdentification></ProductIdentification>
    </ProductLineItem></CFData></CFXML>"#;
    let items = xml_reader::parse_items(document.as_bytes()).expect("문서 자체는 거절하지 않는다");
    assert_eq!(items[0].description, "before");
}

#[test]
fn expands_predefined_entities_but_not_document_entities() {
    // lxml 은 규격이 정한 엔티티(&amp; 등)와 숫자 참조는 언제나 펼치고,
    // 문서가 스스로 정의한 엔티티만 펼치지 않는다. 실제 구성 XML 의
    // 'Premium S&amp;H Indicator' 가 이 자리에 걸린다.
    let document = r#"<CFXML><CFData>
        <ProductLineItem>
            <TransactionType>NEW</TransactionType>
            <ProductIdentification><PartnerProductIdentification>
                <ProductDescription>Premium S&amp;H Indicator</ProductDescription>
                <ProprietaryProductIdentifier>&#65;KNC</ProprietaryProductIdentifier>
            </PartnerProductIdentification></ProductIdentification>
        </ProductLineItem>
    </CFData></CFXML>"#;
    let items = xml_reader::parse_items(document.as_bytes()).expect("읽혀야 한다");
    assert_eq!(items[0].description, "Premium S&H Indicator");
    assert_eq!(items[0].part_number, "AKNC");
}

// --- 값 다듬기 ---------------------------------------------------------------

#[test]
fn strips_surrounding_space_in_every_field() {
    let document = r#"<CFXML><CFData><ProductLineItem>
        <ProductLineNumber>  7  </ProductLineNumber>
        <TransactionType>  NEW  </TransactionType>
        <Quantity>  3  </Quantity>
        <CPUSIUvalue>  1  </CPUSIUvalue>
        <ProductIdentification><PartnerProductIdentification>
            <ProductDescription>  설명  </ProductDescription>
            <ProductName>  백업서버_1식  </ProductName>
            <ProductTypeCode>  Hardware  </ProductTypeCode>
            <ProprietaryProductIdentifier>  1234-567  </ProprietaryProductIdentifier>
        </PartnerProductIdentification></ProductIdentification>
        <UnitListPrice><FinancialAmount><MonetaryAmount>  1,024.50  </MonetaryAmount></FinancialAmount></UnitListPrice>
    </ProductLineItem></CFData></CFXML>"#;
    let items = xml_reader::parse_items(document.as_bytes()).expect("읽혀야 한다");
    let item = &items[0];
    assert_eq!(item.line_number, "7");
    assert_eq!(item.txn_type, "NEW");
    assert_eq!(item.quantity, 3);
    assert_eq!(item.siu, 1);
    assert_eq!(item.description, "설명");
    assert_eq!(item.product_name, "백업서버_1식");
    assert_eq!(item.product_type, "Hardware");
    assert_eq!(item.part_number, "1234-567");
    assert_eq!(item.unit_price, Amount::Priced("1024.50".parse().unwrap()));
}

#[test]
fn missing_numbers_fall_back_like_python() {
    // 파이썬 `_int` 의 기본값 — 수량은 1, CPUSIUvalue 는 0 이다.
    let document = r#"<CFXML><CFData><ProductLineItem>
        <TransactionType>NEW</TransactionType>
    </ProductLineItem></CFData></CFXML>"#;
    let items = xml_reader::parse_items(document.as_bytes()).expect("읽혀야 한다");
    assert_eq!(items[0].quantity, 1);
    assert_eq!(items[0].siu, 0);
    assert_eq!(items[0].unit_price, Amount::Missing);
    assert_eq!(items[0].description, "");
}
