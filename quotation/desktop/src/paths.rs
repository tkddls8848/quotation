//! 파일이 놓이는 자리. 여기가 이 앱의 **경로 정책**이고, 코어는 이것을 모른다.
use std::fs;
use std::path::{Path, PathBuf};

use quotation_core::modes::Mode;

pub const APP_NAME: &str = "QuotationTool";

/// 기준 템플릿을 EXE 안에 담는다.
///
/// 파이썬 판에서는 PyInstaller 가 임시 폴더에 풀어 주었지만, 여기서는 실행
/// 파일이 곧 하나이므로 바이트를 그대로 안고 간다. 저장소의 그 파일들이
/// 유일한 원본이라는 사실은 그대로다 (결정 0001).
const IBM: &[u8] = include_bytes!("../../python/quotation/resources/견적서_template_IBM.xlsx");
const LENOVO: &[u8] =
    include_bytes!("../../python/quotation/resources/견적서_template_Lenovo.xlsx");

pub fn template_name(mode: Mode) -> &'static str {
    match mode {
        Mode::Unix => "견적서_template_IBM.xlsx",
        Mode::Integrated => "견적서_template_Lenovo.xlsx",
    }
}

fn template_bytes(mode: Mode) -> &'static [u8] {
    match mode {
        Mode::Unix => IBM,
        Mode::Integrated => LENOVO,
    }
}

/// EXE 가 놓인 폴더.
pub fn app_dir() -> PathBuf {
    std::env::current_exe()
        .ok()
        .and_then(|exe| exe.parent().map(Path::to_path_buf))
        .unwrap_or_else(|| PathBuf::from("."))
}

/// EXE 옆의 **사용자 편집본** 템플릿. 없으면 한 번 만들어 둔다.
///
/// 견적서 번호와 머리말의 담당자 이름은 이 사본에서 고친다. 원본을 덮어쓰지
/// 않으므로 판을 올려도 고쳐 둔 것이 남는다.
pub fn template_path(mode: Mode) -> std::io::Result<PathBuf> {
    let path = app_dir().join(template_name(mode));
    if !path.exists() {
        fs::write(&path, template_bytes(mode))?;
    }
    Ok(path)
}

pub fn app_data_dir() -> std::io::Result<PathBuf> {
    let base = std::env::var_os("LOCALAPPDATA")
        .map(PathBuf::from)
        .unwrap_or_else(app_dir);
    let dir = base.join(APP_NAME);
    fs::create_dir_all(&dir)?;
    Ok(dir)
}

pub fn config_path() -> std::io::Result<PathBuf> {
    Ok(app_data_dir()?.join("config.json"))
}
