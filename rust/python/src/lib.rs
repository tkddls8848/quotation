//! `quotation.core` 안쪽에서 부르는 확장 모듈.
//!
//! 계획 §4 가 요구하는 것은 **구현 한 벌**이다. 브라우저는 WASM 으로, 데스크톱과
//! CI 는 이 확장으로 같은 Rust 코어를 부른다. 파이썬 쪽 공개 API
//! (`quotation.core.convert` 등)는 그대로 두고 안쪽만 바뀐다.
//!
//! `convert_bytes` 가 XML 한 건을 견적서 파일로 바꾼다. 나머지 함수는 규칙을
//! 하나씩 대조하기 위한 것이고, 파이썬 쪽 대조 하네스가 쓴다.

use pyo3::exceptions::{PyRuntimeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::PyBytes;

use quotation_core::writer::{self, Date};
use quotation_core::xml_reader;
use quotation_core::{modes, money, naming};

/// 금액 텍스트를 읽어 `("priced", "88971.5")` 꼴로 돌려준다.
///
/// 파이썬 쪽에서 `Decimal` 로 만드는 것은 호출자의 몫이다. 확장 경계에서
/// `Decimal` 을 직접 만들면 값이 부동소수를 지나갈 위험이 생긴다.
#[pyfunction]
fn parse_amount(raw: Option<&str>) -> PyResult<(String, String)> {
    match money::parse_amount(raw) {
        Ok(money::Amount::Priced(value)) => Ok(("priced".to_owned(), value.to_string())),
        Ok(money::Amount::NoCharge) => Ok(("nocharge".to_owned(), String::new())),
        Ok(money::Amount::Missing) => Ok(("missing".to_owned(), String::new())),
        Err(error) => Err(PyValueError::new_err(error.to_string())),
    }
}

#[pyfunction]
fn item_key(description: &str) -> String {
    naming::item_key(description)
}

#[pyfunction]
fn sheet_name(key: &str) -> String {
    naming::sheet_name(key)
}

#[pyfunction]
fn product_key(product_name: &str, description: &str) -> String {
    naming::product_key(product_name, description)
}

#[pyfunction]
fn safe_sheet_name(key: &str) -> String {
    naming::safe_sheet_name(key)
}

#[pyfunction]
fn unique_sheet_names(names: Vec<String>) -> Vec<String> {
    naming::unique_sheet_names(names)
}

#[pyfunction]
fn detect_mode(product_names: Vec<String>) -> String {
    modes::detect(product_names).as_str().to_owned()
}

#[pyfunction]
fn normalize_mode(raw: &str) -> PyResult<String> {
    modes::normalize(raw)
        .map(|mode| mode.as_str().to_owned())
        .map_err(|error| PyValueError::new_err(error.to_string()))
}

#[pyfunction]
fn resolve_mode(raw: Option<&str>, product_names: Vec<String>) -> PyResult<String> {
    modes::resolve(raw, product_names)
        .map(|mode| mode.as_str().to_owned())
        .map_err(|error| PyValueError::new_err(error.to_string()))
}

/// eConfig XML 바이트 -> 견적서 `.xlsx` 바이트.
///
/// 파이썬 `quotation.core.convert.convert_bytes` 와 같은 일을 한다. 날짜는
/// 부르는 쪽이 준다 — 달력을 코어에 들이지 않으려는 것이고, 같은 입력이 같은
/// 파일을 내게 하는 값이기도 하다.
#[pyfunction]
#[pyo3(signature = (xml, template, year, month, day, mode=None))]
fn convert_bytes<'py>(
    python: Python<'py>,
    xml: &[u8],
    template: &[u8],
    year: i32,
    month: u32,
    day: u32,
    mode: Option<&str>,
) -> PyResult<Bound<'py, PyBytes>> {
    let quotation = xml_reader::parse_bytes(xml, mode)
        .map_err(|error| PyValueError::new_err(error.to_string()))?;
    let book = writer::build_bytes(&quotation, template, Date { year, month, day })
        .map_err(|error| PyRuntimeError::new_err(error.to_string()))?;
    Ok(PyBytes::new(python, &book))
}

#[pymodule]
fn quotation_rust(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(convert_bytes, module)?)?;
    module.add_function(wrap_pyfunction!(parse_amount, module)?)?;
    module.add_function(wrap_pyfunction!(item_key, module)?)?;
    module.add_function(wrap_pyfunction!(sheet_name, module)?)?;
    module.add_function(wrap_pyfunction!(product_key, module)?)?;
    module.add_function(wrap_pyfunction!(safe_sheet_name, module)?)?;
    module.add_function(wrap_pyfunction!(unique_sheet_names, module)?)?;
    module.add_function(wrap_pyfunction!(detect_mode, module)?)?;
    module.add_function(wrap_pyfunction!(normalize_mode, module)?)?;
    module.add_function(wrap_pyfunction!(resolve_mode, module)?)?;
    Ok(())
}
