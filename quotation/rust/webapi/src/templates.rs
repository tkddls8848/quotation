//! 활성 견적서 템플릿 — IBM 용·레노버 x86 용 두 벌.
//! 파이썬 `web/src/template.py` + `web/scripts/sync_core.py` 의 생성물.
//!
//! 템플릿은 코드와 함께 실려 나간다 ([결정 0001](../../../doc/decisions/0001-template-in-bundle.md)).
//! 요청마다 외부 저장소를 읽지 않으므로 네트워크 실패 지점이 없고, 배포된
//! 코드와 템플릿의 판본이 언제나 일치한다.
//!
//! 원본은 저장소의 `quotation/resources/` 파일 그대로이며 데스크톱 앱도 같은
//! 파일을 쓴다. 판본은 그 내용의 sha256 앞 12자리다.

use sha2::{Digest, Sha256};

use quotation_core::modes::Mode;

const IBM: &[u8] = include_bytes!("../../../quotation/resources/견적서_template_IBM.xlsx");
const LENOVO: &[u8] = include_bytes!("../../../quotation/resources/견적서_template_Lenovo.xlsx");

/// 모드별 활성 템플릿 바이트.
pub fn bytes(mode: Mode) -> &'static [u8] {
    match mode {
        Mode::Unix => IBM,
        Mode::Integrated => LENOVO,
    }
}

/// `X-Template-Version` 과 `/status` 에 쓰는 판본. 내용 해시다.
pub fn version(mode: Mode) -> String {
    let digest = Sha256::digest(bytes(mode));
    let hex: String = digest.iter().map(|byte| format!("{byte:02x}")).collect();
    format!("sha256-{}", &hex[..12])
}
