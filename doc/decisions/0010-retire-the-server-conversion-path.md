# 결정 0010 — 서버 변환 경로(Workers Paid)를 없앤다

- 날짜: 2026-08-28
- 상태: **적용됨**
- 잇는 결정: [결정 0002](0002-convert-in-browser.md)
- 관련 계획: [남은 일정 §5](../plan/rust-wasm-core-schedule.md)

## 결론

`env.server`(Workers Paid 위의 서버 변환 API)를 지운다. 변환은 브라우저의
Rust→WASM 엔진 한 벌만 한다.

지우는 것: `web/src/worker.py`, `wrangler.jsonc` 의 `env.server`,
`web/pyproject.toml`(Pyodide 인덱스용 의존성 고정), 그 경로를 지키던 검사
(`test_worker_smoke.py`, `test_worker_runtime.py`)와 CI 의 pywrangler 단계.

## 왜

브라우저 엔진을 Rust 로 바꾸면서 갈림길이 하나 생겼다. 브라우저 안에서 도는
것은 변환 코어만이 아니라 **API 층**(파일 검증·응답 헤더·오류 문구)까지인데,
그 `api.py` 는 서버 경로와 **같은 파일**이었다. 그래서 셋 중 하나를 골라야 했다.

| | A. 무료 경로만 남긴다 | B. 서버는 파이썬으로 남긴다 | C. 배선을 바꾸지 않는다 |
|---|---|---|---|
| 브라우저 | WASM (코어+API) | WASM (코어+API) | 지금 그대로 Pyodide |
| 서버 | 없앤다 | 파이썬 유지 | 그대로 |
| 구현 벌수 | **한 벌** | 코어까지 두 벌 | 한 벌 |
| 사용자가 얻는 것 | 14.4 MiB → 1.0 MiB | 같음 | 없음 |

B 가 "API 층만 두 벌"이 아니라 **코어까지 두 벌**인 까닭은 이렇다. Workers 의
파이썬은 Pyodide 위에서 돈다. 그 안에서 Rust 확장을 부르려면 emscripten 용
휠을 따로 만들어야 하는데 해 본 적이 없다. 그러지 못하면 서버는 파이썬 코어를
계속 써야 하고, 그것은 이 계획이 처음부터 막으려던 상태다
([착수안 §4](../plan/rust-wasm-core-plan.md)).

사용자가 A 를 골랐다.

## 무엇을 잃는가

**"엔진을 못 띄운 브라우저는 서버로 넘어간다"는 대비책이 사라진다.** 그
대비책이 실제로 쓰인 적은 없고, 운영 계정이 무료라 그 경로는 배포된 적도 없다
(결정 0002 가 브라우저 변환을 고른 이유가 그것이다). 그래도 잃는 것은 잃는 것
이므로 적어 둔다.

되돌리는 값은 크지 않다. 코어와 API 층이 Rust 한 벌로 남아 있으므로, 서버가
필요해지면 그 크레이트를 Workers 의 JavaScript/WASM 위에 얹거나 다른 런타임에
올리면 된다. 파이썬 Worker 로 되돌릴 이유는 없다.

## 남는 것

- 배포는 정적 자산뿐이다. `wrangler` 하나로 끝나고 pywrangler·uv·Pyodide
  vendoring 이 필요 없다.
- CI 의 `bundle` 잡은 "Worker 스크립트가 잡히지 않는가"만 본다. 여기 스크립트가
  잡히면 무료 계정 전제가 깨진 것이다.
- 사고 기록 [0001](../incidents/0001-worker-rejected-everything.md)은 남긴다.
  그 사고가 왜 났는지가 기록의 값이고, 같은 실수(런타임 경계에서 이름이 갈리는
  것)는 다른 경계에서도 날 수 있다.
