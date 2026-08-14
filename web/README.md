# 웹 앱 (Cloudflare Workers)

브라우저에서 eConfig XML을 올리면 Worker가 견적서 `.xlsx` 를 만들어 바로 내려
줍니다. 설계 근거와 단계별 계획은
[`doc/CLOUDFLARE_WORKERS_WEB_IMPLEMENTATION_PLAN.md`](../doc/CLOUDFLARE_WORKERS_WEB_IMPLEMENTATION_PLAN.md).

```text
web/
  src/
    worker.py              HTTP 진입점 (라우팅, R2, 로그)
    api.py                 요청 검증·응답 매핑 (런타임 비의존, 테스트 가능)
    conversion_adapter.py  바이트 기반 코어 호출과 오류 분류
    limits.py              업로드·품목·그룹·결과 크기 상한
    errors.py              오류 코드와 사용자 메시지
    clock.py               Asia/Seoul 견적 날짜
    quotation/             배포 직전 복사되는 공용 코어 (추적하지 않음)
  frontend/                Vite + TypeScript SPA
  scripts/
    sync_core.py           공용 코어를 src/ 로 복사
    verify_template.py     템플릿 검증 (필수 시트·도형·실변환)
  tests/                   API 계약과 층 경계 테스트
  wrangler.jsonc           Workers·R2·정적 자산 설정
  pyproject.toml           Worker 런타임 의존성
```

## API

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
# 1) API·경계 테스트 (Workers 런타임 없이 CPython 에서 돈다)
python -m pytest web/tests -q

# 2) 공용 코어를 Worker 번들 안으로 복사
python web/scripts/sync_core.py

# 3) 화면
cd web/frontend && npm install
npm run dev        # http://localhost:5173, /api 는 wrangler dev 로 넘어간다
npm test           # 다운로드 파일명 처리 단위 테스트
npm run build      # web/frontend/dist

# 4) Worker
cd web && npm install                 # wrangler 4 (package.json 에 고정)
pip install workers-py "uv>=0.12.3"   # Python Workers 배포 도구
python3 -m pywrangler dev            # sync 후 wrangler dev 로 넘어간다
```

`npm run dev` 는 `/api` 요청을 `127.0.0.1:8787` 의 `wrangler dev` 로 넘깁니다.
운영과 같은 동일 출처 구성을 로컬에서도 그대로 씁니다.

## 배포 도구 (여기서 틀리면 배포가 통째로 실패한다)

| 도구 | 최소 판본 | 이유 |
|---|---|---|
| `wrangler` | 4.42.1 | 3.x 는 `wrangler.jsonc` 를 읽지 못해 설정을 통째로 무시하고 `Missing entry-point` 로 죽는다. pywrangler 도 4.42.1 이상을 요구한다 |
| `workers-py` (`pywrangler`) | 최신 | `pyproject.toml` 의 의존성을 Pyodide 대상으로 받아 `web/python_modules/` 에 넣는다 |
| `uv` | 0.12.3 | pywrangler 의 의존성 해석기 |

### `pywrangler` 가 하는 일

`wrangler` 는 JavaScript 배포 도구다. `.py` 파일은 그대로 올려 주지만
**Python 패키지를 받아 오지는 않는다.** `pyproject.toml` 을 읽지 않는다.

`pywrangler` (PyPI `workers-py`)는 그 앞단을 채운다.

```
python3 -m pywrangler deploy
   │
   ├─ 1) sync : pyproject.toml 의 lxml·openpyxl 을 Pyodide 인덱스에서
   │            emscripten-wasm32 wheel 로 받아 web/python_modules/ 에 푼다
   │
   └─ 2) npx wrangler deploy 를 그대로 실행 (인자도 그대로 넘어간다)
```

즉 `pywrangler deploy` = `pywrangler sync` + `wrangler deploy` 다. 나머지는
평범한 wrangler 이므로 `--env staging` 같은 옵션도 똑같이 쓴다.

차이는 번들에서 바로 드러난다.

| 명령 | 번들 |
|---|---|
| `wrangler deploy` | 17 모듈 · 71 KiB — **우리 코드만.** 첫 요청에서 `import lxml` 실패 |
| `python3 -m pywrangler deploy` | 352 모듈 · 7,532 KiB — 의존성 포함, 정상 동작 |

설치는 `pip install workers-py "uv>=0.12.3"` 이고 내부적으로 `npx wrangler`
(4.42.1 이상)를 부른다. `cf_build.sh` 의 1단계가 이 설치를 한다.

```bash
cd web
python ../web/scripts/sync_core.py       # 공용 코어 복사
npm --prefix frontend run build          # 정적 자산
python3 -m pywrangler deploy --env staging   # 의존성 vendoring + 배포
```

자격 증명 없이 설정과 번들만 검사하려면:

```bash
cd web && npx wrangler deploy --dry-run --outdir .wrangler/dry-run
```

CI 의 `bundle` 잡이 매 푸시마다 이 검사를 돌립니다.

## 요금제 (Free 에서는 배포가 거부된다)

Worker 설정에 CPU 한도(`limits.cpu_ms`)를 두면 Free 플랜에서는 배포 API 가
거부한다.

```
✘ CPU limits are not supported for the Free plan [code: 100328]
```

그래서 `wrangler.jsonc` 에서 `limits` 를 빼 두었다. Free 플랜에서도 배포는 되지만
**운영은 Workers Paid 를 전제로 한다**(계획서 §4.2). XLSX 생성은 Free 의 CPU
한도로는 부족해서, 배포가 되더라도 요청 중 `Worker exceeded CPU time limit` 이
날 수 있다. Paid 로 올린 뒤 `wrangler.jsonc` 의 주석 처리된 `limits` 를 되살린다.

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

스테이징 Worker(`quotation-web-staging`)라면 `deploy` 뒤에 `--env staging` 을
붙인다. 인자는 그대로 wrangler 까지 전달된다.

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

My Profile → API Tokens → Create Token 에서 **Edit Cloudflare Workers** 템플릿으로
만들고, R2 를 쓰므로 아래를 확인합니다.

| 범위 | 권한 | 용도 |
|---|---|---|
| Account | Workers Scripts — Edit | Worker 와 정적 자산 업로드 (필수) |
| Account | Workers R2 Storage — Edit | 템플릿 버킷 바인딩·업로드 (필수) |
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

먼저 R2 버킷 `quotation-templates-staging` 을 만들고 템플릿을 올린 뒤
`wrangler.jsonc` 의 `ACTIVE_TEMPLATE_KEY` 를 실제 키로 바꿔야 합니다.

## 템플릿 운영

템플릿은 공개 정적 자산이 아니라 비공개 R2 버킷에 버전별로 둡니다.

```bash
# 1) 검증
python web/scripts/verify_template.py quotation/resources/견적서_template.xlsx

# 2) 불변 키로 업로드
npx wrangler r2 object put \
  quotation-templates/templates/2026-08-13-baseline/quotation-template.xlsx \
  --file quotation/resources/견적서_template.xlsx --remote

# 3) wrangler.jsonc 의 ACTIVE_TEMPLATE_KEY 를 새 키로 바꾸고 스테이징 배포 → 검증 → 운영 배포
```

문제가 생기면 `ACTIVE_TEMPLATE_KEY` 를 이전 키로 되돌려 재배포합니다. 정상 버전은
최소 3개 유지합니다. 자세한 절차는 계획서 §8.2.

## 배포 전에 확인할 것 (계획서 Phase 0)

의존성과 번들은 CI 에서 확인했습니다 (2026-08-14).

| 항목 | 실측 |
|---|---|
| `lxml` | **6.0.0** — 데스크톱은 6.1.1. Pyodide 인덱스에 6.1.1 wheel 이 없다 |
| `openpyxl` | 3.1.5 (데스크톱과 동일) |
| 배포 번들 | 7,532 KiB (gzip 1,943 KiB) — Paid 10 MB 한도 안 |

lxml 판본이 갈리므로 CI 의 코어 테스트를 6.1.1·6.0.0 양쪽에서 돌립니다.

아래는 계정이 준비되어야 확인할 수 있습니다.

- 실제 30 KB 템플릿으로 만든 결과에 그림·도형 관계가 남는가
  (로컬 CPython 기준 대표 입력 변환 시간은 약 80~100 ms 다)
- isolate 메모리 128 MB 안에 드는가
- Workers Paid 의 CPU 한도 안에서 warm p95 5초 목표를 지키는가

하나라도 실패하면 API 계약과 화면은 그대로 두고 변환 실행부만 Cloudflare
Container 로 옮깁니다(계획서 §4.2). `api.py` 와 `conversion_adapter.py` 는
런타임에 의존하지 않으므로 그대로 재사용합니다.

## 저장 정책

올린 XML과 만든 견적서는 R2·KV·로그 어디에도 저장하지 않습니다. 요청을 처리하는
동안만 메모리에 두었다가 응답과 함께 버립니다. 로그에는 요청 ID, 결과 코드, 크기
구간, 품목·그룹 수, 처리 시간, 템플릿 버전만 남깁니다(계획서 §13).
