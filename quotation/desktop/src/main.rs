//! 견적서 작성기 — Windows 단일 EXE.
//!
//! EXE 에 XML 을 끌어다 놓으면 그 파일이 입력란에 채워진다.
#![windows_subsystem = "windows"]

use std::path::PathBuf;

use quotation_desktop::ui;

fn main() {
    let prefill = std::env::args_os()
        .nth(1)
        .map(PathBuf::from)
        .filter(|path| path.is_file());

    if let Err(error) = ui::run(prefill) {
        // 창을 못 띄웠으면 알릴 곳이 여기뿐이다. 콘솔이 없는 프로그램이다.
        let _ = native_windows_gui::init();
        native_windows_gui::error_message(ui::TITLE, &format!("창을 띄우지 못했습니다.\n{error}"));
    }
}
