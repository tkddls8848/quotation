//! 파일 이름 다루기. 파이썬 `web/src/api.py` 의 이름 부분과
//! `quotation/core/convert.py` 의 `output_name_for`.

/// 업로드 파일명에서 경로와 제어문자를 떼어 낸다.
///
/// 브라우저가 보내는 이름을 그대로 믿지 않는다. 한글·공백·`#`·괄호는 살린다.
pub fn safe_source_name(raw: &str) -> String {
    let cleaned: String = raw
        .replace('\\', "/")
        .chars()
        .filter(|ch| !is_control(*ch))
        .collect();
    let tail = cleaned.rsplit('/').next().unwrap_or("").to_owned();
    let trimmed = tail.trim().trim_start_matches('.').to_owned();
    if trimmed.is_empty() {
        "quotation.xml".to_owned()
    } else {
        trimmed
    }
}

/// 파이썬 정규식 `[\x00-\x1f\x7f]`.
fn is_control(ch: char) -> bool {
    let code = ch as u32;
    code < 0x20 || code == 0x7f
}

/// 입력 파일의 기본 이름을 유지하고 확장자만 `.xlsx` 로 바꾼다.
pub fn output_name_for(xml_name: &str) -> String {
    let stem = match xml_name.rsplit_once('.') {
        // 파이썬 `Path.stem` 은 마지막 확장자 하나만 뗀다. 앞이 비면 통째로 이름이다.
        Some((head, _)) if !head.is_empty() => head,
        _ => xml_name,
    };
    let stem = if stem.is_empty() { "quotation" } else { stem };
    format!("{stem}.xlsx")
}

/// RFC 5987 형식. 한글 파일명을 그대로 내려받게 한다.
pub fn content_disposition(filename: &str) -> String {
    let fallback: String = filename
        .chars()
        .map(|ch| if is_ascii_safe(ch) { ch } else { '_' })
        .collect();
    let fallback = fallback.trim();
    let fallback = if fallback.is_empty() {
        "quotation.xlsx"
    } else {
        fallback
    };
    format!(
        "attachment; filename=\"{fallback}\"; filename*=UTF-8''{}",
        percent_encode(filename)
    )
}

/// 파이썬 정규식 `[^A-Za-z0-9._ -]` 의 여집합.
fn is_ascii_safe(ch: char) -> bool {
    ch.is_ascii_alphanumeric() || matches!(ch, '.' | '_' | ' ' | '-')
}

/// 파이썬 `urllib.parse.quote(value, safe="")`.
fn percent_encode(value: &str) -> String {
    let mut out = String::with_capacity(value.len());
    for byte in value.as_bytes() {
        let ch = *byte as char;
        if ch.is_ascii_alphanumeric() || matches!(ch, '_' | '.' | '-' | '~') {
            out.push(ch);
        } else {
            out.push_str(&format!("%{byte:02X}"));
        }
    }
    out
}
