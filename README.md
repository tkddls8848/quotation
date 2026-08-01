# 견적서 작성기 (IBM Quotation Tool)

IBM eConfig Export XML 을 견적서 Excel 로 변환한다.
2005년 VB6 프로그램(`pConvertXMLtoExcel`)을 Windows 11 / Excel 365 환경에 맞춰 재구현했다.

기존 양식을 유지하면서 상세 구성품, 수량, LP 가격을 `.xlsx` 견적서로 변환한다.
날짜·크기·글꼴 등 일부 표현은 실행 환경과 템플릿에 따라 달라질 수 있다.

---

## 사용법

### GUI
`QuotationTool.exe` 를 실행한다. XML 을 EXE 위로 끌어다 놓으면 그 화일이 채워진 채로 열린다.

| 항목 | 설명 |
|---|---|
| XML 화일 | 변환할 eConfig Export XML |
| 완료 후 견적서 열기 | 변환이 끝나면 만든 견적서를 바로 연다 (알림창은 뜨지 않는다) |
| 템플릿 열기 | 견적서 번호와 담당자 이름을 고칠 때 쓴다 (아래 참조) |

**견적서는 언제나 XML 과 같은 폴더에 저장된다.** 이름도 같고 확장자만 `.xlsx` 다.

### 템플릿 — 견적서 번호와 담당자 수정

`견적서_template.xlsx` 는 **EXE 옆에 놓이는 별도 화일**이다. 처음 실행할 때 자동으로
만들어지며, 아래 두 가지를 여기서 고친다.

| 고칠 것 | 위치 |
|---|---|
| 견적서 번호 `NO : Trialinfo-YY-` | TOTAL 시트 **B2 셀** |
| `담당 : 시스템사업부 ○ ○ ○` | TOTAL 시트 상단 **머리말 도형** (그림 위 글상자) |

- 견적서 번호는 **연도 두 자리만 자동으로 갱신**된다. 결과는 언제나
  `NO : Trialinfo-26-` 형태이고 **연도 뒤에는 아무것도 붙지 않는다.**
  앞부분 문구는 템플릿에 적힌 그대로 유지되며, 형식이 다르면 아예 손대지 않는다.
- 담당자 이름과 회사 정보는 도형 안에 있어 프로그램이 건드리지 않는다. 템플릿에 적은
  그대로 나온다.
- 다른 템플릿을 쓰려면 `--template` 옵션이나 `QUOTATION_TEMPLATE` 환경 변수를 쓴다.

---

## 설치

무설치. EXE 를 원하는 폴더에 두면 된다. **Excel 이 설치되어 있지 않아도 동작한다.**

| 위치 | 내용 |
|---|---|
| EXE 옆 `견적서_template.xlsx` | **템플릿. 처음 실행 시 자동 생성, 사용자가 고치는 화일** |
| `%LOCALAPPDATA%\QuotationTool\config.json` | 설정 (최근 경로, 옵션) |
| `%LOCALAPPDATA%\QuotationTool\logs\` | 로그, 일자별 30일 보관 |

구버전 `견적서생성기.ini` 가 남아 있으면 최초 실행 시 자동으로 값을 옮긴다.

---

## 개발

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# 골든 .xls 를 .xlsx 로 변환 (개발 시점 1회, Excel 필요)
.\tools\xls2xlsx.ps1

# 테스트 (Excel 불필요)
.\.venv\Scripts\python.exe -m pytest tests -q

# 빌드
.\.venv\Scripts\python.exe -m PyInstaller QuotationTool.spec --noconfirm --clean

# 빌드된 GUI EXE 기동 시험
.\tools\acceptance.ps1
```

### 구조
```
quotation/
  core/            Excel·GUI 비의존 순수 로직
    money.py       금액 파싱 (콤마, N/C, Decimal)
    models.py      LineItem / SubLineItem / Group / Quotation
    naming.py      종목 키(최대 31자) 및 시트명
    xml_reader.py  eConfig XML 파서 (XXE 차단, 인코딩 자동 판별)
    convert.py     변환 오케스트레이션
    writer/
      ibm_writer.py  견적서 생성 (openpyxl 전용)
  ui/main_window.py  GUI
  config.py, paths.py, logging_setup.py
  resources/         견적서 템플릿
tools/               개발·검증 도구
tests/               단위 및 골든 회귀 테스트
```

### 검증 방식
`tests/test_writer.py` 가 생성물을 골든 견적서와 셀 단위로 대조한다.
값·수식·숫자서식·정렬·글꼴·볼드·병합·열너비·인쇄영역·시트 순서와 숨김 상태를 모두 본다.
예외는 `tests/golden_ignore.txt` 에 근거와 함께 기록한다.

셀 매핑과 검증 기준은 `SPEC_CELLMAP.md`, 기존 사용자 안내는 `MIGRATION.md`에 있다.

---

## 원본 대비 달라진 점

| 항목 | 2005년 원본 | 현재 |
|---|---|---|
| 변환 시간 | 수십 초~수 분 | **0.2초** |
| Excel 설치 | **필수** (Excel 2003) | 불필요 |
| 변환 중 Excel 사용 | 전부 종료해야 함 | **무관** |
| 출력 형식 | `.xls` | `.xlsx` |
| 설치 | 관리자 권한 + OCX 등록 | 무설치 단일 EXE |
| 비트수 | 32bit | 64bit |
| 설정 저장 | `Program Files` (유실됨) | `%LOCALAPPDATA%` |
| 로그 | 없음 | 일자별 파일 |
| 삼성 SDS 양식 | 있음 | 제거 |
| 유지정비료(H·I열) | 채움 | 제거. H열은 빈 칸으로 남는다 |
| 할인율 | 입력란 있음 | 제거. `공급가` 행은 수기 입력 |
| 저장 위치 | 선택 가능 | XML과 같은 폴더로 고정 |
