//! wasm 안에 실린 템플릿의 판본을 내놓는다.
//!
//! `web/tests/test_browser_engine.py` 가 저장소의 양식과 같은지 대조한다.
//! 코어가 `include_bytes!` 로 싣는 파일이 바뀌면 여기 값이 달라진다.

use quotation_core::modes::Mode;
use quotation_webapi::templates;

fn main() {
    println!(
        "{{\"unix\": \"{}\", \"integrated\": \"{}\"}}",
        templates::version(Mode::Unix),
        templates::version(Mode::Integrated),
    );
}
