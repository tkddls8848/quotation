//! 진짜 XML 한 건을 끝까지 변환해 본다. 창 없이, 코어와 저장 경로 정책만으로.
use std::cell::RefCell;
use std::path::{Path, PathBuf};

use quotation_core::modes::Mode;
use quotation_core::writer::Date;
use quotation_desktop::convert;

fn repo_root() -> PathBuf {
    // quotation/desktop -> quotation -> 저장소 뿌리
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .unwrap()
        .parent()
        .unwrap()
        .to_path_buf()
}

fn template(mode: Mode) -> std::io::Result<PathBuf> {
    let name = match mode {
        Mode::Unix => "견적서_template_IBM.xlsx",
        Mode::Integrated => "견적서_template_Lenovo.xlsx",
    };
    Ok(repo_root()
        .join("quotation/python/quotation/resources")
        .join(name))
}

#[test]
fn 공개_fixture_를_견적서로_만든다() {
    let fixture = repo_root().join("quotation/tests/fixtures/public/new_quote.xml");
    if !fixture.is_file() {
        eprintln!("fixture 가 없어 건너뜁니다: {}", fixture.display());
        return;
    }

    let work = std::env::temp_dir().join(format!("quotation-desktop-{}", std::process::id()));
    std::fs::create_dir_all(&work).unwrap();
    let xml = work.join("new_quote.xml");
    std::fs::copy(&fixture, &xml).unwrap();

    // 진행률 콜백은 `Fn` 이다(창에서는 일꾼 실이 부른다). 시험에서도 같은 모양으로 받는다.
    let seen: RefCell<Vec<(u8, String)>> = RefCell::new(Vec::new());
    let outcome = convert::run(
        &xml,
        Date {
            year: 2026,
            month: 9,
            day: 24,
        },
        &template,
        &|percent, message| seen.borrow_mut().push((percent, message.to_owned())),
    );
    let outcome = outcome.unwrap_or_else(|failure| panic!("변환 실패: {}", failure.message()));

    // 결과는 XML 과 같은 폴더, 같은 이름, 확장자만 다르다.
    assert_eq!(outcome.output, work.join("new_quote.xlsx"));
    let bytes = std::fs::read(&outcome.output).unwrap();
    assert_eq!(&bytes[..2], b"PK", "xlsx 는 zip 이다");
    assert!(bytes.len() > 10_000, "너무 작다: {} bytes", bytes.len());
    assert!(outcome.group_count > 0, "장비군이 하나도 없다");

    // 진행률은 화면이 그대로 보여 주는 값이다. 순서와 끝값을 못박는다.
    let seen = seen.into_inner();
    let percents: Vec<u8> = seen.iter().map(|(percent, _)| *percent).collect();
    assert_eq!(percents, vec![5, 35, 45, 100]);
    assert!(seen.last().unwrap().1.contains("완료"));

    std::fs::remove_dir_all(&work).ok();
}
