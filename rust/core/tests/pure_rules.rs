//! Phase 1 순수 규칙의 이식 검증.
//!
//! 기대값은 파이썬 `tests/test_core.py` 와 `quotation/core/` 의 문서 예시에서
//! 그대로 가져왔다. 파이썬 구현이 기준이고, 여기서 다르면 이식이 틀린 것이다.

use quotation_core::modes::{self, Mode};
use quotation_core::money::{self, Amount};
use quotation_core::naming;

fn amount(text: &str) -> Amount {
    money::parse_amount(Some(text)).expect("파싱 가능한 금액")
}

// --- money (SPEC_CELLMAP.md §1.2) --------------------------------------------

#[test]
fn parse_amount_reads_econfig_monetary_amount() {
    assert_eq!(amount("88,971.5").to_string(), "88971.5");
    assert_eq!(amount("796275.83").to_string(), "796275.83");
    assert_eq!(amount("0").to_string(), "0");
    assert_eq!(amount("N/C"), Amount::NoCharge);
    assert_eq!(amount(""), Amount::Missing);
    assert_eq!(money::parse_amount(None).unwrap(), Amount::Missing);
}

#[test]
fn parse_amount_preserves_scale() {
    // 소수 자릿수가 바뀌면 골든 셀 값과 어긋난다.
    assert_eq!(amount("88,971.50").to_string(), "88971.50");
    assert_eq!(amount("309").to_string(), "309");
}

#[test]
fn parse_amount_reads_lenovo_scientific_notation() {
    // 레노버 DCSC 구성기가 실제로 쓰는 표기.
    // `tests/fixtures/public/integrated_quote.xml` 의 MonetaryAmount 값이다.
    assert_eq!(amount("4.0172E7").to_string(), "40172000");
    assert_eq!(amount("4.2812E7").to_string(), "42812000");
    assert_eq!(amount("1.5e-2").to_string(), "0.015");
}

#[test]
fn parse_amount_strips_surrounding_space() {
    assert_eq!(amount("  1,024.00  ").to_string(), "1024.00");
    assert_eq!(amount("   "), Amount::Missing);
}

#[test]
fn parse_amount_rejects_non_numeric_text() {
    assert!(money::parse_amount(Some("n/c")).is_err());
    assert!(money::parse_amount(Some("무상")).is_err());
}

#[test]
fn no_charge_folds_to_zero_in_sums() {
    assert_eq!(money::to_decimal(&Amount::NoCharge).to_string(), "0");
    assert_eq!(money::to_decimal(&Amount::Missing).to_string(), "0");
    assert_eq!(
        money::to_decimal(&amount("88,971.5")).to_string(),
        "88971.5"
    );
}

#[test]
fn is_priced_excludes_no_charge_and_missing() {
    assert!(money::is_priced(&amount("0")));
    assert!(!money::is_priced(&Amount::NoCharge));
    assert!(!money::is_priced(&Amount::Missing));
}

// --- naming (SPEC_CELLMAP.md §2.1) -------------------------------------------

#[test]
fn item_key_and_sheet_name_follow_golden_quotations() {
    let cases = [
        (
            "4680-3P4 #1:IBM Storage FlashSystem 5045 SFF Control Enclosure",
            "4680-3P4 #1",
            "4680-3P4 #1",
        ),
        ("Server 1:Server 1:9080 Model HEX", "Server 1", "SERVER 1"),
        (
            "IBM Expert Labs Project Unit for IBM Power Systems",
            "Expert Labs Project Unit fo",
            "EXPERT LABS PROJECT UNIT FO",
        ),
    ];
    for (description, key, sheet) in cases {
        assert_eq!(naming::item_key(description), key);
        assert_eq!(naming::sheet_name(&naming::item_key(description)), sheet);
    }
}

#[test]
fn item_key_removes_prefix_after_truncation() {
    let key = naming::item_key("IBM Expert Labs Project Unit for IBM Power Systems");
    assert_eq!(key.chars().count(), 27);
}

#[test]
fn item_key_counts_characters_not_bytes() {
    // 31자 제한은 글자 수다. 한글을 바이트로 자르면 32자가 넘어간다.
    let description = "가".repeat(40);
    assert_eq!(naming::item_key(&description).chars().count(), 31);
}

#[test]
fn product_key_prefers_configurator_product_name() {
    assert_eq!(
        naming::product_key("백업서버_1식", "ThinkSystem SR650 V4-3yr Base Warranty"),
        "백업서버_1식"
    );
    assert_eq!(
        naming::product_key("   ", "Server 1:Server 1:9080 Model HEX"),
        "Server 1"
    );
}

#[test]
fn safe_sheet_name_replaces_characters_excel_refuses() {
    assert_eq!(naming::safe_sheet_name("메일/스펨_1식"), "메일-스펨_1식");
    assert_eq!(
        naming::safe_sheet_name(r"a:b\c/d?e*f[g]h"),
        "A-B-C-D-E-F-G-H"
    );
}

#[test]
fn safe_sheet_name_falls_back_when_nothing_usable_remains() {
    assert_eq!(naming::safe_sheet_name("   "), "SHEET");
    assert_eq!(naming::safe_sheet_name("'"), "SHEET");
    assert_eq!(naming::safe_sheet_name("History"), "SHEET");
}

#[test]
fn sheet_names_stay_within_excel_limits() {
    let long = "백".repeat(40);
    assert_eq!(naming::sheet_name(&long).chars().count(), 31);
    assert_eq!(naming::safe_sheet_name(&long).chars().count(), 31);
}

#[test]
fn unique_sheet_names_split_duplicates_in_order() {
    assert_eq!(
        naming::unique_sheet_names(["백업서버", "백업서버", "웹서버", "백업서버"]),
        vec!["백업서버", "백업서버 (2)", "웹서버", "백업서버 (3)"]
    );
}

#[test]
fn unique_sheet_names_keep_suffix_within_limit() {
    let long = "A".repeat(31);
    let split = naming::unique_sheet_names([long.clone(), long.clone()]);
    assert_eq!(split[0], long);
    assert_eq!(split[1].chars().count(), 31);
    assert!(split[1].ends_with(" (2)"));
}

#[test]
fn unique_sheet_names_compare_case_insensitively() {
    // Excel 은 대소문자만 다른 시트명을 같은 이름으로 본다.
    assert_eq!(
        naming::unique_sheet_names(["server 1", "SERVER 1"]),
        vec!["server 1", "SERVER 1 (2)"]
    );
}

// --- modes -------------------------------------------------------------------

#[test]
fn detect_reads_lenovo_documents_as_integrated() {
    assert_eq!(modes::detect(["", "백업서버_1식"]), Mode::Integrated);
    assert_eq!(modes::detect(["", "   "]), Mode::Unix);
    assert_eq!(modes::detect(Vec::<String>::new()), Mode::Unix);
}

#[test]
fn normalize_accepts_known_modes_only() {
    assert_eq!(modes::normalize(" Integrated ").unwrap(), Mode::Integrated);
    assert_eq!(modes::normalize("UNIX").unwrap(), Mode::Unix);
    assert!(modes::normalize("x86").is_err());
}

#[test]
fn resolve_prefers_explicit_mode_over_document() {
    assert_eq!(
        modes::resolve(Some("unix"), ["백업서버_1식"]).unwrap(),
        Mode::Unix
    );
    assert_eq!(
        modes::resolve(Some("  "), ["백업서버_1식"]).unwrap(),
        Mode::Integrated
    );
    assert_eq!(
        modes::resolve(None, ["백업서버_1식"]).unwrap(),
        Mode::Integrated
    );
}

#[test]
fn mode_labels_match_python() {
    assert_eq!(Mode::Unix.as_str(), "unix");
    assert_eq!(Mode::Integrated.as_str(), "integrated");
    assert_eq!(Mode::Unix.label(), "IBM 제품");
    assert_eq!(Mode::Integrated.label(), "통합");
}
