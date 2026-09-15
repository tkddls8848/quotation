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
| [`spec/SPEC_INTEGRATED.md`](spec/SPEC_INTEGRATED.md) | 통합 모드 (레노버 x86) 해석 규칙 |
| [`guide/MIGRATION.md`](guide/MIGRATION.md) | 2005년판에서 넘어오는 기존 사용자 안내 |
| [`plan/web-app-plan.md`](plan/web-app-plan.md) | 웹 앱 구현 계획 (2026-08-14 착수안) |
| [`plan/rust-wasm-core-plan.md`](plan/rust-wasm-core-plan.md) | 변환 코어 Rust→WASM 이식 계획 (착수 전) |
| [`decisions/0001-template-in-bundle.md`](decisions/0001-template-in-bundle.md) | 템플릿을 R2 에서 번들로 |
| [`decisions/0002-convert-in-browser.md`](decisions/0002-convert-in-browser.md) | 변환을 서버에서 브라우저로 |
| [`decisions/0003-reject-rust-wasm-core-after-phase0.md`](decisions/0003-reject-rust-wasm-core-after-phase0.md) | Rust→WASM 전환을 하지 않는다 (결정 0004 가 철회) |
| [`decisions/0004-resume-rust-wasm-phase0.md`](decisions/0004-resume-rust-wasm-phase0.md) | 그 폐기를 철회하고 Phase 0 을 다시 연다 |
| [`decisions/0005-accept-meaningful-xlsx-parity.md`](decisions/0005-accept-meaningful-xlsx-parity.md) | 동등성은 내용과 첫 페이지 도형으로 판정한다 |
| [`decisions/0006-compare-amounts-by-value.md`](decisions/0006-compare-amounts-by-value.md) | 금액은 표기가 아니라 값으로 판정한다 |
| [`decisions/0007-phase0-gates-passed.md`](decisions/0007-phase0-gates-passed.md) | Phase 0 관문 통과 — 이식을 계속한다 |
| [`decisions/0008-wasm-size-after-the-writer.md`](decisions/0008-wasm-size-after-the-writer.md) | 완성된 코어의 전송 크기는 1.012 MiB |
| [`decisions/0009-browser-parity-judges-content.md`](decisions/0009-browser-parity-judges-content.md) | 브라우저 동일성은 ZIP 바이트가 아니라 내용으로 |
| [`decisions/0010-retire-the-server-conversion-path.md`](decisions/0010-retire-the-server-conversion-path.md) | 서버 변환 경로(Workers Paid)를 없앤다 |
| [`decisions/0011-no-byte-reproducibility.md`](decisions/0011-no-byte-reproducibility.md) | 바이트 재현성은 보증하지 않는다. 내용은 보증한다 |
| [`decisions/0012-one-folder-per-feature.md`](decisions/0012-one-folder-per-feature.md) | 기능마다 최상위 폴더 하나 |
| [`decisions/0013-deposit-products-from-fss.md`](decisions/0013-deposit-products-from-fss.md) | 예적금 상품은 공시에서, 창구 Worker 하나 (결정 0014 가 뒤집음) |
| [`decisions/0014-retire-the-fire-calculator.md`](decisions/0014-retire-the-fire-calculator.md) | FIRE 계산기를 내린다 |
| [`decisions/0015-both-pdf-to-hwpx-modes.md`](decisions/0015-both-pdf-to-hwpx-modes.md) | PDF → HWPX 는 이미지·텍스트 두 방식 모두 |
| [`decisions/0016-a-server-only-for-hwp-to-pdf.md`](decisions/0016-a-server-only-for-hwp-to-pdf.md) | HWP → PDF 에만 서버를 다시 들인다 |
| [`decisions/0017-cloudflare-builds-owns-deploys.md`](decisions/0017-cloudflare-builds-owns-deploys.md) | 배포는 Cloudflare Workers Builds 가 갖는다 |
| [`incidents/0001-worker-rejected-everything.md`](incidents/0001-worker-rejected-everything.md) | Worker 가 모든 변환을 거절했다 |
| [`incidents/0002-pyodide-lxml-euckr.md`](incidents/0002-pyodide-lxml-euckr.md) | Pyodide 의 libxml2 는 EUC-KR 을 모른다 |
| [`measurements/runtime.md`](measurements/runtime.md) | CPU·판본·크기 실측 |

운영·배포 절차는 문서 폴더가 아니라 코드 옆에 둔다 —
[`web/README.md`](../web/README.md), [`quotation/desktop/README.md`](../quotation/desktop/README.md).

## 지금 구조

```text
브라우저                                   Cloudflare (정적 자산만)
  ┌──────────────────────────────┐
  │ 셸 (main.ts)                 │  ← index.html, js, css
  │   └ 견적서 탭 (panel.ts)     │
  │       └ 변환 일꾼 (Worker)   │
  │           └ engine.js        │  ← /engine/engine.json
  │               └ quotation_wasm  ← /engine/quotation_wasm_bg.wasm
  │                   └ rust/core · rust/webapi
  └──────────────────────────────┘
     XML 도 결과도 이 안에서만 오간다
```

브라우저가 돌리는 것은 데스크톱이 쓰는 것과 **같은 Rust 코어**다. 변환 규칙도,
파일 검증과 오류 문구도 `quotation/rust/` 한 벌에서 온다. 예전의 Pyodide·파이썬
경로는 남아 있지 않다 ([결정 0004](decisions/0004-resume-rust-wasm-phase0.md),
[0007](decisions/0007-phase0-gates-passed.md),
[0008](decisions/0008-wasm-size-after-the-writer.md)).

견적서의 서버 변환 경로는 남아 있지 않다 — `web/src/worker.py` 와 `env.server` 는
[결정 0010](decisions/0010-retire-the-server-conversion-path.md)이 지웠다. 서버를 쓰는
곳은 문서 변환기의 HWP → PDF 하나뿐이고, 그것은 Cloudflare 가 아니라 따로 도는
컨테이너다 ([결정 0016](decisions/0016-a-server-only-for-hwp-to-pdf.md)).

## 구현 현황

| 단계 | 상태 | 비고 |
|---|---|---|
| Phase 0 기준선·fixture | **완료** | `tests/fixtures/public/` 에 신규·증설·N/C·REMOVE·EUC-KR·인라인 DTD fixture. 런타임 검증은 [실측](measurements/runtime.md)으로 끝냈다 |
| Phase 1 코어 bytes I/O | **완료** | `parse_bytes`, `build_bytes`, `carry_over_bytes`, `convert_bytes`. 경로 API 는 데스크톱 어댑터로 유지. path/bytes 동등성 테스트 통과 |
| Phase 2 변환 API | **완료** | 상한·오류코드·보안 헤더·Asia/Seoul 날짜. 그 계약은 `quotation/rust/webapi` 한 벌이고 데스크톱과 브라우저가 같은 것을 부른다 |
| Phase 3 웹 UI | **완료** | 드래그앤드롭, 여러 화일 일괄 변환, 단계 상태, 취소, 중복 제출 방지, 접근성, 한글 파일명 다운로드 |
| Phase 4 보안·운영 | **범위 축소** | 변환이 브라우저에서 끝나 서버에 남길 것이 없다. 서버 경로 자체를 없앴으므로 Access·Rate Limiting 도 대상이 없다 ([결정 0010](decisions/0010-retire-the-server-conversion-path.md)) |
| Phase 5 CI/CD | **완료** | `.github/workflows/ci.yml` — 테스트·번들 검사·브라우저 동일성·배포 |
| Phase 6 병행 운영 | 진행 중 | 데스크톱 앱을 복구 수단으로 유지. 결과 동일성은 CI 가 매 푸시 대조 |

## 계획에서 달라진 것

| 계획 | 지금 | 기록 |
|---|---|---|
| 템플릿을 비공개 R2 에 버전별로 | 저장소 원본 한 개를 번들에 담는다 | [결정 0001](decisions/0001-template-in-bundle.md) |
| 변환은 Python Worker (Workers Paid 전제) | 변환은 브라우저 (무료 계정) | [결정 0002](decisions/0002-convert-in-browser.md) |
| 변환 코어는 파이썬 한 벌 | Rust 한 벌. 데스크톱은 확장 모듈로, 브라우저는 WASM 으로 부른다 | [결정 0004](decisions/0004-resume-rust-wasm-phase0.md), [0007](decisions/0007-phase0-gates-passed.md) |
| 첫 방문에 엔진 14.4 MiB (Pyodide) | 약 1 MiB (gzip). 기동 1.9초 → 5 ms 안팎 | [결정 0008](decisions/0008-wasm-size-after-the-writer.md) |
| Cloudflare Access 로 접근 제어 | 적용하지 않음. 서버에 XML 이 가지 않는다 | [결정 0002](decisions/0002-convert-in-browser.md) |
| 한 번에 화일 1개 | 화면에서 최대 50개, 변환은 한 건씩 | `web/frontend/src/batch.ts` |
| Container fallback 검토 | 하지 않음. Paid 전제라 무료 계정 문제를 못 푼다 | [결정 0002](decisions/0002-convert-in-browser.md) |
| Worker 스크립트 없음 (정적 자산만) | 그대로다. 공시 중계 창구는 계산기와 함께 내렸다 | [결정 0013](decisions/0013-deposit-products-from-fss.md), [0014](decisions/0014-retire-the-fire-calculator.md) |
| 파일은 브라우저 밖으로 나가지 않는다 | 문서 변환기의 HWP → PDF 만 예외. 동의를 받고 보내며 결과는 15분 뒤 지운다 | [결정 0016](decisions/0016-a-server-only-for-hwp-to-pdf.md) |
| 배포 경로가 둘(대시보드·Actions) | Workers Builds 하나. Actions 의 배포 잡은 지웠다 | [결정 0017](decisions/0017-cloudflare-builds-owns-deploys.md) |
