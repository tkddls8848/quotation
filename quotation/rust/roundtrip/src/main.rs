//! 실제 구성 XML로 만든 Python 견적서의 OOXML 보존성 관문.
//!
//! 이 프로그램은 변환기가 아니다. Python 산출물을 열어 그대로 저장해 umya의
//! round-trip 성질만 본다. 독립 Rust 변환 결과로 사용하면 안 된다.

use std::{
    collections::BTreeMap,
    env, fs,
    io::{Cursor, Read, Write},
};

use anyhow::{Context, Result};
use zip::{CompressionMethod, ZipArchive, ZipWriter, write::SimpleFileOptions};

fn main() -> Result<()> {
    let mut args = env::args_os();
    let executable = args.next().unwrap_or_default();
    let input = args
        .next()
        .with_context(|| format!("usage: {:?} INPUT.xlsx OUTPUT.xlsx", executable))?;
    let output = args
        .next()
        .with_context(|| format!("usage: {:?} INPUT.xlsx OUTPUT.xlsx", executable))?;
    if args.next().is_some() {
        anyhow::bail!("usage: {:?} INPUT.xlsx OUTPUT.xlsx", executable);
    }

    let source = fs::read(input).context("cannot read input workbook")?;
    let book = umya_spreadsheet::reader::xlsx::read_reader(Cursor::new(&source), true)
        .context("umya-spreadsheet cannot read workbook")?;
    let mut target = Cursor::new(Vec::new());
    umya_spreadsheet::writer::xlsx::write_writer(&book, &mut target)
        .context("umya-spreadsheet cannot write workbook")?;
    // umya는 셀·수식은 보존하지만 drawing XML을 재직렬화한다. 이 템플릿의
    // 첫 페이지(TOTAL)는 언제나 sheet1이고 그림은 sheet1 관계가 가리키므로,
    // 원본 drawing/media 부품을 그대로 되돌린다. 셀 XML은 덮어쓰지 않는다.
    let repaired = reinstate_first_page_drawings(&source, &target.into_inner())?;
    fs::write(output, repaired).context("cannot write output workbook")?;
    Ok(())
}

fn read_parts(bytes: &[u8]) -> Result<BTreeMap<String, Vec<u8>>> {
    let mut archive = ZipArchive::new(Cursor::new(bytes)).context("invalid xlsx zip")?;
    let mut parts = BTreeMap::new();
    for index in 0..archive.len() {
        let mut entry = archive.by_index(index)?;
        if entry.is_dir() {
            continue;
        }
        let mut body = Vec::new();
        entry.read_to_end(&mut body)?;
        parts.insert(entry.name().to_owned(), body);
    }
    Ok(parts)
}

/// 템플릿 TOTAL 페이지의 drawing·media를 출력물에 바이트 그대로 되돌린다.
///
/// `quotation/core/writer/drawings.py`의 원칙과 같다. 출력물의 셀·수식은
/// 건드리지 않고, Excel 화면 상단을 구성하는 OOXML 부품만 원본으로 유지한다.
fn reinstate_first_page_drawings(template: &[u8], output: &[u8]) -> Result<Vec<u8>> {
    let source = read_parts(template)?;
    let mut destination = read_parts(output)?;
    let sheet = "xl/worksheets/sheet1.xml";
    let sheet_rels = "xl/worksheets/_rels/sheet1.xml.rels";

    let source_rels = source
        .get(sheet_rels)
        .context("template TOTAL sheet has no drawing relationship")?;
    let output_sheet = destination
        .get(sheet)
        .context("output has no TOTAL sheet")?;
    if !output_sheet
        .windows(b"<drawing".len())
        .any(|part| part == b"<drawing")
    {
        anyhow::bail!("output TOTAL sheet has no drawing reference")
    }

    let drawings: Vec<_> = source
        .iter()
        .filter(|(name, _)| name.starts_with("xl/drawings/") || name.starts_with("xl/media/"))
        .map(|(name, body)| (name.clone(), body.clone()))
        .collect();
    if drawings.is_empty() {
        anyhow::bail!("template has no first-page drawing parts")
    }
    for (name, body) in drawings {
        destination.insert(name, body);
    }
    destination.insert(sheet_rels.to_owned(), source_rels.clone());

    let mut writer = ZipWriter::new(Cursor::new(Vec::new()));
    let options = SimpleFileOptions::default().compression_method(CompressionMethod::Deflated);
    for (name, body) in destination {
        writer.start_file(name, options)?;
        writer.write_all(&body)?;
    }
    Ok(writer.finish()?.into_inner())
}
