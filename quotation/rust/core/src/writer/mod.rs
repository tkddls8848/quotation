//! IBM 견적서 워크북 생성. 파이썬 `quotation/core/writer/ibm_writer.py`.
//!
//! 템플릿을 열어 TOTAL 시트를 채우고, 장비군마다 `template` 시트를 복제해
//! 상세 시트를 만든다. 값을 다 쓴 뒤 장식하고, 마지막에 병합한다 — 이 순서를
//! 지켜야 골든과 같아진다.
//!
//! 저장 뒤에는 템플릿의 그림·도형을 TOTAL 시트로 옮긴다
//! ([결정 0005](../../../doc/decisions/0005-accept-meaningful-xlsx-parity.md)).

mod decorate;
mod drawings;
mod restore;

use std::io::Cursor;

use rust_decimal::prelude::ToPrimitive;
use umya_spreadsheet::{
    Alignment, Font, HorizontalAlignmentValues, NumberingFormat, VerticalAlignmentValues, Workbook,
    Worksheet,
};

use crate::models::{Group, LineItem, Quotation, SubLineItem};
use crate::money::{self, Amount, Decimal};
use decorate::{Layout, decorate};

pub const SHEET_TOTAL: &str = "TOTAL";
pub const SHEET_TEMPLATE: &str = "template";

const FIRST_DATA_ROW: u32 = 8;
const TRAILER_ROWS: u32 = 2;

// --- 라벨 (공백 개수까지 원본과 동일해야 한다) ----------------------------------
const LBL_SUBTOTAL: &str = "합                   계";
const LBL_HW_TOTAL: &str = "합                   계(HardWare)";
const LBL_SW_TOTAL: &str = "합                   계(SoftWare)";
const LBL_GRAND: &str = "총        합       계";
const LBL_SUPPLY: &str = "공        급       가";
const LBL_HW: &str = "H/W";
const LBL_SW: &str = "S/W";

// --- 서식 --------------------------------------------------------------------
const FMT_TEXT: &str = "@";
const FMT_TOTAL_NUM: &str = "#,##0_);[Red]\\(#,##0\\)";
const FMT_DETAIL_NUM: &str = "_-* #,##0_-;\\-* #,##0_-;_-* \"-\"_-;_-@_-";

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

// --- 셀 쓰기 도구 --------------------------------------------------------------

/// 파이썬 `Alignment(...)` 조합 가운데 writer 가 쓰는 것들.
#[derive(Clone, Copy)]
enum Align {
    Left,
    Center,
    CenterWrap,
}

fn font(name: &str, size: f64, bold: bool) -> Font {
    let mut font = Font::default();
    font.set_name(name);
    font.set_size(size);
    font.set_bold(bold);
    font
}

fn font_data() -> Font {
    font("Tahoma", 9.0, false)
}

fn font_data_bold() -> Font {
    font("Tahoma", 9.0, true)
}

fn font_label() -> Font {
    font("돋움", 9.0, true)
}

/// 원본 EXE 문자열의 `Tahoma` / `HY헤드라인M` 이 이 두 셀을 가리킨다.
/// 템플릿은 정반대이므로 반드시 덮어써야 한다.
fn font_title() -> Font {
    font("Tahoma", 18.0, true)
}

fn font_date() -> Font {
    font("HY헤드라인M", 9.0, false)
}

fn apply_style(
    sheet: &mut Worksheet,
    coordinate: &str,
    format: Option<&str>,
    align: Option<Align>,
    font: Font,
) {
    let style = sheet.cell_mut(coordinate).style_mut();
    style.set_font(font);
    if let Some(code) = format {
        let mut numbering = NumberingFormat::default();
        numbering.set_format_code(code);
        style.set_number_format(numbering);
    }
    if let Some(align) = align {
        let mut alignment = Alignment::default();
        match align {
            Align::Left => {
                alignment.set_horizontal(HorizontalAlignmentValues::Left);
            }
            Align::Center => {
                alignment.set_horizontal(HorizontalAlignmentValues::Center);
                alignment.set_vertical(VerticalAlignmentValues::Center);
            }
            Align::CenterWrap => {
                alignment.set_horizontal(HorizontalAlignmentValues::Center);
                alignment.set_vertical(VerticalAlignmentValues::Center);
                alignment.set_wrap_text(true);
            }
        }
        style.set_alignment(alignment);
    }
}

/// XML 에서 온 문자열을 Excel 수식이 아닌 일반 텍스트로 기록한다.
///
/// 품번·설명·장비 이름은 신뢰할 수 없는 입력이므로 값의 생김새와 관계없이
/// 문자열 셀로 고정한다. 내부에서 만드는 합계 수식은 [`put_formula`] 를 쓴다.
fn put_xml_text(
    sheet: &mut Worksheet,
    coordinate: &str,
    value: &str,
    format: Option<&str>,
    align: Option<Align>,
    font: Font,
) {
    sheet.cell_mut(coordinate).set_value_string(value);
    apply_style(sheet, coordinate, format, align, font);
}

/// 우리가 만든 라벨. XML 에서 오지 않는다.
fn put_label(
    sheet: &mut Worksheet,
    coordinate: &str,
    value: &str,
    format: Option<&str>,
    align: Option<Align>,
    font: Font,
) {
    sheet.cell_mut(coordinate).set_value_string(value);
    apply_style(sheet, coordinate, format, align, font);
}

fn put_number(
    sheet: &mut Worksheet,
    coordinate: &str,
    value: f64,
    format: Option<&str>,
    font: Font,
) {
    sheet.cell_mut(coordinate).set_value_number(value);
    apply_style(sheet, coordinate, format, None, font);
}

fn put_formula(
    sheet: &mut Worksheet,
    coordinate: &str,
    formula: &str,
    format: Option<&str>,
    font: Font,
) {
    sheet
        .cell_mut(coordinate)
        .set_formula(formula.trim_start_matches('='));
    apply_style(sheet, coordinate, format, None, font);
}

/// `Decimal` -> Excel 수치. 정수는 정수로 써야 골든과 일치한다.
fn number(value: Decimal) -> f64 {
    value.to_f64().unwrap_or(0.0)
}

fn amount_cell(sheet: &mut Worksheet, coordinate: &str, amount: &Amount, format: &str) {
    match amount {
        Amount::NoCharge => put_label(sheet, coordinate, "N/C", Some(format), None, font_data()),
        Amount::Priced(value) => {
            put_number(sheet, coordinate, number(*value), Some(format), font_data())
        }
        Amount::Missing => {}
    }
}

fn merge(pending: &mut Vec<String>, col: &str, top: u32, bottom: u32) {
    if bottom > top {
        pending.push(format!("{col}{top}:{col}{bottom}"));
    }
}

fn merge_across(pending: &mut Vec<String>, left: &str, right: &str, row: u32) {
    pending.push(format!("{left}{row}:{right}{row}"));
}

// --- TOTAL 시트 ---------------------------------------------------------------

/// B2 의 `Trialinfo-YY-` 번호에서 연도만 갱신한다.
fn update_quote_number(sheet: &mut Worksheet, today: Date) -> Result<()> {
    let current = sheet
        .cell("B2")
        .map(|cell| cell.value().to_string())
        .ok_or_else(|| WriteError::new("템플릿 TOTAL 시트에 B2 가 없습니다."))?;
    let prefix = current.split("Trialinfo-").next().unwrap_or("").to_owned();
    sheet
        .cell_mut("B2")
        .set_value_string(format!("{prefix}Trialinfo-{}-", today.short_year()));
    Ok(())
}

fn write_total_sheet(
    sheet: &mut Worksheet,
    quote: &Quotation,
    today: Date,
) -> Result<(Vec<String>, Layout)> {
    let mut merges: Vec<String> = Vec::new();
    let mut layout = Layout::new(FIRST_DATA_ROW);

    update_quote_number(sheet, today)?;
    put_label(
        sheet,
        "C3",
        &today.iso(),
        Some(FMT_TEXT),
        Some(Align::Left),
        font_date(),
    );

    let mut row = FIRST_DATA_ROW;
    let mut subtotal_rows: Vec<u32> = Vec::new();

    for group in &quote.groups {
        let group_start = row;

        for (kind, items) in group.sections() {
            let section_start = row;
            for item in &items {
                put_xml_text(
                    sheet,
                    &format!("C{row}"),
                    &item.part_number,
                    Some(FMT_TEXT),
                    None,
                    font_data(),
                );
                put_xml_text(
                    sheet,
                    &format!("D{row}"),
                    &item.description,
                    None,
                    None,
                    font_data(),
                );
                put_number(
                    sheet,
                    &format!("E{row}"),
                    item.quantity as f64,
                    None,
                    font_data(),
                );
                if kind != crate::models::HARDWARE {
                    layout.blue_rows.push(row);
                }
                row += 1;
            }
            let section_end = row - 1;

            let amount = items
                .iter()
                .fold(Decimal::ZERO, |total, item| total + item.amount());
            if !amount.is_zero() {
                put_formula(
                    sheet,
                    &format!("F{section_start}"),
                    &format!("=G{section_start}/E{section_start}"),
                    Some(FMT_TOTAL_NUM),
                    font_data(),
                );
                put_number(
                    sheet,
                    &format!("G{section_start}"),
                    number(amount),
                    Some(FMT_TOTAL_NUM),
                    font_data(),
                );
            }
            merge(&mut merges, "F", section_start, section_end);
            merge(&mut merges, "G", section_start, section_end);
        }

        let group_end = row - 1;
        merge(&mut merges, "H", group_start, group_end);

        put_label(
            sheet,
            &format!("C{row}"),
            LBL_SUBTOTAL,
            Some(FMT_TEXT),
            None,
            font_label(),
        );
        merge_across(&mut merges, "C", "F", row);
        put_formula(
            sheet,
            &format!("G{row}"),
            &format!("=SUM(G{group_start}:G{group_end})"),
            Some(FMT_TOTAL_NUM),
            font_data_bold(),
        );
        subtotal_rows.push(row);
        layout.cf_rows.push(row);
        layout.cyan_rows.push(row);

        put_xml_text(
            sheet,
            &format!("B{group_start}"),
            &group.item_key,
            None,
            Some(Align::CenterWrap),
            font_data_bold(),
        );
        merge(&mut merges, "B", group_start, row);
        layout.bands.push((group_start, row));
        row += 1;
    }

    write_footer(
        sheet,
        row,
        &subtotal_rows,
        FMT_TOTAL_NUM,
        &mut merges,
        &mut layout,
        true,
    );
    Ok((merges, layout))
}

// --- 상세 시트 ----------------------------------------------------------------

fn write_detail_sheet(sheet: &mut Worksheet, group: &Group, today: Date) -> (Vec<String>, Layout) {
    let mut merges: Vec<String> = Vec::new();
    let mut layout = Layout::new(FIRST_DATA_ROW);
    layout.fix_header_bottom = true;
    layout.blue_includes_label = true;
    layout.top_black = true;

    // 시트명은 Excel 금칙 문자를 걷어 낸 이름이다. 제목에는 사람이 붙인
    // 이름을 그대로 적는다 (`메일/스펨_1식`). UNIX 모드는 둘이 같다.
    let title = if group.title.is_empty() {
        &group.sheet_name
    } else {
        &group.title
    };
    put_xml_text(
        sheet,
        "C1",
        &format!("({title})"),
        Some(FMT_TEXT),
        Some(Align::CenterWrap),
        font_title(),
    );
    put_label(
        sheet,
        "C3",
        &today.iso(),
        Some(FMT_TEXT),
        Some(Align::Left),
        font_date(),
    );

    let mut row = FIRST_DATA_ROW;
    let mut section_total_rows: Vec<u32> = Vec::new();

    for (kind, items) in group.sections() {
        let section_start = row;
        let is_hw = kind == crate::models::HARDWARE;
        // 블록별 합계행은 H/W 구간에 라인이 둘 이상일 때만 쓴다.
        // 하나뿐이면 바로 합계(HardWare) 로 가고 수식도 범위형이다.
        // S/W 는 개수와 무관하게 언제나 범위형 하나다.
        let per_block = is_hw && items.len() > 1;
        let mut block_rows: Vec<u32> = Vec::new();

        for item in &items {
            let block_start = row;
            row = write_item_block(sheet, item, row, is_hw, &mut layout);
            if per_block {
                // 서브라인이 없으면 스페이서 1행을 둔다
                let last = (row - 1).max(block_start + 1);
                if last >= row {
                    layout.spacer_rows.extend(row..=last);
                }
                row = last + 1;
                put_label(
                    sheet,
                    &format!("C{row}"),
                    LBL_SUBTOTAL,
                    Some(FMT_TEXT),
                    None,
                    font_label(),
                );
                merge_across(&mut merges, "C", "F", row);
                put_formula(
                    sheet,
                    &format!("G{row}"),
                    &format!("=SUM(G{block_start}:G{last})"),
                    Some(FMT_DETAIL_NUM),
                    font_data(),
                );
                block_rows.push(row);
                layout.cf_rows.push(row);
                layout.yellow_rows.push(row);
                row += 1;
            }
        }

        put_label(
            sheet,
            &format!("C{row}"),
            if is_hw { LBL_HW_TOTAL } else { LBL_SW_TOTAL },
            Some(FMT_TEXT),
            None,
            font_label(),
        );
        merge_across(&mut merges, "C", "F", row);
        let formula = if per_block {
            let parts: Vec<String> = block_rows.iter().map(|r| format!("G{r}")).collect();
            format!("=SUM({})", parts.join(","))
        } else {
            format!("=SUM(G{section_start}:G{})", row - 1)
        };
        put_formula(
            sheet,
            &format!("G{row}"),
            &formula,
            Some(FMT_DETAIL_NUM),
            font_data(),
        );
        section_total_rows.push(row);
        layout.cf_rows.push(row);
        layout.cyan_rows.push(row);

        put_label(
            sheet,
            &format!("B{section_start}"),
            if is_hw { LBL_HW } else { LBL_SW },
            None,
            Some(Align::Center),
            font_data_bold(),
        );
        merge(&mut merges, "B", section_start, row);
        layout.bands.push((section_start, row));
        layout.yellow_labels.push(section_start);
        if !is_hw {
            layout.blue_rows.extend(section_start..=row);
        }
        row += 1;
    }

    write_footer(
        sheet,
        row,
        &section_total_rows,
        FMT_DETAIL_NUM,
        &mut merges,
        &mut layout,
        false,
    );
    (merges, layout)
}

/// ProductLineItem 1건과 그 서브라인을 기록한다.
fn write_item_block(
    sheet: &mut Worksheet,
    item: &LineItem,
    row: u32,
    is_hw: bool,
    layout: &mut Layout,
) -> u32 {
    let base = row;
    let mut row = row;
    put_xml_text(
        sheet,
        &format!("C{row}"),
        &item.part_number,
        Some(FMT_TEXT),
        None,
        font_data(),
    );
    put_xml_text(
        sheet,
        &format!("D{row}"),
        &item.description,
        None,
        None,
        font_data(),
    );
    put_number(
        sheet,
        &format!("E{row}"),
        item.quantity as f64,
        None,
        font_data(),
    );
    amount_cell(sheet, &format!("F{row}"), &item.unit_price, FMT_DETAIL_NUM);
    write_g(sheet, row, &item.unit_price);
    row += 1;

    for sub in &item.subs {
        put_xml_text(
            sheet,
            &format!("C{row}"),
            &sub.part_number,
            Some(FMT_TEXT),
            None,
            font_data(),
        );
        put_xml_text(
            sheet,
            &format!("D{row}"),
            &sub.description,
            None,
            None,
            font_data(),
        );
        match sub_quantity(sub, base, item, is_hw) {
            SubQuantity::Number(value) => {
                put_number(sheet, &format!("E{row}"), value as f64, None, font_data())
            }
            SubQuantity::Formula(formula) => {
                put_formula(sheet, &format!("E{row}"), &formula, None, font_data())
            }
        }
        amount_cell(sheet, &format!("F{row}"), &sub.unit_price, FMT_DETAIL_NUM);
        write_g(sheet, row, &sub.unit_price);
        if sub.is_removal() {
            layout.red_rows.push(row);
        }
        row += 1;
    }

    row
}

enum SubQuantity {
    Number(i64),
    Formula(String),
}

/// 서브라인 수량 셀. 골든이 세 형태를 쓴다 (SPEC_CELLMAP.md §4.5).
///
/// ```text
/// H/W + 기준행에 가격 있음 -> "=8*E8"   부모 수량 상대 참조
/// H/W + 기준행이 N/C       -> "=1"      참조 없는 수식
/// S/W                      -> 1         상수
/// ```
///
/// 제거(REMOVE) 부품은 부호를 뒤집는다. XML 의 수량은 양수로 들어온다.
fn sub_quantity(sub: &SubLineItem, base: u32, item: &LineItem, is_hw: bool) -> SubQuantity {
    let quantity = if sub.is_removal() {
        -sub.quantity
    } else {
        sub.quantity
    };
    if !is_hw {
        return SubQuantity::Number(quantity);
    }
    if money::is_priced(&item.unit_price) {
        SubQuantity::Formula(format!("={quantity}*E{base}"))
    } else {
        SubQuantity::Formula(format!("={quantity}"))
    }
}

fn write_g(sheet: &mut Worksheet, row: u32, price: &Amount) {
    match price {
        Amount::NoCharge => put_label(
            sheet,
            &format!("G{row}"),
            "N/C",
            Some(FMT_DETAIL_NUM),
            None,
            font_data(),
        ),
        Amount::Priced(_) => put_formula(
            sheet,
            &format!("G{row}"),
            &format!("=E{row}*F{row}"),
            Some(FMT_DETAIL_NUM),
            font_data(),
        ),
        Amount::Missing => {}
    }
}

// --- 공통 꼬리말 --------------------------------------------------------------

/// 총합계 / 공급가 / 하단 비고 병합 + 인쇄 영역.
///
/// 합계가 하나뿐일 때 TOTAL 시트는 `=SUM(G13)` 을, 상세 시트는 `=G10` 을 쓴다.
fn write_footer(
    sheet: &mut Worksheet,
    row: u32,
    subtotal_rows: &[u32],
    format: &str,
    merges: &mut Vec<String>,
    layout: &mut Layout,
    always_sum: bool,
) {
    let mut row = row;
    put_label(
        sheet,
        &format!("B{row}"),
        LBL_GRAND,
        None,
        Some(Align::Center),
        font_label(),
    );
    merge_across(merges, "B", "F", row);
    let formula = if subtotal_rows.len() == 1 && !always_sum {
        format!("=G{}", subtotal_rows[0])
    } else {
        let parts: Vec<String> = subtotal_rows.iter().map(|r| format!("G{r}")).collect();
        format!("=SUM({})", parts.join(","))
    };
    put_formula(
        sheet,
        &format!("G{row}"),
        &formula,
        Some(format),
        font_data_bold(),
    );
    layout.grand_row = row;
    layout.bf_rows.push(row);
    row += 1;

    // 공급가는 언제나 공란이다 (골든 전부 그러하다). 수기로 적는 칸이다.
    put_label(
        sheet,
        &format!("B{row}"),
        LBL_SUPPLY,
        None,
        Some(Align::Center),
        font_label(),
    );
    merge_across(merges, "B", "F", row);
    layout.supply_row = row;
    layout.bf_rows.push(row);
    row += 1;

    merges.push(format!("B{row}:H{}", row + TRAILER_ROWS - 1));
    set_print_area(sheet, row + TRAILER_ROWS - 1);
}

fn set_print_area(sheet: &mut Worksheet, last_row: u32) {
    let name = sheet.name().to_owned();
    let mut defined = umya_spreadsheet::DefinedName::default();
    defined.set_name("_xlnm.Print_Area");
    defined.set_address(format!("{name}!$A$1:$H${last_row}"));
    sheet.set_defined_names(vec![defined]);
}

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
