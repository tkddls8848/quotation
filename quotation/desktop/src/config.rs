//! 최근 입력 폴더와 결과 열기 옵션. 파이썬 판이 쓰던 `config.json` 그대로다.
//!
//! 칸 이름을 바꾸지 않는 이유는 쓰던 사람의 설정을 그대로 읽기 위해서다.
use std::path::Path;

use serde::{Deserialize, Serialize};

use crate::paths;

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Config {
    #[serde(default)]
    pub last_input_dir: String,
    #[serde(default = "yes")]
    pub open_result_when_done: bool,
}

fn yes() -> bool {
    true
}

impl Default for Config {
    fn default() -> Self {
        Self {
            last_input_dir: String::new(),
            open_result_when_done: true,
        }
    }
}

impl Config {
    pub fn remember(&mut self, input: &Path) {
        if let Some(parent) = input.parent() {
            self.last_input_dir = parent.to_string_lossy().into_owned();
        }
    }
}

/// 읽지 못하면 기본값으로 시작한다. 설정 하나 때문에 앱이 서지 못할 이유가 없다.
pub fn load() -> Config {
    paths::config_path()
        .ok()
        .and_then(|path| std::fs::read_to_string(path).ok())
        .and_then(|text| serde_json::from_str(&text).ok())
        .unwrap_or_default()
}

pub fn save(config: &Config) {
    if let Ok(path) = paths::config_path() {
        if let Ok(text) = serde_json::to_string_pretty(config) {
            let _ = std::fs::write(path, text);
        }
    }
}
