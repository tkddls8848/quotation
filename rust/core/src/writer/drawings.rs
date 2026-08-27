//! 템플릿의 그림·도형을 산출물로 옮긴다.
//! 파이썬 `quotation/core/writer/drawings.py`.
//!
//! 견적서 템플릿은 TOTAL 시트 상단에 로고와 도형으로 된 머리글 블록을 두고
//! 있다. OOXML 라이브러리가 그것을 다시 직렬화하면서 달라질 수 있으므로,
//! **원본 부품을 바이트 그대로** 옮겨 붙인다
//! ([결정 0005](../../../doc/decisions/0005-accept-meaningful-xlsx-parity.md)).
//!
//! 골든과 동일하게 TOTAL 시트에만 옮긴다. 원본 프로그램도 상세 시트와 잔존
//! template 시트에는 그림을 남기지 않는다.

use std::collections::BTreeMap;
use std::io::{Cursor, Read, Write};

use zip::{CompressionMethod, ZipArchive, ZipWriter, write::SimpleFileOptions};

const CONTENT_TYPES: &str = "[Content_Types].xml";
const DRAWING_CT: &str = "application/vnd.openxmlformats-officedocument.drawing+xml";
const DRAWING_REL: &str =
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/drawing";
const R_NS: &str = "http://schemas.openxmlformats.org/officeDocument/2006/relationships";

pub(crate) type Parts = BTreeMap<String, Vec<u8>>;

/// 템플릿의 그림·도형을 산출물 바이트의 지정 시트로 옮긴다.
///
/// 옮길 것이 없으면 `None`.
pub fn carry_over_bytes(template: &[u8], output: &[u8], sheet_name: &str) -> Option<Vec<u8>> {
    let source = read_parts(template)?;
    let source_sheet = sheet_part(&source, sheet_name)?;
    let parts = collect(&source, &source_sheet);
    if parts.is_empty() {
        return None;
    }

    let mut entries = read_parts(output)?;
    let target_sheet = sheet_part(&entries, sheet_name)?;

    // openpyxl 은 저장할 때 그림을 통째로 버린다. 그 뒤에 TOTAL 시트 것만
    // 다시 붙이는 것이 원본 프로그램의 결과다. umya 는 그림을 그대로 들고
    // 있으므로 (상세 시트는 template 을 복제해 만들어 같이 딸려 온다) 여기서
    // 같은 출발점으로 맞춘다.
    strip_drawings(&mut entries);

    let drawings: Vec<String> = parts
        .keys()
        .filter(|name| is_drawing_part(name))
        .cloned()
        .collect();
    let first = drawings.first()?;

    let rels_part = rels_part(&target_sheet);
    let existing = entries
        .get(&rels_part)
        .map(|body| String::from_utf8_lossy(body).into_owned());
    let rid = next_rid(existing.as_deref().unwrap_or(""));
    let target = relative(first, &directory(&target_sheet));

    let media_extensions: Vec<String> = parts
        .keys()
        .filter(|name| name.starts_with("xl/media/"))
        .filter_map(|name| extension(name))
        .collect();

    for (name, body) in parts {
        entries.insert(name, body);
    }
    entries.insert(
        rels_part,
        patch_rels(existing.as_deref(), &rid, &target).into_bytes(),
    );
    let sheet_xml = String::from_utf8_lossy(entries.get(&target_sheet)?).into_owned();
    entries.insert(target_sheet, patch_sheet(&sheet_xml, &rid).into_bytes());
    let types = String::from_utf8_lossy(entries.get(CONTENT_TYPES)?).into_owned();
    entries.insert(
        CONTENT_TYPES.to_owned(),
        patch_content_types(&types, &drawings, &media_extensions).into_bytes(),
    );

    write_parts(entries)
}

/// 모든 시트에서 그림을 떼어 낸다 (openpyxl 이 저장할 때 하는 일과 같다).
fn strip_drawings(entries: &mut Parts) {
    let doomed: Vec<String> = entries
        .keys()
        .filter(|name| name.starts_with("xl/drawings/") || name.starts_with("xl/media/"))
        .cloned()
        .collect();
    for name in &doomed {
        entries.remove(name);
    }

    let sheets: Vec<String> = entries
        .keys()
        .filter(|name| name.starts_with("xl/worksheets/") && name.ends_with(".xml"))
        .cloned()
        .collect();
    for sheet in sheets {
        if let Some(body) = entries.get(&sheet) {
            let xml = String::from_utf8_lossy(body).into_owned();
            let stripped = remove_tags(&xml, "drawing", |_| true);
            entries.insert(sheet.clone(), stripped.into_bytes());
        }
        let rels = rels_part(&sheet);
        if let Some(body) = entries.get(&rels) {
            let xml = String::from_utf8_lossy(body).into_owned();
            let stripped = remove_tags(&xml, "Relationship", |tag| {
                attribute(tag, "Target").is_some_and(|target| target.contains("drawing"))
            });
            entries.insert(rels, stripped.into_bytes());
        }
    }

    if let Some(body) = entries.get(CONTENT_TYPES) {
        let xml = String::from_utf8_lossy(body).into_owned();
        let stripped = remove_tags(&xml, "Override", |tag| {
            attribute(tag, "PartName").is_some_and(|part| part.starts_with("/xl/drawings/"))
        });
        entries.insert(CONTENT_TYPES.to_owned(), stripped.into_bytes());
    }
}

/// 조건에 맞는 태그를 지운다. 짝이 있는 태그는 닫는 태그까지 지운다.
fn remove_tags(xml: &str, name: &str, matches: impl Fn(&str) -> bool) -> String {
    let mut out = xml.to_owned();
    loop {
        let Some(tag) = tags(&out, name).into_iter().find(|tag| matches(tag)) else {
            return out;
        };
        let tag = tag.to_owned();
        let Some(start) = out.find(&tag) else {
            return out;
        };
        let end = if tag.ends_with("/>") {
            start + tag.len()
        } else {
            let close = format!("</{name}>");
            match out[start..].find(&close) {
                Some(offset) => start + offset + close.len(),
                None => start + tag.len(),
            }
        };
        out.replace_range(start..end, "");
    }
}

pub(crate) fn read_parts(bytes: &[u8]) -> Option<Parts> {
    let mut archive = ZipArchive::new(Cursor::new(bytes)).ok()?;
    let mut parts = Parts::new();
    for index in 0..archive.len() {
        let mut entry = archive.by_index(index).ok()?;
        if entry.is_dir() {
            continue;
        }
        let mut body = Vec::new();
        entry.read_to_end(&mut body).ok()?;
        parts.insert(entry.name().to_owned(), body);
    }
    Some(parts)
}

fn write_parts(entries: Parts) -> Option<Vec<u8>> {
    let mut writer = ZipWriter::new(Cursor::new(Vec::new()));
    // 수정 시각을 고정한다. 견적서 내용이 아니고, 고정하면 같은 입력이 같은
    // 파일을 낸다.
    let options = SimpleFileOptions::default()
        .compression_method(CompressionMethod::Deflated)
        .last_modified_time(zip::DateTime::default());
    for (name, body) in entries {
        writer.start_file(name, options).ok()?;
        writer.write_all(&body).ok()?;
    }
    Some(writer.finish().ok()?.into_inner())
}

/// 속성 순서에 기대지 않고 값을 읽는다.
pub(crate) fn attribute(tag: &str, name: &str) -> Option<String> {
    let needle = format!("{name}=\"");
    let start = tag.find(&needle)? + needle.len();
    let end = tag[start..].find('"')? + start;
    Some(tag[start..end].to_owned())
}

/// `<이름 ...>` 꼴의 태그를 모두 찾는다.
pub(crate) fn tags<'a>(xml: &'a str, name: &str) -> Vec<&'a str> {
    let open = format!("<{name}");
    let mut found = Vec::new();
    let mut rest = xml;
    while let Some(start) = rest.find(&open) {
        let after = &rest[start..];
        // `<sheetPr` 같은 다른 태그를 잘못 집지 않는다.
        let boundary = after[open.len()..].chars().next().unwrap_or(' ');
        if boundary.is_alphanumeric() {
            rest = &rest[start + open.len()..];
            continue;
        }
        let Some(end) = after.find('>') else { break };
        found.push(&after[..=end]);
        rest = &after[end..];
    }
    found
}

/// 관계의 Target 을 zip 내부 경로로 바꾼다. 절대/상대 모두 받는다.
fn resolve(base_part: &str, target: &str) -> String {
    if let Some(absolute) = target.strip_prefix('/') {
        return absolute.to_owned();
    }
    normalize(&format!("{}/{target}", directory(base_part)))
}

fn directory(part: &str) -> String {
    match part.rfind('/') {
        Some(index) => part[..index].to_owned(),
        None => String::new(),
    }
}

fn normalize(path: &str) -> String {
    let mut stack: Vec<&str> = Vec::new();
    for piece in path.split('/') {
        match piece {
            "" | "." => {}
            ".." => {
                stack.pop();
            }
            other => stack.push(other),
        }
    }
    stack.join("/")
}

fn relative(part: &str, base: &str) -> String {
    match part.strip_prefix(&format!("{base}/")) {
        Some(rest) => rest.to_owned(),
        None => format!("../{}", part.trim_start_matches("xl/")),
    }
}

fn rels_part(part: &str) -> String {
    let folder = directory(part);
    let name = part.rsplit('/').next().unwrap_or(part);
    format!("{folder}/_rels/{name}.rels")
}

fn is_drawing_part(name: &str) -> bool {
    name.strip_prefix("xl/drawings/drawing")
        .and_then(|rest| rest.strip_suffix(".xml"))
        .is_some_and(|digits| !digits.is_empty() && digits.chars().all(|c| c.is_ascii_digit()))
}

fn extension(name: &str) -> Option<String> {
    name.rsplit('.').next().map(|ext| ext.to_lowercase())
}

/// 시트 이름 -> `xl/worksheets/sheetN.xml`
pub(crate) fn sheet_part(parts: &Parts, sheet_name: &str) -> Option<String> {
    let workbook = String::from_utf8_lossy(parts.get("xl/workbook.xml")?).into_owned();
    let rels = String::from_utf8_lossy(parts.get("xl/_rels/workbook.xml.rels")?).into_owned();
    for tag in tags(&workbook, "sheet") {
        if attribute(tag, "name").as_deref() != Some(sheet_name) {
            continue;
        }
        let id = attribute(tag, "r:id")?;
        let target = tags(&rels, "Relationship")
            .into_iter()
            .find(|relationship| attribute(relationship, "Id").as_deref() == Some(&id))
            .and_then(|relationship| attribute(relationship, "Target"))?;
        let part = resolve("xl/workbook.xml", &target);
        return parts.contains_key(&part).then_some(part);
    }
    None
}

/// 시트에 딸린 drawing 과 그것이 참조하는 media 를 모은다.
fn collect(parts: &Parts, sheet_part: &str) -> Parts {
    let mut found = Parts::new();
    let Some(rels) = parts.get(&rels_part(sheet_part)) else {
        return found;
    };
    let rels = String::from_utf8_lossy(rels).into_owned();
    for relationship in tags(&rels, "Relationship") {
        let Some(target) = attribute(relationship, "Target") else {
            continue;
        };
        if !target.contains("drawing") {
            continue;
        }
        let drawing = resolve(sheet_part, &target);
        let Some(body) = parts.get(&drawing) else {
            continue;
        };
        found.insert(drawing.clone(), body.clone());

        // drawing 이 참조하는 이미지까지 따라간다
        let drawing_rels = rels_part(&drawing);
        if let Some(body) = parts.get(&drawing_rels) {
            found.insert(drawing_rels.clone(), body.clone());
            let inner = String::from_utf8_lossy(body).into_owned();
            for relationship in tags(&inner, "Relationship") {
                let Some(target) = attribute(relationship, "Target") else {
                    continue;
                };
                let media = resolve(&drawing, &target);
                if let Some(body) = parts.get(&media) {
                    found.insert(media, body.clone());
                }
            }
        }
    }
    found
}

fn next_rid(rels_xml: &str) -> String {
    let mut highest = 0;
    for tag in tags(rels_xml, "Relationship") {
        if let Some(id) = attribute(tag, "Id")
            && let Some(digits) = id.strip_prefix("rId")
            && let Ok(number) = digits.parse::<u32>()
        {
            highest = highest.max(number);
        }
    }
    format!("rId{}", highest + 1)
}

fn patch_rels(existing: Option<&str>, rid: &str, target: &str) -> String {
    let entry = format!("<Relationship Id=\"{rid}\" Type=\"{DRAWING_REL}\" Target=\"{target}\"/>");
    match existing {
        Some(body) if !body.is_empty() => {
            body.replace("</Relationships>", &format!("{entry}</Relationships>"))
        }
        _ => format!(
            "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>\
             <Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">\
             {entry}</Relationships>"
        ),
    }
}

/// `<drawing>` 은 스키마상 워크시트의 끝부분에 온다.
fn patch_sheet(sheet_xml: &str, rid: &str) -> String {
    if sheet_xml.contains("<drawing ") {
        return sheet_xml.to_owned();
    }
    let mut patched = sheet_xml.to_owned();
    if !patched.contains("xmlns:r=") {
        let head_end = match patched.find('>') {
            Some(index) => index,
            None => return patched,
        };
        let head = &patched[..head_end];
        if head.contains("<worksheet") {
            patched = format!("{head} xmlns:r=\"{R_NS}\"{}", &patched[head_end..]);
        }
    }
    patched.replace(
        "</worksheet>",
        &format!("<drawing r:id=\"{rid}\"/></worksheet>"),
    )
}

fn patch_content_types(xml: &str, drawing_parts: &[String], extensions: &[String]) -> String {
    let mut additions = String::new();
    let mut seen: Vec<&str> = Vec::new();
    for ext in extensions {
        if seen.contains(&ext.as_str()) || xml.contains(&format!("Extension=\"{ext}\"")) {
            continue;
        }
        seen.push(ext);
        additions.push_str(&format!(
            "<Default Extension=\"{ext}\" ContentType=\"image/{ext}\"/>"
        ));
    }
    for part in drawing_parts {
        let name = format!("/{part}");
        if xml.contains(&format!("PartName=\"{name}\"")) {
            continue;
        }
        additions.push_str(&format!(
            "<Override PartName=\"{name}\" ContentType=\"{DRAWING_CT}\"/>"
        ));
    }
    if additions.is_empty() {
        return xml.to_owned();
    }
    xml.replace("</Types>", &format!("{additions}</Types>"))
}
