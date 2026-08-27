//! 파이썬 `ibm_writer.build_bytes` 와 나란히 세워 두는 작성 탐침.
//!
//! ```text
//! workbook-probe TEMPLATE.xlsx OUT.xlsx YYYY-MM-DD < 구성.xml
//! ```
//!
//! 표준 입력의 XML 을 읽어 견적서를 만들고 파일로 적는다. 같은 입력으로 만든
//! 파이썬 산출물과 `tools/rust_parity_workbook.py` 가 셀 단위로 대조한다.

use std::io::{self, Read};
use std::process::ExitCode;

use quotation_core::writer::{self, Date};
use quotation_core::xml_reader;

fn main() -> ExitCode {
    let arguments: Vec<String> = std::env::args().skip(1).collect();
    let [template, output, day] = arguments.as_slice() else {
        eprintln!("usage: workbook-probe TEMPLATE.xlsx OUT.xlsx YYYY-MM-DD < 구성.xml");
        return ExitCode::from(2);
    };

    let mut xml = Vec::new();
    if let Err(error) = io::stdin().read_to_end(&mut xml) {
        eprintln!("표준 입력을 읽을 수 없습니다: {error}");
        return ExitCode::from(2);
    }
    let template_bytes = match std::fs::read(template) {
        Ok(bytes) => bytes,
        Err(error) => {
            eprintln!("템플릿을 읽을 수 없습니다: {error}");
            return ExitCode::from(2);
        }
    };
    let today = match parse_date(day) {
        Some(date) => date,
        None => {
            eprintln!("날짜는 YYYY-MM-DD 로 준다: {day}");
            return ExitCode::from(2);
        }
    };

    let quotation = match xml_reader::parse_bytes(&xml, None) {
        Ok(quotation) => quotation,
        Err(error) => {
            eprintln!("{error}");
            return ExitCode::from(1);
        }
    };
    let workbook = match writer::build_bytes(&quotation, &template_bytes, today) {
        Ok(bytes) => bytes,
        Err(error) => {
            eprintln!("{error}");
            return ExitCode::from(1);
        }
    };
    if let Err(error) = std::fs::write(output, workbook) {
        eprintln!("산출물을 적을 수 없습니다: {error}");
        return ExitCode::from(2);
    }
    ExitCode::SUCCESS
}

fn parse_date(text: &str) -> Option<Date> {
    let mut pieces = text.split('-');
    Some(Date {
        year: pieces.next()?.parse().ok()?,
        month: pieces.next()?.parse().ok()?,
        day: pieces.next()?.parse().ok()?,
    })
}
