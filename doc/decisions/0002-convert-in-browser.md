# 결정 0002 — 변환을 서버에서 브라우저로 옮긴다

- 날짜: 2026-08-14
- 상태: **적용됨**
- 뒤집은 것: [계획 §4 권장 아키텍처](../plan/web-app-plan.md#4-권장-아키텍처),
  [계획 §1 결론](../plan/web-app-plan.md#1-결론)
- 근거가 된 실측: [변환 1건의 CPU 시간](../measurements/runtime.md#변환-1건의-cpu-시간)

## 계획은 무엇이었나

계획 §4.2 는 "운영 기준은 Workers Paid" 로 잡았고, 변환은 Python Worker 가
수행하는 구조였다. [실측](../measurements/runtime.md)이 그 판단을 확정했다.

## 왜 바꿨나

운영 계정이 **무료 계정** 이면 그 길이 애초에 닫혀 있다. Workers Free 는
요청당 CPU 10 ms 인데 가장 작은 견적서도 73 ms 가 든다. 코드를 빨리 만들어
넘길 수 있는 차이가 아니다(7~42배).

Paid 로 올리지 않고 무료 계정에서 원활히 돌리는 길은 하나뿐이다 — 변환을
서버에서 빼는 것. 그렇다고 변환기를 다시 쓰면 결과가 달라질 위험이 생기고,
그것은 견적서에서 용납되지 않는다. 그래서 **같은 파이썬을 브라우저에서
돌린다.**

```text
이전   브라우저 --XML--> Worker(Pyodide) --XLSX--> 브라우저
이후   브라우저(Pyodide) 안에서 시작하고 끝난다. Cloudflare 는 자산만 준다
```

계획 §1 은 "브라우저에서 Excel 을 직접 만드는 방식" 을 1차안에서 제외했는데,
그 제외는 **지금도 유효하다.** 제외된 것은 TypeScript 로 OOXML 생성기를 다시
쓰는 것이었고, 여기서 하는 것은 같은 파이썬을 옮겨 돌리는 것이다. 회귀 범위가
지나치게 커진다는 §1 의 우려는 재작성을 하지 않으므로 생기지 않는다.

## 바뀌지 않는 것

- 변환 코어(`quotation.core`), 검증·가드(`conversion_adapter`, `limits`),
  응답 계약(`api`), 견적 날짜(`clock`), 템플릿(`template`) — **파일이 같다.**
  사본을 두지 않고 `build_browser_engine.py` 가 `web/src` 를 그대로 담는다.
- 부르는 함수도 같다. `worker.py` 와 `browser/entry.py` 가 둘 다
  `api.convert_response` 를 부른다.
- API 계약(계획 §6)과 화면(계획 §7)의 겉모습.

## 바뀌는 것

| | 이전 | 이후 |
|---|---|---|
| 변환 위치 | Worker (Pyodide) | 브라우저 (Pyodide) |
| 기본 배포 | Python Worker + 자산 | **자산만** (`main` 없음) |
| 요청당 CPU 한도 | 걸린다 | 해당 없음 |
| 하루 요청 한도 | 변환마다 소모 | 소모 없음 (정적 자산은 무료·무제한) |
| 배포 도구 | pywrangler + uv + vendoring | wrangler 만 |
| 업로드 XML | 서버 메모리를 거친다 | 브라우저 밖으로 나가지 않는다 |
| 첫 방문 비용 | 없음 | 엔진 14.4 MiB (한 번, 이후 재검증만) |
| 변환 1건 | — | 약 0.3 초 (기동 후) |

계획 §4.2 의 Container 전환은 하지 않는다. 그것은 Paid 를 전제로 하므로 무료
계정 문제를 풀지 못한다. 서버 변환 자체는 버리지 않고 `wrangler.jsonc` 의
`env.server`(Workers Paid 전용)로 남겨 둔다. 화면은 브라우저 엔진을 못 띄웠을
때만 그쪽으로 넘어간다.

## 결과가 같다는 것을 무엇으로 증명하는가

"같은 코드를 쓴다" 는 설계일 뿐이므로 테스트로 못박는다.

| 테스트 | 지키는 것 |
|---|---|
| `web/tests/test_browser_engine.py` | 엔진에 담기는 코드와 양식이 저장소 원본과 바이트가 같다. lxml·openpyxl 판본이 `web/pyproject.toml` 과 같다. 받아 오는 파일은 모두 sha256 으로 고정되어 있다 |
| `web/tests/test_browser_parity.py` | Node 로 엔진을 돌려 만든 견적서가 CPython 산출물과 같다. `.xlsx`(zip) 안의 모든 부품을 바이트로, 그리고 골든 회귀와 같은 비교기(`tools/compare.py`)로 셀 단위로. 오류 사례의 상태 코드·오류 코드도 함께 |
| `web/tests/test_browser_e2e.py` | 운영과 같은 CSP 를 건 서버에서 실제 Chromium 으로 내려받은 파일이 CPython 산출물과 같다 |

정규화하는 것은 둘뿐이며 둘 다 견적서 내용이 아니다 — 파일 생성 **시각**
(`docProps/core.xml` 의 `dcterms:modified`)과 `<mergeCell>` 의 나열 **순서**
(집합은 같아야 하고, 다르면 테스트가 잡는다). 근거는 `web/tests/xlsx_parity.py`.

## 이 결정이 드러낸 결함

옮기고 실제로 돌려 보니 EUC-KR 견적서가 통째로 변환되지 않았다. Python Worker
로 갔어도 같은 결과였을 문제다 —
[사고 0002](../incidents/0002-pyodide-lxml-euckr.md).

## 남은 것

- 첫 방문 14.4 MiB 는 Cloudflare 가 압축해 보내지만 여전히 크다. 줄일 여지는
  lxml(1.7 MiB)을 걷어내는 것뿐인데, 파서를 바꾸면 동작이 갈릴 수 있으므로
  하지 않는다.
- WebAssembly 를 못 쓰는 브라우저에서는 `env.server` 배포가 있어야 변환된다.
  무료 계정만 쓸 때는 그런 브라우저를 지원하지 않는다는 뜻이 된다.
