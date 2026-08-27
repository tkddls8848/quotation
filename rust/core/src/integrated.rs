//! 레노버 x86 구성 파일(통합 모드)의 해석 규칙.
//! 파이썬 `quotation/core/integrated.py`.
//!
//! 문서 형식은 IBM eConfig Export 와 같다. 다른 것은 **값이 뜻하는 바** 이며,
//! 지금까지 확인된 차이는 둘뿐이다.
//!
//! 1. 장비 이름이 ProductDescription 이 아니라 ProductName 에 있다.
//!    한 파일에 같은 기종을 여러 대 담으면 설명이 전부 같고, 사람이 붙인 이름
//!    (`백업서버_1식`)만 장비를 구분한다.
//! 2. 본체 라인의 UnitListPrice 가 **그 서버 한 대의 전체 LP** 다. XML 의
//!    소프트웨어 라인은 자리표 1 원일 뿐이라 그대로 더하면 두 번 센다.
//!    요약표(`dcsc_summary`)를 읽으면 품목별 실금액을 적고, 못 읽으면 금액
//!    칸을 비운다. **어느 쪽이든 장비군 합계는 본체 LP 그대로다.**

use crate::dcsc_summary::{self, Summary};
use crate::models::LineItem;
use crate::money::{Amount, Decimal, is_priced, to_decimal};
use crate::naming::product_key;

/// 그룹의 본체 라인. CPUSIUvalue=1 인 하드웨어 라인이다.
pub fn body_index(items: &[LineItem]) -> Option<usize> {
    items
        .iter()
        .position(|item| item.siu == 1 && item.is_hardware())
}

/// 장비군 이름. 본체 라인의 ProductName 을 먼저 쓴다.
pub fn group_key(items: &[LineItem]) -> String {
    let line = body_index(items).map_or(&items[0], |index| &items[index]);
    product_key(&line.product_name, &line.description)
}

/// 본체 LP 에 이미 들어 있는 금액을 갈라 놓는다 (머리말 2번).
///
/// 값이 붙은 본체 라인이 있을 때만 손댄다. 랙·PDU·케이블처럼 본체 없이
/// 부품만 들어 있는 그룹은 저마다 제 금액을 가지므로 그대로 둔다.
pub fn fold_prices(items: Vec<LineItem>, summary: Option<&mut Summary>) -> Vec<LineItem> {
    let Some(body) = body_index(&items) else {
        return items;
    };
    if !is_priced(&items[body].unit_price) {
        return items;
    }

    let config =
        summary.and_then(|summary| summary.take(&items[body].part_number, &items[body].unit_price));
    if let Some(mut config) = config {
        if let Some(split) = split_prices(&items, body, &mut config) {
            return split;
        }
    }
    // 요약표가 없으면 하드웨어가 아닌 라인의 금액 칸을 비운다.
    items
        .into_iter()
        .map(|item| {
            if item.is_hardware() {
                item
            } else {
                LineItem {
                    unit_price: Amount::Missing,
                    ..item
                }
            }
        })
        .collect()
}

/// 요약표의 실금액을 라인에 적고 하드웨어는 남는 값으로 잡는다.
///
/// 남는 값에 자리표 몇 원과 소수 넷째 자리 반올림이 모이므로 장비군 합계는
/// 본체 LP 와 한 푼도 어긋나지 않는다.
///
/// 같은 품번이 그 장비군에 두 번 나오면 앞선 라인이 금액을 가져가고 뒤는
/// 비운다. 합계는 어느 쪽이든 같다.
///
/// 남는 값이 음수면 짝을 잘못 지은 것이므로 `None`.
fn split_prices(
    items: &[LineItem],
    body: usize,
    config: &mut dcsc_summary::Config,
) -> Option<Vec<LineItem>> {
    let mut priced: Vec<LineItem> = Vec::with_capacity(items.len());
    let mut others = Decimal::ZERO;
    for item in items {
        if item.is_hardware() {
            priced.push(item.clone());
            continue;
        }
        match config.take_price(&dcsc_summary::part_key(&item.part_number)) {
            // 요약표에 없거나 자리표뿐인 라인 (Configuration Instruction).
            None => priced.push(LineItem {
                unit_price: Amount::Missing,
                ..item.clone()
            }),
            Some(price) if price.is_zero() => priced.push(LineItem {
                unit_price: Amount::Missing,
                ..item.clone()
            }),
            Some(price) => {
                others += price;
                priced.push(LineItem {
                    unit_price: Amount::Priced(price),
                    ..item.clone()
                });
            }
        }
    }

    let rest = to_decimal(&items[body].unit_price) - others;
    if rest.is_sign_negative() {
        return None;
    }
    priced[body].unit_price = Amount::Priced(rest);
    Some(priced)
}
