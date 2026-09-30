//! TOTAL sheet: group summaries and subtotals.
use super::cells::{
    Align, FMT_TEXT, FMT_TOTAL_NUM, LBL_SUBTOTAL, font_data, font_data_bold, font_date, font_label,
    merge, merge_across, number, put_formula, put_label, put_number, put_xml_text,
};
use super::{Date, FIRST_DATA_ROW, Result, WriteError, decorate::Layout, footer::write_footer};
use crate::{models::Quotation, money::Decimal};
use umya_spreadsheet::Worksheet;

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

pub(super) fn write_total_sheet(
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
