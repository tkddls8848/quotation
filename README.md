# 견적서 작성기 (IBM Quotation Tool)

IBM eConfig Export XML을 기존 견적서 양식의 Excel 파일(`.xlsx`)로 변환하는 Windows용 도구입니다. 2005년 VB6 프로그램 `pConvertXMLtoExcel`을 Windows 11 환경에서 다시 구현했습니다.

- Excel을 설치하지 않아도 변환할 수 있습니다.
- 상세 구성품·수량·LP 가격을 TOTAL 및 장비군별 상세 시트에 반영합니다.
- 증설 견적의 제거 부품은 음수 수량과 빨간 글씨로 표시합니다.
- 기존 양식의 로고와 머리말 도형을 보존합니다.

## 사용 방법

1. `QuotationTool.exe`를 실행합니다.
2. eConfig Export XML 파일을 선택합니다. XML을 EXE 위로 끌어 놓아도 파일 경로가 자동으로 채워집니다.
3. 필요하면 `완료 후 견적서 열기`를 선택하거나 해제합니다.
4. `변환`을 누릅니다.

결과 파일은 **항상 XML 파일과 같은 폴더**에 저장됩니다. 파일명은 XML과 같고 확장자만 `.xlsx`로 바뀝니다. 같은 이름의 결과 파일이 있으면 덮어쓰기 전에 확인합니다.

변환이 끝난 뒤 결과를 자동으로 열도록 선택한 경우, Windows에 연결된 기본 프로그램으로 파일을 엽니다. 따라서 변환 자체에는 Excel이 필요 없지만, 결과를 열어 보려면 `.xlsx`를 열 수 있는 프로그램이 필요합니다.

## 템플릿 사용자 지정

첫 실행 시 EXE와 같은 폴더에 `견적서_template.xlsx`가 만들어집니다. 이 파일은 사용자가 직접 편집하는 템플릿입니다. 화면의 `템플릿 열기(견적번호·담당자 수정)` 버튼으로 바로 열 수 있습니다.

| 변경 항목 | 위치 |
|---|---|
| 견적서 번호 앞부분 | `TOTAL` 시트의 `B2` 셀 |
| 담당자 이름·회사 정보 | `TOTAL` 시트 상단의 머리말 도형 |

견적서 번호가 `Trialinfo-YY-` 형식이면 변환 시 연도 두 자리만 현재 연도로 갱신합니다. 예를 들어 `NO : Trialinfo-26-`이 됩니다. 형식이 다르면 값은 그대로 둡니다. 담당자와 회사 정보는 템플릿의 도형 내용을 그대로 사용합니다.

## 저장 위치와 설정

| 위치 | 내용 |
|---|---|
| EXE 옆 `견적서_template.xlsx` | 자동 생성되는 사용자 편집용 템플릿 |
| `%LOCALAPPDATA%\QuotationTool\config.json` | 최근 XML 폴더와 결과 자동 열기 설정 |

## 개발

요구 사항: Python 3.x, Windows. 템플릿의 원본 `.xls`를 다시 변환할 때만 Microsoft Excel이 필요합니다.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# 테스트 (Excel 불필요)
.\.venv\Scripts\python.exe -m pytest tests -q --basetemp .cache\pytest

# 원본 .xls 템플릿을 다시 .xlsx로 변환할 때만 실행 (Excel 필요)
.\tools\xls2xlsx.ps1

# 단일 GUI EXE 빌드
.\.venv\Scripts\python.exe -m PyInstaller QuotationTool.spec --noconfirm --clean

# 빌드 산출물 기동 및 템플릿 생성 확인
.\tools\acceptance.ps1
```

## 프로젝트 구조

```text
quotation/
  core/                 Excel·GUI 비의존 변환 로직
    xml_reader.py       eConfig XML 파서 (XXE 차단, 인코딩 처리)
    models.py           견적 데이터 모델
    money.py            금액 파싱 (콤마, N/C, Decimal)
    naming.py           종목 키 및 시트명 생성
    convert.py          변환 오케스트레이션
    writer/             openpyxl 기반 견적서 작성 및 도형 보존
  ui/main_window.py     Tkinter GUI
  resources/            번들 템플릿
  config.py             사용자 설정
  paths.py              실행·템플릿·데이터 경로 처리
tools/                  변환·검증 보조 도구
tests/                  단위·골든 회귀·UI 스모크 테스트
```

`tests/test_writer.py`는 생성 파일을 골든 견적서와 셀 단위로 비교합니다. 값, 수식, 숫자 서식, 정렬, 글꼴, 병합, 열 너비, 인쇄 영역, 시트 순서 및 숨김 상태를 검증하며, 허용 예외는 근거와 함께 `tests/golden_ignore.txt`에 기록합니다.

셀 매핑과 상세 검증 기준은 [SPEC_CELLMAP.md](SPEC_CELLMAP.md), 기존 프로그램에서 달라진 동작의 상세는 [MIGRATION.md](MIGRATION.md)를 참고하십시오.

## 원본 대비 주요 변경 사항

| 항목 | 2005년 원본 | 현재 |
|---|---|---|
| 출력 형식 | `.xls` | `.xlsx` |
| Excel 설치 | 필수 | 변환에는 불필요 |
| 변환 중 Excel 사용 | 모두 종료 필요 | 무관 |
| 설치 | 관리자 권한 및 OCX 등록 | 단일 EXE 실행 |
| 비트수 | 32비트 | 64비트 빌드 |
| 설정 저장 | `Program Files` | `%LOCALAPPDATA%` |
| 삼성 SDS 양식 | 지원 | 지원하지 않음 |
| 유지정비료(H·I열) | 입력 | 제거, H열은 빈 칸 |
| 할인율 | 입력란 제공 | 제거, `공급가` 행은 수기 입력 |
| 저장 위치 | 선택 가능 | XML과 같은 폴더로 고정 |
