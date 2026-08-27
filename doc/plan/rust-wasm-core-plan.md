# 변환 코어를 Rust→WASM 으로 옮기는 계획 (착수안)

- 성격: **계획**. 착수 시점의 설계 의도와 범위를 적는다. 뒤집히면 이 문서를
  고쳐 덮지 않고 [`doc/decisions/`](../decisions/) 에 결정 기록을 남긴다.
- 상태: **Phase 2 진행 중.** Phase 0 관문 셋을 모두 통과했고
  ([결정 0007](../decisions/0007-phase0-gates-passed.md)), Phase 1 순수 규칙은
  파이썬과 1,009건이 같다 (`tools/rust_parity_pure_rules.py`).
  Phase 0 재개 경위: 이전의 폐기 판단은 템플릿을 한 셀만 바꾼 저장본을
  구성 XML 변환 결과와 혼동한 잘못된 근거였다. [결정 0004](../decisions/0004-resume-rust-wasm-phase0.md)가
  [결정 0003](../decisions/0003-reject-rust-wasm-core-after-phase0.md)를 철회한다.
  실제 구성 XML을 Python 원본과 독립 Rust 구현에 각각 넣어 비교하기 전에는
  동등성·폐기를 판정하지 않는다.
- 승인 기준: [결정 0005](../decisions/0005-accept-meaningful-xlsx-parity.md)의
  제품·금액·수식·구조 동등성과 첫 페이지 도형 보존을 쓴다. ZIP 직렬화 차이는
  계속 관찰하되 그 자체로 중단 사유로 삼지 않는다.
- 근거가 된 실측: [`measurements/runtime.md`](../measurements/runtime.md)
- 남은 일정: [`rust-wasm-core-schedule.md`](rust-wasm-core-schedule.md)
- 되돌아봐야 할 결정: [결정 0002](../decisions/0002-convert-in-browser.md),
  [계획 §1](web-app-plan.md#1-결론)

## 1. 이 계획이 답하려는 것

무료 계정에서 웹 앱을 돌리기 위해 지금 **첫 방문자가 14.4 MiB 를 받고 2.5 초를
기다린다.** 변환 자체는 그 뒤 0.3 초다. 즉 사용자가 기다리는 시간의 대부분이
견적서를 만드는 일이 아니라 **파이썬 런타임을 브라우저에 세우는 일**이다.

| 항목 | 지금 (Pyodide) | Rust→WASM **추정** |
|---|---:|---:|
| 엔진 자산 | 14.4 MiB (Pyodide 11.1 + lxml 1.7 + openpyxl 0.9 + 코어 0.1) | 0.3–0.8 MiB |
| 첫 기동 | 1.9 s + lxml 0.6 s = **2.5 s** | 30–100 ms |
| 변환 1건 | 0.3 s (CPython 0.1 s 의 3배) | 5–15 ms |

**오른쪽 열은 추정이다.** 근거는 "WASM 은 네이티브의 1.5–2배 시간, Pyodide 는
2–5배"라는 통상치와 CPython 실측 73–423 ms 뿐이다. 이 값을 확인하는 것이
Phase 0 의 일이고, 빗나가면 계획을 접는다.

## 2. 왜 지금 다시 보는가 — 달라진 것은 하나뿐이다

계획 §1 은 **"TypeScript 로 OOXML 생성기를 다시 쓰는 것"을 회귀 범위 때문에
제외했다.** 결정 0002 도 같은 이유로 재작성 대신 "같은 파이썬을 브라우저에서
돌린다"를 골랐다. **그 판단은 그때 옳았다.**

그 뒤에 하나가 생겼다: **바이트 수준 동등성 판정기**다.

| 지금 있는 것 | 무엇을 보장하나 |
|---|---|
| [`web/tests/xlsx_parity.py`](../../web/tests/xlsx_parity.py) | zip 부품별 정규화 비교. 정규화하는 것은 `dcterms:modified` 와 `<mergeCell>` 나열 **순서** 둘뿐이고 병합 **집합**이 달라지면 걸린다 |
| `web/tests/test_browser_parity.py` | 엔진 산출물 ↔ CPython 산출물 |
| `web/tests/test_browser_e2e.py` | 운영과 같은 CSP 아래 실제 Chromium 다운로드 ↔ CPython 산출물 |
| `tests/test_convert.py` 외 골든 회귀 | fixture 6종의 셀 단위 값·수식·서식·정렬·글꼴·병합·열너비·시트순서 |

즉 **"결과가 달라질 위험"을 사람의 검토가 아니라 기계가 판정한다.** 재작성을
막던 유일한 근거가 검증 가능한 문제로 바뀌었다. 이것 말고 새로 생긴 근거는
없다 — 성능이 불만이라는 사용자 보고도, 새 요구도 없다. 그러므로 이 계획은
**"해야 한다"가 아니라 "이제 재볼 수 있다"** 는 뜻이다.

## 3. 무엇이 열리는가 — 10 ms 벽

결정 0002 의 전제는 "Workers Free 는 요청당 CPU 10 ms 인데 가장 작은 견적서도
73 ms" 였다. 네이티브 Rust 로 73 ms 짜리가 5 ms 안쪽이면 **그 전제 자체가
무너지고 서버 변환이 무료 계정에서 성립한다.** 그러면 14.4 MiB 다운로드가
통째로 사라진다.

그런데 결정 0002 는 부수적으로 성질 하나를 얻었다 — **업로드한 XML 이
브라우저 밖으로 나가지 않는다.** 견적 데이터는 거래 조건이라 이 성질에는
값이 있다.

그래서 갈래가 둘이고, **이 계획은 A 를 고른다.**

| | A. 브라우저 WASM | B. 서버 Worker (Rust) |
|---|---|---|
| 자산 | 14.4 MiB → ~0.5 MiB | 0 (요청당 변환) |
| 기동 | 2.5 s → ~0.1 s | 없음 |
| XML 이 서버로 | **가지 않는다** | 간다 |
| 무료 계정 | 지금도 가능 | 10 ms 안에 들어야 가능 |
| 되돌리기 | 자산 교체 | 배포 구조 변경 |

A 는 지금의 아키텍처(자산만 배포)를 **그대로 두고 엔진만 바꾼다.** 얻는 것의
대부분(14.4 MiB, 2.5 s)을 가져오면서 잃는 것이 없다. B 는 A 를 끝낸 뒤에도
언제든 같은 코어로 열 수 있으니 지금 결정할 이유가 없다. **B 는 이 계획의
범위 밖이다.**

## 4. 단일 구현을 어떻게 지키는가 — 데스크톱 문제

가장 중요한 제약이다. 지금 저장소의 규칙은 **"변환 규칙은 공용 코어에 한 벌"**
이고, 데스크톱 EXE 가 그 코어를 그대로 부른다:

```
desktop_ibm/quotation_desktop/ui/main_window.py
    from quotation.core import convert, modes
```

웹만 Rust 로 옮기면 **구현이 둘이 된다.** 같은 견적서를 만드는 코드가 두 벌인
것은 이 저장소가 지금까지 한 번도 허용하지 않은 상태이고, 결정 0002 가
"사본을 따로 두지 않는다"고 못박은 것이기도 하다.

그래서 목표 구조는 **Rust 코어 한 벌 + 얇은 바인딩 둘**이다.

```text
                      quotation-core (Rust)   ← 변환 규칙은 여기 한 벌
                        ├── wasm-bindgen  →  브라우저 (web/)
                        └── PyO3          →  quotation.core (데스크톱·CI·골든)
```

`quotation.core` 의 **파이썬 공개 API 는 그대로 둔다** (`convert`,
`convert_bytes`, `parse_bytes`, `build_bytes`, `carry_over_bytes`,
`QuotationXmlError`, `modes`). 데스크톱과 기존 테스트는 import 를 한 줄도
고치지 않고 계속 돈다 — 안쪽 구현만 Rust 확장으로 바뀐다.

**이 구조가 성립하지 않으면 계획 전체를 접는다.** 구현을 두 벌로 갈라서까지
14.4 MiB 를 줄이지는 않는다.

## 5. Phase 0 — 관문 (1~2일)

나머지 단계는 전부 여기에 달려 있다. **세 가지만 확인하고, 하나라도 실패하면
이 문서는 폐기하고 그 사실을 결정 기록으로 남긴다.**

### 관문 1. 템플릿의 그림·서식이 보존되는가 ★ 가장 위험

지금 방식은 openpyxl 로 템플릿을 열어 채우고, openpyxl 이 버리는 그림·도형을
[`writer/drawings.py`](../../quotation/core/writer/drawings.py) 가 저장 뒤
zip 을 직접 손봐 되살린다. Rust 에서 확인할 것:

- `umya-spreadsheet` 로 템플릿을 열고 저장했을 때 그림·도형·서식이 남는가.
  남는다면 `drawings.py` 의 zip 수술이 **통째로 불필요**해진다.
- 남지 않는다면 `zip` + `quick-xml` 로 직접 다룬다. 이쪽이 오히려 지금 코드와
  가깝다 — `drawings.py` 는 이미 openpyxl 을 믿지 않고 zip 을 직접 고치고 있다.
- 판정: **템플릿을 열어 셀 한 개만 바꿔 저장한 결과가 `xlsx_parity.py` 기준으로
  openpyxl 산출물과 같은가.** 같으면 통과다.

### 관문 2. 추정한 크기·속도가 나오는가

- 코어 없이 "zip 열기 + XML 파싱 + 셀 쓰기 + zip 저장"만 하는 최소 WASM 을
  빌드해 **gzip 전송 크기**와 **기동 시간**을 잰다.
- 판정: 전송 1 MiB 이하, 기동 200 ms 이하. 넘으면 §1 표의 전제가 틀린 것이다.

### 관문 3. PyO3 확장이 배포 경로에 얹히는가

- 데스크톱은 PyInstaller 단일 EXE (`QuotationTool.spec`), CI 는 ubuntu-latest 다.
- 판정: PyO3 확장 모듈이 PyInstaller 번들에 들어가 EXE 가 뜨고, CI 에서
  `pip install` 로 빌드되거나 휠이 준비되는가.

## 6. Phase 1~5 (관문 통과 시)

포팅 대상은 코어 **1,975 줄** 중 `resources.py`(템플릿 위치, 30줄)를 뺀 1,944 줄이다. 위험이 낮은 것부터 옮기고, 매 단계마다
파이썬 구현과 **같은 fixture 로 대조**한다.

| 단계 | 범위 | 줄 수 | 동등성 판정 |
|---|---|---:|---|
| 1 ✅ | `money`, `naming`, `modes` | 186 | 단위 테스트 이식(`rust/core/tests/pure_rules.rs`). 파이썬·Rust 양쪽에 같은 입력을 넣어 출력 비교(`tools/rust_parity_pure_rules.py`) |
| 2 | `xml_reader` (`quick-xml` + `encoding_rs`) | 325 | fixture 6종의 파싱 결과가 파이썬 모델과 같은가. XXE 차단·인라인 DTD 거절 포함 |
| 3 | `models`, `integrated`, `dcsc_summary`, `convert` | 611 | 같은 fixture 로 중간 모델 비교 |
| 4 | `writer/*` (`ibm_writer`, `decorate`, `drawings`) | 822 | **`xlsx_parity.py` 로 최종 산출물 비교.** 여기가 본체다 |
| 5 | 바인딩 둘 + 배선 교체 | — | 아래 §7 |

### Phase 1 결과 (2026-08-26)

`rust/core` 크레이트에 `money` · `naming` · `modes` 를 옮겼다. 규칙은 한 줄도
바꾸지 않았고, 파이썬이 계속 기준이다.

- 이식한 단위 테스트 21건 통과 (`cargo test`).
- 대조 1,009건 통과 (`tools/rust_parity_pure_rules.py`). 입력은 지어내지 않고
  골든 fixture 6종과 저장소의 실제 구성 XML 에서 ProductDescription ·
  ProductName · MonetaryAmount 를 그대로 뽑아 썼다.
- 하네스가 실제로 차이를 잡는지 확인했다. Rust 쪽 금칙 문자 치환자를 일부러
  `-` 에서 `_` 로 바꾸자 `메일/스펨_1식`, `PCIe Gen4 I/O Expansion Drawer` 등
  실제 fixture 값에서 14건이 붉어졌다.

이 단계에서 파이썬 구현만으로는 몰랐던 것 하나가 드러났다. 레노버 DCSC 는
금액을 지수 표기(`4.0172E7`)로 적고, 그 값이 골든 fixture 에 들어 있다.
[결정 0006](../decisions/0006-compare-amounts-by-value.md) 이 이 값을 어떻게
대조할지 정한다.

파이썬 문자열 규칙 가운데 Rust 기본값과 다른 둘은 `rust/core/src/text.rs` 에
모아 두었다 — `str.strip()` 의 공백 범위(`0x1c`~`0x1f` 포함)와, 바이트가
아니라 글자 수로 자르는 슬라이스다. 한글 장비 이름이 31자 제한에 걸리는 자리다.

Phase 2 에서 **EUC-KR 우회책이 없어진다.** Pyodide 의 libxml2 에 iconv 가 없어
넣은 것인데([사고 0002](../incidents/0002-pyodide-lxml-euckr.md)),
`encoding_rs` 는 EUC-KR 을 기본으로 안다. 우회책은 지우고 사고 기록은 남긴다 —
왜 있었는지가 기록의 값이다.

## 7. 동등성을 어떻게 지키는가

**새 판정기를 만들지 않는다.** 지금 있는 것을 Rust 산출물에 그대로 겨눈다.

1. `tests/` 의 골든 회귀 — fixture 6종(신규·증설·N/C·REMOVE·EUC-KR·인라인 DTD)이
   셀 단위로 통과해야 한다. `golden_ignore.txt` 를 늘리지 않는다.
2. `web/tests/test_browser_parity.py` — 브라우저 WASM 산출물 ↔ CPython 산출물.
   이 테스트의 "CPython" 쪽은 포팅 중 **파이썬 원본**을 가리키게 유지한다.
   그래야 Rust 가 파이썬과 같은지를 계속 묻는다.
3. `web/tests/test_browser_e2e.py` — 실제 Chromium.
4. CI `core` 잡의 lxml 6.1.1 / 6.0.0 이중 매트릭스는 **Phase 2 완료 시점에
   없어진다.** lxml 판본이 갈리는 문제 자체가 사라지기 때문이다. 매트릭스를
   지우는 커밋에 그 이유를 적는다.

**전환 시점의 규칙:** 파이썬 구현과 Rust 구현을 나란히 두는 기간은 CI 대조를
위해서만 존재하고, Phase 5 가 끝나면 **파이썬 구현을 지운다.** 플래그로 두
경로를 남기지 않는다.

## 8. 범위 밖

- **서버 변환(B 안).** §3 참조. 코어가 Rust 가 되면 언제든 열 수 있다.
- **템플릿 규칙 변경.** 셀 매핑([`spec/SPEC_CELLMAP.md`](../spec/SPEC_CELLMAP.md))과
  통합 모드 해석([`spec/SPEC_INTEGRATED.md`](../spec/SPEC_INTEGRATED.md))은 한 줄도
  바꾸지 않는다. 이 계획은 **같은 결과를 더 싸게 만드는 것**이지 결과를 바꾸는
  것이 아니다.
- **화면(`web/frontend`).** 변환 일꾼이 부르는 것이 Pyodide 에서 WASM 모듈로
  바뀔 뿐 API 계약과 UI 는 그대로다.
- **데스크톱 UI.** `quotation.core` 의 공개 API 가 유지되므로 손대지 않는다.

## 9. 되돌리는 조건

- Phase 0 관문 셋 중 하나라도 실패 → 계획 폐기. 결정 기록에 "무엇이 막았는지"를
  적는다.
- Phase 4 에서 `xlsx_parity.py` 를 통과시키기 위해 **정규화 규칙을 늘려야 한다면
  중단한다.** 지금 정규화하는 둘은 견적서 내용이 아니다. 셋째가 필요하다는 것은
  결과가 달라졌다는 뜻이고, 견적서에서 그것은 용납되지 않는다.
- 단일 구현(§4)이 깨지면 중단한다.

## 10. 열린 질문 (Phase 0 에서 답한다)

- `umya-spreadsheet` 가 템플릿의 도형·머리말 이미지를 보존하는가, 아니면 zip 을
  직접 다뤄야 하는가.
- PyO3 확장이 PyInstaller 단일 EXE 에 들어가는가. 안 들어가면 데스크톱만
  파이썬으로 남기는 선택지가 생기는데, 그건 §4 를 깨므로 그 자체가 중단 사유다.
- WASM 모듈을 Web Worker 안에서 부를 때 큰 XML(상한은 `web/src/limits.py`)
  전달 비용이 얼마인가. 지금은 Pyodide 가 파일 바이트를 그대로 받는다.
