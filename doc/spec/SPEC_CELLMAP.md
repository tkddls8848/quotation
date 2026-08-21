# 변환 사양서 — XML → 견적서 셀 매핑 (Phase 0/1 실측 결과)

- 작성일: 2026-07-23
- 근거 자료: `samples/FS5045_260722.{xml,xls}` (2026-07, 현행 템플릿 기준 **주 골든**), `samples/X-ROIS 통합서버#2.{xml,xls}` (2025-01, 보조 골든)
- 검증 상태: ✅ 실측 확인 / ⚠️ 추정(구현 중 확정 필요)

---

## 1. 입력 XML — 실제 스키마 (DTD 내장)

샘플에 **인라인 DTD가 포함**되어 있어 스키마가 완전히 확정된다.

```
CFXML
├─ thisDocumentGenerationDateTime/DateTimeStamp        예) 16:28:07
├─ thisDocumentIdentifier/ProprietaryDocumentIdentifier 예) CFXML.FS5045.2026-07-22T00:00:00+00:00
└─ CFData
   ├─ ProprietaryInformation* (Name, Value)
   │     CFXML=1.0 / Configurator Identifier=ECMSSD.90501a261971
   │     Price File Date=2026-07-22 / Checksum=2302753820
   └─ ProductLineItem+
      ├─ ProductLineNumber            1000, 2000, …
      ├─ TransactionType              NEW
      ├─ CPUSIUvalue
      ├─ ConfigurationControlNumber?
      ├─ ProprietaryGroupIdentifier   1000 / 4000 / 7000  ← **그룹 키**
      ├─ ServicePacLineNumberReference?
      ├─ Quantity
      ├─ ProductIdentification/PartnerProductIdentification
      │    ├─ OrderedProductIdentifier?
      │    ├─ ProprietaryProductIdentifier   예) 4680-3P4  ← 모델번호
      │    ├─ ProductDescription?
      │    ├─ ProductTypeCode?               Hardware / Software / Services
      │    └─ ProductIdentifierTypeCode?
      ├─ UnitListPrice? (FinancialAmount(GlobalCurrencyCode, MonetaryAmount), PriceTerm)
      └─ ProductSubLineItem*
         (LineNumber, TransactionType, Quantity, ExchangeAddSubLineItemNumber?,
          ProductIdentification, UnitListPrice?)
```

배송비와 유지정비료 태그는 현재 출력 범위가 아니므로 파싱하지 않는다.

### 1.0 TransactionType 과 증설 견적 ✅ (골든 `1080MES`)

신규 견적은 `NEW`/`ADD` 만 쓰지만, **증설 견적**은 기존 구성과 증설 후 구성을
참조용으로 함께 담는다.

| TransactionType | 뜻 | 견적서 포함 |
|---|---|---|
| `BASE` | 기존 구성 | ❌ **제외** |
| `PROPOSED` | 증설 후 구성 | ❌ **제외** |
| `UPGRADE` | 장비 업그레이드 (본체) | ✅ |
| `DISCO` | 단종/철거 라인 | ✅ |
| `NEW` | 신규 추가 라인 | ✅ |
| 서브라인 `CONVERSION` / `ADD` | 교체·추가 부품 | ✅ 정상 표기 |
| 서브라인 `REMOVE` | **제거 부품** | ✅ **음수 + 붉은 글꼴** (§1.0.2) |

`1080MES` 예: 29라인 중 BASE 11 + PROPOSED 13 을 빼고 **증설분 5라인만** 견적한다.

#### 1.0.1 장비군 묶기와 이름 ✅

- 그룹은 `ProprietaryGroupIdentifier` 로 나눈다.
- **증설 견적에서만** 본체 라인(`CPUSIUvalue = 1`)이 없는 그룹을 앞 그룹에 붙인다.
  `1080MES` 의 DISCO/NEW 그룹(26000)이 UPGRADE 그룹(25000)과 한 장에 나오는 이유다.
  결과는 상세 시트 1장.
  > ⚠️ 신규 견적에는 이 병합을 적용하면 안 된다. `TS4300` 골든의
  > `No CPUSIU for the following products` 그룹(9000)은 본체 라인이 없지만
  > **제 장을 갖는다.** 병합을 무조건 적용하면 이 그룹이 사라진 것처럼 보인다.
- **증설 견적의 장비 이름은 BASE/PROPOSED 구성의 본체 라인에서 딴다.**
  UPGRADE 라인 설명은 `9080 Model HEU` 로 장비 이름이 없지만, 골든의 시트명은
  `SERVER 1` 이다. 이는 BASE 라인 `Server 1:Server 1:IBM Power E1080` 에서 온다.
  참조 구성이 없는 신규 견적은 종전대로 그룹 첫 라인에서 딴다.

> ⚠️ 장비 여러 대를 한 번에 증설하는 XML 샘플이 없다. 현재는 BASE 본체 라인을
> 문서 순서대로 그룹에 짝지어 이름을 붙인다. 그런 문서가 나오면 재검증이 필요하다.

#### 1.0.2 제거(REMOVE) 부품 표기 ✅

```
E열 수량  기준행에 가격 있음 -> "=-1*E8"    부호를 뒤집는다
          기준행이 무가격     -> "=-1"       (DISCO 블록)
F열 단가  비움          G열 금액  비움
글꼴색    C~G 전부 FFFF0000 (빨강)
```
> XML 의 `Quantity` 는 **양수**로 들어온다. 표시할 때 부호를 뒤집는다.
> 제거 부품에는 `UnitListPrice` 가 없어 단가·금액 칸은 자연히 비고, 합계에도 0 으로 든다.

#### 1.0.3 총합계 수식이 시트마다 다르다 ✅

합계가 하나뿐일 때 **TOTAL 시트는 `=SUM(G13)`**, **상세 시트는 `=G10`** 을 쓴다.
둘 이상이면 양쪽 다 열거형(`=SUM(G41,G51)`)이다.

---

### 1.1 2005년 가정과 다른 점 — **리팩토링 필수 반영 사항**

| 항목 | 2005년 EXE 가정 | 2026년 실제 | 조치 |
|---|---|---|---|
| 인코딩 | `EUC-KR` 하드코딩 | **`UTF-8`** | 선언 인코딩 자동 판별 (EUC-KR 파일도 계속 수용) |
| TransactionType | BASE/PROPOSED/REMOVE/HARDWARE/FMOD/DISCO/CONVERSION/UPGRADE | 신규 견적은 `NEW`/`ADD`, **증설 견적은 구 키워드를 그대로 쓴다** | §1.0 참조. 구 키워드가 실제로 쓰이므로 전부 처리한다 |
| DOCTYPE | 없음 가정 | **인라인 DTD 존재** | `resolve_entities=False`, `load_dtd=False` 로 파싱 (XXE 차단) |
| MonetaryAmount | 숫자 | **천단위 콤마 포함 문자열** `"88,971.5"`, **`"N/C"`** 리터럴 | 전용 파서 필요 (§1.2) |
| GlobalCurrencyCode | — | `KWON` (KRW 아님) | 통화 코드는 표시에 사용 안 함 |
| 장비 분류 | Description 키워드 매칭 (Storage 17종/Server 2종) | **`ProprietaryGroupIdentifier` 로 그룹핑** | §3.1 — 키워드 매칭은 사용되지 않음 |

### 1.2 MonetaryAmount 파싱 규칙 ✅

```
"88,971.5"  → Decimal("88971.5")     콤마 제거 후 Decimal
"N/C"       → 특수값 NO_CHARGE       셀에 문자열 "N/C" 그대로 기록, 합계에서 0 취급
"0"         → Decimal("0")           셀에 0 기록 (서식상 "-" 로 표시됨)
(태그 없음)  → None                   셀 비움
```
> `float` 금지. `Decimal` 사용. 원본 소수점 자릿수를 그대로 셀에 기록한다 (예: `88971.5`, `796275.83`).

---

## 2. 출력 파일 전체 구조 ✅

```
{XML파일명}.xlsx
├─ TOTAL                     종합 시트 (항상 첫 번째)
├─ {종목키1 대문자}            그룹별 상세 시트
├─ {종목키2 대문자}
├─ …
└─ template                  원본 템플릿 시트 (Visible=0, 숨김 상태로 잔존)
```

- 시트 수 = 1(TOTAL) + 그룹 수 + 1(template 숨김)
- FS5045: 5시트 = TOTAL + 3그룹 + template
- X-ROIS: 4시트 = TOTAL + 2그룹 + template

> `template` 시트를 **숨김 상태로 남기는 것**이 현행 동작이다. 동일성 유지를 위해 그대로 재현한다.

### 2.1 종목 키(ITEM Key) 및 시트명 생성 규칙 ✅

`ProductDescription` 으로부터 생성:

```
1) ":" 가 있으면 → 첫 ":" 앞부분을 취함
     "4680-3P4 #1:IBM Storage FlashSystem 5045 SFF Control Enclosure" → "4680-3P4 #1"
     "Server 1:Server 1:9080 Model HEX"                              → "Server 1"
2) 31자로 절단
3) 그 다음에 선두 "IBM " 제거   ← 순서가 중요하다
4) 시트명 = 위 결과를 대문자 변환
```

| Description | 31자 절단 | IBM 제거 = 종목 키 | 길이 |
|---|---|---|---|
| `IBM Expert Labs Project Unit for IBM Power Systems` | `IBM Expert Labs Project Unit fo` | `Expert Labs Project Unit fo` | 27 |
| `TS4300 Tape Library Base Module with Expert Care` | `TS4300 Tape Library Base Module` | 그대로 | 31 |
| `No CPUSIU for the following products:IBM 18 TB …` | `No CPUSIU for the following pro` | 그대로 | 31 |

⚠️ 그룹 키는 `ProprietaryGroupIdentifier`이며, 종목 키는 **그룹의 첫 ProductLineItem** 의
Description 에서 뽑는다 (증설 견적은 예외 — §1.0.1).

---

## 3. TOTAL 시트 매핑 ✅

### 3.1 고정 영역 (템플릿에서 상속, 값만 기록)

| 셀 | 값 | 비고 |
|---|---|---|
| B2 | `NO : Trialinfo-{YY}-` | YY = 생성연도 2자리. FS5045=`26`, X-ROIS=`25` ✅ |
| B3 | `D  A  T  E :` | 템플릿 고정 |
| C3 | `2026-07-23` | **변환 실행일** (XML의 Price File Date 아님) ✅, 서식 `@`(텍스트) |
| B4 | `수신 :  귀중` | 템플릿 고정, Bold |
| B5 | `견적 유효기간 : 견적 후 2주` | 템플릿 고정, Bold |
| H5 | `(단위: 천원, 부가세 별도)` | 템플릿 고정 |
| B6:H7 | 헤더 2행 | 템플릿 고정 (§5 참조) |

### 3.2 데이터 영역 — **8행부터**

그룹마다 다음 블록을 이어서 기록한다. 그룹 내 `ProductLineItem` 1건당 1행.

| 열 | 내용 | 첫 행 | 이후 행 |
|---|---|---|---|
| B | 종목 키 (§2.1) | 기록, **Bold**, 블록 전체 세로 병합 | — |
| C | `ProprietaryProductIdentifier` | 기록 | 기록 |
| D | `ProductDescription` (원문 그대로) | 기록 | 기록 |
| E | `Quantity` | 기록 | 기록 |
| F | `=G{구간첫행}/E{구간첫행}` (단위가) | 수식, **구간 단위** 병합 | — |
| G | **구간(H/W·S/W) 금액 소계 (상수)** | 값, **구간 단위** 병합 | — |
| H | 비고 | 그룹 전체 병합, 값은 기록하지 않음 | — |

**G열 값 = 구간(H/W·S/W) 소계 (상수로 기록)** ✅ 검증됨

> ⚠️ **정정 (2026-07-23, Phase 2 테스트로 발견)**
> 초판에 "G = 그룹 소계"로 적었으나 **틀렸다.** 한 그룹은 `ProductTypeCode` 기준으로
> **H/W 구간과 S/W 구간으로 나뉘어 각각 별도의 병합 셀·별도 소계**를 가진다.
> FS5045는 S/W 소계가 0이라 두 해석이 우연히 일치해 놓쳤고, X-ROIS에서 드러났다.

```
X-ROIS 그룹 2000 (행 10~22)
  G10:G12 병합 = 5,378,973.5   ← H/W 구간 (9080-HEX, 7226-1U3, 5313-HPO)
  G13:G22 병합 =   600,468.5   ← S/W 구간 (5692-A6P 외 9건)
  G23 = SUM(G10:G22) = 5,979,442   ← 그룹 합계행
  ─ 검산: 5,378,973.5 + 600,468.5 = 5,979,442  ✓

FS5045 그룹 1000 (행 8~10)
  G8:G9  병합 = 796,275.83     ← H/W 구간 (라인 1000, 2000)
  (행 10 S/W 는 전부 N/C → 소계 0 → **셀을 비움**)
  ─ 검산: 88,971.5 + 168.8×1 + 391.2×8 + 49,379×12 + 26,463.3 + 7,379.3 = 718,660.5
          + 77,615.33 (라인 2000)                                        = 796,275.83  ✓
```

**구간 소계 = Σ(구간 내 ProductLineItem 및 그 ProductSubLineItem 의 Quantity × MonetaryAmount)**, N/C는 0.
**구간 소계가 0이면 F·G 셀을 비운다** (병합은 유지).

**구간 분류**: `ProductTypeCode == "Hardware"`만 H/W 구간, 그 외(`Software`, `Services`)는 S/W 구간 ✅

**그룹 종료 행 (합계)**
| 셀 | 내용 |
|---|---|
| C{n} | `합                   계` (Bold, C{n}:F{n} 병합) |
| G{n} | `=SUM(G{첫행}:G{n-1})` Bold |

**최종 행**
| 셀 | 내용 |
|---|---|
| B{n} | `총        합       계` (Bold, B{n}:F{n} 병합) |
| G{n} | `=SUM(G11,G15,G19)` — **각 그룹 합계 행을 콤마로 열거** ✅ |
| B{n+1} | `공        급       가` (Bold, 병합). **값 없음 — 수기 입력란** ✅ |

**인쇄 영역**: `$A$1:$H${마지막행+2}` (FS5045: `$A$1:$H$23`, 공급가 행 21 + 하단 비고 병합 B22:H23) ✅

---

## 4. 상세 시트 매핑 (그룹별) ✅

### 4.1 고정 영역
| 셀 | 값 |
|---|---|
| C1 | `({종목 키})` — 예 `(4680-3P4 #1)`, Bold, C1:G1 병합 |
| C3 | 변환 실행일 |
| B5 | `세 부 내 역` |
| H5 | `(단위: 천원, 부가세 별도)` |
| B6:H7 | 헤더 (H6=`비고`, H6:H7 병합) |

### 4.2 데이터 영역 — **8행부터**, ProductTypeCode 별 섹션

```
[H/W 섹션]  B8 = "H/W"  (Bold, 섹션 전체 세로 병합)
  ┌ ProductLineItem 블록 (Hardware 각각)
  │   기준행:  C=모델번호  D=Description  E=Quantity(상수)
  │            F=UnitListPrice(상수)   G= =E{r}*F{r}
  │   서브행:  C=서브 모델번호  D=서브 Description
  │            E= =({서브Quantity}*E{기준행})     ← 부모 수량 상대 참조 ✅
  │            F=서브 단가(상수)     G= =E{r}*F{r}
  └ 합계행:   C{n}="합                   계" (C{n}:F{n} 병합, Bold)
              G{n}= =SUM(G{블록첫행}:G{n-1})
  … (블록 반복)
  합계(HardWare) 행: C="합                   계(HardWare)"
              G= =SUM(G20,G23)   ← 각 블록 합계행 열거
[S/W 섹션]  B{n} = "S/W"  (Bold, 세로 병합)
  … 동일 구조 (Software 라인 + 서브라인)
  합계(SoftWare) 행: C="합                   계(SoftWare)"
              G= =SUM(G25:G26)   ← 이쪽은 범위형 ⚠️
[총 합 계]   B= "총        합       계"  G= =SUM(G24,G27)  Bold
[공 급 가]   B= "공        급       가"  값 없음
```

**N/C 처리** ✅: `F`, `G` 모두 문자열 `"N/C"` 를 그대로 기록 (수식 아님). 상위 SUM에서 자동으로 0 취급됨.

### 4.3 섹션별 합계 구조 ✅

**H/W 구간과 S/W 구간의 합계 방식이 다르다.**

| | H/W 구간 | S/W 구간 |
|---|---|---|
| 블록별 합계행 | **있음** — 라인아이템 블록마다 `합                   계` | **없음** |
| 구간 합계 수식 | `=SUM(G20,G23)` — 블록 합계행 **열거** | `=SUM(G68:G103)` — 구간 전체 **범위** |

**총 합 계 행**: 구간이 2개면 `=SUM(G24,G27)` 열거, 1개면 `=G10` **직접 참조** ✅

**빈 행(스페이서) 규칙** ✅: 서브라인이 0건인 블록은 합계 범위가 최소 2행이 되도록
빈 행 1개를 둔다. FS5045 `4690-A03`(행 21, 서브 0건) → 행 22 공란 → `=SUM(G21:G22)`.
세 시트에서 동일하게 확인.

### 4.4 서브라인 수량(E열) — 세 가지 형태 ✅

```
H/W 구간 + 기준행에 가격 있음  ->  "=8*E8"    부모 수량 상대 참조
H/W 구간 + 기준행이 N/C        ->  "=1"       참조 없는 수식
S/W 구간                       ->  1          상수
```

> 초판에서 X-ROIS `SERVER 1!E59:E65` 를 "원인 불명 이상치(원본 버그 또는 수기 편집)"로
> 기록했으나 **철회한다.** 위 규칙으로 완전히 설명된다. 해당 블록(라인 4000 `5313-HPO`)은
> H/W 구간이면서 기준행이 N/C 인 유일한 사례였다.

### 4.5 글꼴 ✅ (`tools/inspect_fonts.py` 실측)

| 대상 | 글꼴 |
|---|---|
| 데이터·금액·서브라인·구간 라벨(H/W, S/W) | **Tahoma 9** |
| 한글 합계 라벨 (`합계`, `합계(HardWare/SoftWare)`, `총 합 계`, `공 급 가`) | **돋움 9 볼드** |
| 시트 제목 `C1` | **Tahoma 18 볼드** (템플릿은 HY헤드라인M — 반드시 덮어씀) |
| 날짜 `C3` | **HY헤드라인M 9** (템플릿은 Tahoma 10 — 반드시 덮어씀) |
| 표제 `B2` | 템플릿 유지 (Arial 9) |

볼드 여부: TOTAL 시트의 그룹 합계 G는 볼드, 상세 시트의 블록·구간 합계 G는 볼드 아님.
총 합계 G는 양쪽 모두 볼드.

---

## 5. 서식 사양 ✅

| 대상 | 숫자 서식 |
|---|---|
| TOTAL 시트 F·G열 | `#,##0_);[빨강](#,##0)` |
| 상세 시트 F·G열 | `_-* #,##0_-;-* #,##0_-;_-* "-"_-;_-@_-` (회계 서식) |
| C열 (모델번호) 전체 | `@` (텍스트) — **선행 0 보존을 위해 필수** |

| 항목 | 값 |
|---|---|
| 가로 정렬 | `-4108`(가운데) / `-4131`(왼쪽) / `-4152`(오른쪽) / `1`(일반) |
| Bold | 종목 키(B), 합계 라벨/값, 총합계, 공급가, C1 시트 제목 |
| 열 너비 (TOTAL) | A=1.33 B=9.78 C=9.67 D=30.89 E=3.89 F=9.33 G=9.44 H=10.44 I=1.44 |
| 열 너비 (상세) | A=1.44 B=9.67 C=8.56 D=32.33 E=4.89 F=8.67 G=9.89 H=8.56 I=1.44 |
| 공통 병합 | C1:G1, D6:D7, H6:H7 |
| 하단 비고 | B{끝}:H{끝+1} 병합 |

---

### 5.1 그림·도형 (셀이 아닌 요소) ✅

템플릿 `TOTAL` 시트 상단에는 **로고 이미지 1개와 도형 3개**로 된 머리글 블록이 있다
(`xl/media/image1.png`, `xl/drawings/drawing1.xml`). 견적서의 첫 장 상단이 바로 이것이다.

| 시트 | 그림 |
|---|---|
| TOTAL | **유지** (drawing1 + image1.png) |
| 상세 시트 | 없음 |
| 숨김 `template` | 없음 (템플릿의 drawing2 는 버려진다) |

> ⚠️ **openpyxl 은 워크북을 저장할 때 그림·도형·텍스트박스를 전부 버린다.**
> 저장이 끝난 뒤 xlsx(zip)를 직접 손봐 템플릿의 해당 파트를 다시 넣어야 한다
> (`writer/drawings.py`). 셀만 비교해서는 이 누락을 잡을 수 없으므로
> `tools/compare.py` 가 그림이 붙은 시트와 미디어 파일 목록도 비교한다.

주의할 점 두 가지:
- openpyxl 은 관계(Target)를 `/xl/...` 절대 경로로, 속성 순서도 Excel 과 다르게 쓴다.
  파싱을 속성 순서에 의존하면 안 된다.
- openpyxl 이 만든 워크시트 XML 에는 `xmlns:r` 선언이 없을 수 있다.
  선언 없이 `<drawing r:id=…/>` 를 넣으면 파일이 깨진다.

---

## 6. 구현 검증 기준 (회귀 테스트)

`tools/compare.py` 가 골든 대비 다음을 전수 비교한다:

1. 시트 목록 및 순서, 숨김 상태
2. 각 셀의 **수식 문자열** (`=SUM(G8:G10)` 등 문자 단위 일치)
3. 각 셀의 **값** (Decimal 정밀도 유지)
4. 숫자 서식, 가로·세로 정렬, 줄바꿈
5. 글꼴 이름·크기·굵기·색
6. **채우기**(패턴과 색), **테두리**(4면 스타일과 색)
7. 병합 영역 목록, 행 높이, 열 너비, 인쇄 영역
8. **그림이 붙은 시트와 이미지 파일 목록**

> 4~6, 8 은 처음에 빠져 있었다. 그 탓에 "차이 0건"이 서식과 로고 누락을
> 보증하지 못했다. 셀 값만 맞추는 비교는 "출력 완전 동일"의 근거가 될 수 없다.

**합격 기준: FS5045 / X-ROIS 두 샘플 모두 차이 0건**

---

## 7. 출력 범위

- 유지정비료(H·I열), 배송비, 할인율은 출력하지 않는다.
- 공급가 행은 수기 입력란으로 비워 둔다.
- 견적서 번호는 `Trialinfo-` 형식일 때 실행 연도의 두 자리만 갱신한다.
- 양식은 `quotation/resources/견적서_template_IBM.xlsx` 와 `..._Lenovo.xlsx`
  둘뿐이다. 데스크톱과 웹이 같은 파일을 쓰며 다른 양식은 만들지 않는다.
  어느 것을 쓸지는 XML 내용(IBM/레노버)으로 정해지고 화면이 고르지 않는다.
- 데스크톱은 처음 실행할 때 두 템플릿을 EXE 옆에 복사하며, 이후 사용자
  편집본을 덮어쓰지 않는다.
