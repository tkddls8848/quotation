# 문서

성격에 따라 나눠 둔다. 찾는 것이 무엇이냐에 따라 갈 곳이 다르다.

| 폴더 | 성격 | 언제 보는가 |
|---|---|---|
| [`spec/`](spec/) | 명세 | 어느 셀에 무엇이 들어가야 하는가. 회귀 판정 기준 |
| [`guide/`](guide/) | 사용자 안내 | 쓰는 사람에게 무엇이 달라지는가 |
| [`plan/`](plan/) | 계획 | 착수 시점의 설계 의도와 범위 |
| [`decisions/`](decisions/) | 결정 기록 | 계획을 뒤집은 이유와 되돌리는 조건 |
| [`incidents/`](incidents/) | 사고 기록 | 실제로 깨진 것과 재발을 막는 장치 |
| [`measurements/`](measurements/) | 실측 | 판단의 근거가 된 숫자 |

계획은 **착수 시점 그대로 둔다.** 뒤집힌 것은 계획을 고쳐 덮지 않고 결정
기록으로 남긴다. 그래야 왜 그렇게 됐는지가 남는다. 지금 무엇이 사실인지는
아래 표와 각 폴더의 `README`·본문이 답한다.

## 문서 목록

| 문서 | 성격 |
|---|---|
| [`spec/SPEC_CELLMAP.md`](spec/SPEC_CELLMAP.md) | 셀 매핑과 검증 기준 |
| [`guide/MIGRATION.md`](guide/MIGRATION.md) | 2005년판에서 넘어오는 기존 사용자 안내 |
| [`plan/web-app-plan.md`](plan/web-app-plan.md) | 웹 앱 구현 계획 (2026-08-14 착수안) |
| [`decisions/0001-template-in-bundle.md`](decisions/0001-template-in-bundle.md) | 템플릿을 R2 에서 번들로 |
| [`decisions/0002-convert-in-browser.md`](decisions/0002-convert-in-browser.md) | 변환을 서버에서 브라우저로 |
| [`incidents/0001-worker-rejected-everything.md`](incidents/0001-worker-rejected-everything.md) | Worker 가 모든 변환을 거절했다 |
| [`incidents/0002-pyodide-lxml-euckr.md`](incidents/0002-pyodide-lxml-euckr.md) | Pyodide 의 libxml2 는 EUC-KR 을 모른다 |
| [`measurements/runtime.md`](measurements/runtime.md) | CPU·판본·크기 실측 |

운영·배포 절차는 문서 폴더가 아니라 코드 옆에 둔다 —
[`web/README.md`](../web/README.md), [`desktop/README.md`](../desktop/README.md).

## 지금 구조

```text
브라우저                                   Cloudflare (정적 자산만)
  ┌──────────────────────────────┐
  │ 화면 (main.ts)               │  ← index.html, js, css
  │   └ 변환 일꾼 (Web Worker)   │
  │       └ Pyodide              │  ← /py/*
  │           └ entry.py         │  ← quotation-core.zip
  │               └ api.py       │     (= web/src 의 그 파일들)
  │                   └ quotation.core
  └──────────────────────────────┘
     XML 도 결과도 이 안에서만 오간다
```

서버 변환 경로(`web/src/worker.py`)는 버리지 않고 `wrangler.jsonc` 의
`env.server`(Workers Paid 전용)에 남겨 두었다. 무료 계정 배포에는 없다.

## 구현 현황

| 단계 | 상태 | 비고 |
|---|---|---|
| Phase 0 기준선·fixture | **완료** | `tests/fixtures/public/` 에 신규·증설·N/C·REMOVE·EUC-KR·인라인 DTD fixture. 런타임 검증은 [실측](measurements/runtime.md)으로 끝냈다 |
| Phase 1 코어 bytes I/O | **완료** | `parse_bytes`, `build_bytes`, `carry_over_bytes`, `convert_bytes`. 경로 API 는 데스크톱 어댑터로 유지. path/bytes 동등성 테스트 통과 |
| Phase 2 변환 API | **완료** | `/convert`, `/status`, `/config`, 상한·오류코드·보안 헤더·Asia/Seoul 날짜·구조화 로그. 같은 `api.py` 를 Worker 와 브라우저가 함께 쓴다 |
| Phase 3 웹 UI | **완료** | 드래그앤드롭, 여러 화일 일괄 변환, 단계 상태, 취소, 중복 제출 방지, 접근성, 한글 파일명 다운로드 |
| Phase 4 보안·운영 | **범위 축소** | 변환이 브라우저에서 끝나 서버에 남길 것이 없다. Access·Rate Limiting 은 `env.server` 를 쓸 때만 필요 |
| Phase 5 CI/CD | **완료** | `.github/workflows/ci.yml` — 테스트·번들 검사·브라우저 동일성·배포 |
| Phase 6 병행 운영 | 진행 중 | 데스크톱 앱을 복구 수단으로 유지. 결과 동일성은 CI 가 매 푸시 대조 |

## 계획에서 달라진 것

| 계획 | 지금 | 기록 |
|---|---|---|
| 템플릿을 비공개 R2 에 버전별로 | 저장소 원본 한 개를 번들에 담는다 | [결정 0001](decisions/0001-template-in-bundle.md) |
| 변환은 Python Worker (Workers Paid 전제) | 변환은 브라우저 (무료 계정) | [결정 0002](decisions/0002-convert-in-browser.md) |
| Cloudflare Access 로 접근 제어 | 적용하지 않음. 서버에 XML 이 가지 않는다 | [결정 0002](decisions/0002-convert-in-browser.md) |
| 한 번에 화일 1개 | 화면에서 최대 50개, 변환은 한 건씩 | `web/frontend/src/batch.ts` |
| Container fallback 검토 | 하지 않음. Paid 전제라 무료 계정 문제를 못 푼다 | [결정 0002](decisions/0002-convert-in-browser.md) |
