//! Detail sheets: items, subitems, removals and section totals.
use super::cells::{
    Align, FMT_DETAIL_NUM, FMT_TEXT, LBL_HW, LBL_HW_TOTAL, LBL_SUBTOTAL, LBL_SW, LBL_SW_TOTAL,
    amount_cell, font_data, font_data_bold, font_date, font_label, font_title, merge, merge_across,
    put_formula, put_label, put_number, put_xml_text,
};
use super::{Date, FIRST_DATA_ROW, decorate::Layout, footer::write_footer};
use crate::{
    models::{Group, LineItem, SubLineItem},
    money::{self, Amount},
};
use umya_spreadsheet::Worksheet;

pub(super) fn write_detail_sheet(
    sheet: &mut Worksheet,
    group: &Group,
    today: Date,
) -> (Vec<String>, Layout) {
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
