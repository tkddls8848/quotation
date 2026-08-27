//! 견적 변환 규칙의 Rust 코어.
//!
//! 파이썬 `quotation/core/` 를 그대로 옮긴다. 규칙을 바꾸지 않는 것이 이
//! 크레이트의 유일한 목표이고, 파이썬 구현이 언제나 기준이다
//! ([계획 §7](../../doc/plan/rust-wasm-core-plan.md)).

pub mod dcsc_summary;
pub mod integrated;
pub mod models;
pub mod modes;
pub mod money;
pub mod naming;
pub mod text;
pub mod xml_reader;
pub mod xmldom;
