//! Cell values, styles, labels and merge ranges.
use crate::money::{Amount, Decimal};
use rust_decimal::prelude::ToPrimitive;
use umya_spreadsheet::{
    Alignment, Font, HorizontalAlignmentValues, NumberingFormat, VerticalAlignmentValues, Worksheet,
};

pub(super) const LBL_SUBTOTAL: &str = "합                   계";
pub(super) const LBL_HW_TOTAL: &str = "합                   계(HardWare)";
pub(super) const LBL_SW_TOTAL: &str = "합                   계(SoftWare)";
pub(super) const LBL_GRAND: &str = "총        합       계";
pub(super) const LBL_SUPPLY: &str = "공        급       가";
pub(super) const LBL_HW: &str = "H/W";
pub(super) const LBL_SW: &str = "S/W";

// --- 서식 --------------------------------------------------------------------
pub(super) const FMT_TEXT: &str = "@";
pub(super) const FMT_TOTAL_NUM: &str = "#,##0_);[Red]\\(#,##0\\)";
pub(super) const FMT_DETAIL_NUM: &str = "_-* #,##0_-;\\-* #,##0_-;_-* \"-\"_-;_-@_-";

/// 파이썬 `Alignment(...)` 조합 가운데 writer 가 쓰는 것들.
#[derive(Clone, Copy)]
pub(super) enum Align {
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

pub(super) fn font_data() -> Font {
    font("Tahoma", 9.0, false)
}

pub(super) fn font_data_bold() -> Font {
    font("Tahoma", 9.0, true)
}

pub(super) fn font_label() -> Font {
    font("돋움", 9.0, true)
}

/// 원본 EXE 문자열의 `Tahoma` / `HY헤드라인M` 이 이 두 셀을 가리킨다.
/// 템플릿은 정반대이므로 반드시 덮어써야 한다.
pub(super) fn font_title() -> Font {
    font("Tahoma", 18.0, true)
}

pub(super) fn font_date() -> Font {
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
pub(super) fn put_xml_text(
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
pub(super) fn put_label(
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

pub(super) fn put_number(
    sheet: &mut Worksheet,
    coordinate: &str,
    value: f64,
    format: Option<&str>,
    font: Font,
) {
    sheet.cell_mut(coordinate).set_value_number(value);
    apply_style(sheet, coordinate, format, None, font);
}

pub(super) fn put_formula(
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
pub(super) fn number(value: Decimal) -> f64 {
    value.to_f64().unwrap_or(0.0)
}

pub(super) fn amount_cell(sheet: &mut Worksheet, coordinate: &str, amount: &Amount, format: &str) {
    match amount {
        Amount::NoCharge => put_label(sheet, coordinate, "N/C", Some(format), None, font_data()),
        Amount::Priced(value) => {
            put_number(sheet, coordinate, number(*value), Some(format), font_data())
        }
        Amount::Missing => {}
    }
}

pub(super) fn merge(pending: &mut Vec<String>, col: &str, top: u32, bottom: u32) {
    if bottom > top {
        pending.push(format!("{col}{top}:{col}{bottom}"));
    }
}

pub(super) fn merge_across(pending: &mut Vec<String>, left: &str, right: &str, row: u32) {
    pending.push(format!("{left}{row}:{right}{row}"));
}
