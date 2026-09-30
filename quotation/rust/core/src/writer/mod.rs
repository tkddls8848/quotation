//! Workbook orchestration. See README.md here for the module map.

mod cells;
mod decorate;
mod detail;
mod drawings;
mod footer;
mod restore;
mod total;

use crate::models::Quotation;
use decorate::{Layout, decorate};
use detail::write_detail_sheet;
use std::io::Cursor;
use total::write_total_sheet;
use umya_spreadsheet::{Font, Workbook, Worksheet};

pub const SHEET_TOTAL: &str = "TOTAL";
pub const SHEET_TEMPLATE: &str = "template";
const FIRST_DATA_ROW: u32 = 8;
const TRAILER_ROWS: u32 = 2;

/// 견적서에 적는 날짜. 달력 계산이 필요 없으므로 값만 받는다.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Date {
    pub year: i32,
    pub month: u32,
    pub day: u32,
}

impl Date {
    /// 파이썬 `date.isoformat()`.
    pub fn iso(&self) -> String {
        format!("{:04}-{:02}-{:02}", self.year, self.month, self.day)
    }

    /// 파이썬 `f"{date:%y}"`.
    pub fn short_year(&self) -> String {
        format!("{:02}", self.year.rem_euclid(100))
    }
}

#[derive(Debug)]
pub struct WriteError {
    pub message: String,
}

impl std::fmt::Display for WriteError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(&self.message)
    }
}

impl std::error::Error for WriteError {}

impl WriteError {
    fn new(message: impl Into<String>) -> Self {
        Self {
            message: message.into(),
        }
    }
}

type Result<T> = std::result::Result<T, WriteError>;

/// 장식 후 병합. 순서를 지켜야 골든과 같아진다.
fn finish(sheet: &mut Worksheet, merges: Vec<String>, layout: Layout, default_font: &Font) {
    decorate(sheet, &layout, default_font);
    for reference in merges {
        sheet.add_merge_cells(reference);
    }
}

// --- 진입점 ------------------------------------------------------------------

/// 템플릿 바이트 -> 완성된 견적서 `.xlsx` 바이트. 파일시스템을 쓰지 않는다.
pub fn build_bytes(quote: &Quotation, template: &[u8], today: Date) -> Result<Vec<u8>> {
    let mut book: Workbook =
        umya_spreadsheet::reader::xlsx::read_reader(Cursor::new(template), true)
            .map_err(|error| WriteError::new(format!("템플릿을 열 수 없습니다: {error}")))?;

    let default_font = template_default_font(template).unwrap_or_default();

    // umya 가 읽다가 잃어버린 테두리 색을 되돌린다. 상세 시트는 template 을
    // 복제해 만들므로, 복제 전에 되돌려야 그쪽에도 함께 실린다.
    restore::border_colors(&mut book, template, &[SHEET_TOTAL, SHEET_TEMPLATE]);

    // 템플릿의 H7('DESCRIPTION') 을 지우고 H6:H7 을 병합한다. 복제 전에 해야
    // 상세 시트와 잔존 template 시트가 모두 골든과 같아진다.
    {
        let template_sheet = sheet_by_name(&mut book, SHEET_TEMPLATE)?;
        template_sheet.cell_mut("H7").set_blank();
        template_sheet.add_merge_cells("H6:H7");
    }

    {
        let total = sheet_by_name(&mut book, SHEET_TOTAL)?;
        let (merges, layout) = write_total_sheet(total, quote, today)?;
        finish(total, merges, layout, &default_font);
    }

    for group in &quote.groups {
        let mut sheet = sheet_by_name(&mut book, SHEET_TEMPLATE)?.clone();
        sheet.set_name(&group.sheet_name);
        let (merges, layout) = write_detail_sheet(&mut sheet, group, today);
        finish(&mut sheet, merges, layout, &default_font);
        book.add_sheet(sheet)
            .map_err(|error| WriteError::new(format!("시트를 더할 수 없습니다: {error}")))?;
    }

    sheet_by_name(&mut book, SHEET_TEMPLATE)?.set_state(umya_spreadsheet::SheetStateValues::Hidden);

    // 템플릿 파일의 차례는 [TOTAL, template] 이고 상세 시트는 뒤에 붙는다.
    // 골든의 차례는 [TOTAL, 상세..., template] 이므로 template 을 끝으로 민다.
    let sheets = book.sheet_collection_mut();
    if sheets.len() > 2 {
        sheets[1..].rotate_left(1);
    }

    // 시트에 딸린 이름(인쇄 영역·인쇄 제목)은 시트 차례를 가리킨다. 차례를
    // 바꿨으니 다시 매긴다 — 빠지면 Excel 이 그 이름을 전역으로 읽는다.
    for (index, sheet) in book.sheet_collection_mut().iter_mut().enumerate() {
        for defined in sheet.defined_names_mut() {
            defined.set_local_sheet_id(index as u32);
        }
    }

    let mut saved = Cursor::new(Vec::new());
    umya_spreadsheet::writer::xlsx::write_writer(&book, &mut saved)
        .map_err(|error| WriteError::new(format!("워크북을 저장할 수 없습니다: {error}")))?;
    let saved = saved.into_inner();

    // 템플릿의 로고와 머리글 도형을 TOTAL 시트로 되돌린다.
    Ok(drawings::carry_over_bytes(template, &saved, SHEET_TOTAL).unwrap_or(saved))
}

/// 템플릿 `styles.xml` 의 첫 글꼴 — 새로 만든 셀이 물려받는 기본 글꼴이다.
///
/// openpyxl 은 새 셀에 통합 문서 기본 글꼴을 준다. umya 는 글꼴을 지정하지
/// 않은 셀에 **글꼴표 0번**을 주는데, 그 0번은 우리가 처음 쓴 글꼴이 되어
/// 버린다. 그래서 템플릿의 기본 글꼴을 읽어 직접 채운다.
fn template_default_font(template: &[u8]) -> Option<Font> {
    let mut archive = zip::ZipArchive::new(Cursor::new(template)).ok()?;
    let mut styles = String::new();
    {
        use std::io::Read;
        archive
            .by_name("xl/styles.xml")
            .ok()?
            .read_to_string(&mut styles)
            .ok()?;
    }
    let start = styles.find("<font>")? + "<font>".len();
    let end = styles[start..].find("</font>")? + start;
    let first = &styles[start..end];
    let mut font = Font::default();
    if let Some(name) = attribute(first, "name", "val") {
        font.set_name(name);
    }
    if let Some(size) = attribute(first, "sz", "val").and_then(|v| v.parse::<f64>().ok()) {
        font.set_size(size);
    }
    font.set_bold(first.contains("<b/>") || first.contains("<b "));
    Some(font)
}

/// `<이름 속성="값"/>` 에서 값을 꺼낸다.
fn attribute(xml: &str, tag: &str, name: &str) -> Option<String> {
    let start = xml.find(&format!("<{tag} "))?;
    let rest = &xml[start..];
    let end = rest.find("/>")?;
    let piece = &rest[..end];
    let needle = format!("{name}=\"");
    let value_start = piece.find(&needle)? + needle.len();
    let value_end = piece[value_start..].find('"')? + value_start;
    Some(piece[value_start..value_end].to_owned())
}

fn sheet_by_name<'a>(book: &'a mut Workbook, name: &str) -> Result<&'a mut Worksheet> {
    book.sheet_by_name_mut(name)
        .map_err(|_| WriteError::new(format!("템플릿에 {name} 시트가 없습니다.")))
}
