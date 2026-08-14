# 견적서 작성기 (IBM Quotation Tool)

IBM eConfig Export XML을 기존 견적서 양식의 Excel 파일(`.xlsx`)로 변환합니다.
2005년 VB6 프로그램 `pConvertXMLtoExcel`을 다시 구현했으며, 지금은 **같은 변환
코어를 두 가지 방식으로 제공**합니다.

| 실행 방식 | 위치 | 상태 |
|---|---|---|
| 데스크톱 앱 (Windows 단일 EXE) | [`desktop/`](desktop/) | 운영 중 |
| 웹 앱 (Cloudflare Workers) | [`web/`](web/) | 구현 중 — [구현 계획서](doc/CLOUDFLARE_WORKERS_WEB_IMPLEMENTATION_PLAN.md) |

- Excel을 설치하지 않아도 변환할 수 있습니다.
- 상세 구성품·수량·LP 가격을 TOTAL 및 장비군별 상세 시트에 반영합니다.
- 증설 견적의 제거 부품은 음수 수량과 빨간 글씨로 표시합니다.
- 기존 양식의 로고와 머리말 도형을 보존합니다.

## 저장소 구조

앱(데스크톱)과 웹 파일은 섞이지 않습니다. 변환 규칙만 공용 코어에 한 벌 둡니다.

```text
quotation/              공용 코어 — Excel·GUI·경로에 의존하지 않는 순수 변환 로직
  core/
    xml_reader.py       eConfig XML 파서 (경로·바이트 입력, XXE 차단, 인코딩 처리)
    models.py           견적 데이터 모델
    money.py            금액 파싱 (콤마, N/C, Decimal)
    naming.py           종목 키 및 시트명 생성
    convert.py          변환 오케스트레이션 (convert / convert_bytes)
    resources.py        기준 템플릿 위치
    writer/             openpyxl 기반 견적서 작성 및 도형 보존
  resources/            기준 템플릿 (.xls 편집 원본과 .xlsx 배포본)

desktop/                데스크톱 전용 — 웹에서 쓰지 않는다
  quotation_desktop/    Tkinter 화면, 사용자 설정, 실행 경로
  launcher.py           PyInstaller 진입점
  QuotationTool.spec    단일 EXE 빌드 정의
  tools/                EXE 인수 테스트
  tests/                데스크톱 전용 테스트

web/                    웹 전용 — 데스크톱에서 쓰지 않는다
  src/                  Python Worker (worker/api/conversion_adapter/limits/errors/clock)
  frontend/             Vite + TypeScript SPA
  scripts/              코어 동기화, 템플릿 검증
  tests/                API·경계 테스트
  wrangler.jsonc        Workers 배포 정의

tests/                  공용 코어 테스트 + 익명화 fixture(tests/fixtures/public)
tools/                  공용 개발 도구 (골든 비교, 템플릿 덤프·변환)
doc/                    설계·구현 계획서
```

경계는 테스트로 지킵니다. `web/tests/test_worker_smoke.py` 는 Worker 층과 공용
코어가 `tkinter`·`quotation_desktop` 을 import 하지 못하게 막고,
`tests/test_bytes_api.py` 는 경로 입력(데스크톱)과 바이트 입력(웹)의 산출물이
셀 단위로 같은지 대조합니다.

## 데스크톱 앱 사용

1. `QuotationTool.exe`를 실행합니다.
2. eConfig Export XML 파일을 선택합니다. XML을 EXE 위로 끌어 놓아도 됩니다.
3. 필요하면 `완료 후 견적서 열기`를 선택하거나 해제합니다.
4. `변환`을 누릅니다.

결과 파일은 **항상 XML 파일과 같은 폴더**에 저장됩니다. 파일명은 XML과 같고
확장자만 `.xlsx`로 바뀝니다. 자세한 내용은 [desktop/README.md](desktop/README.md).

## 웹 앱

브라우저에서 XML을 올리면 서버가 같은 견적서를 만들어 바로 내려 줍니다. 올린
XML과 결과 파일은 서버에 저장하지 않습니다. 실행·배포 방법은
[web/README.md](web/README.md).

## 템플릿 사용자 지정

| 변경 항목 | 위치 |
|---|---|
| 견적서 번호 앞부분 | `TOTAL` 시트의 `B2` 셀 |
| 담당자 이름·회사 정보 | `TOTAL` 시트 상단의 머리말 도형 |

견적서 번호가 `Trialinfo-YY-` 형식이면 변환 시 연도 두 자리만 현재 연도로
갱신합니다(예: `NO : Trialinfo-26-`). 형식이 다르면 값은 그대로 둡니다.

**양식은 하나뿐입니다.** `quotation/resources/견적서_template.xlsx` 가 유일한
원본이며 데스크톱과 웹이 같은 파일을 씁니다. 다른 양식은 지원하지 않습니다.

- 데스크톱: 첫 실행 때 EXE 옆으로 복사되고, 그 사본을 사용자가 직접 고쳐 씁니다.
- 웹: 배포 직전 그 파일이 Worker 번들에 담깁니다. 바꾸려면 원본을 고쳐 커밋하고,
  되돌리려면 그 커밋을 되돌립니다.

## 개발

요구 사항: Python 3.11 이상. 웹 UI 작업에는 Node.js 22 이상. 템플릿의 원본
`.xls`를 다시 변환할 때만 Microsoft Excel이 필요합니다.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# 전체 테스트 (Excel 불필요)
.\.venv\Scripts\python.exe -m pytest tests web\tests desktop\tests -q

# 원본 .xls 템플릿을 다시 .xlsx 로 변환할 때만 실행 (Excel 필요)
.\tools\xls2xlsx.ps1

# 데스크톱 EXE 빌드
.\.venv\Scripts\python.exe -m pip install -r desktop\requirements.txt
.\.venv\Scripts\python.exe -m PyInstaller desktop\QuotationTool.spec --noconfirm --clean
.\desktop\tools\acceptance.ps1
```

`tests/test_writer.py`는 생성 파일을 골든 견적서와 셀 단위로 비교합니다. 값,
수식, 숫자 서식, 정렬, 글꼴, 병합, 열 너비, 인쇄 영역, 시트 순서 및 숨김 상태를
검증하며, 허용 예외는 근거와 함께 `tests/golden_ignore.txt`에 기록합니다. 골든과
실데이터(`samples/`)는 저장소에 담지 않으므로 해당 테스트는 자료가 없으면
건너뜁니다. 자료 없이도 도는 검증은 `tests/fixtures/public/` 의 익명화 fixture가
담당합니다.

셀 매핑과 상세 검증 기준은 [SPEC_CELLMAP.md](SPEC_CELLMAP.md), 기존 프로그램에서
달라진 동작의 상세는 [MIGRATION.md](MIGRATION.md)를 참고하십시오.

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
