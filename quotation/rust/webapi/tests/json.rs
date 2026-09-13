//! 응답 본문의 JSON 은 사용자에게도 테스트에도 그대로 보인다.
//! 파이썬 `json.dumps(..., ensure_ascii=False)` 와 같은 글이어야 한다.

use quotation_webapi::json;

#[test]
fn escapes_the_way_python_does() {
    // 한글은 이스케이프하지 않는다 (ensure_ascii=False).
    assert_eq!(json::string("보통 문구"), r#""보통 문구""#);
    // 제어문자는 두 글자 이스케이프로 나가야 한다. 날것으로 나가면 JSON 이 깨진다.
    assert_eq!(json::string("줄\n바꿈"), r#""줄\n바꿈""#);
    assert_eq!(json::string("탭\t자리"), r#""탭\t자리""#);
    assert_eq!(json::string("복귀\r"), r#""복귀\r""#);
    assert_eq!(json::string("따옴표\""), r#""따옴표\"""#);
    assert_eq!(json::string("역슬래시\\"), r#""역슬래시\\""#);
    assert_eq!(json::string("벨\u{7}"), r#""벨\u0007""#);
}

#[test]
fn writes_thousands_like_python() {
    assert_eq!(json::thousands(5_000), "5,000");
    assert_eq!(json::thousands(200), "200");
    assert_eq!(json::thousands(1_234_567), "1,234,567");
}
