# 웹 앱 (Cloudflare Workers)

브라우저에서 eConfig XML 을 고르면 견적서 `.xlsx` 가 만들어져 바로 내려옵니다.
설계 근거와 단계별 계획은
[`doc/CLOUDFLARE_WORKERS_WEB_IMPLEMENTATION_PLAN.md`](../doc/CLOUDFLARE_WORKERS_WEB_IMPLEMENTATION_PLAN.md).

## 변환은 브라우저에서 돈다 (무료 계정 기준)

Cloudflare Workers **Free 는 요청당 CPU 10 ms** 다. 견적서 한 건을 만드는 데는
가장 작은 입력도 73 ms, 큰 것은 423 ms 가 든다(계획서 §18.3 실측). 서버에서
만드는 길은 무료 계정에서 애초에 성립하지 않는다.

그래서 변환을 브라우저로 옮겼다. Cloudflare 는 정적 자산만 내려 준다.

```text
브라우저                                   Cloudflare (정적 자산만)
  ┌──────────────────────────────┐
  │ 화면 (main.ts)               │  ← index.html, js, css
  │   └ 변환 일꾼 (Web Worker)   │
  │       └ Pyodide              │  ← /py/pyodide.*  python_stdlib.zip
  │           ├ lxml (wasm wheel)│  ← /py/lxml-*.whl
  │           ├ openpyxl         │  ← /py/python-deps.zip
  │           └ entry.py         │  ← /py/quotation-core.zip
  │               └ api.py       │     (= web/src 의 그 파일들)
  │                   └ quotation.core
  └──────────────────────────────┘
     XML 도 결과도 이 안에서만 오간다
```

무료 계정에서 이렇게 하면:

| | |
|---|---|
| 요청당 CPU 한도 (10 ms) | 해당 없음 — Worker 스크립트가 없다 |
| 하루 요청 한도 (10만) | 쓰지 않음 — 정적 자산 요청은 무료·무제한 |
| Worker 스크립트 크기 (3 MiB) | 해당 없음 |
| 배포 도구 | wrangler 만. pywrangler·uv·Pyodide vendoring 불필요 |
| 업로드한 XML | 브라우저 밖으로 나가지 않는다 |

첫 방문에 변환 엔진 약 14 MiB 를 받고(압축 전송), 그 뒤로는 재검증만 한다.
엔진이 뜬 뒤 변환 자체는 대표 입력 기준 0.3 초 안팎이다.

### 결과가 같다는 것은 어떻게 아는가

브라우저가 돌리는 파이썬은 서버가 돌리던 것과 **같은 파일** 이다. 사본을 따로
두지 않고 `web/scripts/build_browser_engine.py` 가 `web/src` 에서 그대로 zip
으로 묶는다. 부르는 함수도 `api.convert_response` 로 같다.

그 위에 테스트 세 겹을 둔다.

| 테스트 | 무엇을 지키는가 |
|---|---|
| `web/tests/test_browser_engine.py` | 담기는 코드·양식이 저장소 원본과 바이트가 같다 |
| `web/tests/test_browser_parity.py` | Pyodide 로 만든 견적서가 CPython 산출물과 같다 — zip 부품 전부를 바이트로, 그리고 골든 회귀와 같은 비교기로 셀 단위(값·수식·서식·정렬·글꼴·병합·열너비·시트순서)로 |
| `web/tests/test_browser_e2e.py` | 운영과 같은 CSP 아래 실제 Chromium 으로 내려받은 파일이 CPython 산출물과 같다 |

정규화하는 것은 딱 둘이고 둘 다 견적서 내용이 아니다 — 파일을 만든 **시각**
(`docProps/core.xml` 의 `dcterms:modified`), 그리고 `<mergeCell>` 의 나열
**순서**(병합 집합은 같고, 다르면 테스트가 잡는다). 근거는
`web/tests/xlsx_parity.py` 에 적어 두었다.

### Pyodide 의 libxml2 는 EUC-KR 을 모른다

Pyodide 의 lxml 은 iconv 없이 빌드되어 EUC-KR 문서를 거부한다.

```
XMLSyntaxError: Unsupported encoding EUC-KR, line 1, column 38
```

2005년 형식 견적 XML 은 EUC-KR 이 흔하다. 그대로 두면 그 견적서는 통째로
변환되지 않는다. **Python Worker 로 갔어도 같은 문제가 났을 것이다** — 그쪽도
Pyodide 다.

그래서 `quotation/core/xml_reader.py` 에 좁은 대비책을 두었다. 파싱이 **아예
실패했을 때만**, 선언된 인코딩을 파이썬 표준 코덱으로 디코딩해 UTF-8 로 다시
적고 한 번 더 읽는다. 문자는 하나도 바뀌지 않으므로 파서가 보는 문서는 iconv
가 있는 데스크톱이 보는 것과 같다. 이미 읽히는 문서에는 이 경로가 닿지 않고,
다시 읽어도 실패하면 **처음 오류 문구 그대로** 알린다.

## 폴더

```text
web/
  src/
    worker.py              Workers 전용 진입점 (Paid 배포에만 쓴다)
    api.py                 요청 검증·응답 매핑 (런타임 비의존)
    conversion_adapter.py  바이트 기반 코어 호출과 오류 분류
    limits.py              업로드·품목·그룹·결과 크기 상한
    errors.py              오류 코드와 사용자 메시지
    clock.py               Asia/Seoul 견적 날짜
    template.py            번들에 담긴 견적서 템플릿
    quotation/             배포 직전 복사되는 공용 코어 (추적하지 않음)
    template_data.py       배포 직전 생성되는 템플릿 (추적하지 않음)
  browser/
    entry.py               브라우저(Pyodide) 진입점. worker.py 와 같은 역할
  frontend/
    src/engine.js          Pyodide 기동과 entry.convert 호출 (검증도 이 파일을 쓴다)
    src/convert.worker.ts  변환 Web Worker
    src/converter.ts       브라우저 우선, 실패 시 서버로 넘어가는 배선
    e2e/browser_smoke.mjs  실제 브라우저 스모크
    public/py/             변환 엔진 자산 (생성물, 추적하지 않음)
  scripts/
    sync_core.py           공용 코어 복사 + 템플릿 내장 모듈 생성
    build_browser_engine.py 브라우저 변환 엔진 포장
    browser_convert.mjs    엔진을 Node 로 돌리는 동일성 검증 구동기
    verify_template.py     템플릿 검증 (필수 시트·도형·실변환)
  tests/                   API 계약, 층 경계, 동일성 검증
  wrangler.jsonc           기본=정적 자산(무료), env.server=Python Worker(Paid)
```

`web/src` 의 모듈은 Worker 와 브라우저가 **함께** 쓴다. `worker.py` 만 Workers
런타임 전용이고, 브라우저 쪽 대응물이 `browser/entry.py` 다.

## API (Workers Paid 의 `--env server` 배포에만 있다)

무료 계정 배포에는 이 경로들이 없다. 화면도 이 경로를 부르지 않는다 — 상한과
판본은 배포와 함께 정해지므로 물어볼 이유가 없고, 물어보면 그것만으로 Worker 가
깨어나 무료 계정의 요청·CPU 한도를 쓴다.

브라우저 엔진은 아래 계약을 **그대로** 만족한다. 같은 `api.py` 가 만드는
응답이라 상태 코드도, `Content-Disposition` 도, 오류 본문도 같다.

| 메서드 | 경로 | 설명 |
|---|---|---|
| POST | `/api/v1/convert` | `multipart/form-data` 의 `file` 필드(XML 1개) → XLSX 다운로드 |
| GET | `/api/v1/status` | 배포 버전, 활성 템플릿 버전 |
| GET | `/api/v1/config` | 업로드 상한, 허용 확장자 등 공개 설정 |

성공 응답은 `Content-Disposition` 에 원본 이름(확장자만 `.xlsx`)을 RFC 5987 로
담고 `X-Request-Id`, `X-Template-Version` 을 함께 보냅니다. 오류는 아래 형식이며
스택·경로·XML 본문을 담지 않습니다.

```json
{ "error": { "code": "INVALID_QUOTATION_XML", "message": "…", "request_id": "…" } }
```

| 상태 | 코드 |
|---:|---|
| 400 | `INVALID_REQUEST` |
| 413 | `FILE_TOO_LARGE` |
| 415 | `UNSUPPORTED_MEDIA_TYPE` |
| 422 | `INVALID_QUOTATION_XML` |
| 500 | `CONVERSION_FAILED` |
| 503 | `TEMPLATE_UNAVAILABLE` |

## 개발

```bash
# 1) 파이썬 테스트 (Workers 런타임 없이 CPython 에서 돈다)
python -m pytest web/tests -q

# 2) 공용 코어와 템플릿 생성
python web/scripts/sync_core.py

# 3) 브라우저 변환 엔진 생성 (Pyodide 런타임 + wheel + 코어 zip, 약 14 MiB)
#    받는 것마다 sha256 이 고정되어 있고 web/.engine-cache 에 캐시된다
python web/scripts/build_browser_engine.py
python web/scripts/build_browser_engine.py --check   # 최신인지만 확인 (CI 용)

# 4) 화면
cd web/frontend && npm install
npm run dev        # http://localhost:5173
npm test           # 다운로드 파일명 처리 단위 테스트
npm run build      # web/frontend/dist

# 5) 동일성 검증 — 여기가 붉으면 내보내지 않는다
python -m pytest web/tests/test_browser_parity.py -q   # Node 로 엔진 구동
npm --prefix web/frontend install --no-save playwright
python -m pytest web/tests/test_browser_e2e.py -q      # 실제 Chromium
```

`build_browser_engine.py` 는 Pyodide 배포판 CDN 과 PyPI 에서 파일을 받는다.
망을 타지 않고 만들려면 Pyodide 배포판 폴더를 가리켜 준다.

```bash
PYODIDE_DIST_DIR=/어딘가/pyodide python web/scripts/build_browser_engine.py
```

## 배포

배포 대상이 둘이고, 무료 계정에서 쓰는 것은 첫째 하나뿐이다.

| 대상 | 명령 | 올라가는 것 |
|---|---|---|
| 기본 (무료) | `bash web/scripts/cf_deploy.sh deploy` | 정적 자산만. Worker 스크립트 없음 |
| 스테이징 (무료) | `... cf_deploy.sh deploy --env staging` | 위와 같음 |
| 서버 변환 포함 (Paid) | `... cf_deploy.sh deploy --env server` | 위 + Python Worker |

`cf_deploy.sh` 가 대상을 보고 도구를 고른다. 무료 대상이면 `wrangler` 로 끝나고,
`--env server` 일 때만 `pywrangler` 를 설치해 Pyodide 의존성을 vendoring 한다.

자격 증명 없이 설정만 검사하려면:

```bash
cd web
npx wrangler deploy --dry-run --env=""       # 무료 기본 — Worker 스크립트가 없어야 한다
npx wrangler deploy --dry-run --env server   # Paid 서버 환경
```

CI 의 `bundle` 잡이 매 푸시마다 둘 다 돌린다.

### Workers Paid 로 올릴 때만 필요한 도구

서버 변환 API(`--env server`)를 함께 올릴 때만 아래가 필요하다. 무료 계정
배포에는 하나도 쓰이지 않는다.

| 도구 | 최소 판본 | 이유 |
|---|---|---|
| `wrangler` | 4.42.1 | 3.x 는 `wrangler.jsonc` 를 읽지 못해 설정을 통째로 무시하고 `Missing entry-point` 로 죽는다 |
| `workers-py` (`pywrangler`) | 최신 | `pyproject.toml` 의 의존성을 Pyodide 대상으로 받아 `web/python_modules/` 에 넣는다 |
| `uv` | 0.12.3 | pywrangler 의 의존성 해석기 |

`wrangler` 는 JavaScript 배포 도구라 `.py` 파일은 올려 주지만 **Python 패키지를
받아 오지는 않는다.** `pyproject.toml` 을 읽지 않는다. `pywrangler` 가 그 앞단을
채운다 — `pywrangler deploy` = `pywrangler sync` + `wrangler deploy` 다.

| 명령 | 번들 |
|---|---|
| `wrangler deploy` | 우리 코드만. 첫 요청에서 `import lxml` 실패 |
| `python3 -m pywrangler deploy` | 352 모듈 · 7,532 KiB — 의존성 포함, 정상 동작 |

`limits.cpu_ms` 는 Paid 전용이라 무료 계정에서는 그 항목이 있는 것만으로 배포가
거부된다(`✘ CPU limits are not supported for the Free plan [code: 100328]`).
그래서 `wrangler.jsonc` 의 기본 환경에는 없고 `env.server` 에만 있다.

Worker 이름은 대시보드에 연결된 이름(`quotation`)과 맞춰 두었다. 다르면 배포 때
경고가 나고 Cloudflare 가 이름을 고치는 PR 을 연다.

## 배포 경로는 하나만 켠다

같은 Worker 에 배포하는 길이 둘 있다. 둘을 함께 켜두면 두 번 배포되며 서로를
덮어쓴다. 하나를 골라 반대쪽은 끈다.

| 경로 | 트리거 | 끄는 방법 |
|---|---|---|
| Cloudflare Workers Builds | 대시보드에 연결한 Git 저장소 | Worker → Settings → Build → Git 연결 해제 |
| GitHub Actions | main 푸시 | 저장소 변수 `CLOUDFLARE_DEPLOY` 삭제 |

## Cloudflare Workers Builds 설정

대시보드 → Workers & Pages → 해당 Worker → **Settings → Build**.

**프로덕션 브랜치와 그 외 브랜치의 설정이 따로다.** 둘 다 채워야 한다. 한쪽만
고치면 다른 쪽 빌드는 계속 기본값(`npx wrangler deploy` / `npx wrangler versions
upload`)으로 돌아 `Missing entry-point` 로 죽는다.

| 항목 | 값 |
|---|---|
| Root directory | 아무 값이나 무방 (비워 두어도 된다) |
| Build command (양쪽 공통) | `bash "$(git rev-parse --show-toplevel)"/web/scripts/cf_build.sh` |
| Deploy command (프로덕션) | `bash "$(git rev-parse --show-toplevel)"/web/scripts/cf_deploy.sh deploy` |
| Deploy command (프리뷰) | `bash "$(git rev-parse --show-toplevel)"/web/scripts/cf_deploy.sh versions upload` |

스테이징 Worker(`quotation-staging`)라면 `deploy` 뒤에 `--env staging` 을 붙인다.
Workers Paid 에서 서버 변환 API 까지 올리려면 `--env server` 를 붙인다. 인자는
그대로 배포 도구까지 전달된다.

프리뷰 빌드를 아예 돌리고 싶지 않으면 Settings → Build → Branch control 에서
프로덕션 브랜치(`main`)만 남긴다. 작업 브랜치 푸시마다 빌드가 도는 것을 막는다.

로그에서 어느 설정이 쓰였는지 바로 알 수 있다.

```
Executing user build command: ...       ← 이 줄이 없으면 Build command 가 비어 있다
Executing user deploy command: npx wrangler versions upload
                                        ← 기본값. 프리뷰 설정이 안 채워졌다는 뜻
Installing project dependencies: pip install -r requirements.txt
                                        ← 저장소 루트의 파일. Root directory 가 루트다
```

두 스크립트는 **자기 위치를 보고 `web/` 으로 이동한다.** 그래서 대시보드의
Root directory 값이 무엇이든 똑같이 동작한다. 이 장치가 없으면 Root directory
가 저장소 루트일 때 wrangler 가 설정을 못 찾아 이렇게 죽는다.

```
✘ [ERROR] Missing entry-point to Worker script or to assets directory
```

`wrangler.jsonc` 는 저장소 루트가 아니라 `web/` 에 있기 때문이다.

빌드 로그 첫 줄에 `=== 작업 폴더: /opt/buildhome/repo/web` 가 찍히면 스크립트가
제대로 실행된 것이다. 그 줄이 없으면 대시보드의 Build/Deploy command 가 저장되지
않았거나 다른 Worker 의 설정을 고친 것이다.
- Deploy command 의 `--env` 는 `wrangler.jsonc` 의 Worker 이름과 맞아야 한다
  (top-level `quotation-web`, `env.staging` 은 `quotation-web-staging`).
- **`wrangler deploy` 를 쓰지 말고 `cf_deploy.sh`(=`pywrangler deploy`)** 를 쓴다.
  wrangler 만 쓰면 의존성 vendoring 이 빠진다.
- 빌드·배포 순서는 `web/scripts/cf_build.sh`, `web/scripts/cf_deploy.sh` 가 갖고
  있다. 대시보드에 긴 명령을 넣지 않는 이유는 설정과 코드가 어긋나지 않게 하기
  위함이다.
- **설정을 바꾼 뒤에는 새 빌드를 돌려야 한다.** `Retry build` 는 이전 빌드를
  그때의 설정으로 재실행하므로 바뀐 값이 반영되지 않는다.
- `Failed: The build token ... has been deleted or rolled` 는 API 토큰이 아니라
  **Workers Builds 전용 빌드 토큰** 문제다. Settings → Build → Build token 에서
  갱신하고 재시도한다.

## GitHub Actions 배포 켜기

배포 잡은 Cloudflare 준비가 끝날 때까지 건너뜁니다. 아래를 등록하면 켜집니다.

| 종류 | 이름 | 값 |
|---|---|---|
| Variable | `CLOUDFLARE_DEPLOY` | `true` |
| Secret | `CLOUDFLARE_API_TOKEN` | 아래 권한을 가진 **API 토큰** |
| Secret | `CLOUDFLARE_ACCOUNT_ID` | 계정 ID |
| Variable | `STAGING_BASE_URL` | 스모크 테스트용 주소 (선택) |

### API 토큰 권한

토큰 권한이 모자라면 업로드 직전에 이렇게 죽습니다.

```
✘ [ERROR] A request to the Cloudflare API (/accounts/.../workers/services/...) failed.
  Authentication error [code: 10000]
✘ [ERROR] Failed to automatically retrieve account IDs for the logged in user.
```

My Profile → API Tokens → Create Token 에서 **Edit Cloudflare Workers** 템플릿을
그대로 쓰면 됩니다. 별도 권한 추가는 필요 없습니다(R2 를 쓰지 않습니다).

| 범위 | 권한 | 용도 |
|---|---|---|
| Account | Workers Scripts — Edit | Worker 와 정적 자산 업로드 (필수) |
| Account | Account Settings — Read | 계정 조회 |
| User | User Details — Read | `wrangler whoami` |
| Zone | Workers Routes — Edit | 커스텀 도메인을 붙일 때만 |

흔한 실수:

- **Global API Key 를 넣었다.** 그것은 `CLOUDFLARE_API_TOKEN` 이 아니라
  `CLOUDFLARE_API_KEY` + `CLOUDFLARE_EMAIL` 로 넘겨야 합니다. API 토큰을 새로
  만드는 쪽이 낫습니다.
- **토큰 값 대신 토큰 ID 를 붙여넣었다.** 값은 생성 직후 한 번만 보입니다.
- **줄바꿈·공백이 함께 붙여넣어졌다.**
- **토큰이 다른 계정 소속이거나 만료됐다.** `CLOUDFLARE_ACCOUNT_ID` 와 같은
  계정인지 확인합니다.

토큰만 따로 1초에 검사하는 방법:

```bash
curl -sS https://api.cloudflare.com/client/v4/user/tokens/verify \
  -H "Authorization: Bearer <토큰>"
# 정상이면 "status": "active"
```

CI 의 배포 잡은 업로드 전에 `wrangler whoami` 를 돌려 토큰이 무엇을 볼 수 있는지
로그에 남깁니다(실패해도 배포는 시도하며, 판정은 실제 배포가 합니다).

## 템플릿 운영

템플릿은 저장소에 한 벌만 둔다. 데스크톱 앱과 웹이 같은 파일을 쓴다.

```text
quotation/resources/견적서_template.xlsx   ← 유일한 원본
   ├─ 데스크톱: EXE 옆으로 복사되어 사용자가 직접 편집
   └─ 웹: sync_core.py 가 web/src/template_data.py 로 만들고
          build_browser_engine.py 가 그것을 quotation-core.zip 에 담는다
```

바꾸는 절차:

```bash
# 1) Excel 에서 quotation/resources/견적서_template.xlsx 를 고친다
#    (견적번호는 TOTAL!B2, 담당자·회사는 상단 머리말 도형)

# 2) 검증 — 필수 시트, 도형, 공개 fixture 로 실제 변환까지 해 본다
python web/scripts/verify_template.py quotation/resources/견적서_template.xlsx

# 3) 골든 회귀 테스트
python -m pytest -q

# 4) 커밋하면 배포와 함께 반영된다
```

되돌리려면 그 커밋을 되돌린다. 템플릿 판본은 내용 해시(`sha256-…`)로 계산되어
화면 아래와 `/py/engine.json`, 응답의 `X-Template-Version` 에 실린다. 어떤
템플릿으로 만든 견적서인지 나중에도 추적할 수 있다.

배포되는 템플릿이 저장소 원본과 같은지는 테스트가 매번 확인한다 —
`web/tests/test_api.py::test_bundled_template_matches_the_repository_original`
(Worker 번들)과
`web/tests/test_browser_engine.py::test_template_travels_as_the_repository_original`
(브라우저 엔진).


## 실측 (2026-08-14)

| 항목 | 실측 |
|---|---|
| `lxml` | **6.0.0** — 데스크톱은 6.1.1. Pyodide 배포판에 6.1.1 wheel 이 없다 |
| `openpyxl` | 3.1.5 (데스크톱과 동일) |
| 브라우저 엔진 자산 | 14.4 MiB (Pyodide 11.1 + lxml 1.7 + openpyxl 0.9 + 코어 0.1) |
| Pyodide 기동 | 약 1.9 초 (첫 변환 전 한 번) |
| lxml 적재 | 약 0.6 초 |
| 변환 1건 | 대표 입력 약 0.3 초 (CPython 0.1 초의 3배) |
| Paid `--env server` 번들 | 7,532 KiB (gzip 1,943 KiB) — Paid 10 MB 한도 안 |

lxml 판본이 갈리므로 CI 의 코어 테스트를 6.1.1·6.0.0 양쪽에서 돌립니다.
브라우저에서 나온 견적서가 CPython 산출물과 같은지는 CI 의 `browser` 잡이
매 푸시마다 대조합니다.

## 저장 정책

무료 계정 배포에서는 **XML 이 서버로 가지 않습니다.** 변환이 브라우저 안에서
끝나므로 올린 XML 도 만들어진 견적서도 네트워크를 타지 않고, 서버에는 남길
것도 없습니다.

Workers Paid 의 `--env server` 배포에서 서버 변환을 쓸 때도 저장하지 않습니다.
요청을 처리하는 동안만 메모리에 두었다가 응답과 함께 버리고, 로그에는 요청 ID,
결과 코드, 크기 구간, 품목·그룹 수, 처리 시간, 템플릿 버전만 남깁니다(계획서 §13).
