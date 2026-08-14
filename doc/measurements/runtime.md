# 실측 — 런타임, 판본, 크기

측정일 2026-08-14. 판단의 근거가 된 숫자만 모은다. 이 숫자들이 계획을 두 번
뒤집었다([결정 0001](../decisions/0001-template-in-bundle.md),
[결정 0002](../decisions/0002-convert-in-browser.md)).

## 변환 1건의 CPU 시간

`time.process_time()` 기준, 워밍업 후 평균, 네이티브 CPython. I/O 대기는
포함하지 않으므로 Workers 의 CPU 한도와 직접 비교할 수 있다.

| 입력 | 라인 | CPU | Free 한도(10 ms) 대비 |
|---|---:|---:|---:|
| `euckr_quote.xml` | 1 | 73 ms | 7배 |
| `new_quote.xml` | 3 | 108 ms | 11배 |
| `upgrade_quote.xml` | 2 | 82 ms | 8배 |
| 합성 대형 (7시트) | 51 | 423 ms | 42배 |

**가장 작은 견적서도 Free 한도를 7배 넘는다.** Pyodide(WASM)는 네이티브보다
통상 2~5배 느리고 첫 요청의 import 비용이 더해지므로 실제 소요는 이보다 크다.

이 표가 계획 §4.2 의 "운영 기준은 Workers Paid" 판단을 확정했고, 운영 계정이
무료 계정이라는 사실과 만나 [결정 0002](../decisions/0002-convert-in-browser.md)
가 됐다.

## 판본 — 데스크톱과 브라우저가 갈리는 곳

| 항목 | 데스크톱 | 브라우저/Worker (Pyodide) |
|---|---|---|
| `lxml` | 6.1.1 | **6.0.0** — Pyodide 인덱스에 6.1.1 wheel 이 없다 |
| `openpyxl` | 3.1.5 | 3.1.5 (같다) |
| 부수 | — | `et-xmlfile` 2.0.0, `workers-runtime-sdk` 1.6.13 |

`lxml` 판본이 갈리므로 **CI 의 코어 테스트를 6.1.1 과 6.0.0 양쪽에서 돌린다.**

## 크기

| 항목 | 실측 | 한도 대비 |
|---|---|---|
| 브라우저 엔진 자산 | 14.4 MiB (Pyodide 11.1 + lxml 1.7 + openpyxl 0.9 + 코어 0.1) | 정적 자산이라 한도 없음 |
| Paid `--env server` 번들 | 7,532 KiB (gzip 1,943 KiB), 352 모듈 | Paid 10 MB 안. 여유는 넉넉하지 않다 |
| vendoring | 8.3 MB (lxml 6.6 MB + openpyxl 1.4 MB) | |
| 템플릿 | 30 KB → base64 41 KB | 번들 대비 무시할 수준 |

## 브라우저 기동

| 항목 | 실측 |
|---|---|
| Pyodide 기동 | 약 1.9 초 (첫 변환 전 한 번) |
| lxml 적재 | 약 0.6 초 |
| 변환 1건 | 대표 입력 약 0.3 초 (CPython 0.1 초의 3배) |

## 요금제 제약 (배포 실측)

`limits.cpu_ms` 는 **Workers Paid 전용**이라 Free 계정에서는 그 항목이 있는
것만으로 배포가 거부된다.

```text
✘ CPU limits are not supported for the Free plan [code: 100328]
```

그래서 `wrangler.jsonc` 의 기본 환경에는 없고 `env.server` 에만 있다.

## 배포 도구 사실관계

첫 CI 배포 실패로 확인한 내용이다. 계획 §4 의 아키텍처와 별개로 배포 절차가
계획과 달랐다.

- `cloudflare/wrangler-action@v3` 은 기본으로 **wrangler 3.90** 을 설치한다.
  3.x 는 `wrangler.jsonc` 를 읽지 못해 설정 전체를 무시하고 `Missing
  entry-point` 로 죽는다. **wrangler 4.42.1 이상**이 필요하며 판본은
  `web/package.json` 에 고정했다.
- 의존성은 `requirements.txt` 가 아니라 `pyproject.toml` 에 적고 **`pywrangler`**
  (PyPI `workers-py`, `uv>=0.12.3` 필요)로 배포한다. `pywrangler sync` 가
  Pyodide 인덱스(`index.pyodide.org`)에서 대상 플랫폼
  (`cpython-*-emscripten-wasm32-musl`)용 패키지를 받아 `web/python_modules/` 에
  vendoring 한 뒤 wrangler 로 넘긴다. `wrangler deploy` 를 직접 부르면 코드만
  올라가고 `lxml`·`openpyxl` 이 빠져 첫 요청에서 import 오류가 난다.
- `wrangler deploy --dry-run` 은 자격 증명 없이 설정과 번들을 검사한다. CI 의
  `bundle` 잡이 매 푸시마다 이 검사를 돌린다.

이 항목들은 **`--env server`(Paid) 배포에만** 해당한다. 무료 계정 배포는
정적 자산뿐이라 `wrangler` 하나로 끝난다.

## 다시 재려면

```powershell
python -m pytest web/tests/test_browser_parity.py -q   # 동일성
python web/scripts/build_browser_engine.py --check     # 엔진 자산 최신 여부
cd web; npx wrangler deploy --dry-run --env server     # 번들 크기
```
