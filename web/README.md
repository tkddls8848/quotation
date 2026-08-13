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
cd web && npx wrangler dev
```

`npm run dev` 는 `/api` 요청을 `127.0.0.1:8787` 의 `wrangler dev` 로 넘깁니다.
운영과 같은 동일 출처 구성을 로컬에서도 그대로 씁니다.

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

아래는 실제 Cloudflare 계정에서 확인해야 하며, 코드로 미리 정할 수 없습니다.

- `lxml==6.1.1`, `openpyxl==3.1.5` 가 Python Workers(Pyodide)에서 설치·동작하는가
- 실제 30 KB 템플릿으로 만든 결과에 그림·도형 관계가 남는가
  (로컬 CPython 기준 대표 입력 변환 시간은 약 80~100 ms 다)
- isolate 메모리 128 MB, 배포 번들 크기(Paid 10 MB) 안에 드는가
- Workers Paid 의 CPU 한도 안에서 warm p95 5초 목표를 지키는가

하나라도 실패하면 API 계약과 화면은 그대로 두고 변환 실행부만 Cloudflare
Container 로 옮깁니다(계획서 §4.2). `api.py` 와 `conversion_adapter.py` 는
런타임에 의존하지 않으므로 그대로 재사용합니다.

## 저장 정책

올린 XML과 만든 견적서는 R2·KV·로그 어디에도 저장하지 않습니다. 요청을 처리하는
동안만 메모리에 두었다가 응답과 함께 버립니다. 로그에는 요청 ID, 결과 코드, 크기
구간, 품목·그룹 수, 처리 시간, 템플릿 버전만 남깁니다(계획서 §13).
