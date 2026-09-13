//! 종목 키와 Excel 시트명 생성. 파이썬 `quotation/core/naming.py`.

use std::collections::HashSet;

use crate::text;

/// Excel 시트명 제한에 맞춰 자른 뒤 IBM 접두사를 제거한다.
pub const ITEM_KEY_MAX: usize = 31;
pub const SHEET_NAME_MAX: usize = 31;

/// Excel 이 시트명에 허용하지 않는 글자. 대신 하이픈을 넣는다.
/// `메일/스펨_1식` -> `메일-스펨_1식`
pub const SHEET_FORBIDDEN: &str = r":\/?*[]";
pub const SHEET_REPLACEMENT: char = '-';

/// Excel 이 예약해 둔 시트명 (대소문자 무관).
pub const SHEET_RESERVED: &str = "history";

/// 금칙 문자를 다 걷어 내고도 이름이 남지 않을 때 쓸 이름.
pub const SHEET_FALLBACK: &str = "SHEET";

/// ProductDescription -> 종목 키 (원본 대소문자 유지).
pub fn item_key(description: &str) -> String {
    let head = description.split_once(':').map_or(description, |(a, _)| a);
    let text = text::truncate_chars(text::strip(head), ITEM_KEY_MAX);
    text::strip(text.strip_prefix("IBM ").unwrap_or(text)).to_owned()
}

/// 종목 키 -> 시트명 (대문자).
pub fn sheet_name(key: &str) -> String {
    text::truncate_chars(&key.to_uppercase(), SHEET_NAME_MAX).to_owned()
}

/// 레노버 구성의 종목 키.
///
/// 한 파일에 같은 기종을 여러 대 담으면 ProductDescription 이 전부 같다
/// (`ThinkSystem SR650 V4-3yr Base Warranty` x 10). 장비를 구분하는 이름은
/// 구성기에서 사람이 적어 넣은 ProductName 에 있다 (`백업서버_1식`).
/// 그래서 그쪽을 먼저 쓰고, 없으면 지금까지 하던 대로 설명에서 딴다.
pub fn product_key(product_name: &str, description: &str) -> String {
    let text = text::strip(text::truncate_chars(
        text::strip(product_name),
        ITEM_KEY_MAX,
    ));
    if text.is_empty() {
        item_key(description)
    } else {
        text.to_owned()
    }
}

/// 종목 키 -> **Excel 이 받아 주는** 시트명.
///
/// `sheet_name` 과 달리 금칙 문자를 걷어 낸다. IBM 문서의 종목 키에는 금칙
/// 문자가 나오지 않지만 사람이 적어 넣은 이름에는 나온다 (`메일/스펨_1식`).
pub fn safe_sheet_name(key: &str) -> String {
    let cleaned: String = key
        .to_uppercase()
        .chars()
        .map(|ch| {
            if SHEET_FORBIDDEN.contains(ch) {
                SHEET_REPLACEMENT
            } else {
                ch
            }
        })
        .collect();
    let text = text::truncate_chars(&cleaned, SHEET_NAME_MAX);
    let text = text::strip(text::strip(text).trim_matches('\''));
    if text.is_empty() || text.to_lowercase() == SHEET_RESERVED {
        return SHEET_FALLBACK.to_owned();
    }
    text.to_owned()
}

/// 겹치는 시트명을 갈라 준다. 순서와 길이 제한을 지킨다.
///
/// Excel 은 한 통합 문서에 같은 이름의 시트를 둘 수 없고 이름은 31자까지다.
/// 라이브러리에 맡기면 뒤에 숫자를 이어 붙여 32자짜리 이름을 만들어 내므로
/// 여기서 먼저 정리한다.
///
/// `["백업서버", "백업서버", "웹서버"]` -> `["백업서버", "백업서버 (2)", "웹서버"]`
pub fn unique_sheet_names<I, S>(names: I) -> Vec<String>
where
    I: IntoIterator<Item = S>,
    S: AsRef<str>,
{
    let mut taken: HashSet<String> = HashSet::new();
    let mut result: Vec<String> = Vec::new();
    for name in names {
        let name = name.as_ref();
        let mut candidate = name.to_owned();
        let mut ordinal = 2u32;
        while taken.contains(&candidate.to_uppercase()) {
            let suffix = format!(" ({ordinal})");
            let room = SHEET_NAME_MAX - suffix.chars().count();
            let base = text::strip(text::truncate_chars(name, room));
            let base = if base.is_empty() {
                SHEET_FALLBACK
            } else {
                base
            };
            candidate = format!("{base}{suffix}");
            ordinal += 1;
        }
        taken.insert(candidate.to_uppercase());
        result.push(candidate);
    }
    result
}
