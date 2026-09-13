//! Phase 3 — 모델 · 통합 모드 · DCSC 요약표 · 그룹 구성의 이식 검증.
//!
//! 기대값은 전부 파이썬 `quotation.core.xml_reader.parse_bytes` 가 같은
//! fixture 에서 내는 값이다.

use std::path::PathBuf;

use quotation_core::modes::Mode;
use quotation_core::xml_reader;

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

fn quotation(name: &str) -> quotation_core::models::Quotation {
    xml_reader::parse_bytes(&fixture(name), None).unwrap_or_else(|error| panic!("{name}: {error}"))
}

// --- 모드 판정 ---------------------------------------------------------------

#[test]
fn detects_the_mode_from_the_document() {
    assert_eq!(quotation("new_quote.xml").mode, Mode::Unix);
    assert_eq!(quotation("euckr_quote.xml").mode, Mode::Unix);
    assert_eq!(quotation("upgrade_quote.xml").mode, Mode::Unix);
    assert_eq!(quotation("integrated_quote.xml").mode, Mode::Integrated);
}

#[test]
fn honours_an_explicit_mode() {
    let forced = xml_reader::parse_bytes(&fixture("integrated_quote.xml"), Some("unix"))
        .expect("읽혀야 한다");
    assert_eq!(forced.mode, Mode::Unix);
    assert!(xml_reader::parse_bytes(&fixture("new_quote.xml"), Some("x86")).is_err());
}

// --- 그룹 구성 ---------------------------------------------------------------

#[test]
fn groups_new_quotes_by_group_identifier() {
    let quotation = quotation("new_quote.xml");
    let sheets: Vec<_> = quotation
        .groups
        .iter()
        .map(|group| group.sheet_name.as_str())
        .collect();
    assert_eq!(sheets, ["SAMPLE-100 #1", "SAMPLE-200 #2"]);
    assert_eq!(quotation.groups[0].amount().to_string(), "2851.00");
    assert_eq!(quotation.groups[1].amount().to_string(), "11800");
    // 제목 칸은 UNIX 모드에서 비어 있다. 시트명을 그대로 쓴다.
    assert!(quotation.groups.iter().all(|group| group.title.is_empty()));
}

#[test]
fn merges_upgrade_groups_without_a_body_line() {
    // 증설은 장비 한 대에 대한 변경이라 UPGRADE/DISCO 가 한 장에 나온다.
    // 시트 이름은 BASE 구성의 본체 라인에서 온다.
    let quotation = quotation("upgrade_quote.xml");
    assert_eq!(quotation.groups.len(), 1);
    let group = &quotation.groups[0];
    assert_eq!(group.group_id, "3000");
    assert_eq!(group.item_key, "Server 1");
    assert_eq!(group.sheet_name, "SERVER 1");
    assert_eq!(group.items.len(), 2);
    assert_eq!(group.amount().to_string(), "5500");
}

#[test]
fn keeps_no_charge_lines_at_zero() {
    let quotation = quotation("no_charge.xml");
    assert_eq!(quotation.groups[0].amount().to_string(), "0");
    assert_eq!(quotation.groups[0].items[0].amount().to_string(), "0");
}

#[test]
fn splits_sections_into_hardware_and_software() {
    let quotation = quotation("new_quote.xml");
    let first: Vec<_> = quotation.groups[0]
        .sections()
        .iter()
        .map(|(kind, items)| (*kind, items.len()))
        .collect();
    assert_eq!(first, [("Hardware", 1), ("Software", 1)]);
    // 6911-301 은 Services 지만 골든에서 S/W 구간에 들어간다.
    let second: Vec<_> = quotation.groups[1]
        .sections()
        .iter()
        .map(|(kind, items)| (*kind, items.len()))
        .collect();
    assert_eq!(second, [("Software", 1)]);
}

// --- 통합 모드 ---------------------------------------------------------------

#[test]
fn integrated_names_groups_from_product_name() {
    let quotation = quotation("integrated_quote.xml");
    let keys: Vec<_> = quotation
        .groups
        .iter()
        .map(|group| group.item_key.as_str())
        .collect();
    assert_eq!(
        keys,
        [
            "백업서버_1식",
            "메일/스펨_2식",
            "Sample 42U Deep Static Rack"
        ]
    );
    // 시트명은 금칙 문자를 걷어 내고, 제목 칸에는 원래 이름이 남는다.
    let sheets: Vec<_> = quotation
        .groups
        .iter()
        .map(|group| group.sheet_name.as_str())
        .collect();
    assert_eq!(
        sheets,
        [
            "백업서버_1식",
            "메일-스펨_2식",
            "SAMPLE 42U DEEP STATIC RACK"
        ]
    );
    assert_eq!(quotation.groups[1].title, "메일/스펨_2식");
}

#[test]
fn integrated_without_summary_empties_non_hardware_prices() {
    // 본체 LP 에 이미 들어 있는 금액이라 그대로 더하면 두 번 센다.
    let quotation = quotation("integrated_quote.xml");
    let group = &quotation.groups[0];
    assert_eq!(group.amount().to_string(), "40172000");
    for item in group.items.iter().filter(|item| !item.is_hardware()) {
        assert_eq!(
            item.unit_price,
            quotation_core::money::Amount::Missing,
            "{}",
            item.part_number
        );
    }
}

#[test]
fn integrated_with_summary_splits_the_body_price() {
    // 요약표(SectionData/GroupData)가 품목별 실금액을 담고 있다.
    let quotation = quotation("integrated_summary_quote.xml");
    let group = &quotation.groups[0];
    let prices: Vec<_> = group
        .items
        .iter()
        .map(|item| item.amount().to_string())
        .collect();
    assert_eq!(prices, ["29041000.0", "5440000.0", "5691000.0"]);
    // 갈라 놓아도 장비군 합계는 본체 LP 그대로다.
    assert_eq!(group.amount().to_string(), "40172000.0");

    let second = &quotation.groups[1];
    assert_eq!(second.amount().to_string(), "85624000.0");
    assert_eq!(second.items[0].unit_price.to_string(), "41971000.0");
    assert_eq!(second.items[1].unit_price.to_string(), "841000.0");
}

#[test]
fn integrated_leaves_part_only_groups_alone() {
    // 랙·PDU 처럼 본체 없이 부품만 있는 그룹은 제 금액을 그대로 쓴다.
    let quotation = quotation("integrated_quote.xml");
    let rack = &quotation.groups[2];
    assert_eq!(rack.amount().to_string(), "17920000.0");
    assert_eq!(rack.items[0].unit_price.to_string(), "8960000.0");
}

// --- EUC-KR ------------------------------------------------------------------

#[test]
fn reads_the_korean_fixture_end_to_end() {
    let quotation = quotation("euckr_quote.xml");
    assert_eq!(quotation.groups[0].item_key, "서버 1");
    assert_eq!(quotation.groups[0].sheet_name, "서버 1");
    assert_eq!(quotation.groups[0].amount().to_string(), "1000.5");
}
