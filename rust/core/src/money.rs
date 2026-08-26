//! 금액 파싱 — eConfig MonetaryAmount 전용. 파이썬 `quotation/core/money.py`.
//!
//! SPEC_CELLMAP.md §1.2
//!
//! ```text
//! "88,971.5"  -> 88971.5
//! "N/C"       -> NoCharge   (셀에 문자열 "N/C" 기록, 합계에서 0)
//! "0"         -> 0
//! 없음 / ""   -> Missing    (셀 비움)
//! ```
//!
//! 부동소수를 쓰지 않는다. 원본 소수점 자릿수를 그대로 보존해야 골든과 같다.
//!
//! 레노버 DCSC 는 큰 금액을 지수 표기로 적는다 (`4.0172E7`). 파이썬 `Decimal`
//! 이 이를 받으므로 여기서도 받는다. 파이썬은 지수 형태를 글로 옮길 때도
//! `4.0172E+7` 로 두지만, 셀에 실제로 적히는 것은 openpyxl 이 만든 자릿수
//! 표기(`40172000`)다. 그래서 이 크레이트는 값만 같게 유지하고 지수 형태는
//! 남기지 않는다.
//!
//! 유효자릿수 28 자리를 넘는 값은 오류로 돌려준다. 조용히 반올림해 다른
//! 숫자를 만드는 것보다 멈추는 편이 낫다.

use std::str::FromStr;

use rust_decimal::Decimal;

use crate::text;

/// 파이썬 `money.Amount` (`Decimal | NoCharge | None`).
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum Amount {
    Priced(Decimal),
    /// 무상(N/C) 표식. 합계에서는 0 으로 접힌다.
    NoCharge,
    /// 값이 없다. 셀을 비운다.
    Missing,
}

#[derive(Debug, PartialEq, Eq)]
pub struct AmountError {
    pub raw: String,
}

impl std::fmt::Display for AmountError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "금액을 읽을 수 없습니다: {}", self.raw)
    }
}

impl std::error::Error for AmountError {}

/// MonetaryAmount 텍스트 -> `Amount`.
pub fn parse_amount(raw: Option<&str>) -> Result<Amount, AmountError> {
    let Some(raw) = raw else {
        return Ok(Amount::Missing);
    };
    let text = text::strip(raw);
    if text.is_empty() {
        return Ok(Amount::Missing);
    }
    if text == "N/C" {
        return Ok(Amount::NoCharge);
    }
    let digits = text.replace(',', "");
    parse_decimal(&digits)
        .map(Amount::Priced)
        .ok_or_else(|| AmountError {
            raw: raw.to_owned(),
        })
}

/// 자릿수 표기와 지수 표기를 모두 읽는다. 반올림은 하지 않는다.
fn parse_decimal(digits: &str) -> Option<Decimal> {
    if let Ok(value) = Decimal::from_str_exact(digits) {
        return Some(value);
    }
    if digits.contains(['e', 'E']) {
        return Decimal::from_scientific(digits).ok();
    }
    None
}

/// 합계 계산용. N/C 와 없음은 0 으로 접는다.
pub fn to_decimal(amount: &Amount) -> Decimal {
    match amount {
        Amount::Priced(value) => *value,
        Amount::NoCharge | Amount::Missing => Decimal::ZERO,
    }
}

/// 실제 금액이 붙어 있는가 (N/C·없음 제외).
pub fn is_priced(amount: &Amount) -> bool {
    matches!(amount, Amount::Priced(_))
}

impl FromStr for Amount {
    type Err = AmountError;

    fn from_str(raw: &str) -> Result<Self, Self::Err> {
        parse_amount(Some(raw))
    }
}

impl std::fmt::Display for Amount {
    /// 셀에 적히는 표현. `N/C` 는 문자열 그대로, 없음은 빈 칸이다.
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Amount::Priced(value) => write!(f, "{value}"),
            Amount::NoCharge => f.write_str("N/C"),
            Amount::Missing => Ok(()),
        }
    }
}
