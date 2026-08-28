# 견적서 작성기 (Quotation Tool)

eConfig Export XML을 기존 견적서 양식의 Excel 파일(`.xlsx`)로 변환합니다.
2005년 VB6 프로그램 `pConvertXMLtoExcel`을 다시 구현했으며, 지금은 **같은 변환
코어를 두 가지 방식으로 제공**합니다.

| 실행 방식 | 위치 | 상태 |
|---|---|---|
| 데스크톱 앱 (Windows 단일 EXE) | [`desktop_ibm/`](desktop_ibm/) | 운영 중 — IBM·레노버 x86 모두 지원 |
| 웹 앱 (Cloudflare Workers) | [`web/`](web/) | 운영 중 — [문서](doc/) |

웹 앱은 **브라우저 안에서** 변환합니다. Cloudflare Workers 무료 계정의 CPU
한도(요청당 10 ms)로는 견적서를 만들 수 없기 때문이며, 브라우저가 돌리는 것은
데스크톱이 쓰는 것과 **같은 Rust 코어**입니다 (WASM). 자세한 근거는
[web/README.md](web/README.md).

- Excel을 설치하지 않아도 변환할 수 있습니다.
- 상세 구성품·수량·LP 가격을 TOTAL 및 장비군별 상세 시트에 반영합니다.
- 증설 견적의 제거 부품은 음수 수량과 빨간 글씨로 표시합니다.
- 기존 양식의 로고와 머리말 도형을 보존합니다.

## IBM·레노버 판별

구성 파일을 만든 구성기에 따라 값의 뜻이 달라집니다. 사람이 고르지 않고
문서 내용으로 알아냅니다 — 레노버 구성기만 장비 본체 라인에 사람이 적어 넣은
이름(`ProductName`)을 남기기 때문입니다 (`rust/core/src/modes.rs`).

| 문서 | 판별 근거 | 무엇이 다른가 |
|---|---|---|
| IBM eServer and TotalStorage — eConfig Export | `ProductName` 없음 | 지금까지와 같습니다 |
| 레노버 x86 (Lenovo DCSC) | `ProductName` 있음 | 장비 이름을 구성기에 적어 넣은 이름으로 붙이고, 서버 본체 LP 에 이미 들어 있는 SW·서비스 금액을 두 번 세지 않습니다. 구성 파일에 담긴 DCSC 요약표를 읽어 H/W·S/W 금액을 갈라 적습니다 |

레노버 x86 판독 규칙의 근거는
[doc/spec/SPEC_INTEGRATED.md](doc/spec/SPEC_INTEGRATED.md) 에 있습니다.
데스크톱 앱과 웹 앱 모두 같은 판별을 쓰므로 두 문서를 가리지 않고 받습니다.

## 저장소 구조

앱(데스크톱)과 웹 파일은 섞이지 않습니다. 변환 규칙만 공용 코어에 한 벌 둡니다.

```text
rust/                   변환 규칙 — 여기 한 벌뿐이다
  core/                 XML 읽기부터 견적서 작성까지 (money·naming·modes·models·
                        xml_reader·integrated·dcsc_summary·writer)
  webapi/               요청 검증·응답 헤더·오류 문구 (브라우저가 쓴다)
  wasm/                 브라우저 진입점 (wasm-bindgen)
  python/               데스크톱·CI 용 확장 모듈 (PyO3, quotation_rust)
  tools/                판본 확인 같은 개발용 실행 파일
  roundtrip/            템플릿 도형 보존 확인용

quotation/              얇은 파이썬 얼굴 — 규칙은 없다
  core/
    convert.py          공개 API (convert / convert_bytes / document_mode)
    modes.py            모드 이름 (unix / integrated)
    xml_reader.py       QuotationXmlError (확장이 정의한 것을 그대로 쓴다)
    resources.py        기준 템플릿 위치
  resources/            기준 템플릿 (.xlsx 두 벌이 유일한 원본)

desktop_ibm/            데스크톱 전용 — 웹에서 쓰지 않는다
  quotation_desktop/    Tkinter 화면, 사용자 설정, 실행 경로
  launcher.py           PyInstaller 진입점
  QuotationTool.spec    단일 EXE 빌드 정의
  tools/                EXE 인수 테스트
  tests/                데스크톱 전용 테스트

web/                    웹 전용 — 데스크톱에서 쓰지 않는다
  frontend/             Vite + TypeScript SPA + 변환 일꾼
    src/engine.js       wasm 을 세우고 convert 를 부른다 (규칙 없음)
    public/engine/      배포 직전 만드는 엔진 자산 (추적하지 않음)
  scripts/              엔진 포장, 템플릿 검증, 배포 스크립트
  tests/                브라우저↔데스크톱 동일성 + 실제 Chromium E2E
  wrangler.jsonc        정적 자산 배포 (무료 계정)

tests/                  공개 API 회귀 + 익명화 fixture(tests/fixtures/public)
tools/                  개발 도구 (골든 비교, 내용 비교기, 템플릿 변환, 실측)
doc/                    성격별로 나눈 문서 — 명세·안내·계획·결정·사고·실측
```

**변환 규칙은 `rust/` 에 한 벌뿐입니다.** 데스크톱은 확장 모듈로, 브라우저는
WASM 으로 같은 코어를 부릅니다. 두 경로가 같은 견적서를 만드는지는
`web/tests/test_browser_parity.py` 가 매번 대조합니다.

`rust/`, `quotation/`, `tests/`, `tools/` 는 **데스크톱과 웹이 함께 쓰는 공용
자산**입니다. 어느 한쪽에 딸린 것이 아니므로 `desktop_ibm/` 이나 `web/` 아래로
옮기지 않습니다.

경계는 테스트로 지킵니다. `tests/test_bytes_api.py` 는 경로 입력(데스크톱)과
바이트 입력(웹)의 산출물이 같은지 보고, `web/tests/test_browser_parity.py` 와
`web/tests/test_browser_e2e.py` 는 브라우저(WASM)가 만든 견적서가 데스크톱
(확장 모듈) 산출물과 셀 단위로 같은지 대조합니다 — 실제 Chromium 으로 받아 본
파일까지 같은 기준으로 봅니다.

## 데스크톱 앱 사용

1. `QuotationTool.exe`를 실행합니다.
2. eConfig Export XML 파일을 선택합니다. XML을 EXE 위로 끌어 놓아도 됩니다.
3. 필요하면 `완료 후 견적서 열기`를 선택하거나 해제합니다.
4. `변환`을 누릅니다.

결과 파일은 **항상 XML 파일과 같은 폴더**에 저장됩니다. 파일명은 XML과 같고
확장자만 `.xlsx`로 바뀝니다. 자세한 내용은 [desktop_ibm/README.md](desktop_ibm/README.md).

## 웹 앱

브라우저에서 XML을 고르면 **그 자리에서** 같은 견적서를 만들어 내려받습니다.
XML도 결과 파일도 네트워크를 타지 않습니다. 처음 한 번 변환기(약 1 MiB)를
내려받은 뒤로는 다시 받지 않습니다.

데스크톱과 같은 Rust 코어를 브라우저가 WASM 으로 돌립니다. 결과가 같은지는
테스트가 매번 셀 단위로 대조하고, 실제 Chromium 으로 받아 본 파일까지 같은
기준으로 봅니다. 실행·배포 방법과 근거는 [web/README.md](web/README.md).

## 템플릿 사용자 지정

| 변경 항목 | 위치 |
|---|---|
| 견적서 번호 앞부분 | `TOTAL` 시트의 `B2` 셀 |
| 담당자 이름·회사 정보 | `TOTAL` 시트 상단의 머리말 도형 |

견적서 번호가 `Trialinfo-YY-` 형식이면 변환 시 연도 두 자리만 현재 연도로
갱신합니다(예: `NO : Trialinfo-26-`). 형식이 다르면 값은 그대로 둡니다.

**양식은 IBM 용·레노버 x86 용 둘뿐입니다.**
`quotation/resources/견적서_template_IBM.xlsx` 와 `..._Lenovo.xlsx` 가 유일한
원본이며 데스크톱과 웹이 같은 파일을 씁니다. 어느 것을 쓸지는 문서에서 알아낸
읽기 방식(위 "IBM·레노버 판별")이 정하며, 다른 양식은 지원하지 않습니다.

- 데스크톱: 첫 실행 때 둘 다 EXE 옆으로 복사되고, 그 사본을 사용자가 직접
  고쳐 씁니다.
- 웹: 배포 직전 두 파일이 브라우저 변환 엔진에 담깁니다. 바꾸려면 원본을 고쳐
  커밋하고, 되돌리려면 그 커밋을 되돌립니다.

## 개발

요구 사항: Python 3.11 이상, **Rust 툴체인**(변환 규칙이 거기 있습니다). 웹 UI 작업에는 Node.js 22 이상. `.xls` 골든
견적서를 `.xlsx` 로 변환할 때만 Microsoft Excel이 필요합니다.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt maturin

# 변환 코어 확장 빌드와 설치 (파이썬 쪽 테스트·데스크톱이 이것을 부른다)
.\.venv\Scripts\python.exe -m maturin build --release -m rust\python\Cargo.toml --out target\wheels
.\.venv\Scripts\python.exe -m pip install --force-reinstall target\wheels\quotation_rust-0.1.0-cp311-abi3-win_amd64.whl

# 브라우저 엔진 자산 (web/tests 를 돌리기 전에 한 번)
cargo install wasm-pack
.\.venv\Scripts\python.exe web\scripts\build_browser_engine.py

# 전체 테스트 (Excel 불필요)
.\.venv\Scripts\python.exe -m pytest -q

# 변환 규칙 자체의 테스트와 실측
cargo test
node tools\wasm_startup_bench.mjs

# samples\ 의 .xls 골든을 .cache\ 로 변환할 때만 실행 (Excel 필요)
.\tools\xls2xlsx.ps1

# 데스크톱 EXE 빌드 (산출물은 desktop_ibm\dist, 중간물은 desktop_ibm\build)
.\.venv\Scripts\python.exe -m pip install -r desktop_ibm\requirements.txt
.\.venv\Scripts\python.exe -m PyInstaller desktop_ibm\QuotationTool.spec --noconfirm --clean `
    --distpath desktop_ibm\dist --workpath desktop_ibm\build
.\desktop_ibm\tools\acceptance.ps1
```

`tests/` 는 생성 파일을 골든 견적서와 셀 단위로 비교합니다. 값, 수식, 숫자
서식, 정렬, 글꼴, 병합, 열 너비, 인쇄 영역, 시트 순서 및 숨김 상태를 검증하며,
허용 예외는 근거와 함께 `tests/golden_ignore.txt`에 기록합니다. 골든과
실데이터(`samples/`)는 저장소에 담지 않으므로 해당 테스트는 자료가 없으면
건너뜁니다. 자료 없이도 도는 검증은 `tests/fixtures/public/` 의 익명화 fixture가
담당합니다.

파일 전체 바이트는 재현되지 않습니다 — 스타일표의 나열 순서와 zip 이 적는
시각이 실행마다 달라집니다. 내용은 재현됩니다
([결정 0011](doc/decisions/0011-no-byte-reproducibility.md)).

셀 매핑과 상세 검증 기준은 [doc/spec/SPEC_CELLMAP.md](doc/spec/SPEC_CELLMAP.md),
기존 프로그램에서 달라진 동작의 상세는
[doc/guide/MIGRATION.md](doc/guide/MIGRATION.md)를 참고하십시오. 설계 경위와
실측은 [doc/](doc/) 에 성격별로 나눠 두었습니다.

## 원본 대비 주요 변경 사항

| 항목 | 2005년 원본 | 현재 |
|---|---|---|
| 출력 형식 | `.xls` | `.xlsx` |
| Excel 설치 | 필수 | 변환에는 불필요 |
| 변환 중 Excel 사용 | 모두 종료 필요 | 무관 |
| 설치 | 관리자 권한 및 OCX 등록 | 단일 EXE 실행 또는 브라우저 |
| 비트수 | 32비트 | 64비트 빌드 |
| 설정 저장 | `Program Files` | `%LOCALAPPDATA%` (웹은 저장하지 않음) |
| 유지정비료(H·I열) | 입력 | 제거, H열은 빈 칸 |
| 할인율 | 입력란 제공 | 제거, `공급가` 행은 수기 입력 |
| 저장 위치 | 선택 가능 | XML과 같은 폴더 고정 (웹은 브라우저 다운로드) |
| XML 인코딩 | EUC-KR | 그대로 지원. 선언된 인코딩을 코어가 직접 읽는다 |
