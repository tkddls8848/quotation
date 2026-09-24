//! 변환 한 건. 화면에서 떼어 놓아 그대로 시험한다.
//!
//! 파이썬 판의 `quotation/core/convert.py` 가 하던 일이다 — 코어를 부르고,
//! **어디에 저장할지**를 정하고, 진행률을 알린다. 변환 규칙은 한 줄도 여기
//! 없다.
use std::path::{Path, PathBuf};
use std::time::Instant;

use quotation_core::modes::Mode;
use quotation_core::writer::{self, Date};
use quotation_core::xml_reader;

pub const OUTPUT_SUFFIX: &str = "xlsx";

/// 화면이 보여 줄 결과.
pub struct Outcome {
    pub output: PathBuf,
    pub group_count: usize,
    pub elapsed: f64,
}

/// 사람에게 그대로 보여 줄 실패.
#[derive(Debug, PartialEq, Eq)]
pub enum Failure {
    /// XML 을 읽지 못했다. 코어가 낸 문구를 그대로 전한다.
    Xml(String),
    /// 저장할 파일이 다른 프로그램에서 열려 있다.
    Locked,
    /// 그 밖의 파일 문제.
    File(String),
    /// 템플릿을 열지 못했거나 견적서를 만들지 못했다.
    Build(String),
}

impl Failure {
    pub fn message(&self) -> String {
        match self {
            Failure::Xml(text) => text.clone(),
            Failure::Locked => {
                "저장할 파일이 다른 프로그램에서 열려 있습니다.\n해당 견적서를 닫고 다시 시도하십시오."
                    .to_owned()
            }
            Failure::File(text) => format!("파일을 저장하지 못했습니다.\n{text}"),
            Failure::Build(text) => text.clone(),
        }
    }
}

/// 출력 파일 이름. 입력의 기본 이름을 유지하고 확장자만 바꾼다.
pub fn output_name_for(xml_name: &str) -> String {
    let stem = Path::new(xml_name)
        .file_stem()
        .map(|s| s.to_string_lossy().into_owned())
        .filter(|s| !s.is_empty())
        .unwrap_or_else(|| "quotation".to_owned());
    format!("{stem}.{OUTPUT_SUFFIX}")
}

/// 출력 경로. **언제나 XML 과 같은 폴더**, 같은 이름, 확장자만 .xlsx.
pub fn output_path_for(xml: &Path) -> PathBuf {
    let name = output_name_for(
        &xml.file_name()
            .map(|n| n.to_string_lossy().into_owned())
            .unwrap_or_default(),
    );
    match xml.parent() {
        Some(dir) => dir.join(name),
        None => PathBuf::from(name),
    }
}

/// 한 건을 변환해 파일로 남긴다.
///
/// `template` 은 알아낸 읽기 방식(IBM/레노버)으로 템플릿을 고르는 함수다.
/// 어느 쪽인지는 문서를 읽어야 알므로 미리 고르지 않는다.
pub fn run(
    xml: &Path,
    today: Date,
    template: &dyn Fn(Mode) -> std::io::Result<PathBuf>,
    progress: &dyn Fn(u8, &str),
) -> Result<Outcome, Failure> {
    let started = Instant::now();

    progress(5, "XML파일을 읽고 있습니다.");
    let bytes = std::fs::read(xml).map_err(|error| Failure::File(error.to_string()))?;

    // 파이썬 판은 모드 판별과 변환에서 문서를 두 번 읽었다. 한 번만 읽는다.
    let quotation =
        xml_reader::parse_bytes(&bytes, None).map_err(|error| Failure::Xml(error.to_string()))?;

    progress(35, "XML파일 분석을 완료하였습니다.");
    let template_path =
        template(quotation.mode).map_err(|error| Failure::File(error.to_string()))?;
    let template_bytes =
        std::fs::read(&template_path).map_err(|error| Failure::File(error.to_string()))?;
    let out = output_path_for(xml);

    progress(45, "Excel파일을 생성하고 있습니다.");
    let book = writer::build_bytes(&quotation, &template_bytes, today)
        .map_err(|error| Failure::Build(error.to_string()))?;

    std::fs::write(&out, &book).map_err(|error| match error.kind() {
        std::io::ErrorKind::PermissionDenied => Failure::Locked,
        _ => Failure::File(error.to_string()),
    })?;

    progress(100, "견적서작성을 완료하였습니다.");
    Ok(Outcome {
        output: out,
        group_count: quotation.groups.len(),
        elapsed: started.elapsed().as_secs_f64(),
    })
}

/// 오늘 날짜. 코어는 시계를 읽지 않으므로 여기서 정한다.
pub fn today() -> Date {
    use chrono::Datelike;
    let now = chrono::Local::now().date_naive();
    Date {
        year: now.year(),
        month: now.month(),
        day: now.day(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn 출력은_입력과_같은_폴더에_확장자만_바뀐다() {
        let out = output_path_for(Path::new(r"C:\견적\2026\입력.xml"));
        assert_eq!(out, PathBuf::from(r"C:\견적\2026\입력.xlsx"));
    }

    #[test]
    fn 이름이_없으면_기본_이름을_쓴다() {
        assert_eq!(output_name_for(""), "quotation.xlsx");
    }

    #[test]
    fn 이름이_점으로_시작하면_그것이_이름이다() {
        // 파이썬 판(`Path(".xml").stem`)도 ".xml" 을 이름으로 본다. 흔한 입력은
        // 아니지만 두 판이 다른 파일을 만들면 안 되므로 그대로 못박는다.
        assert_eq!(output_name_for(".xml"), ".xml.xlsx");
    }

    #[test]
    fn 점이_여럿이어도_마지막_확장자만_바꾼다() {
        assert_eq!(output_name_for("2026.03.견적.xml"), "2026.03.견적.xlsx");
    }

    #[test]
    fn 잠긴_파일은_사람이_읽을_문구로_알린다() {
        assert!(
            Failure::Locked
                .message()
                .contains("다른 프로그램에서 열려 있습니다")
        );
        assert_eq!(
            Failure::Xml("빈 파일입니다.".into()).message(),
            "빈 파일입니다."
        );
    }
}
