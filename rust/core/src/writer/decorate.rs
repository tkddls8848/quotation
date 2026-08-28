//! 표 장식 — 테두리·채우기·정렬·행높이.
//! 파이썬 `quotation/core/writer/decorate.py`.
//!
//! 원본 VB6 의 `DecorateTOTSheet` 에 해당한다.
//!
//! 병합은 장식이 끝난 뒤에 적용해야 한다. 덮인 셀의 스타일이 버려지는데,
//! 골든도 정확히 그 상태다.

use umya_spreadsheet::{
    Alignment, Border, BorderStyleValues, Color, Fill, HorizontalAlignmentValues, PatternFill,
    PatternValues, VerticalAlignmentValues, Worksheet,
};

/// 색인 64 = 자동(automatic). 골든의 모든 테두리가 이 색을 명시하고 있다.
pub const AUTO_INDEX: u32 = 64;
/// 헤더 아래 굵은 선만 색인 0(검정)을 쓴다.
pub const BLACK_INDEX: u32 = 0;
/// 레거시 팔레트 색인 9 = 흰색.
pub const WHITE_INDEX: u32 = 9;

pub const YELLOW: &str = "FFFFFF99";
pub const CYAN: &str = "FFCCFFFF";
pub const ORANGE: &str = "FFFFCC99";

/// Software 구간은 파란 글꼴이다.
pub const BLUE: &str = "FF0000FF";
/// 제거(REMOVE) 부품은 붉은 글꼴이다.
pub const RED: &str = "FFFF0000";

pub const ROW_H_DATA: f64 = 12.0;
pub const ROW_H_TOTAL: f64 = 20.1;
pub const ROW_H_TRAILER: f64 = 30.0;

pub const COLS: [&str; 7] = ["B", "C", "D", "E", "F", "G", "H"];

/// 어느 쪽 테두리도 없음.
#[derive(Clone, Copy, PartialEq, Eq)]
pub enum Line {
    None,
    Thin,
    Medium,
    MediumBlack,
}

impl Line {
    fn apply(self, border: &mut Border) {
        match self {
            Line::None => {
                border.set_style(BorderStyleValues::None);
            }
            Line::Thin => {
                border.set_style(BorderStyleValues::Thin);
                border.set_color(indexed(AUTO_INDEX));
            }
            Line::Medium => {
                border.set_style(BorderStyleValues::Medium);
                border.set_color(indexed(AUTO_INDEX));
            }
            Line::MediumBlack => {
                border.set_style(BorderStyleValues::Medium);
                border.set_color(indexed(BLACK_INDEX));
            }
        }
    }
}

pub fn indexed(index: u32) -> Color {
    let mut color = Color::default();
    color.set_indexed(index);
    color
}

pub fn argb(value: &str) -> Color {
    let mut color = Color::default();
    color.set_argb_str(value);
    color
}

/// 장식에 필요한 표 구조. writer 가 값을 쓰면서 채운다.
#[derive(Debug, Default)]
pub struct Layout {
    pub first_row: u32,
    /// B열 세로 병합 구간 (시작, 끝)
    pub bands: Vec<(u32, u32)>,
    /// C:F 로 병합되는 행 (합계류)
    pub cf_rows: Vec<u32>,
    /// B:F 로 병합되는 행 (총합계, 공급가)
    pub bf_rows: Vec<u32>,
    /// 노랑 채우기 (C, G, H)
    pub yellow_rows: Vec<u32>,
    /// 하늘 채우기 (C, G, H)
    pub cyan_rows: Vec<u32>,
    /// B열 노랑 채우기 셀의 행
    pub yellow_labels: Vec<u32>,
    /// 파란 글꼴 행
    pub blue_rows: Vec<u32>,
    /// 파란 글꼴을 B열(구간 라벨)까지 적용하는가. 상세 시트만 참.
    pub blue_includes_label: bool,
    /// 제거(REMOVE) 부품 행. 붉은 글꼴로 표시한다.
    pub red_rows: Vec<u32>,
    pub grand_row: u32,
    pub supply_row: u32,
    /// 상세 시트는 헤더 아래 테두리를 medium 으로 다시 그린다 (템플릿은 double)
    pub fix_header_bottom: bool,
    /// 표 첫 행 윗선의 색. TOTAL 은 색인 64, 상세 시트는 색인 0 이다.
    pub top_black: bool,
    /// 서브라인이 없는 블록의 스페이서 행. C열에 배경을 칠하지 않는다.
    pub spacer_rows: Vec<u32>,
}

impl Layout {
    pub fn new(first_row: u32) -> Self {
        Self {
            first_row,
            ..Self::default()
        }
    }
}

/// 열별 가로 정렬. 세로는 전부 가운데다. 줄바꿈은 템플릿 값을 그대로 둔다.
fn horizontal(col: &str) -> HorizontalAlignmentValues {
    match col {
        "C" | "E" => HorizontalAlignmentValues::Center,
        "D" => HorizontalAlignmentValues::Left,
        _ => HorizontalAlignmentValues::Right,
    }
}

/// 가로 방향 테두리 (왼쪽, 오른쪽).
fn side(col: &str, layout: &Layout, row: u32) -> (Line, Line) {
    if layout.bf_rows.contains(&row) {
        // B:F 병합 — 첫 칸은 양쪽, 중간은 없음, 마지막 칸은 오른쪽만
        match col {
            "B" => return (Line::Medium, Line::Thin),
            "C" | "D" | "E" => return (Line::None, Line::None),
            "F" => return (Line::None, Line::Thin),
            _ => {}
        }
    } else if layout.cf_rows.contains(&row) {
        match col {
            "C" => return (Line::Thin, Line::Thin),
            "D" | "E" => return (Line::None, Line::None),
            "F" => return (Line::None, Line::Thin),
            _ => {}
        }
    }
    match col {
        "B" => (Line::Medium, Line::Thin),
        "H" => (Line::Thin, Line::Medium),
        _ => (Line::Thin, Line::Thin),
    }
}

/// 세로 방향 테두리 (위, 아래).
fn vert(col: &str, layout: &Layout, row: u32) -> (Line, Line) {
    let first_top = if layout.top_black {
        Line::MediumBlack
    } else {
        Line::Medium
    };
    let top = if row == layout.first_row {
        first_top
    } else {
        Line::Thin
    };
    let bottom = if row == layout.supply_row {
        Line::Medium
    } else {
        Line::Thin
    };

    if col == "B" {
        for &(start, end) in &layout.bands {
            if start <= row && row <= end {
                if row == start {
                    let top = if start == layout.first_row {
                        first_top
                    } else {
                        Line::Thin
                    };
                    return (top, Line::Thin);
                }
                if row == end {
                    return (Line::None, Line::Thin);
                }
                return (Line::None, Line::None);
            }
        }
    }
    (top, bottom)
}

fn body_fill() -> Fill {
    solid(indexed(WHITE_INDEX))
}

fn solid(foreground: Color) -> Fill {
    let mut pattern = PatternFill::default();
    pattern.set_pattern_type(PatternValues::Solid);
    pattern.set_foreground_color(foreground);
    pattern.set_background_color(indexed(AUTO_INDEX));
    let mut fill = Fill::default();
    fill.set_pattern_fill(pattern);
    fill
}

fn no_fill() -> Fill {
    let mut pattern = PatternFill::default();
    pattern.set_pattern_type(PatternValues::None);
    let mut fill = Fill::default();
    fill.set_pattern_fill(pattern);
    fill
}

/// 셀을 손대기 전에 **없던 셀인지** 알아 두고, 없던 셀이면 기본 모습을 준다.
///
/// umya 는 새 셀을 만들 때 행·열 치수의 스타일을 물려준다. 파이썬(openpyxl)은
/// 통합 문서 기본값을 주므로, 없던 셀은 기본 글꼴과 일반 서식으로 맞춘다.
fn touch(sheet: &mut Worksheet, coordinate: &str, default_font: &umya_spreadsheet::Font) {
    if sheet.cell(coordinate).is_some() {
        return;
    }
    let style = sheet.cell_mut(coordinate).style_mut();
    style.set_font(default_font.clone());
    let mut general = umya_spreadsheet::NumberingFormat::default();
    general.set_format_code(umya_spreadsheet::NumberingFormat::FORMAT_GENERAL);
    style.set_number_format(general);
    // 행·열 치수에서 물려받은 정렬도 지운다. 파이썬의 새 셀은 정렬이 없다.
    style.set_alignment(Alignment::default());
}

/// 표 전체에 테두리·채우기·정렬·행높이를 적용한다.
pub fn decorate(sheet: &mut Worksheet, layout: &Layout, default_font: &umya_spreadsheet::Font) {
    let last = layout.supply_row;

    for row in layout.first_row..=last {
        let height = if row == layout.grand_row || row == layout.supply_row {
            ROW_H_TOTAL
        } else {
            ROW_H_DATA
        };
        sheet.row_dimension_mut(row).set_height(height);

        for col in COLS {
            let (left, right) = side(col, layout, row);
            let (top, bottom) = vert(col, layout, row);
            let coordinate = format!("{col}{row}");

            let wrap = sheet
                .cell(&*coordinate)
                .and_then(|cell| cell.style().alignment().map(|a| a.wrap_text()))
                .unwrap_or(false);

            touch(sheet, &coordinate, default_font);
            let cell = sheet.cell_mut(&*coordinate);
            let style = cell.style_mut();
            {
                let borders = style.borders_mut();
                left.apply(borders.left_mut());
                right.apply(borders.right_mut());
                top.apply(borders.top_mut());
                bottom.apply(borders.bottom_mut());
            }

            // 스페이서 행의 C열은 원본이 손대지 않아 배경이 없다
            if col != "B" && !(col == "C" && layout.spacer_rows.contains(&row)) {
                style.set_fill(body_fill());
                // 총합계·공급가 행은 가로 정렬을 지정하지 않는다 (골든 = 일반)
                let mut alignment = Alignment::default();
                if !layout.bf_rows.contains(&row) {
                    alignment.set_horizontal(horizontal(col));
                }
                alignment.set_vertical(VerticalAlignmentValues::Center);
                alignment.set_wrap_text(wrap);
                style.set_alignment(alignment);
            }
        }
    }

    {
        let coordinate = format!("I{}", layout.first_row);
        touch(sheet, &coordinate, default_font);
        let cell = sheet.cell_mut(&*coordinate);
        let style = cell.style_mut();
        style.set_fill(body_fill());
        let mut alignment = Alignment::default();
        alignment.set_vertical(VerticalAlignmentValues::Center);
        style.set_alignment(alignment);
    }

    apply_row_fills(sheet, layout, default_font);
    apply_blue(sheet, layout);
    decorate_trailer(sheet, layout, default_font);
    if layout.fix_header_bottom {
        fix_header(sheet, default_font);
    }
}

fn apply_row_fills(sheet: &mut Worksheet, layout: &Layout, default_font: &umya_spreadsheet::Font) {
    for &row in &layout.yellow_rows {
        for col in ["C", "G", "H"] {
            let coordinate = format!("{col}{row}");
            touch(sheet, &coordinate, default_font);
            sheet
                .cell_mut(&*coordinate)
                .style_mut()
                .set_fill(solid(argb(YELLOW)));
        }
    }
    for &row in &layout.cyan_rows {
        for col in ["C", "G", "H"] {
            let coordinate = format!("{col}{row}");
            touch(sheet, &coordinate, default_font);
            sheet
                .cell_mut(&*coordinate)
                .style_mut()
                .set_fill(solid(argb(CYAN)));
        }
    }
    for &row in &layout.yellow_labels {
        let coordinate = format!("B{row}");
        touch(sheet, &coordinate, default_font);
        sheet
            .cell_mut(&*coordinate)
            .style_mut()
            .set_fill(solid(argb(YELLOW)));
    }
    for row in [layout.grand_row, layout.supply_row] {
        if row == 0 {
            continue;
        }
        for col in ["B", "G", "H"] {
            let coordinate = format!("{col}{row}");
            touch(sheet, &coordinate, default_font);
            sheet
                .cell_mut(&*coordinate)
                .style_mut()
                .set_fill(solid(argb(ORANGE)));
        }
        for col in ["C", "D", "E", "F"] {
            let coordinate = format!("{col}{row}");
            touch(sheet, &coordinate, default_font);
            sheet.cell_mut(&*coordinate).style_mut().set_fill(no_fill());
        }
    }
}

/// 글꼴 색만 바꾼다. 이름·크기·굵기는 그대로 둔다.
fn recolor(sheet: &mut Worksheet, rows: &[u32], cols: &str, color: &str) {
    for &row in rows {
        for col in cols.chars() {
            let coordinate = format!("{col}{row}");
            let Some(cell) = sheet.cell(&*coordinate) else {
                continue;
            };
            let font = cell.style().font();
            let (name, size, bold) = match font {
                // 이름이 없는 글꼴은 파이썬 쪽에서도 건너뛴다.
                Some(font) if !font.name().is_empty() => {
                    (font.name().to_owned(), font.size(), font.bold())
                }
                _ => continue,
            };
            let style = sheet.cell_mut(&*coordinate).style_mut();
            let mut replacement = umya_spreadsheet::Font::default();
            replacement.set_name(name);
            replacement.set_size(size);
            replacement.set_bold(bold);
            replacement.set_color(argb(color));
            style.set_font(replacement);
        }
    }
}

/// Software 구간은 파랑, 제거 부품은 빨강.
///
/// 파랑은 TOTAL 시트에서 C~G 만, 상세 시트에서는 구간 라벨(B)까지 적용한다.
/// 빨강은 파랑보다 나중에 칠한다. S/W 구간에서 제거된 부품도 빨갛게 나온다.
fn apply_blue(sheet: &mut Worksheet, layout: &Layout) {
    let blue_cols = if layout.blue_includes_label {
        "BCDEFG"
    } else {
        "CDEFG"
    };
    let blue_rows = layout.blue_rows.clone();
    recolor(sheet, &blue_rows, blue_cols, BLUE);
    let red_rows = layout.red_rows.clone();
    recolor(sheet, &red_rows, "CDEFG", RED);
}

/// 공급가 아래 비고 블록 (2행). 바깥만 medium 이다.
fn decorate_trailer(sheet: &mut Worksheet, layout: &Layout, default_font: &umya_spreadsheet::Font) {
    let top = layout.supply_row + 1;
    let bottom = top + 1;
    sheet.row_dimension_mut(top).set_height(ROW_H_TRAILER);
    sheet.row_dimension_mut(bottom).set_height(ROW_H_TRAILER);

    set_borders(
        sheet,
        &format!("B{top}"),
        default_font,
        Line::Medium,
        Line::Medium,
        Line::Medium,
        Line::Medium,
    );
    sheet
        .cell_mut(&*format!("B{top}"))
        .style_mut()
        .set_fill(body_fill());
    set_borders(
        sheet,
        &format!("B{bottom}"),
        default_font,
        Line::Medium,
        Line::None,
        Line::None,
        Line::Medium,
    );
    for col in ["C", "D", "E", "F", "G"] {
        set_borders(
            sheet,
            &format!("{col}{top}"),
            default_font,
            Line::None,
            Line::None,
            Line::Medium,
            Line::None,
        );
        set_borders(
            sheet,
            &format!("{col}{bottom}"),
            default_font,
            Line::None,
            Line::None,
            Line::None,
            Line::Medium,
        );
    }
    set_borders(
        sheet,
        &format!("H{top}"),
        default_font,
        Line::None,
        Line::Medium,
        Line::Medium,
        Line::None,
    );
    set_borders(
        sheet,
        &format!("H{bottom}"),
        default_font,
        Line::None,
        Line::Medium,
        Line::None,
        Line::Medium,
    );
}

/// 네 변을 한꺼번에 다시 그린다 (파이썬 `Border(...)` 새로 만들기와 같다).
fn set_borders(
    sheet: &mut Worksheet,
    coordinate: &str,
    default_font: &umya_spreadsheet::Font,
    left: Line,
    right: Line,
    top: Line,
    bottom: Line,
) {
    touch(sheet, coordinate, default_font);
    let style = sheet.cell_mut(coordinate).style_mut();
    let borders = style.borders_mut();
    left.apply(borders.left_mut());
    right.apply(borders.right_mut());
    top.apply(borders.top_mut());
    bottom.apply(borders.bottom_mut());
}

/// 상세 시트 헤더 아래를 medium 으로. 템플릿은 double 로 되어 있다.
fn fix_header(sheet: &mut Worksheet, default_font: &umya_spreadsheet::Font) {
    let mut addresses: Vec<String> = COLS.iter().map(|col| format!("{col}7")).collect();
    addresses.push("D6".to_owned());
    addresses.push("H6".to_owned());
    for address in addresses {
        touch(sheet, &address, default_font);
        let style = sheet.cell_mut(&*address).style_mut();
        Line::MediumBlack.apply(style.borders_mut().bottom_mut());
    }
}
