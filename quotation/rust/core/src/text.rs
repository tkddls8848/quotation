//! 파이썬 문자열 규칙을 그대로 흉내 내는 최소 도구.
//!
//! 종목 키·시트명은 사람이 적어 넣은 한글 이름을 자르고 다듬는다. 파이썬의
//! 잘라내기는 글자 수 기준이고 공백 판정 범위도 Rust 기본값과 다르므로,
//! 규칙이 갈리지 않도록 여기 한 곳에 모아 둔다.

/// 파이썬 `str.isspace()` 와 같은 범위.
///
/// 유니코드 White_Space 에 파이썬만 공백으로 보는 구분 문자
/// (`\x1c`~`\x1f`) 를 더한다.
fn is_python_space(ch: char) -> bool {
    ch.is_whitespace() || matches!(ch, '\u{1c}'..='\u{1f}')
}

/// 파이썬 `str.strip()`.
pub fn strip(text: &str) -> &str {
    text.trim_matches(is_python_space)
}

/// 파이썬 슬라이스 `text[:limit]` — 바이트가 아니라 글자 수로 자른다.
pub fn truncate_chars(text: &str, limit: usize) -> &str {
    match text.char_indices().nth(limit) {
        Some((end, _)) => &text[..end],
        None => text,
    }
}
