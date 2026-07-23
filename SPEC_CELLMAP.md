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
   ├─ ProprietaryShippingInformation? (Name, FinancialAmount)
   │     "Total Non-discountable Shipping and Handling Charge" KWON 1,826.9
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
      ├─ ShippingUnitListPrice?
      ├─ MaintenanceUnitListPrice?
      └─ ProductSubLineItem*
         (LineNumber, TransactionType, Quantity, ExchangeAddSubLineItemNumber?,
          ProductIdentification, UnitListPrice?, MaintenanceUnitListPrice?)
```

### 1.1 2005년 가정과 다른 점 — **리팩토링 필수 반영 사항**

| 항목 | 2005년 EXE 가정 | 2026년 실제 | 조치 |
|---|---|---|---|
| 인코딩 | `EUC-KR` 하드코딩 | **`UTF-8`** | 선언 인코딩 자동 판별 (EUC-KR 파일도 계속 수용) |
| TransactionType | BASE/PROPOSED/REMOVE/HARDWARE/FMOD/DISCO/CONVERSION/UPGRADE | **`NEW`**(라인) / **`ADD`**(서브라인) | NEW/ADD를 1급 처리, 구 키워드는 호환 유지 |
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
2) 없으면 → 선두 "IBM " 제거
     "IBM Expert Labs Project Unit for IBM Power Systems"
       → "Expert Labs Project Unit for IBM Power Systems"
3) 27자로 절단
       → "Expert Labs Project Unit fo"     ← TOTAL 시트 B열 값 (원본 대소문자 유지)
4) 시트명 = 위 결과를 대문자 변환
       → "EXPERT LABS PROJECT UNIT FO"
       → "SERVER 1",  "4680-3P4 #1"(이미 대문자)
```
⚠️ 절단 길이 27자는 두 샘플에서 일치 확인. 다른 길이 케이스가 나오면 재확인 필요.
⚠️ 그룹 키는 `ProprietaryGroupIdentifier`이며, 종목 키는 **그룹의 첫 ProductLineItem** 의 Description에서 뽑는다.

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
| H | **그룹 MA 합계 (상수)** ✅ | 값, **그룹 전체** 병합 | — |

> ⚠️ **F·G 는 구간 단위, H 는 그룹 단위로 병합 범위가 다르다.**
> X-ROIS 그룹 2000: `G10:G12` + `G13:G22` (구간 2개) vs `H10:H22` (그룹 전체 1개)

**H열 = 제안가(유지정비료)** ✅ 검증됨 — X-ROIS 샘플
```
그룹 2000 (행 10~22) → H10 = 309  (상수, H10:H22 병합)
  = Σ(그룹 내 모든 ProductLineItem/SubLineItem 의 MaintenanceUnitListPrice/FinancialAmount/MonetaryAmount)
  ─ 검산: 라인 3000(7226-1U3) 의 MA 309 만 존재 → 그룹 합 309  ✓
MA 값이 하나도 없는 그룹 → H 셀 비움 (FS5045 전 그룹 해당)
```
> **수량을 곱하지 않는다.** MA는 원본 `MonetaryAmount` 를 그대로 기록한다. `PriceTerm` 은 `Y`(연간)이나 셀에는 반영되지 않는다.

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

**구간 분류**: `ProductTypeCode == "Software"` → S/W 구간, 그 외(`Hardware`, `Services`)는 H/W 구간 ✅
(X-ROIS `6911-301` 은 `Services` 이나 골든에서 H/W 섹션에 배치됨)

**그룹 종료 행 (합계)**
| 셀 | 내용 |
|---|---|
| C{n} | `합                   계` (Bold, C{n}:F{n} 병합) |
| G{n} | `=SUM(G{첫행}:G{n-1})` Bold |
| H{n} | `=SUM(H{첫행}:H{n-1})` Bold |

**최종 행**
| 셀 | 내용 |
|---|---|
| B{n} | `총        합       계` (Bold, B{n}:F{n} 병합) |
| G{n} | `=SUM(G11,G15,G19)` — **각 그룹 합계 행을 콤마로 열거** ✅ |
| H{n} | `=SUM(H11,H15,H19)` |
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
              H{n}= =SUM(H{블록첫행}:H{n-1})
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

### 4.3 H열(제안가/유지정비료) — 상세 시트 ✅

| 위치 | 내용 |
|---|---|
| ProductLineItem 기준행 | `MaintenanceUnitListPrice` **상수** 기록 (수량 미곱). 없으면 비움 |
| ProductSubLineItem 행 | 서브라인의 MA. 두 샘플 모두 전부 없음 ⚠️ 미검증 |
| 블록 합계행 | `=SUM(H{블록첫행}:H{합계행-1})` — **G열과 동일 범위** |
| 합계(HardWare) | `=SUM(H50,H57,H66)` — G열과 동일 열거 |
| 총 합 계 | `=SUM(H67,H104)` |
| 숫자 서식 | 상세 시트 H열 = `#,##0_ ` / TOTAL 시트 H열 = `#,##0_);[빨강](#,##0)` |

검증 (X-ROIS `SERVER 1` 시트): `H51 = 309` (라인 3000 기준행) → `H57 = SUM(H51:H56) = 309`
→ `H67 = SUM(H50,H57,H66) = 309` → `H105 = SUM(H67,H104) = 309` ✅

> 블록이 1개뿐인 시트(`EXPERT LABS PROJECT UNIT FO`)에서는 `H11 = =H10` 형태의 **직접 참조**를 쓴다. ⚠️ 블록 1개일 때의 예외 규칙.

**⚠️ 미확정 사항 — 빈 행 규칙**
FS5045 `4680-3P4 #1` 시트에서 서브라인이 0개인 라인(4690-A03, 행21) 블록의 합계가 `=SUM(G21:G22)` 이며 **행 22가 비어 있다**. 서브라인 0건일 때 스페이서 행 1개를 넣는 것으로 보이나, 다른 케이스로 교차 검증 필요.

**⚠️ 미확정 사항 — E열 수식 이상 케이스**
X-ROIS `SERVER 1` 시트 행 59~65(라인 4000 `5313-HPO` 의 서브라인 7건)만 `=1` 로 기록되어 있다.
다른 모든 서브라인은 `={수량}*E{기준행}` 형태다. 데이터상으로는 라인 5000의 서브라인과 구조가
동일(전부 qty=1, N/C)하므로 **원본 프로그램의 버그이거나 골든 파일의 수기 편집**으로 추정된다.
→ 구현은 일관 규칙(`={수량}*E{기준행}`)을 따르고, 이 7개 셀은 diff 예외로 처리 후 사용자 확인.

---

## 5. 서식 사양 ✅

| 대상 | 숫자 서식 |
|---|---|
| TOTAL 시트 F·G·H열 | `#,##0_);[빨강](#,##0)` |
| 상세 시트 F·G열 | `_-* #,##0_-;-* #,##0_-;_-* "-"_-;_-@_-` (회계 서식) |
| 상세 시트 H열 합계 | `#,##0_ ` |
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

## 6. 구현 검증 기준 (회귀 테스트)

`tools/compare.py` 가 골든 대비 다음을 전수 비교한다:

1. 시트 목록 및 순서, 숨김 상태
2. 각 셀의 **수식 문자열** (`=SUM(G8:G10)` 등 문자 단위 일치)
3. 각 셀의 **값** (Decimal 정밀도 유지)
4. `NumberFormat`, `HorizontalAlignment`, `Font.Bold`
5. 병합 영역 목록
6. 열 너비, 인쇄 영역

**합격 기준: FS5045 / X-ROIS 두 샘플 모두 차이 0건**

---

## 7. 남은 확인 사항

**해소됨**
- ~~F/G/H 병합 범위 판정 기준~~ → **확정**: F·G는 H/W/S/W 구간 단위, H는 그룹 단위. 분류는 `ProductTypeCode == "Software"` 여부 (§3.2)

**구현 중 골든 diff로 자체 확정**
2. **서브라인 0건 시 스페이서 행** 규칙 (§4.2)
3. **종목 키 27자 절단** 이 상수인지, 시트명 31자 제한과 별개인지
4. 합계 수식이 범위형(`SUM(G25:G26)`)과 열거형(`SUM(G20,G23)`)으로 갈리는 규칙 — 블록 1개면 범위형/직접참조로 보임
5. 서브라인 레벨 `MaintenanceUnitListPrice` — 두 샘플 모두 없음. 나오면 기준행과 동일 규칙 적용으로 가정

**사용자 확인 필요**
6. `ProprietaryShippingInformation`(배송비 KWON 1,826.9 / 4,820.49)이 견적서에 전혀 반영되지 않음 — 의도된 동작인지
7. X-ROIS `SERVER 1` 행 59~65 의 `=1` 수식 (§4.2 하단) — 원본 버그인지 수기 편집인지
8. `공급가` 행이 항상 공란(수기 입력)인지
9. 할인율 적용 견적 샘플 — 두 샘플 모두 할인 미적용이라 `*(1-J행)` 수식 미검증

**범위 제외 (2026-07-23 결정)**
- ~~삼성 SDS B2B 양식~~ → **구현하지 않음**
