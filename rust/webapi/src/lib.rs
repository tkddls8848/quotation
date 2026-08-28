//! 요청 검증과 응답 매핑. 파이썬 `web/src/` 의 `api` · `limits` · `errors` ·
//! `conversion_adapter` · `clock` · `template` 을 한 크레이트로 옮긴 것이다.
//!
//! 브라우저에서 도는 것은 변환 코어만이 아니다. 파일 이름을 다듬고, 크기와
//! 형식을 거르고, 오류를 사용자 문구로 바꾸고, 응답 헤더를 짓는 일까지
//! 여기서 한다. 지금까지 그 일은 Pyodide 안의 파이썬이 했다.
//!
//! **화면과의 계약은 그대로다.** 같은 상태 코드, 같은 헤더, 같은 오류 문구,
//! 같은 로그 항목을 낸다. 그것을 `tools/rust_parity_webapi.py` 가 파이썬
//! 구현과 대조한다.

pub mod errors;
pub mod json;
pub mod limits;
pub mod names;
pub mod templates;
pub mod time;

use quotation_core::models::Quotation;
use quotation_core::writer::{self, Date};
use quotation_core::xml_reader;

pub use errors::ApiError;
pub use time::seoul_today;

/// 업로드된 파일 하나.
#[derive(Clone, Debug)]
pub struct Upload {
    pub filename: String,
    pub content: Vec<u8>,
    pub content_type: String,
}

/// 로그 항목의 값. 구조화 로그로 나가는 것만 담는다 (계획서 §13).
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum LogValue {
    Text(String),
    Int(i64),
}

/// 화면(그리고 서버)이 받는 응답.
#[derive(Clone, Debug)]
pub struct ApiResponse {
    pub status: u16,
    /// 파이썬 딕셔너리와 같은 순서로 담는다.
    pub headers: Vec<(String, String)>,
    pub body: Vec<u8>,
    pub log: Vec<(String, LogValue)>,
}

const XLSX_CONTENT_TYPE: &str = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";
const JSON_CONTENT_TYPE: &str = "application/json; charset=utf-8";

/// 계획서 §9. 정적 자산에는 `web/frontend/public/_headers` 가 같은 정책을 건다.
const SECURITY_HEADERS: [(&str, &str); 4] = [
    ("Cache-Control", "no-store"),
    ("X-Content-Type-Options", "nosniff"),
    ("Referrer-Policy", "no-referrer"),
    ("X-Frame-Options", "DENY"),
];

/// 브라우저가 붙일 수 있는 XML MIME. 확장자와 함께 참고만 하고 최종 판단은 파싱이다.
const XML_CONTENT_TYPES: [&str; 5] = [
    "text/xml",
    "application/xml",
    "text/plain",
    "application/octet-stream",
    "",
];

fn headers_with(extra: &[(&str, String)]) -> Vec<(String, String)> {
    let mut headers: Vec<(String, String)> = SECURITY_HEADERS
        .iter()
        .map(|(name, value)| ((*name).to_owned(), (*value).to_owned()))
        .collect();
    for (name, value) in extra {
        headers.push(((*name).to_owned(), value.clone()));
    }
    headers
}

fn json_response(
    status: u16,
    payload: String,
    request_id: &str,
    log: Vec<(String, LogValue)>,
) -> ApiResponse {
    ApiResponse {
        status,
        headers: headers_with(&[
            ("Content-Type", JSON_CONTENT_TYPE.to_owned()),
            ("X-Request-Id", request_id.to_owned()),
        ]),
        body: payload.into_bytes(),
        log,
    }
}

fn error_response(
    error: &ApiError,
    request_id: &str,
    base_log: &[(String, LogValue)],
) -> ApiResponse {
    let mut log = vec![
        ("outcome".to_owned(), LogValue::Text("error".to_owned())),
        (
            "error_code".to_owned(),
            LogValue::Text(error.code.to_owned()),
        ),
        ("status".to_owned(), LogValue::Int(error.status() as i64)),
    ];
    log.extend_from_slice(base_log);
    json_response(error.status(), error.payload(request_id), request_id, log)
}

/// 로그에 남길 크기 구간. 정확한 크기는 남기지 않는다 (계획서 §13).
pub fn size_bucket(size: usize) -> &'static str {
    const STEPS: [(usize, &str); 5] = [
        (64 * 1024, "<=64KiB"),
        (256 * 1024, "<=256KiB"),
        (limits::MIB, "<=1MiB"),
        (4 * limits::MIB, "<=4MiB"),
        (limits::MAX_UPLOAD_BYTES, "<=10MiB"),
    ];
    for (limit, label) in STEPS {
        if size <= limit {
            return label;
        }
    }
    ">10MiB"
}

/// `GET /api/v1/config` — 클라이언트가 1차 검사에 쓸 공개 설정.
pub fn config_response(request_id: &str) -> ApiResponse {
    json_response(
        200,
        limits::public_config(),
        request_id,
        vec![
            ("outcome".to_owned(), LogValue::Text("ok".to_owned())),
            ("status".to_owned(), LogValue::Int(200)),
        ],
    )
}

/// `GET /api/v1/status` — 배포 판본과 모드별 활성 템플릿 판본.
pub fn status_response(request_id: &str, deployment_version: &str) -> ApiResponse {
    let payload = format!(
        "{{\"deployment_version\": {}, \"template_versions\": {{\"unix\": {}, \"integrated\": {}}}}}",
        json::string(deployment_version),
        json::string(&templates::version(quotation_core::modes::Mode::Unix)),
        json::string(&templates::version(quotation_core::modes::Mode::Integrated)),
    );
    json_response(
        200,
        payload,
        request_id,
        vec![
            ("outcome".to_owned(), LogValue::Text("ok".to_owned())),
            ("status".to_owned(), LogValue::Int(200)),
        ],
    )
}

/// 한 요청에 파일 하나. 형식과 크기를 여기서 1차로 거른다.
fn pick_upload(upload: &Upload) -> Result<String, ApiError> {
    let name = names::safe_source_name(&upload.filename);
    if !name.to_lowercase().ends_with(limits::ALLOWED_SUFFIX) {
        return Err(errors::unsupported_media_type());
    }
    let media = upload
        .content_type
        .split(';')
        .next()
        .unwrap_or("")
        .trim()
        .to_lowercase();
    if !XML_CONTENT_TYPES.contains(&media.as_str()) {
        return Err(errors::unsupported_media_type());
    }
    if upload.content.len() > limits::MAX_UPLOAD_BYTES {
        return Err(errors::file_too_large(&format!(
            "XML 화일은 {} MiB 까지 올릴 수 있습니다.",
            limits::MAX_UPLOAD_BYTES / limits::MIB
        )));
    }
    Ok(name)
}

/// 변환에 성공했을 때 응답을 짓는 데 필요한 값.
struct Converted {
    xlsx: Vec<u8>,
    filename: String,
    group_count: usize,
    line_count: usize,
    mode: &'static str,
    template_version: String,
}

/// `POST /api/v1/convert` — 업로드 한 건을 견적서로 바꿔 바로 내려 준다.
///
/// 입력과 결과는 저장하지 않는다. 요청이 끝나면 함께 사라진다.
///
/// IBM 문서인지 레노버 x86 문서인지는 화면이 고르지 않는다. 업로드된 XML
/// 내용으로 알아내고, 그 모드에 맞는 템플릿을 그 뒤에 고른다.
pub fn convert_response(
    upload: &Upload,
    deployment_version: &str,
    request_id: &str,
    today: Date,
    elapsed_ms: i64,
) -> ApiResponse {
    let mut base_log = vec![(
        "deployment_version".to_owned(),
        LogValue::Text(deployment_version.to_owned()),
    )];

    let name = match pick_upload(upload) {
        Ok(name) => name,
        Err(error) => return error_response(&error, request_id, &base_log),
    };
    base_log.push((
        "input_size_bucket".to_owned(),
        LogValue::Text(size_bucket(upload.content.len()).to_owned()),
    ));

    let converted = match convert_upload(&upload.content, &name, today) {
        Ok(converted) => converted,
        Err(error) => return error_response(&error, request_id, &base_log),
    };

    let headers = headers_with(&[
        ("Content-Type", XLSX_CONTENT_TYPE.to_owned()),
        (
            "Content-Disposition",
            names::content_disposition(&converted.filename),
        ),
        ("Content-Length", converted.xlsx.len().to_string()),
        ("X-Request-Id", request_id.to_owned()),
        ("X-Template-Version", converted.template_version.clone()),
    ]);

    let mut log = base_log;
    log.extend([
        ("outcome".to_owned(), LogValue::Text("ok".to_owned())),
        ("status".to_owned(), LogValue::Int(200)),
        ("mode".to_owned(), LogValue::Text(converted.mode.to_owned())),
        (
            "template_version".to_owned(),
            LogValue::Text(converted.template_version),
        ),
        (
            "line_count".to_owned(),
            LogValue::Int(converted.line_count as i64),
        ),
        (
            "group_count".to_owned(),
            LogValue::Int(converted.group_count as i64),
        ),
        (
            "output_size_bucket".to_owned(),
            LogValue::Text(size_bucket(converted.xlsx.len()).to_owned()),
        ),
        ("total_ms".to_owned(), LogValue::Int(elapsed_ms)),
    ]);

    ApiResponse {
        status: 200,
        headers,
        body: converted.xlsx,
        log,
    }
}

/// 업로드된 XML 바이트 -> 견적서 바이트. 코어 오류를 API 오류로 분류한다.
fn convert_upload(xml: &[u8], source_name: &str, today: Date) -> Result<Converted, ApiError> {
    guard_document_size(xml)?;

    let quotation = xml_reader::parse_bytes(xml, None)
        // 원본 프로그램과 같은 문구를 그대로 사용자에게 보여 준다.
        .map_err(|error| errors::invalid_quotation_xml(&error.to_string()))?;

    let template = templates::bytes(quotation.mode);
    validate_template(template)?;

    if quotation.groups.len() > limits::MAX_GROUPS {
        return Err(errors::invalid_quotation_xml(&format!(
            "장비군이 너무 많습니다. (최대 {}개)",
            limits::MAX_GROUPS
        )));
    }
    if item_count(&quotation) > limits::MAX_LINE_ITEMS {
        return Err(errors::invalid_quotation_xml(&too_many_items()));
    }

    let xlsx = writer::build_bytes(&quotation, template, today)
        .map_err(|_| errors::conversion_failed())?;
    guard_output(&xlsx, quotation.groups.len())?;

    Ok(Converted {
        filename: names::output_name_for(source_name),
        group_count: quotation.groups.len(),
        line_count: quotation
            .groups
            .iter()
            .map(|group| group.items.len())
            .sum::<usize>(),
        mode: quotation.mode.as_str(),
        template_version: templates::version(quotation.mode),
        xlsx,
    })
}

fn too_many_items() -> String {
    format!(
        "구성 품목이 너무 많습니다. (최대 {}건)",
        json::thousands(limits::MAX_LINE_ITEMS)
    )
}

/// 나무를 만들기 전에 싸게 걸러 낸다.
fn guard_document_size(xml: &[u8]) -> Result<(), ApiError> {
    if xml.len() > limits::MAX_UPLOAD_BYTES {
        return Err(errors::file_too_large(&format!(
            "XML 화일은 {} MiB 까지 올릴 수 있습니다.",
            limits::MAX_UPLOAD_BYTES / limits::MIB
        )));
    }
    if xml.iter().all(u8::is_ascii_whitespace) {
        return Err(errors::invalid_request("빈 화일입니다."));
    }
    if rough_item_count(xml) > limits::MAX_LINE_ITEMS {
        return Err(errors::invalid_quotation_xml(&too_many_items()));
    }
    Ok(())
}

/// 파이썬 정규식 `<(?:ProductLineItem|ProductSubLineItem)[\s>]` 의 개수와 같다.
fn rough_item_count(xml: &[u8]) -> usize {
    let mut found = 0;
    for tag in [
        b"<ProductLineItem".as_slice(),
        b"<ProductSubLineItem".as_slice(),
    ] {
        let mut at = 0;
        while let Some(index) = find(&xml[at..], tag) {
            let end = at + index + tag.len();
            if xml
                .get(end)
                .is_some_and(|byte| byte.is_ascii_whitespace() || *byte == b'>')
            {
                found += 1;
            }
            at = end;
        }
    }
    found
}

fn find(haystack: &[u8], needle: &[u8]) -> Option<usize> {
    haystack
        .windows(needle.len())
        .position(|window| window == needle)
}

fn item_count(quotation: &Quotation) -> usize {
    quotation
        .groups
        .iter()
        .flat_map(|group| group.items.iter())
        .map(|item| 1 + item.subs.len())
        .sum()
}

/// 템플릿과 산출물에 반드시 있어야 하는 시트.
const REQUIRED_SHEETS: [&str; 2] = ["TOTAL", "template"];

/// 활성 템플릿이 쓸 만한지 검사한다.
fn validate_template(template: &[u8]) -> Result<(), ApiError> {
    if template.is_empty() {
        return Err(errors::template_unavailable());
    }
    let names = sheet_names(template).ok_or_else(errors::template_unavailable)?;
    if REQUIRED_SHEETS
        .iter()
        .any(|sheet| !names.iter().any(|name| name == sheet))
    {
        return Err(errors::template_unavailable());
    }
    Ok(())
}

fn guard_output(xlsx: &[u8], group_count: usize) -> Result<(), ApiError> {
    if xlsx.len() > limits::MAX_OUTPUT_BYTES {
        return Err(errors::invalid_quotation_xml(&format!(
            "생성된 견적서가 너무 큽니다. (최대 {} MiB)",
            limits::MAX_OUTPUT_BYTES / limits::MIB
        )));
    }
    let names = sheet_names(xlsx).ok_or_else(errors::conversion_failed)?;
    // TOTAL + 장비군별 상세 + 숨김 template
    if names.len() != group_count + 2
        || REQUIRED_SHEETS
            .iter()
            .any(|sheet| !names.iter().any(|name| name == sheet))
    {
        return Err(errors::conversion_failed());
    }
    Ok(())
}

/// xlsx(zip) 의 시트 이름. 워크북 전체를 열지 않고 목록만 읽는다.
fn sheet_names(xlsx: &[u8]) -> Option<Vec<String>> {
    use std::io::Read;

    let mut archive = zip::ZipArchive::new(std::io::Cursor::new(xlsx)).ok()?;
    let mut workbook = String::new();
    archive
        .by_name("xl/workbook.xml")
        .ok()?
        .read_to_string(&mut workbook)
        .ok()?;

    let mut names = Vec::new();
    let mut rest = workbook.as_str();
    while let Some(start) = rest.find("<sheet ") {
        let after = &rest[start..];
        let Some(end) = after.find('>') else { break };
        let tag = &after[..=end];
        if let Some(name) = attribute(tag, "name") {
            names.push(name);
        }
        rest = &after[end..];
    }
    Some(names)
}

fn attribute(tag: &str, name: &str) -> Option<String> {
    let needle = format!("{name}=\"");
    let start = tag.find(&needle)? + needle.len();
    let end = tag[start..].find('"')? + start;
    Some(tag[start..end].to_owned())
}
