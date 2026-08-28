//! 견적 날짜. 파이썬 `web/src/clock.py`.
//!
//! 견적서의 날짜 칸은 한국 영업일 기준이어야 한다. 대한민국은 1988년 이후
//! 서머타임이 없어 UTC+9 고정 오프셋으로 충분하다 — 시간대 자료를 싣지 않는다.

use quotation_core::writer::Date;

const KST_OFFSET_MS: i64 = 9 * 60 * 60 * 1000;
const DAY_MS: i64 = 24 * 60 * 60 * 1000;

/// 에포크 밀리초 -> Asia/Seoul 날짜.
pub fn seoul_today(epoch_ms: i64) -> Date {
    let days = (epoch_ms + KST_OFFSET_MS).div_euclid(DAY_MS);
    civil_from_days(days)
}

/// 1970-01-01 부터의 날짜 수 -> 달력 날짜 (Howard Hinnant 의 방법).
fn civil_from_days(days: i64) -> Date {
    let z = days + 719_468;
    let era = z.div_euclid(146_097);
    let day_of_era = z - era * 146_097;
    let year_of_era =
        (day_of_era - day_of_era / 1_460 + day_of_era / 36_524 - day_of_era / 146_096) / 365;
    let year = year_of_era + era * 400;
    let day_of_year = day_of_era - (365 * year_of_era + year_of_era / 4 - year_of_era / 100);
    let shifted_month = (5 * day_of_year + 2) / 153;
    let day = day_of_year - (153 * shifted_month + 2) / 5 + 1;
    let month = if shifted_month < 10 {
        shifted_month + 3
    } else {
        shifted_month - 9
    };
    Date {
        year: (year + i64::from(month <= 2)) as i32,
        month: month as u32,
        day: day as u32,
    }
}
