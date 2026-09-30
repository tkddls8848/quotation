//! Shared totals, supply-price row and print area.
use super::cells::{
    Align, LBL_GRAND, LBL_SUPPLY, font_data_bold, font_label, merge_across, put_formula, put_label,
};
use super::{TRAILER_ROWS, decorate::Layout};
use umya_spreadsheet::Worksheet;

/// 총합계 / 공급가 / 하단 비고 병합 + 인쇄 영역.
///
/// 합계가 하나뿐일 때 TOTAL 시트는 `=SUM(G13)` 을, 상세 시트는 `=G10` 을 쓴다.
pub(super) fn write_footer(
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
