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
pywrangler dev                        # sync 후 wrangler dev 로 넘어간다
```

`npm run dev` 는 `/api` 요청을 `127.0.0.1:8787` 의 `wrangler dev` 로 넘깁니다.
운영과 같은 동일 출처 구성을 로컬에서도 그대로 씁니다.

## 배포 도구 (여기서 틀리면 배포가 통째로 실패한다)

| 도구 | 최소 판본 | 이유 |
|---|---|---|
| `wrangler` | 4.42.1 | 3.x 는 `wrangler.jsonc` 를 읽지 못해 설정을 통째로 무시하고 `Missing entry-point` 로 죽는다. pywrangler 도 4.42.1 이상을 요구한다 |
| `workers-py` (`pywrangler`) | 최신 | `pyproject.toml` 의 의존성을 Pyodide 대상으로 받아 `web/python_modules/` 에 넣는다 |
| `uv` | 0.12.3 | pywrangler 의 의존성 해석기 |

**`wrangler deploy` 를 직접 부르지 마십시오.** 그러면 `lxml`·`openpyxl` 없이
Worker 만 올라가고 첫 요청에서 import 오류가 납니다. 항상 `pywrangler deploy` 를
씁니다 — `sync`(의존성 vendoring)를 먼저 하고 wrangler 로 넘깁니다.

```bash
cd web
python ../web/scripts/sync_core.py       # 공용 코어 복사
npm --prefix frontend run build          # 정적 자산
pywrangler deploy --env staging          # 의존성 vendoring + 배포
```

자격 증명 없이 설정과 번들만 검사하려면:

```bash
cd web && npx wrangler deploy --dry-run --outdir .wrangler/dry-run
```

CI 의 `bundle` 잡이 매 푸시마다 이 검사를 돌립니다.

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

CI 의 배포 잡은 업로드 전에 `wrangler whoami` 를 돌려 토큰이 무엇을 볼 수 있는지
로그에 남깁니다.

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
