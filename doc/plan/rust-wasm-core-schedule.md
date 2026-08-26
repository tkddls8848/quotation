# Rust→WASM 전환 — 남은 일정

- 성격: **계획(일정)**. [착수안](rust-wasm-core-plan.md)이 *무엇을 왜* 하는지를
  적고, 이 문서는 *어떤 순서로 언제* 하는지를 적는다. 순서가 먼저고 날짜는
  목표치다. 관문 결과에 따라 뒤집히면 이 문서를 고쳐 덮지 않고
  [`doc/decisions/`](../decisions/)에 결정 기록을 남긴다.
- 기준일: 2026-08-27
- 승인 기준: [결정 0005](../decisions/0005-accept-meaningful-xlsx-parity.md),
  금액 대조는 [결정 0006](../decisions/0006-compare-amounts-by-value.md)

## 1. 지금 어디까지 왔나

| | 상태 | 근거 |
|---|---|---|
| Phase 0 관문 1 — 템플릿 도형·내용 보존 | **통과** | [결정 0005](../decisions/0005-accept-meaningful-xlsx-parity.md). 셀 값·수식 0건 차이, 첫 페이지 drawing·media·관계는 바이트까지 동일 |
| Phase 0 관문 2 — WASM 크기·기동 | **아직 재지 않음** | 판정 기준만 있다 (전송 1 MiB 이하, 기동 200 ms 이하) |
| Phase 0 관문 3 — PyO3 확장이 배포 경로에 얹히는가 | **아직 재지 않음** | PyInstaller 단일 EXE + CI ubuntu-latest |
| Phase 1 — `money`·`naming`·`modes` | **완료** | `cargo test` 21건, 파이썬 대조 1,009건 일치 |

**관문 둘이 남아 있다는 점이 이 일정의 가장 중요한 사실이다.** 둘 중 하나라도
실패하면 Phase 2 이후는 하지 않는다. 그래서 관문을 먼저 끝낸다 — 코어를 다
옮긴 뒤에 "브라우저에 못 싣는다"를 알게 되는 순서는 쓰지 않는다.

## 2. 순서와 목표 시점

각 단계는 앞 단계가 초록일 때만 시작한다. 기간은 추정이고, 늘어나는 쪽으로
틀릴 수 있다. 늘어나면 범위를 줄이지 말고 일정을 늘린다 — 이 계획에서 줄일 수
있는 것은 속도지 동등성이 아니다.

| 단계 | 하는 일 | 기간(추정) | 목표 시점 |
|---|---|---|---|
| **A. 남은 관문** | 관문 2·3 실측 | 2일 | 2026-08-28 ~ 08-31 |
| **B. Phase 2** | `xml_reader` (`quick-xml` + `encoding_rs`) | 4일 | ~ 2026-09-04 |
| **C. Phase 3** | `models`·`integrated`·`dcsc_summary`·`convert` | 5일 | ~ 2026-09-11 |
| **D. Phase 4** | `writer/*` — 본체 | 10일 | ~ 2026-09-25 |
| **E. Phase 5** | 바인딩 둘 + 배선 교체 + 파이썬 구현 제거 | 5일 | ~ 2026-10-02 |

## 3. A. 남은 관문 (2026-08-28 ~ 08-31)

Phase 1 을 옮겨 두었으므로 빈 껍데기가 아니라 **실제 규칙이 든 코어**로 잰다.
그만큼 관문 2 의 답이 정직해진다.

### 관문 2 — 크기와 기동

- 할 일: `quotation-core` 에 `wasm-bindgen` 진입점을 붙여 `wasm-pack` 으로
  빌드하고, gzip 전송 크기와 브라우저 기동 시간을 잰다.
- 판정: **전송 1 MiB 이하, 기동 200 ms 이하.**
- 결과는 [`measurements/runtime.md`](../measurements/runtime.md)에 지금
  Pyodide 실측(14.4 MiB / 2.5 s) 옆에 나란히 적는다.
- 실패하면: 착수안 §1 표의 전제가 틀린 것이다. 계획을 접고 결정 기록을 남긴다.

### 관문 3 — PyO3 확장이 배포 경로에 얹히는가

- 할 일: `quotation-core` 에 PyO3 바인딩을 붙여 `quotation.core` 안쪽에서
  부를 수 있는 확장 모듈을 만들고, `desktop_ibm/QuotationTool.spec` 으로
  단일 EXE 를 빌드해 뜨는지 본다. CI(ubuntu-latest)에서 휠이 서는지도 본다.
- 판정: **EXE 가 뜨고 `desktop_ibm/tools/acceptance.ps1` 이 통과한다.**
- 실패하면: 데스크톱만 파이썬으로 남기는 선택지가 생기는데 그것은 착수안 §4
  (단일 구현)를 깨므로 그 자체가 중단 사유다.

## 4. B~D. 코어 이식 (2026-09-01 ~ 09-25)

세 단계 모두 같은 방식으로 진행한다.

1. 파이썬 테스트를 Rust 로 이식해 **먼저 붉게** 만든다.
2. 규칙을 옮긴다. 규칙 자체는 바꾸지 않는다.
3. 대조 하네스를 그 단계 범위까지 넓히고, 실제로 차이를 잡는지 **일부러
   틀려서** 확인한다 (Phase 1 에서 한 것과 같은 방식).

| 단계 | 옮기는 것 | 대조 방법 | 중단 조건 |
|---|---|---|---|
| B. Phase 2 | `xml_reader` 325줄 | fixture 6종의 파싱 결과를 파이썬 모델과 항목 단위로 비교. XXE 차단·인라인 DTD 거절·EUC-KR 포함 | 파싱 결과가 다르거나, 파이썬이 거절하는 문서를 Rust 가 받아들인다 |
| C. Phase 3 | `models`·`integrated`·`dcsc_summary`·`convert` 611줄 | 같은 fixture 의 중간 모델(그룹·시트명·금액·구간)을 비교 | 금액이나 그룹 구성이 갈린다 |
| D. Phase 4 | `writer/*` 822줄 | **`web/tests/xlsx_parity.py` 로 최종 산출물 비교** + `tests/` 골든 회귀 | `xlsx_parity.py` 를 통과시키려고 정규화 규칙을 늘려야 한다 |

Phase 2 를 끝내면 두 가지가 딸려 없어진다.

- **EUC-KR 우회책** — Pyodide 의 libxml2 에 iconv 가 없어 넣은 것이다
  ([사고 0002](../incidents/0002-pyodide-lxml-euckr.md)). `encoding_rs` 는
  EUC-KR 을 기본으로 안다. 우회책은 지우고 사고 기록은 남긴다.
- **CI `core` 잡의 lxml 6.1.1 / 6.0.0 이중 매트릭스** — lxml 판본이 갈리는
  문제 자체가 사라진다. 매트릭스를 지우는 커밋에 그 이유를 적는다.

Phase 4 가 이 계획의 본체다. 열흘을 잡은 것은 822줄이 많아서가 아니라
**openpyxl 이 조용히 해 주던 일**(수치 직렬화, 서식 인덱스, 병합, 인쇄 영역)을
전부 눈으로 확인해야 하기 때문이다. 결정 0006 이 그런 자리 하나를 이미 보여
줬다 — 파이썬 `Decimal` 의 지수 표기는 셀에 닿지 않는다.

## 5. E. Phase 5 — 배선 교체 (2026-09-28 ~ 10-02)

- 브라우저: 변환 일꾼이 부르는 것을 Pyodide 에서 WASM 모듈로 바꾼다. API
  계약과 화면은 그대로다.
- 데스크톱·CI: `quotation.core` 의 공개 API(`convert`, `convert_bytes`,
  `parse_bytes`, `build_bytes`, `carry_over_bytes`, `QuotationXmlError`,
  `modes`)를 그대로 두고 안쪽만 Rust 확장으로 바꾼다. import 는 한 줄도
  고치지 않는다.
- 마지막으로 **파이썬 구현을 지운다.** 플래그로 두 경로를 남기지 않는다
  (착수안 §7).
- 지우기 전에 마지막으로 `pytest` 전체와 `web/tests/test_browser_e2e.py`
  (실제 Chromium)를 돌린다.

## 6. 매 단계 공통 규칙

- **파이썬이 기준이다.** 이식이 끝날 때까지 `web/tests/test_browser_parity.py`
  의 "CPython" 쪽은 파이썬 원본을 가리킨다.
- **`tests/golden_ignore.txt` 를 늘리지 않는다.** 늘려야 한다면 결과가 달라진
  것이고, 견적서에서 그것은 용납되지 않는다.
- **대조 하네스는 스스로도 검증한다.** 규칙을 일부러 틀려서 붉어지는 것을 본
  뒤에만 "통과"라고 적는다.
- 각 단계가 끝나면 착수안 §6 의 표에 결과를 적고, 판단이 바뀐 것이 있으면
  결정 기록을 남긴다.

## 7. 이 일정을 접는 조건

착수안 §9 와 같다. 요약하면 셋이다.

1. 관문 2·3 중 하나라도 실패.
2. Phase 4 에서 `xlsx_parity.py` 의 정규화 규칙을 늘려야 함.
3. 단일 구현(착수안 §4)이 깨짐 — 웹과 데스크톱이 서로 다른 변환 코드를 쓰게 됨.

접을 때는 **무엇이 막았는지**를 결정 기록에 적는다. 이미 한 번
([결정 0003](../decisions/0003-reject-rust-wasm-core-after-phase0.md)) 잘못된
근거로 접었다가 철회한 적이 있다. 근거는 실측이어야 하고, 실측은 같은 입력을
양쪽에 넣은 결과여야 한다.
