//! umya-spreadsheet 3.1.0 이 읽다가 잃어버리는 것을 템플릿에서 되돌린다.
//!
//! `Border::set_attributes` 가 `<color>` 를 **복사본에 담고 버린다**
//! (`self.color.clone().unwrap_or_default().set_attributes(...)`). 그래서 읽고
//! 다시 쓰면 템플릿의 테두리 색이 모두 사라진다.
//!
//! 대부분은 색인 64(자동)이라 눈에 띄지 않지만, 이 견적서 템플릿의 TOTAL 시트
//! 머리말에는 **흰 테두리**(색인 9)가 있다. 그대로 두면 머리말에 검은 실선이
//! 그어져 첫 페이지 모양이 달라진다.
//!
//! 그래서 템플릿의 styles.xml 을 직접 읽어, 자동이 아닌 테두리 색만 셀에 다시
//! 적어 준다. 우리가 쓰는 셀은 writer 가 색까지 지정하므로 영향받지 않는다.

use umya_spreadsheet::{Border, Color, Workbook};

use super::drawings::{attribute, read_parts, sheet_part, tags};

/// 색인 64/65 는 자동(automatic) — 색을 지정하지 않은 것과 같다.
const SYSTEM_INDEXES: [u32; 2] = [64, 65];

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Paint {
    Indexed(u32),
    Argb([u8; 8]),
}

/// 테두리 네 변의 색 (왼쪽, 오른쪽, 위, 아래).
type SideColors = [Option<Paint>; 4];

const SIDES: [&str; 4] = ["left", "right", "top", "bottom"];

/// 템플릿에서 잃어버린 테두리 색을 되돌린다. 되돌릴 것이 없으면 아무 일도 없다.
pub(super) fn border_colors(book: &mut Workbook, template: &[u8], sheets: &[&str]) {
    let Some(parts) = read_parts(template) else {
        return;
    };
    let Some(styles) = parts.get("xl/styles.xml") else {
        return;
    };
    let styles = String::from_utf8_lossy(styles).into_owned();
    let borders = border_table(&styles);
    let formats = cell_formats(&styles);
    if borders.is_empty() || formats.is_empty() {
        return;
    }

    for name in sheets {
        let Some(part) = sheet_part(&parts, name) else {
            continue;
        };
        let Some(sheet_xml) = parts.get(&part) else {
            continue;
        };
        let sheet_xml = String::from_utf8_lossy(sheet_xml).into_owned();
        let painted = painted_cells(&sheet_xml, &formats, &borders);
        if painted.is_empty() {
            continue;
        }
        let Ok(sheet) = book.sheet_by_name_mut(name) else {
            continue;
        };
        for (coordinate, colors) in painted {
            let style = sheet.cell_mut(&*coordinate).style_mut();
            let sides = style.borders_mut();
            for (index, paint) in colors.iter().enumerate() {
                let Some(paint) = paint else { continue };
                let border: &mut Border = match index {
                    0 => sides.left_mut(),
                    1 => sides.right_mut(),
                    2 => sides.top_mut(),
                    _ => sides.bottom_mut(),
                };
                border.set_color(color(*paint));
            }
        }
    }
}

fn color(paint: Paint) -> Color {
    let mut color = Color::default();
    match paint {
        Paint::Indexed(index) => {
            color.set_indexed(index);
        }
        Paint::Argb(value) => {
            color.set_argb_str(std::str::from_utf8(&value).unwrap_or("FF000000"));
        }
    }
    color
}

/// styles.xml 의 `<borders>` — 순서가 곧 borderId 다.
fn border_table(styles: &str) -> Vec<SideColors> {
    let Some(block) = between(styles, "<borders", "</borders>") else {
        return Vec::new();
    };
    let mut table = Vec::new();
    for border in split_blocks(&block, "border") {
        let mut colors: SideColors = [None; 4];
        for (index, side) in SIDES.iter().enumerate() {
            if let Some(piece) = between(&border, &format!("<{side}"), &format!("</{side}>")) {
                colors[index] = paint_of(&piece);
            }
        }
        table.push(colors);
    }
    table
}

/// styles.xml 의 `<cellXfs>` — 순서가 곧 셀의 `s` 값이고, 값은 borderId 다.
fn cell_formats(styles: &str) -> Vec<usize> {
    let Some(block) = between(styles, "<cellXfs", "</cellXfs>") else {
        return Vec::new();
    };
    tags(&block, "xf")
        .into_iter()
        .map(|tag| {
            attribute(tag, "borderId")
                .and_then(|value| value.parse::<usize>().ok())
                .unwrap_or(0)
        })
        .collect()
}

/// 시트에서 **자동이 아닌** 테두리 색을 가진 셀만 골라 온다.
fn painted_cells(
    sheet_xml: &str,
    formats: &[usize],
    borders: &[SideColors],
) -> Vec<(String, SideColors)> {
    let mut painted = Vec::new();
    for cell in tags(sheet_xml, "c") {
        let Some(coordinate) = attribute(cell, "r") else {
            continue;
        };
        let format = attribute(cell, "s")
            .and_then(|value| value.parse::<usize>().ok())
            .unwrap_or(0);
        let Some(&border_id) = formats.get(format) else {
            continue;
        };
        let Some(colors) = borders.get(border_id) else {
            continue;
        };
        if colors.iter().flatten().any(|paint| !is_system(paint)) {
            painted.push((coordinate, *colors));
        }
    }
    painted
}

fn is_system(paint: &Paint) -> bool {
    matches!(paint, Paint::Indexed(index) if SYSTEM_INDEXES.contains(index))
}

fn paint_of(side: &str) -> Option<Paint> {
    let tag = tags(side, "color").into_iter().next()?;
    if let Some(index) = attribute(tag, "indexed").and_then(|v| v.parse::<u32>().ok()) {
        return Some(Paint::Indexed(index));
    }
    let rgb = attribute(tag, "rgb")?;
    let bytes = rgb.as_bytes();
    if bytes.len() != 8 {
        return None;
    }
    let mut value = [0u8; 8];
    value.copy_from_slice(bytes);
    Some(Paint::Argb(value))
}

fn between(xml: &str, open: &str, close: &str) -> Option<String> {
    let start = xml.find(open)?;
    let end = xml[start..].find(close)? + start;
    Some(xml[start..end].to_owned())
}

/// `<border>...</border>` 조각을 순서대로 자른다. 빈 태그도 한 자리다.
fn split_blocks(xml: &str, name: &str) -> Vec<String> {
    let open = format!("<{name}");
    let close = format!("</{name}>");
    let mut blocks = Vec::new();
    let mut rest = xml;
    while let Some(start) = rest.find(&open) {
        let after = &rest[start..];
        // `<borders ...>` 자체는 건너뛴다.
        let boundary = after[open.len()..].chars().next().unwrap_or(' ');
        if boundary.is_alphanumeric() {
            rest = &after[open.len()..];
            continue;
        }
        let Some(head_end) = after.find('>') else {
            break;
        };
        if after[..=head_end].ends_with("/>") {
            blocks.push(after[..=head_end].to_owned());
            rest = &after[head_end..];
            continue;
        }
        let Some(end) = after.find(&close) else { break };
        blocks.push(after[..end].to_owned());
        rest = &after[end..];
    }
    blocks
}
