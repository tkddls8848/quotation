//! 파이썬 `json.dumps(..., ensure_ascii=False)` 와 같은 글을 만든다.
//!
//! 응답 본문은 사용자에게도 테스트에도 그대로 보이므로 구분자 자리(`": "`,
//! `", "`)까지 파이썬과 맞춘다. 한글은 이스케이프하지 않는다.

/// JSON 문자열 리터럴.
pub fn string(value: &str) -> String {
    let mut out = String::with_capacity(value.len() + 2);
    out.push('"');
    for ch in value.chars() {
        match ch {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            ch if (ch as u32) < 0x20 => out.push_str(&format!("\\u{:04x}", ch as u32)),
            ch => out.push(ch),
        }
    }
    out.push('"');
    out
}

/// 파이썬 `f"{n:,}"`.
pub fn thousands(value: usize) -> String {
    let digits = value.to_string();
    let mut out = String::with_capacity(digits.len() + digits.len() / 3);
    for (index, digit) in digits.chars().enumerate() {
        if index > 0 && (digits.len() - index) % 3 == 0 {
            out.push(',');
        }
        out.push(digit);
    }
    out
}
