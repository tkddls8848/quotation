//! 변환 모드. 파이썬 `quotation/core/modes.py`.
//!
//! 같은 eConfig 형식이라도 문서를 만든 구성기가 다르면 값의 뜻이 달라진다.
//! 모드는 **문서를 어떻게 읽을지** 를 고르는 것이며 견적서 양식은 하나뿐이다.
//!
//! ```text
//! UNIX        IBM eServer / TotalStorage eConfig Export
//! INTEGRATED  레노버 x86 (Lenovo DCSC) 구성 파일 — 통합 견적
//! ```
//!
//! 레노버 구성기만 본체 라인에 ProductName 을 적어 넣는다. 그래서 문서 자체가
//! 어느 쪽인지 알려 주며, 사람이 고를 필요가 없다 — `detect()` 하나로 정한다.

use crate::text;

pub const UNIX: &str = "unix";
pub const INTEGRATED: &str = "integrated";

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Mode {
    Unix,
    Integrated,
}

#[derive(Debug, PartialEq, Eq)]
pub struct ModeError {
    pub raw: String,
}

impl std::fmt::Display for ModeError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "모르는 변환 모드입니다: {}", self.raw)
    }
}

impl std::error::Error for ModeError {}

impl Mode {
    pub fn as_str(self) -> &'static str {
        match self {
            Mode::Unix => UNIX,
            Mode::Integrated => INTEGRATED,
        }
    }

    /// 진단 로그·안내문에 쓸 이름.
    pub fn label(self) -> &'static str {
        match self {
            Mode::Unix => "IBM 제품",
            Mode::Integrated => "통합",
        }
    }
}

impl std::fmt::Display for Mode {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(self.as_str())
    }
}

/// 문서 내용으로 읽는 방식을 고른다.
///
/// 본체 라인에 ProductName 이 있으면 레노버 x86(통합) 구성이고, 없으면 IBM
/// 문서다. IBM eConfig 는 이 항목을 쓰지 않는다.
pub fn detect<I, S>(product_names: I) -> Mode
where
    I: IntoIterator<Item = S>,
    S: AsRef<str>,
{
    if product_names
        .into_iter()
        .any(|name| !text::strip(name.as_ref()).is_empty())
    {
        Mode::Integrated
    } else {
        Mode::Unix
    }
}

/// 모드 문자열을 정규화한다. 자동 판정을 강제로 덮어쓸 때만 쓴다 (테스트용).
pub fn normalize(raw: &str) -> Result<Mode, ModeError> {
    match text::strip(raw).to_lowercase().as_str() {
        UNIX => Ok(Mode::Unix),
        INTEGRATED => Ok(Mode::Integrated),
        _ => Err(ModeError {
            raw: raw.to_owned(),
        }),
    }
}

/// 명시로 준 모드가 있으면 그대로 쓰고, 없으면 문서에서 알아낸다.
pub fn resolve<I, S>(raw: Option<&str>, product_names: I) -> Result<Mode, ModeError>
where
    I: IntoIterator<Item = S>,
    S: AsRef<str>,
{
    let text = text::strip(raw.unwrap_or(""));
    if text.is_empty() {
        Ok(detect(product_names))
    } else {
        normalize(text)
    }
}
