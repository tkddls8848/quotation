//! Phase 4 — 견적서 작성의 이식 검증.
//!
//! 셀 하나하나의 대조는 `tools/rust_parity_workbook.py` 가 파이썬 산출물과
//! 직접 비교한다. 여기서는 그 대조가 돌지 않는 자리에서도 무너지지 않도록
//! 뼈대(시트 구성·도형 보존·재현성)만 붙잡아 둔다.

use std::io::{Cursor, Read};
use std::path::PathBuf;

use quotation_core::writer::{self, Date};
use quotation_core::xml_reader;

const TODAY: Date = Date {
    year: 2026,
    month: 8,
    day: 27,
};

fn repository(parts: &[&str]) -> PathBuf {
    let mut path = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    path.push("..");
    path.push("..");
    path.extend(parts);
    path
}

fn template() -> Vec<u8> {
    let path = repository(&["quotation", "resources", "견적서_template_IBM.xlsx"]);
    std::fs::read(&path).unwrap_or_else(|error| panic!("템플릿 {path:?}: {error}"))
}

fn fixture(name: &str) -> Vec<u8> {
    let path = repository(&["tests", "fixtures", "public", name]);
    std::fs::read(&path).unwrap_or_else(|error| panic!("fixture {path:?}: {error}"))
}

fn build(name: &str) -> Vec<u8> {
    let quotation = xml_reader::parse_bytes(&fixture(name), None).expect("읽혀야 한다");
    writer::build_bytes(&quotation, &template(), TODAY).expect("만들어져야 한다")
}

fn part(book: &[u8], name: &str) -> Option<Vec<u8>> {
    let mut archive = zip::ZipArchive::new(Cursor::new(book)).ok()?;
    let mut body = Vec::new();
    archive.by_name(name).ok()?.read_to_end(&mut body).ok()?;
    Some(body)
}

fn names(book: &[u8]) -> Vec<String> {
    let archive = zip::ZipArchive::new(Cursor::new(book)).expect("xlsx");
    archive.file_names().map(str::to_owned).collect()
}

#[test]
fn writes_a_sheet_for_every_group_and_hides_the_template() {
    let book = build("new_quote.xml");
    let workbook =
        String::from_utf8_lossy(&part(&book, "xl/workbook.xml").expect("workbook")).into_owned();
    // 차례는 TOTAL, 상세…, template 이고 template 만 숨긴다.
    let order: Vec<&str> = workbook.match_indices("<sheet ").map(|(_, s)| s).collect();
    assert_eq!(order.len(), 4, "{workbook}");
    assert!(workbook.contains(r#"<sheet name="TOTAL""#));
    assert!(workbook.contains(r#"<sheet name="SAMPLE-100 #1""#));
    assert!(workbook.contains(r#"<sheet name="SAMPLE-200 #2""#));
    assert!(
        workbook.contains(r#"name="template" sheetId="4" r:id="rId4" state="hidden""#),
        "{workbook}"
    );
}

#[test]
fn keeps_the_first_page_drawing_byte_for_byte() {
    // 결정 0005 의 두 번째 조건. 로고와 머리글 도형은 템플릿 원본 그대로다.
    let book = build("new_quote.xml");
    let template = template();
    for part_name in ["xl/drawings/drawing1.xml", "xl/media/image1.png"] {
        assert_eq!(
            part(&book, part_name),
            part(&template, part_name),
            "{part_name}"
        );
    }
    // 숨긴 template 시트의 그림은 따라오지 않는다 (openpyxl 도 버린다).
    assert!(!names(&book).contains(&"xl/drawings/drawing2.xml".to_owned()));
}

#[test]
fn puts_the_drawing_reference_on_the_first_sheet_only() {
    let book = build("new_quote.xml");
    let first = String::from_utf8_lossy(&part(&book, "xl/worksheets/sheet1.xml").expect("sheet1"))
        .into_owned();
    assert!(first.contains("<drawing r:id="), "TOTAL 시트에 그림이 없다");
    for other in ["xl/worksheets/sheet2.xml", "xl/worksheets/sheet4.xml"] {
        let body = String::from_utf8_lossy(&part(&book, other).expect(other)).into_owned();
        assert!(!body.contains("<drawing r:id="), "{other} 에 그림이 붙었다");
    }
}

#[test]
fn writes_the_same_content_for_the_same_input() {
    // 날짜를 고정하면 내용이 재현된다. 대조가 성립하는 전제다.
    //
    // 파일 전체 바이트는 같지 않다 (결정 0011). zip 은 부품마다 수정 시각을
    // 담고, `xl/styles.xml` 의 numFmt 나열 순서는 실행마다 달라진다 — 둘 다
    // 견적서 내용이 아니다.
    let first = build("upgrade_quote.xml");
    let second = build("upgrade_quote.xml");
    for name in [
        "xl/worksheets/sheet1.xml",
        "xl/worksheets/sheet2.xml",
        "xl/sharedStrings.xml",
    ] {
        assert_eq!(part(&first, name), part(&second, name), "{name}");
    }
}

#[test]
fn reads_every_public_fixture_end_to_end() {
    for name in [
        "euckr_quote.xml",
        "integrated_quote.xml",
        "integrated_summary_quote.xml",
        "new_quote.xml",
        "no_charge.xml",
        "upgrade_quote.xml",
    ] {
        let book = build(name);
        assert!(book.len() > 10_000, "{name} 산출물이 너무 작다");
        assert!(part(&book, "xl/worksheets/sheet1.xml").is_some(), "{name}");
    }
}

#[test]
fn dates_follow_python_formatting() {
    assert_eq!(TODAY.iso(), "2026-08-27");
    assert_eq!(TODAY.short_year(), "26");
    let old = Date {
        year: 2007,
        month: 1,
        day: 5,
    };
    assert_eq!(old.iso(), "2007-01-05");
    assert_eq!(old.short_year(), "07");
}
