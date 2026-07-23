# IBM 견적서 생성기 (Quotation Tool V2.0) 전면 리팩토링 계획

- 문서 작성일: 2026-07-23
- 대상: `pConvertXMLtoExcel-2005-05-13.exe` (VB6, 2005) → 2026년 Windows 11 기준 재구현
- 원칙: **입력(eConfig XML)과 출력(견적서 Excel)은 완전히 동일**, 변환 로직/실행 환경만 전면 교체

---

## 1. 현행 시스템 분석 (역공학 결과)

### 1.1 배포 패키지 구성
`setup.exe` + `SETUP.LST` + `pConvertXMLtoExcel-2005-05-13.CAB` 는 **VB6 Package & Deployment Wizard** 산출물이다. CAB 전개 결과:

| 구분 | 파일 |
|---|---|
| 본체 | `pConvertXMLtoExcel-2005-05-13.exe` (256KB, VB6 네이티브 컴파일) |
| 런타임 | `msvbvm60.dll`, `VB6KO.DLL`, `OLEAUT32/OLEPRO32/ASYCFILT/COMCAT/MSVCRT.DLL`, `STDOLE2.TLB` |
| ActiveX (자체등록) | `MSCOMCTL.OCX`(ProgressBar), `COMDLG32.OCX`(파일선택), `MSMASK32.OCX`(MaskEdBox), `MSSTDFMT.DLL` |
| 파서 | `msxml.dll` **(MSXML 2.x / 2004년판)** |
| 기타 | `scrrun.dll`(FileSystemObject), 한국어 리소스 DLL 5종 |
| 데이터 | `견적서_template.xls`, `삼성 B2B 견적서 양식_견적작성기 참조용.xls`, `ReadMe.txt` |

`ReadMe.txt` 명시 요구사항: **"Excel XP(2003) 필요, 없으면 실행 시 심각한 오류 발생"**. 현재 환경은 Excel 16.0(Microsoft 365)이며, 이것이 장애의 근원이다.

### 1.2 프로그램 구조 (EXE 문자열/임포트 분석)
- `Form1` : 메인 화면. 컨트롤 = `optIBM`/`optSDS`(출력 양식 선택 라디오), `Check_MA`(유지정비료 포함 여부), `Text1`(할인율), `MaskEdBox`, `ProgressBar1`, `OpenDLG`(CommonDialog), `Command1~4`
- `Form2` : 보조 화면
- `Module1`, `Module2` : 변환 로직
- 설정 저장: `견적서생성기.ini` + Win32 API `GetPrivateProfileStringA` / `WritePrivateProfileStringA`
- 확인된 내부 프로시저명: `MakeServerSheet`, `MakeTotalSheet`, `WriteExcel`, `WriteSDSExcel`, `DecorateTOTSheet`, `GetServerName`, `DeleteExcel`, `INIReadWrite`, `Check_MA`

### 1.3 입력 XML 스키마 (RosettaNet 계열 eConfig Export)
선언: `<?xml version="1.0" encoding="EUC-KR"?>`

탐색 경로(XPath, 프로그램 내 하드코딩):

```
/CFXML                      … 루트. 없으면 "CFXML을 찾을수 없습니다."
  ./CFData                  … 없으면 "CFData을 찾을수 없습니다."
    .//ProductLineItem      … 없으면 "견적서 작성을 위한 Item을 찾을 수 없습니다."
      ./TransactionType
      ./ProductLineNumber
      ./ProprietaryGroupIdentifier
      ./Quantity
      ./ProductIdentification/PartnerProductIdentification/ProductDescription
      ./ProductIdentification/PartnerProductIdentification/ProductTypeCode
      ./ProductIdentification/PartnerProductIdentification/ProprietaryProductIdentifier
      ./UnitListPrice/FinancialAmount/GlobalCurrencyCode
      ./UnitListPrice/FinancialAmount/MonetaryAmount
      ./UnitListPrice/PriceTerm
      ./MaintenanceUnitListPrice/FinancialAmount/GlobalCurrencyCode
      ./MaintenanceUnitListPrice/FinancialAmount/MonetaryAmount
      ./MaintenanceUnitListPrice/PriceTerm
      .//ProductSubLineItem … (하위 구성품 재귀)
```

`TransactionType` 분류 키워드: `BASE`, `PROPOSED`, `REMOVE`, `HARDWARE`, `FMOD`, `DISCO`, `CONVERSION`, `UPGRADE`
→ 이 값에 따라 라인 아이템의 견적서 포함/제외 및 시트 배치가 결정됨.

### 1.4 장비 분류 규칙 (`GetServerName` / `MakeServerSheet` 내 하드코딩 문자열)
Description 문자열 매칭으로 시트를 분리 생성한다:

```
Storage 계열 : "Storage", "Solutions", "Total", "Tape Library",
               "200GB", "400GB", "1.8M", "2.0M",
               "Ultri.", "Ultr.", "ultrium", "ultrium 2/3/4",
               "Scalable", "DS6000 Expansion", "DS8000 Expansion",
               "exp storage plus", "EXP700"
Server 계열  : "Server", "Entr"
```
→ 장비군별로 **시트 1장씩 생성**한 뒤 `MakeTotalSheet`로 종합 시트를 만든다.

> ⚠️ **Phase 0 실측 결과 정정**: 2026년 실제 eConfig XML에서는 이 키워드 매칭 경로가 **사용되지 않는다**.
> 시트 분리는 `ProprietaryGroupIdentifier` 값(1000/4000/7000 …)으로 이루어지며, 시트명은
> `ProductDescription` 접두어에서 생성된다. 상세는 `SPEC_CELLMAP.md` §2.1.
> 위 키워드 목록은 구형 XML 호환용 폴백으로만 보존한다.

### 1.5 출력 Excel 사양 (템플릿 실측)
`견적서_template.xls` — 시트 2장, 사용범위 `$B$1:$I$93`

**[template] 시트 (개별 장비군 시트, IBM 양식)**

| 셀 | 내용 |
|---|---|
| B5 | `세 부 내 역` / H5 `(단위: 천원, 부가세 별도)` |
| B6~H6 | 종 목 / 모델 번호 / DESCRIPTION / 수 량 / 단위가 / 금액 / 비고 |
| B7~H7 | ITEM / MODEL NO. / (공백) / Q'TY / UNIT PRICE / AMOUNT / DESCRIPTION |
| **8행부터** | 데이터 기록 시작 |

EXE 내 확인된 서식/범위 상수: `B8:B`, `C8:C`, `E8:E`, `F8:F`, `G8:G`, `H8:H`, `I8:I`, `B8:H`, `H8:I`, 인쇄영역 `$A$1:$H$n`, 숫자서식 `#,##0_`, `WrapText`, 폰트 `Tahoma` / `HY헤드라인M`

**[TOTAL] 시트 (종합)** — 동일 레이아웃, `합 계`, `총 합 계`, `공 급 가`, `합 계(HardWare)`, `합 계(SoftWare)` 행을 `=SUM(...)`, `=SUM(G...)`, `=SUM(H...)` 수식으로 생성. 할인 적용 수식: `*(1-J{행})`

**[삼성 SDS B2B 양식]** (`optSDS` 선택 시, `WriteSDSExcel`)
- 참조 파일: `삼성 B2B 견적서 양식_견적작성기 참조용.xls`
- 결과 시트명: `견적서_종합`, 파일 접두어 `삼성 B2B_`
- **10행부터** 데이터, 열 `B10:K` 사용
- 숫자서식: `###,###,###,###.00` (I열), `0.0%` (J열 = 할인율)

**할인율 입력 검증** (현행 UI 규칙, 그대로 유지)
- 99 초과 불가 → "할인율은 99보다 클수 없습니다."
- 소수점 1자리까지만 → "할인율은 소숫점 1자리만 입력 가능합니다."

> ⚠️ **템플릿 버전 차이 발견**
> CAB 내장 템플릿(2005, 37KB)과 바탕화면 템플릿(2024-04-29, 70KB)의 헤더가 다릅니다.
> - 2005판: `H6=유지정비료`, B1 `견적서`, A2 `제출처`, G2 `한국아이비엠주식회사`
> - 2024판: `H6=비고`, TOTAL 시트에 `NO : Trialinfo-24-`, `수신 : 귀중`, `견적 유효기간 : 견적 후 2주`, `H6=제안가`
> **바탕화면의 2024판을 기준(Source of Truth)으로 삼습니다.**

### 1.6 현행 장애 원인 (2026년 환경 부적합)

| # | 원인 | 증상 |
|---|---|---|
| 1 | **Excel COM 자동화 의존** — `CreateObject("Excel.Application")` 후 셀 단위 late-binding 호출 (`__vbaLateIdCall` 다수) | 셀 하나당 COM 왕복 → 수백~수천 회. 이것이 **느린 변환의 단일 최대 원인** |
| 2 | 오류 발생 시 `Excel.Quit`/`ReleaseComObject` 미수행 → **유령 EXCEL.EXE 프로세스 잔류** | "같은 이름의 Excel화일이 이미 열려 있을 수 있습니다." → **모든 Excel 강제 종료 필요** (사용자가 호소한 증상과 정확히 일치) |
| 3 | Excel XP(10.0) 전제 API를 Excel 16.0에서 호출 | 속성 미지원/인자 순서 변경으로 런타임 오류 |
| 4 | **MSXML 2.x(2004년판)** 의존 | Windows 11에 미탑재/미등록. 등록해도 EUC-KR 처리 및 XPath 동작이 현행과 상이 |
| 5 | 32비트 ActiveX(OCX) 자체등록 필요 | 관리자 권한 + `regsvr32` 필요, Office 64비트와 비트수 충돌 |
| 6 | `st6unst.exe` 기반 설치/제거 | Windows 11에서 UAC·앱&기능 미연동 |
| 7 | ANSI(`GetPrivateProfileStringA`) INI + EUC-KR 하드코딩 | 유니코드 경로/사용자명에서 깨짐 |
| 8 | `$(ProgramFiles)\Quotation` 에 INI 기록 | Program Files 쓰기 차단 → VirtualStore 우회로 설정 유실 |

---

## 2. 목표 및 비기능 요구사항

| 항목 | 현행 | 목표 |
|---|---|---|
| 변환 속도 | 수십 초 ~ 수 분 (COM 왕복) | **1~3초 이내** (Excel 프로세스 미사용) |
| Excel 설치 | **필수** (그것도 2003) | **불필요** |
| 실행 중 Excel 충돌 | 전체 종료 필요 | **무관** — 사용자가 Excel을 켜둔 채 변환 가능 |
| 설치 | 관리자 권한 + OCX 등록 | **무설치 단일 EXE** 또는 사용자 영역 설치 |
| 비트수 | 32bit 고정 | 64bit |
| 오류 처리 | 메시지 후 프로세스 잔류 | 구조화된 예외 + 로그 파일 |
| 문자 인코딩 | EUC-KR 하드코딩 | UTF-8 내부 처리, 입력은 선언 인코딩 자동 판별 |

**변경 금지 (Contract)**
- 입력 XML 스키마 해석 규칙, XPath 경로
- 출력 셀 좌표, 시트 구성, 수식, 숫자 서식, 폰트, 인쇄 영역
- 장비 분류 키워드 및 우선순위
- 할인율 검증 규칙, TransactionType 필터 규칙

---

## 3. 목표 아키텍처

### 3.1 기술 스택 (권장안)

```
언어      : Python 3.13 (설치 확인됨: C:\Users\tkddl\AppData\Local\Programs\Python\Python313)
XML       : lxml  (XPath 1.0 완전 지원 → 현행 XPath 문자열 무수정 재사용)
Excel     : openpyxl (템플릿 .xlsx 로드 → 셀 기록 → 저장. Excel 프로세스 불필요)
GUI       : PySide6 또는 tkinter (현행 Form1 레이아웃 1:1 재현)
설정      : %LOCALAPPDATA%\QuotationTool\config.json  (INI 값 자동 마이그레이션)
로그      : %LOCALAPPDATA%\QuotationTool\logs\  (일자별 로테이션)
패키징    : PyInstaller --onefile (무설치 단일 EXE) + 선택적 Inno Setup 설치본
```

**선정 근거**: node/dotnet 미설치, Python은 이미 사용 가능. openpyxl은 순수 파일 조작이므로 Excel 실행 중 여부와 완전히 무관하며 COM 왕복이 사라져 속도 문제가 원천 해소된다.

### 3.2 출력 파일 포맷 — **확정: `.xlsx`**

| 안 | 방식 | 속도 | Excel 의존 | 서식 재현 | 채택 |
|---|---|---|---|---|---|
| **A** | 템플릿을 `.xlsx`로 1회 변환 → openpyxl → **`.xlsx` 출력** | ◎ 1초 내 | 없음 | 완전 | ✅ **확정** |
| B | `xlrd 1.2 + xlwt` 로 `.xls` 입출력 | ○ | 없음 | 부분 손실 | ✗ |
| C | openpyxl로 xlsx 생성 후 Excel COM 1회 호출로 `.xls` 변환 | △ | 있음 | 완전 | ✗ |

**A안 확정.** 출력 확장자만 `.xls` → `.xlsx` 로 바뀌며, **시트 구성·셀 좌표·값·수식·서식은 100% 동일**하게 유지한다.
템플릿 `.xls` → `.xlsx` 변환은 **개발 시점에 1회만** 수행(Excel COM 사용)하고, 이후 런타임은 Excel과 무관하다.

### 3.3 모듈 설계

```
quotation/
├─ __main__.py            엔트리
├─ ui/
│   └─ main_window.py     Form1 대체. 라디오(IBM/SDS), MA 체크, 할인율, 진행바
├─ core/
│   ├─ xml_reader.py      CFXML/CFData 검증, ProductLineItem/SubLineItem 파싱
│   ├─ models.py          LineItem 데이터클래스 (frozen)
│   ├─ classifier.py      GetServerName 대체. 분류 키워드는 rules.yaml 외부화
│   ├─ pricing.py         할인율·MA·SUM 계산 (순수 함수, Excel 무관)
│   └─ writer/
│       └─ ibm_writer.py  MakeServerSheet + MakeTotalSheet + DecorateTOTSheet
├─ config.py              INI→JSON 마이그레이션
└─ resources/
    ├─ 견적서_template.xlsx
    └─ rules.yaml         그룹핑·TransactionType 규칙
```

**핵심 설계 원칙**: `core/`는 GUI·파일 I/O와 완전 분리된 순수 함수로 구성한다. 이로써 XML→중간모델→셀맵 전 단계를 Excel 없이 단위 테스트할 수 있다.

### 3.4 성능 전략
1. Excel COM 제거 (셀당 왕복 → 메모리 내 일괄 기록)
2. XML은 `lxml.etree.parse` 1회 + XPath 컴파일 재사용
3. 시트 생성은 템플릿 시트 `copy_worksheet()` 로 처리
4. 수식은 문자열로 직접 기록 (재계산은 Excel이 열 때 수행)

---

## 4. 실행 계획 (Phase)

### Phase 0 — 기준선 확보 ✅ **완료 (2026-07-23)**
- [x] 샘플 2쌍 수령: `FS5045_260722`(2026-07, 현행 템플릿 = **주 골든**), `X-ROIS 통합서버#2`(2025-01, 보조)
- [x] 개발 환경 구성: `.venv` + lxml 6.1.1 + openpyxl 3.1.5
- [x] XML 덤프 도구 `tools/dump_xml.py` — 인라인 DTD로 **전체 스키마 확정**
- [x] XLS 덤프 도구 `tools/dump_xls.ps1` — 셀·수식·서식·병합·열너비 전수 덤프
- [x] **`SPEC_CELLMAP.md` 작성** — XML↔셀 매핑 사양 확정
- [x] 금액 계산식 검증: `G8 = 796,275.83` 이 XML 라인+서브라인 합계와 **정확히 일치**
- [ ] `git init` 후 현행 자산 커밋
- [ ] 회귀 비교기 `tools/compare.py` 작성

#### Phase 0 에서 밝혀진 계획 변경 사항 ⚠️
1. **XML 인코딩이 UTF-8** — 2005년 EXE의 EUC-KR 하드코딩과 불일치. 선언 인코딩 자동 판별로 구현.
2. **TransactionType 이 `NEW`/`ADD`** — 2005년 키워드(BASE/PROPOSED/REMOVE/…)는 현행 eConfig에서 미사용.
3. **장비 분류는 Description 키워드 매칭이 아니라 `ProprietaryGroupIdentifier` 그룹핑** — §1.4의 Storage/Server 키워드 17종은 현재 경로에서 사용되지 않음. `rules.yaml` 우선순위 이슈 소멸.
4. **인라인 DTD 존재** — XXE 차단 위해 `load_dtd=False, resolve_entities=False` 필수.
5. **MonetaryAmount 가 콤마 포함 문자열 + `N/C` 리터럴** — 전용 파서 필요, `Decimal` 사용.
6. 출력에 원본 `template` 시트가 **숨김 상태로 잔존** — 동일성 위해 그대로 재현.

### Phase 1 — 사양 확정 (대부분 Phase 0에서 선행 완료)
- [x] XML 필드 → 셀 좌표 대응표 확정 (`SPEC_CELLMAP.md` §3~§5)
- [x] 그룹핑/종목키/시트명 생성 규칙 확정 (`SPEC_CELLMAP.md` §2.1)
- [x] 금액·소계·총계 수식 형태 확정
- [ ] 잔여 미확정 6건 해소 (`SPEC_CELLMAP.md` §7) — 구현 중 골든 diff로 확정
- [ ] **추가 샘플 필요**: ① MA(유지정비료) 포함 견적 1건 ② 삼성 SDS 양식 견적 1건

### Phase 2 — 코어 구현 (3~5일)
- [ ] `xml_reader` + `models` — 스키마 검증 및 파싱
- [ ] `classifier` — 규칙 외부화(`rules.yaml`)
- [ ] `pricing` — 소계/합계/할인/공급가
- [ ] 단위 테스트: 파싱·분류·계산 (Excel 불필요)

### Phase 3 — 출력 구현 (3~4일)
- [ ] 템플릿 `.xls` → `.xlsx` 변환 및 서식 보존 검증
- [ ] `ibm_writer` — 장비군 시트 + TOTAL 시트 + 서식/인쇄영역 + H열(MA)
- [ ] **골든 XLS 대비 셀별 diff 테스트** (값·수식·숫자서식·병합 비교 스크립트)

### Phase 4 — UI 및 부가 기능 (2~3일)
- [ ] Form1 레이아웃 재현 (조작 순서·단축키 동일하게)
- [ ] 진행률 표시 (기존 ProgressBar 대응)
- [ ] 설정 마이그레이션 (`견적서생성기.ini` → JSON)
- [ ] 예외 처리: 실패 시에도 잔류 프로세스·잠긴 파일 없음 보장
- [ ] 결과 폴더 자동 열기, 최근 경로 기억

### Phase 5 — 검증 및 배포 (2~3일)
- [ ] 회귀 테스트: 확보 가능한 모든 XML 샘플에 대해 골든 대비 100% 일치
- [ ] 성능 측정: 변환 시간 before/after 기록
- [ ] Excel을 여러 개 띄운 상태에서 변환 → 충돌 없음 확인
- [ ] PyInstaller 단일 EXE 빌드, 한글 경로/사용자명 환경 테스트
- [ ] 사용자 인수 테스트 → 기존 EXE 병행 운영 후 전환

---

## 5. 위험 요소 및 대응

| 위험 | 영향 | 대응 |
|---|---|---|
| XML 샘플이 특정 장비군에 치우침 | 미검증 분류 규칙 잔존 | 서버/스토리지/혼합 최소 3종 요청. 미커버 규칙은 `rules.yaml`에 보수적으로 이식 |
| 골든 XLS와 XML의 짝이 맞지 않음 | diff 비교 무의미 | Phase 0에서 짝 검증 먼저 수행 |
| 분류 키워드 매칭 순서 미상 | 시트 배치 불일치 | 골든 출력물 역산으로 확정, `rules.yaml`로 조정 가능하게 |
| 소수점/반올림 차이 (VB6 `CCur` vs Python) | 금액 1원 단위 오차 | `Decimal` 사용 + 은행가 반올림 여부를 골든으로 검증 |
| 2024판 템플릿의 추가 필드 (`제안가`, `Trialinfo-24-`) | 현행 EXE는 채우지 못함 | 신규 요구사항으로 분리 관리 (본 리팩토링 범위 외로 명시) |

---

## 6. 산출물

1. `REFACTORING_PLAN.md` (본 문서)
2. `SPEC_CELLMAP.md` — XML 필드 ↔ 셀 좌표 명세
3. `quotation/` 소스 트리 + 단위/회귀 테스트
4. `QuotationTool.exe` — 무설치 단일 실행 파일 (64bit)
5. `MIGRATION.md` — 기존 사용자 전환 가이드 (INI 이관, 구버전 제거)

---

## 7. 확정 사항 및 남은 확인 사항

### 확정 (2026-07-23)
| 항목 | 결정 |
|---|---|
| 출력 형식 | **`.xlsx`** — 내용·서식은 100% 동일, 확장자만 변경 |
| 삼성 SDS B2B 양식 | ❌ **범위 제외** (2026-07-23 결정) — `optSDS` 모드·`WriteSDSExcel`·삼성 템플릿 미구현. UI에서 라디오 버튼 제거 |
| MA(유지정비료) | **구현 대상** — H열. 규칙 확정 완료 (`SPEC_CELLMAP.md` §3.2, §4.3) |
| 검증 기준선 | **XML 샘플 + 골든 견적서 보유** → 셀 단위 회귀 테스트로 동일성 검증 |
| 기준 템플릿 | 바탕화면 2024-04-29판 `견적서_template.xls` |

### 남은 확인 사항 (2026-07-23 갱신)

**해소됨 (2026-07-23 골든 재생성)**
- [x] MA 샘플 — X-ROIS 골든에 MA 반영 확인 (`H10=309`, `H51=309`). H열 규칙 전면 확정
- [x] 삼성 SDS — **범위 제외 결정**

**사용자 확인 필요 (진행 차단 없음)**
1. **할인율 적용 견적 샘플** — 두 샘플 모두 할인 미적용(`공급가` 행 공란)이라 `*(1-J행)` 수식 미검증
2. `공급가` 행이 현행 프로그램에서 **항상 공란(수기 입력)** 인지
3. `ProprietaryShippingInformation`(배송비, KWON 1,826.9 / 4,820.49)이 견적서에 전혀 반영되지 않는데 의도된 동작인지
4. X-ROIS `SERVER 1` 시트 행 59~65 의 `=1` 수식 — 원본 프로그램 버그인지 골든 수기 편집인지

**구현 중 골든 diff로 자체 확정 가능** — `SPEC_CELLMAP.md` §7 참조

### 다음 액션
1. `git init` + 현행 자산 커밋
2. `tools/compare.py` (회귀 비교기) 작성
3. Phase 2 착수 — `core/xml_reader.py` + `models.py` + `pricing.py`
