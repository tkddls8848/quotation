# 견적 변환 웹 앱 구현 계획 — Cloudflare Workers

- 작성일: 2026-08-14
- 대상 저장소: `C:\quotation\quotation`
- 대상 서비스: IBM eConfig Export XML → 기존 견적서 양식 `.xlsx` 변환
- 문서 상태: 구현 착수안

## 1. 결론

1차 구현은 **Cloudflare Workers Static Assets + Python Worker API + 비공개 R2 템플릿** 구조로 진행한다.

- 웹 화면은 Vite 기반 TypeScript SPA로 만들고 Workers Static Assets로 배포한다.
- 변환 API는 Python Worker에서 실행한다. 기존 `quotation/core`의 금액·그룹·시트 작성 규칙을 재사용하되 파일 경로 I/O를 `bytes`/`BytesIO` I/O로 분리한다.
- 견적서 템플릿은 공개 정적 자산으로 노출하지 않고 비공개 R2 버킷에서 버전별로 관리한다.
- 업로드한 고객 XML과 생성한 견적서는 기본적으로 저장하지 않고 한 요청 안에서만 처리하여 다운로드 응답으로 반환한다.
- 사내용 서비스라면 사용자 인증은 애플리케이션에 직접 구현하지 않고 Cloudflare Access로 제한한다.
- 구현에 앞서 `lxml==6.1.1`, `openpyxl==3.1.5`의 Python Workers/Pyodide 호환성, CPU, 메모리, 도형 보존을 검증한다. 합격하지 못하면 API 계약과 UI는 유지한 채 변환 실행부만 **Cloudflare Container**로 전환한다.

브라우저에서 Excel을 직접 만드는 방식이나 TypeScript로 전체 OOXML 생성기를 즉시 재작성하는 방식은 1차안에서 제외한다. 현재 구현은 값과 수식뿐 아니라 병합, 테두리, 인쇄 영역, 숨김 시트, 로고와 텍스트 도형까지 보존하므로 전면 재작성은 회귀 범위가 지나치게 크다.

## 2. 현재 프로그램 분석

### 2.1 실행 구조

| 영역 | 현재 구현 | 웹 전환 시 처리 |
|---|---|---|
| 사용자 화면 | `quotation/ui/main_window.py`, Tkinter | SPA로 교체 |
| 변환 오케스트레이션 | `quotation/core/convert.py` | 경로 기반 처리와 분리하여 재사용 |
| XML 파싱 | `quotation/core/xml_reader.py`, lxml | 바이트 입력 지원, 보안 제한 강화 |
| 데이터 모델/계산 | `models.py`, `money.py`, `naming.py` | 그대로 재사용 |
| Excel 작성 | `writer/ibm_writer.py`, openpyxl | `BytesIO` 기반으로 리팩터링 |
| 로고·도형 보존 | `writer/drawings.py`, ZIP 직접 수정 | 메모리 ZIP 처리로 리팩터링 |
| 템플릿 | EXE 옆 사용자 파일 및 번들 리소스 | R2의 중앙 버전 템플릿으로 전환 |
| 로컬 설정 | `%LOCALAPPDATA%`의 JSON | 웹에서는 제거; 필요한 설정만 브라우저 로컬 저장 |
| 결과 저장 | XML과 같은 폴더에 덮어쓰기 확인 후 저장 | 브라우저 다운로드로 변경 |

### 2.2 유지해야 할 핵심 동작

- UTF-8 및 EUC-KR XML 수용
- 인라인 DTD가 있어도 외부 엔티티 및 네트워크 참조 차단
- `BASE`/`PROPOSED` 제외와 증설 그룹 병합 규칙
- `N/C`, 소수 금액, 수량 계산에서 이진 부동소수점 사용 금지
- H/W·S/W 구간, REMOVE 음수/빨간 글꼴, 합계 수식 유지
- 시트 순서, 병합, 인쇄 설정, 숨김 `template` 시트 유지
- `TOTAL` 시트의 로고와 머리글 도형 유지
- 입력 파일의 기본 이름을 유지하고 확장자만 `.xlsx`로 바꾸어 다운로드
- 견적 날짜는 Worker의 UTC 날짜가 아니라 **Asia/Seoul 기준 날짜** 사용

### 2.3 저장소 데이터 정책

`samples/`는 고객/실데이터와 골든 파일이 들어갈 수 있으므로 저장소 추적 대상에서 제외한다. `.gitignore`에 `samples/`를 등록하고 Git 인덱스에서도 제거한다. CI에서 필요한 자료는 다음과 같이 분리한다.

- 공개 가능하며 익명화된 최소 fixture: `tests/fixtures/public/`에 추적
- 실데이터/고객 샘플: 개발자 로컬 또는 접근 제한된 CI 보관소에만 저장
- 실데이터 파일명, XML 본문, 견적 금액: Worker 로그에 기록하지 않음

## 3. 목표와 제외 범위

### 3.1 1차 출시 목표

- 로그인한 사용자가 브라우저에서 XML을 선택하거나 끌어 놓는다.
- 서버가 기존 데스크톱 앱과 의미상 같은 Excel 견적서를 생성한다.
- 사용자는 별도 설치 없이 결과를 바로 다운로드한다.
- 입력과 결과는 서버에 영구 보관하지 않는다.
- 중앙 템플릿을 버전 관리하고 문제 발생 시 즉시 이전 버전으로 되돌릴 수 있다.
- 배포, 오류, 처리 시간, 실패율을 운영자가 확인할 수 있다.

### 3.2 1차 출시에서 제외

- 견적 이력/검색/재다운로드
- 다중 테넌트 및 회사별 템플릿 자동 선택
- 웹에서 템플릿 도형이나 셀을 편집하는 기능
- 할인율·공급가 자동 계산 등 기존 프로그램에 없는 기능
- 비동기 작업 큐와 이메일 알림
- 모바일 화면에서 Excel 내용을 미리 보는 기능

## 4. 권장 아키텍처

```text
사용자 브라우저
  ├─ GET /, /assets/* ───── Workers Static Assets
  └─ POST /api/v1/convert ─ Cloudflare Access
                              │
                              ▼
                         Python Worker
                         ├─ 업로드/스키마 검증
                         ├─ quotation/core 변환
                         ├─ 메모리 내 XLSX 생성
                         └─ R2에서 활성 템플릿 읽기
                              │
                              ▼
                       비공개 R2 버킷
                       templates/{version}/template.xlsx
```

### 4.1 Cloudflare 구성요소

| 구성요소 | 용도 | 필수 여부 |
|---|---|---|
| Workers Static Assets | SPA 정적 파일 제공 | 필수 |
| Python Worker | 업로드 검증 및 동기 변환 API | 필수 |
| R2 | 비공개 템플릿 버전 저장 | 필수 권장 |
| Cloudflare Access | 사내 사용자 인증/접근 제어 | 사내용이면 필수 |
| Workers Logs/Tracing | 오류율, 처리 시간, 요청 추적 | 필수 |
| Rate Limiting | 과다 요청과 비용 폭주 방지 | 공개 범위가 있으면 필수 |
| Container | Python Worker 호환성 실패 시 변환 실행 대체 | 조건부 |

### 4.2 런타임 선택 근거

Cloudflare Python Workers는 Pyodide 기반이며 pure Python 및 PyEmscripten 패키지를 지원한다. 현재 핵심 코드가 Python이고 `openpyxl` 중심이므로 우선 재사용 가능성을 검증한다. 다만 다음 조건 때문에 기술검증 전에는 확정 완료로 보지 않는다.

- `lxml`의 해당 버전과 하위 의존성이 PyEmscripten 환경에서 정상 설치/실행되는지 확인 필요
- `openpyxl`이 그림·도형을 버리는 현재 동작과 이후 ZIP 패치가 Pyodide에서도 동일한지 확인 필요
- Workers는 isolate당 메모리 제한이 128 MB이므로 XML, 템플릿, 워크북, 최종 ZIP을 동시에 보유할 때 최대 사용량 측정 필요
- Workers Free의 CPU 한도 10 ms는 XLSX 생성에 현실적으로 부족하므로 운영 기준은 Workers Paid로 잡아야 함
- Workers 배포 번들 제한은 Free 3 MB, Paid 10 MB이므로 의존성 번들 크기 확인 필요

기술검증 실패 시 Cloudflare Containers에 기존 CPython 실행 환경을 넣는다. Container는 Workers Paid에서 사용할 수 있고 기존 라이브러리와 파일시스템 사용이 가능하지만, 일반적으로 1~3초 수준의 콜드 스타트 가능성과 컨테이너 운영비가 추가된다.

## 5. 변환 처리 설계

### 5.1 코어 API 리팩터링

데스크톱용 경로 I/O와 순수 변환을 분리한다.

```python
def parse_xml_bytes(source: bytes) -> Quotation: ...

def build_xlsx_bytes(
    quote: Quotation,
    template_bytes: bytes,
    *,
    today: date,
) -> bytes: ...

def convert_bytes(
    xml_bytes: bytes,
    template_bytes: bytes,
    *,
    today: date,
) -> ConversionResult: ...
```

- 기존 `convert(path)`는 위 순수 함수의 데스크톱 어댑터로 남겨 EXE 동작을 깨지 않는다.
- `xml_reader.parse()`는 경로와 바이트 모두 받을 수 있게 하거나 `parse_bytes()`를 추가한다.
- `ibm_writer.build()`는 `load_workbook(BytesIO(template_bytes))`를 사용한다.
- `drawings.carry_over()`는 임시 경로 대신 입력/출력 `BytesIO` ZIP을 받아 패치된 바이트를 돌려준다.
- 날짜는 요청 처리 시작 시 Asia/Seoul 기준으로 한 번만 확정하고 모든 시트에 동일하게 전달한다.
- Worker 모듈에서는 `tkinter`, `config.py`, `paths.py`, `os.startfile`, PyInstaller 코드를 import하지 않는다.

### 5.2 요청 처리 순서

1. Access 인증을 통과한 동일 출처 요청인지 확인한다.
2. `Content-Type`, 전체 요청 크기, 파일 수를 확인한다.
3. XML 파일명과 내용을 검사한다. 확장자만 신뢰하지 않는다.
4. 외부 엔티티/네트워크 접근을 금지한 파서로 XML을 파싱한다.
5. 문서 노드 수, 라인 아이템 수, 그룹 수 상한을 검사한다.
6. R2에서 `ACTIVE_TEMPLATE_KEY`에 지정된 템플릿을 읽고 ETag/버전을 기록한다.
7. 템플릿 필수 시트(`TOTAL`, `template`)와 기본 셀 구조를 검사한다.
8. 메모리 안에서 XLSX를 생성하고 ZIP 구조 및 필수 시트를 재검사한다.
9. 다운로드 헤더와 요청 ID를 붙여 XLSX 바이트를 응답한다.
10. 입력 바이트와 결과 바이트를 별도 저장하지 않고 요청 종료와 함께 폐기한다.

### 5.3 애플리케이션 제한 초깃값

Cloudflare 계정의 최대 업로드 한도보다 작은 애플리케이션 자체 제한을 둔다.

| 항목 | 초깃값 | 비고 |
|---|---:|---|
| XML 업로드 | 10 MiB | 실제 샘플 분포 측정 후 축소 가능 |
| 한 요청의 파일 수 | 1 | 다중 변환은 후속 기능 |
| `ProductLineItem` | 5,000개 | 비정상 문서/메모리 폭주 방지 |
| 그룹 | 200개 | Excel 시트 폭증 방지 |
| 생성 XLSX | 20 MiB | 초과 시 422 또는 413 계열 응답 |
| Worker 목표 메모리 | 피크 96 MB 이하 | 128 MB 한도 대비 여유 확보 |
| 변환 시간 목표 | warm p95 5초 이하 | 실측 후 SLO 확정 |

## 6. HTTP API 계약

### 6.1 `POST /api/v1/convert`

요청:

- `multipart/form-data`
- 필드 `file`: XML 파일 1개
- 선택 필드 `template_version`: 기본값은 서버 활성 버전. 일반 사용자는 임의 버전을 선택하지 못하게 할 수 있음

성공 응답:

- 상태: `200 OK`
- `Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`
- `Content-Disposition: attachment; filename*=UTF-8''{인코딩된 파일명}.xlsx`
- `Cache-Control: no-store`
- `X-Request-Id: {uuid}`
- `X-Template-Version: {version}`
- 본문: 생성된 XLSX 바이트

오류 응답:

```json
{
  "error": {
    "code": "INVALID_QUOTATION_XML",
    "message": "견적서 작성에 필요한 XML 항목을 찾을 수 없습니다.",
    "request_id": "..."
  }
}
```

| 상태 | 코드 예시 | 의미 |
|---:|---|---|
| 400 | `INVALID_REQUEST` | 파일 누락, 잘못된 multipart |
| 413 | `FILE_TOO_LARGE` | 입력 제한 초과 |
| 415 | `UNSUPPORTED_MEDIA_TYPE` | XML이 아닌 입력 |
| 422 | `INVALID_QUOTATION_XML` | XML 구문/필수 항목/상한 검증 실패 |
| 500 | `CONVERSION_FAILED` | 예상하지 못한 변환 실패 |
| 503 | `TEMPLATE_UNAVAILABLE` | 활성 템플릿을 읽거나 검증하지 못함 |

스택 추적, XML 본문, 로컬/R2 경로는 사용자 응답에 포함하지 않는다.

### 6.2 보조 엔드포인트

- `GET /api/v1/status`: 배포 버전과 활성 템플릿 버전만 반환. 외부 의존성 상세나 비밀값은 반환하지 않음
- `GET /api/v1/config`: 클라이언트에 필요한 업로드 크기, 허용 확장자 등 공개 설정 반환

## 7. 웹 UI 계획

### 7.1 화면 구성

- 서비스 설명과 지원 형식
- 클릭/드래그앤드롭 파일 선택 영역
- 선택한 파일명과 크기 표시
- `변환 및 다운로드` 버튼
- `업로드 중 → 변환 중 → 다운로드 준비` 상태 표시
- 오류 메시지와 요청 ID
- 개인정보/파일 비저장 안내
- 활성 템플릿 버전과 배포 버전 표시(운영 지원용)

### 7.2 사용자 경험 규칙

- `.xml` 확장자, 파일 크기, 빈 파일 여부를 브라우저에서 1차 검사하되 서버에서 반드시 재검사한다.
- 처리 중 중복 클릭을 막고 `AbortController`로 요청 취소를 지원한다.
- 성공 시 `Content-Disposition`의 파일명을 사용해 즉시 다운로드한다.
- 브라우저 다운로드 정책상 기존 파일 덮어쓰기 확인은 브라우저에 맡긴다.
- 실제 서버 진행률을 알 수 없는 동기 API에서 가짜 백분율을 표시하지 않고 단계 상태만 표시한다.
- 한글 파일명, 공백, `#`, 괄호가 포함된 파일명의 다운로드를 E2E로 검증한다.
- 접근성 기준으로 키보드 조작, 포커스 표시, 오류의 텍스트 안내를 포함한다.

## 8. 템플릿 운영 계획

### 8.1 저장 및 선택

- R2 버킷은 공개 액세스를 끄고 Worker binding으로만 읽는다.
- 객체 키 예: `templates/2026-08-13-a1b2c3/견적서_template.xlsx`
- `ACTIVE_TEMPLATE_KEY`는 환경별 Worker 변수로 둔다.
- 활성화 전 템플릿 검증 도구로 필수 시트, 필수 셀, 도형 관계, 파일 해시를 검사한다.
- 새 버전을 올린 뒤 Worker 변수를 바꾸어 배포하고, 문제 시 이전 키로 재배포한다.
- 최소 최근 3개 정상 버전을 유지한다.

### 8.2 템플릿 변경 절차

1. 담당자가 Excel에서 템플릿을 수정한다.
2. 로컬 검증 명령으로 구조와 골든 회귀 테스트를 통과시킨다.
3. immutable 버전 키로 R2에 업로드한다.
4. 스테이징의 `ACTIVE_TEMPLATE_KEY`를 바꾸고 대표 XML로 검증한다.
5. 승인 후 운영 키를 전환한다.
6. 버전, 해시, 변경자, 변경 사유를 릴리스 기록에 남긴다.

1차 출시에서는 일반 사용자의 템플릿 업로드/영구 저장 UI를 제공하지 않는다. 사용자별 템플릿이 필수라는 업무 요건이 확인되면, 요청마다 템플릿을 함께 올리고 저장하지 않는 모드 또는 Access 그룹 기반 템플릿 선택을 별도 설계한다.

## 9. 보안 및 개인정보

- 서비스 전체를 사용자/그룹 기반 Cloudflare Access 정책으로 보호한다.
- API와 정적 UI를 동일 출처로 제공하고 CORS를 열지 않는다.
- 상태 변경 API는 `POST`만 허용하고 `Origin`/`Sec-Fetch-Site`를 검사한다.
- XML 파서는 DTD를 로드하지 않고 외부 엔티티와 네트워크 접근을 차단한다.
- 입력 크기뿐 아니라 노드/라인/그룹 수를 제한하여 XML 확장 및 계산량 공격을 막는다.
- XML 본문, 고객명, 제품 설명, 금액, 원본 파일명, 생성 XLSX를 로그에 남기지 않는다.
- 로그는 요청 ID, 결과 코드, 입력 크기 구간, 그룹 수, 처리 시간, 템플릿 버전만 구조화해 남긴다.
- `Cache-Control: no-store`, `X-Content-Type-Options: nosniff`, CSP, `Referrer-Policy` 등 보안 헤더를 적용한다.
- R2 binding을 사용하여 애플리케이션 코드에 R2 API 키를 두지 않는다.
- CI의 Cloudflare API 토큰은 최소 계정/Worker/R2 권한으로 제한하고 저장소에 넣지 않는다.
- 공개 서비스가 필요하면 Access 제거 전에 별도의 사용자 인증, CSRF, Rate Limiting, 감사 정책을 먼저 설계한다.

## 10. 저장소 목표 구조

```text
quotation/                      공용 순수 도메인/변환 로직 (데스크톱·웹 공용)
  core/
    convert.py                  convert() 경로 어댑터 + convert_bytes() 순수 함수
    xml_reader.py               parse() / parse_bytes()
    resources.py                기준 템플릿 위치
    writer/                     build() / build_bytes(), carry_over_bytes()
  resources/                    기준 템플릿(.xls 편집 원본, .xlsx 배포본)
desktop/                        데스크톱 전용. 웹 번들에 절대 들어가지 않는다
  quotation_desktop/            Tkinter 화면, config.py, paths.py
  launcher.py, QuotationTool.spec
  tools/, tests/
web/
  pyproject.toml                Python Worker 의존성
  wrangler.jsonc                assets, R2, 변수, observability 설정
  src/
    worker.py                   HTTP 엔트리포인트
    api.py                      요청 검증/응답 매핑
    conversion_adapter.py       bytes 기반 코어 호출
    limits.py, errors.py, clock.py
    quotation/                  배포 직전 복사되는 공용 코어 (추적하지 않음)
  frontend/
    package.json
    src/
    vite.config.ts
  scripts/
    sync_core.py                공용 코어를 src/ 로 복사
    verify_template.py          템플릿 검증
  tests/
    test_api.py
    test_worker_smoke.py
tests/
  fixtures/public/              익명화된 추적 가능 fixture
  ...                           기존 코어/골든 테스트
tools/                          공용 개발 도구 (골든 비교, 템플릿 변환)
doc/
  CLOUDFLARE_WORKERS_WEB_IMPLEMENTATION_PLAN.md
```

데스크톱 앱을 당장 제거하지 않는다. 동일한 순수 코어를 데스크톱 어댑터와 Worker 어댑터가 함께 사용하게 하여 전환 기간에 결과를 대조한다. 다만 **데스크톱 전용 코드와 웹 전용 코드는 같은 폴더에 섞지 않는다.** Tkinter 화면·사용자 설정·실행 경로·PyInstaller 정의는 `desktop/` 아래로 모으고, 공용 패키지 `quotation/` 에는 실행 환경을 모르는 코어만 남긴다. 이 경계는 `web/tests/test_worker_smoke.py` 가 정적으로 검사한다.

Worker 는 `main` 이 있는 폴더 아래 모듈만 번들에 담으므로, 배포 직전 `web/scripts/sync_core.py` 가 공용 코어를 `web/src/quotation/` 으로 복사한다. 복사본은 저장소에서 추적하지 않는다. 심볼릭 링크를 쓰지 않는 이유는 개발이 Windows 에서도 이루어지기 때문이다.

## 11. 단계별 구현 계획

### Phase 0 — 기준선 고정 및 런타임 기술검증 (1~2일)

작업:

- 현재 테스트를 실행하여 기준 성공/skip 목록을 기록한다.
- 익명화된 신규, 증설, N/C, REMOVE, EUC-KR 최소 fixture를 만든다.
- Python Worker 최소 프로젝트에서 `lxml`, `openpyxl`, `BytesIO`, `zipfile`을 검증한다.
- 실제 30 KB 템플릿으로 XLSX를 만들고 그림/도형 관계가 남는지 확인한다.
- 작은/대표/상한 근접 입력의 CPU 시간, 전체 시간, 피크 메모리, 배포 크기를 측정한다.

통과 기준:

- 로컬 CPython 결과와 기존 의미 비교 도구 기준으로 차이가 없음
- 배포 번들, 시작 시간, CPU, 메모리 제한 안에서 동작
- UTF-8/EUC-KR/인라인 DTD 수용 및 XXE 테스트 통과

결정 게이트:

- 모두 통과: Python Worker 계속
- `lxml`만 실패: 안전한 대체 파서로 교체한 뒤 재검증
- `openpyxl`/메모리/배포 크기 실패: Container 실행부로 전환

### Phase 1 — 코어를 바이트 I/O로 분리 (3~4일)

작업:

- XML 바이트 파서 추가
- XLSX `BytesIO` 생성과 도형 ZIP 패치 추가
- 경로 기반 데스크톱 함수는 호환 래퍼로 유지
- Asia/Seoul 날짜 결정 로직 추가
- 예외를 입력 오류, 템플릿 오류, 내부 오류로 분류

통과 기준:

- 기존 데스크톱 테스트가 계속 통과
- 같은 fixture의 path 방식과 bytes 방식이 의미상 동일
- 생성물의 시트, 값, 수식, 서식, 병합, 도형, 인쇄 영역 회귀 없음

### Phase 2 — Worker API와 템플릿 binding (2~3일)

작업:

- `/api/v1/convert`, `/status`, `/config` 구현
- multipart, 크기, 파일형식, 상한 검증 구현
- 비공개 R2 binding과 활성 템플릿 버전 처리
- 표준 오류 형식, 요청 ID, 다운로드 헤더 구현
- no-store와 보안 헤더 적용

통과 기준:

- `wrangler dev`에서 실제 업로드/다운로드 성공
- 잘못된 입력별 상태 코드와 메시지 일관성 확보
- 입력/결과 파일이 R2, KV, 로그에 저장되지 않음

### Phase 3 — 웹 UI (2~3일)

작업:

- 드래그앤드롭/파일 선택/상태/오류/다운로드 화면 구현
- 한글 파일명과 브라우저 다운로드 처리
- 취소, 중복 제출 방지, 접근성 구현
- Workers Static Assets와 API 라우팅 통합

통과 기준:

- Chrome/Edge 최신판에서 대표 시나리오 E2E 통과
- 키보드만으로 파일 선택부터 오류 확인까지 가능
- 정적 자산 경로 새로고침과 API 경로가 충돌하지 않음

### Phase 4 — 보안·운영·성능 (2일)

작업:

- Cloudflare Access 스테이징 정책 적용
- Rate Limiting 및 CPU 상한 설정
- 구조화 로그와 tracing sampling 구성
- 업로드 상한/복잡도/병렬 요청/컨테이너 fallback 부하 테스트
- 런북, 장애 코드, 템플릿 롤백 절차 작성

통과 기준:

- 비인가 사용자는 UI와 API에 접근 불가
- XML/파일명이 로그에 노출되지 않음
- 목표 메모리와 warm p95 기준 충족
- 템플릿 장애 시 이전 버전으로 복구 가능

### Phase 5 — CI/CD 및 배포 (1~2일)

작업:

- PR에서 Python 테스트, 프런트 lint/typecheck/unit/E2E 실행
- preview 환경에 배포 후 API smoke test
- `main` 승인 배포와 운영 환경 분리
- Cloudflare API token/account ID를 CI secret으로 등록
- 커스텀 도메인, TLS, Access 정책 연결

통과 기준:

- 코드와 템플릿 버전을 추적할 수 있음
- 실패한 테스트나 smoke test가 운영 승격을 차단
- 이전 Worker 버전과 템플릿으로 롤백 절차 확인

### Phase 6 — 병행 운영 및 전환 (3~5영업일)

작업:

- 제한된 사용자로 파일럿 운영
- 동일 XML을 데스크톱 앱과 웹 앱에서 변환하여 결과 비교
- 오류율, 처리 시간, 사용자 피드백 수집
- 승인 후 웹 앱을 기본 경로로 안내하고 EXE는 일정 기간 fallback으로 유지

종료 기준:

- 대표 신규/증설 견적에서 승인되지 않은 차이 0건
- 파일럿 기간 중 변환 성공률 99% 이상
- 운영 담당자가 로그 조회, 템플릿 교체, 롤백을 독립 수행 가능

예상 총 소요는 1인 기준 약 12~18 개발일이며, Container 전환 또는 새로운 실데이터 예외 발견 시 별도 여유가 필요하다.

## 12. 테스트 전략

### 12.1 코어/회귀

- 기존 `test_core.py`, `test_writer.py`, `tools/compare.py`를 유지한다.
- path 입력과 bytes 입력의 동일성 테스트를 추가한다.
- 새 견적, 증설, N/C, REMOVE, Services→S/W, CPUSIU 없는 그룹, EUC-KR을 포함한다.
- XLSX ZIP의 drawing/media/rels/[Content_Types] 관계를 별도 검사한다.
- 날짜를 고정하여 `TOTAL!C3`, 상세 `C3`, 견적번호 연도를 검증한다.

### 12.2 API/보안

- 빈 파일, 복수 파일, 잘못된 multipart, 잘못된 XML, 필수 노드 누락
- 외부 엔티티, 큰 DTD/entity expansion, 과도한 노드/그룹/라인
- 10 MiB 경계값, 잘못된 파일명, 한글/공백/`#` 파일명
- 템플릿 없음/손상/필수 시트 누락/R2 오류
- 오류 응답에 스택, 경로, XML 내용이 없는지 검사

### 12.3 브라우저/E2E

- 파일 선택 및 드래그앤드롭
- 성공 다운로드와 파일명
- 서버 오류 표시 및 요청 ID
- 중복 클릭 방지, 요청 취소, 재시도
- Access 인증 후 원래 URL 복귀

### 12.4 성능

- 소형, 대표, 상한 근접 XML 각각의 warm/cold 시간과 메모리 측정
- 동시 요청 시 isolate 메모리 압력과 오류율 확인
- Python Worker와 Container fallback의 결과 및 지연 비교

## 13. 관측성과 운영

구조화 로그 필드:

- `request_id`, `deployment_version`, `template_version`
- `outcome`, `error_code`, HTTP 상태
- `input_size_bucket`, `line_count`, `group_count`, `output_size_bucket`
- `parse_ms`, `template_ms`, `write_ms`, `total_ms`

기록 금지 필드:

- XML 원문과 생성 XLSX
- 고객/제품 설명, 금액, 파트번호
- 원본/출력 파일명
- Access 토큰과 쿠키

초기 경보 기준:

- 5분간 5xx 비율 2% 초과
- `TEMPLATE_UNAVAILABLE` 1건 이상
- Worker exceeded resource limits 발생
- warm p95 5초 초과가 15분 지속
- 변환 성공률 99% 미만

## 14. 위험 및 대응

| 위험 | 영향 | 대응 |
|---|---|---|
| `lxml`/`openpyxl` Pyodide 비호환 | Python Worker 실행 불가 | Phase 0에서 조기 검증, Container fallback |
| 128 MB 메모리 초과 | 요청 실패 | 입력/복잡도 제한, BytesIO 복사 최소화, 실측 후 제한 축소 |
| 도형/서식 유실 | 업무 문서 품질 저하 | 기존 ZIP 패치 이식, drawing 관계 자동 테스트, 파일럿 대조 |
| UTC 날짜 사용 | 견적 날짜 오기 | Asia/Seoul 명시 및 자정 경계 테스트 |
| 템플릿 오배포 | 전 사용자 결과 손상 | immutable R2 버전, 사전 검증, staging, 즉시 롤백 |
| 실데이터 Git 유출 | 고객정보/가격정보 노출 | `samples/` ignore/untrack, 익명 fixture, secret scan |
| 로그에 민감정보 노출 | 정보 유출 | 허용 필드 기반 구조화 로그, 원문/파일명 로깅 금지 |
| Free plan CPU 한도 | 변환 실패/불안정 | Workers Paid를 운영 전제로 예산 승인 |
| Container 콜드 스타트 | 첫 요청 지연 | 작은 이미지, `sleepAfter` 조정, UI 단계 안내, 실측 SLO |
| 새 XML 변형 | 일부 견적 실패 | 오류 코드/요청 ID, 익명화 회귀 fixture 추가 절차 |

## 15. 완료 정의

- 기존 대표 골든과 값·수식·서식·병합·시트·도형·인쇄 설정이 승인 기준 내에서 동일하다.
- UTF-8/EUC-KR, 신규/증설, N/C/REMOVE 핵심 시나리오가 자동 테스트된다.
- Access로 비인가 사용자를 차단하고 입력/결과를 영구 저장하지 않는다.
- XML 본문, 금액, 파일명이 로그와 오류 응답에 노출되지 않는다.
- R2 템플릿 버전 전환과 롤백이 문서화되고 검증된다.
- PR 테스트, preview, 승인 배포, smoke test, 롤백 경로가 동작한다.
- 운영 담당자가 요청 ID로 실패를 찾고 사용자에게 민감정보 없이 안내할 수 있다.
- 파일럿 승인 후에도 데스크톱 앱을 정한 기간 동안 복구 수단으로 유지한다.

## 16. 착수 전에 확정할 업무 결정

1. 서비스가 사내 전용인지, 외부 고객도 접근하는지
2. 허용할 Access 사용자 이메일 도메인/그룹
3. 운영 커스텀 도메인과 스테이징 도메인
4. 중앙 템플릿 담당자와 변경 승인자
5. 사용자별 템플릿이 반드시 필요한지
6. 입력·결과 무저장 정책에 대한 업무 승인
7. Workers Paid 및 필요 시 Containers/R2 비용 승인
8. 파일럿 사용자와 대표 익명화 회귀 자료

## 17. 공식 참고 자료

- [Cloudflare Workers limits](https://developers.cloudflare.com/workers/platform/limits/)
- [Cloudflare Workers pricing](https://developers.cloudflare.com/workers/platform/pricing/)
- [Python Workers](https://developers.cloudflare.com/workers/languages/python/)
- [Python Workers packages](https://developers.cloudflare.com/workers/languages/python/packages/)
- [Python Workers standard library](https://developers.cloudflare.com/workers/languages/python/stdlib/)
- [Workers Static Assets](https://developers.cloudflare.com/workers/static-assets/)
- [R2 Workers API](https://developers.cloudflare.com/r2/get-started/workers-api/)
- [Cloudflare Containers](https://developers.cloudflare.com/containers/)
- [Container lifecycle and cold starts](https://developers.cloudflare.com/containers/platform-details/architecture/)
- [Cloudflare Access policies](https://developers.cloudflare.com/cloudflare-one/access-controls/policies/)
- [Workers Logs](https://developers.cloudflare.com/workers/observability/logs/workers-logs/)
- [Workers tracing](https://developers.cloudflare.com/workers/observability/traces/)
- [Workers GitHub Actions deployment](https://developers.cloudflare.com/workers/ci-cd/external-cicd/github-actions/)

위 한도와 제품 상태는 2026-08-14 기준으로 작성했으며 구현 착수 시 다시 확인한다.

## 18. 구현 현황

| 단계 | 상태 | 비고 |
|---|---|---|
| Phase 0 기준선·fixture | 코드 부분 완료 | `tests/fixtures/public/` 에 신규·증설·N/C·REMOVE·EUC-KR·인라인 DTD fixture 작성. **Pyodide 런타임 기술검증은 실제 Cloudflare 계정에서 남아 있다.** |
| Phase 1 코어 bytes I/O | 완료 | `parse_bytes`, `build_bytes`, `carry_over_bytes`, `convert_bytes`. 경로 API 는 데스크톱 어댑터로 유지. path/bytes 동등성 테스트 통과 |
| Phase 2 Worker API | 완료 | `/convert`, `/status`, `/config`, 상한·오류코드·보안 헤더·Asia/Seoul 날짜·구조화 로그. `wrangler dev` 실측은 남아 있다 |
| Phase 3 웹 UI | 완료 | 드래그앤드롭, 단계 상태, 취소, 중복 제출 방지, 접근성, 한글 파일명 다운로드. 브라우저 E2E 는 남아 있다 |
| Phase 4 보안·운영 | 설정만 | Access 정책·Rate Limiting·부하 테스트·런북은 계정 작업 |
| Phase 5 CI/CD | 부분 완료 | `.github/workflows/ci.yml` 의 테스트·빌드·스테이징 배포. Cloudflare 토큰 등록 필요 |
| Phase 6 병행 운영 | 미착수 | 파일럿과 결과 대조는 배포 후 |

계정 작업 없이 진행할 수 없는 항목(§16 의 업무 결정, R2 버킷 생성, Access 정책,
커스텀 도메인, Workers Paid 승인)은 코드에 설정 자리만 두었다. `wrangler.jsonc`
의 버킷 이름과 `ACTIVE_TEMPLATE_KEY` 는 실제 값으로 바꿔야 한다.

### 18.1 배포 도구 사실관계 (실측)

첫 CI 배포 실패로 확인한 내용이다. §4 의 아키텍처는 그대로지만 배포 절차가 다르다.

- `cloudflare/wrangler-action@v3` 은 기본으로 **wrangler 3.90** 을 설치한다. 3.x 는
  `wrangler.jsonc` 를 읽지 못해 설정 전체를 무시하고 `Missing entry-point` 로 죽는다.
  **wrangler 4.42.1 이상**이 필요하다. 판본은 `web/package.json` 에 고정했다.
- 의존성은 `requirements.txt` 가 아니라 `pyproject.toml` 에 적고 **`pywrangler`**
  (PyPI `workers-py`, `uv>=0.12.3` 필요)로 배포한다. `pywrangler sync` 가
  Pyodide 인덱스(`index.pyodide.org`)에서 대상 플랫폼
  (`cpython-*-emscripten-wasm32-musl`)용 패키지를 받아 `web/python_modules/` 에
  vendoring 한 뒤 wrangler 로 넘긴다. `wrangler deploy` 를 직접 부르면 코드만
  올라가고 `lxml`·`openpyxl` 이 빠져 첫 요청에서 import 오류가 난다.
- `wrangler deploy --dry-run` 은 자격 증명 없이 설정과 번들을 검사한다. 공용 코어
  17개 모듈과 정적 자산, R2·변수 바인딩이 모두 잡히는 것을 확인했다(총 71 KiB).
  CI 의 `bundle` 잡이 매 푸시마다 이 검사를 돌린다.
- 따라서 §11 Phase 0 의 "`lxml`/`openpyxl` Pyodide 호환성" 판정은 CI 의
  `pywrangler sync` 단계가 대신한다. 이 단계가 실패하면 판본을 인덱스에 있는
  것으로 낮추거나 §4.2 의 Container 전환을 실행한다.

### 18.2 Phase 0 런타임 검증 결과 (2026-08-14, CI 실측)

**Python Worker 로 간다.** Container 전환은 하지 않는다.

| 항목 | 실측 | 기준 |
|---|---|---|
| `lxml` | **6.0.0** (Pyodide 0.28.3 인덱스) | 데스크톱은 6.1.1. 인덱스에 6.1.1 wheel 이 없어 판본이 갈린다 |
| `openpyxl` | 3.1.5 | 데스크톱과 동일 |
| 부수 의존성 | `et-xmlfile` 2.0.0, `workers-runtime-sdk` 1.6.13 | |
| vendoring 크기 | 8.3 MB (`lxml` 6.6 MB + `openpyxl` 1.4 MB) | |
| 배포 번들 | **7,532 KiB (gzip 1,943 KiB)**, 352 모듈 | Paid 10 MB 한도 안. 여유는 넉넉하지 않다 |
| 변환 시간 | 로컬 CPython 기준 대표 입력 80~100 ms | Worker 실측은 `wrangler dev` 로 |

`lxml` 판본이 데스크톱과 갈리므로 CI 의 코어 테스트를 6.1.1 과 6.0.0 양쪽에서
돌린다.

배포 실측에서 확인한 요금제 제약: `limits.cpu_ms` 는 **Workers Paid 전용**이라
Free 계정에서는 그 항목이 있는 것만으로 배포가 거부된다(`code: 100328`). 기본
설정에서는 빼 두고 Paid 전환 시 되살린다.

### 18.4 §8 변경 — 템플릿을 R2 에서 번들로

계획서 §8 은 템플릿을 비공개 R2 에 두고 `ACTIVE_TEMPLATE_KEY` 로 전환하도록
설계했다. 1차 출시에서는 이를 **번들 내장으로 바꾼다.**

바꾼 이유:

- 템플릿은 중앙 한 개뿐이고 사용자별 템플릿 요건은 아직 확정되지 않았다(§16-5).
- 활성 키를 바꾸는 것도 결국 Worker 재배포가 필요하다. "코드 배포 없이 교체"
  라는 이점이 크지 않았다.
- 대신 버킷 생성, 토큰 R2 권한, 업로드 절차, 키 관리, 요청 경로의 R2 실패
  가능성(`TEMPLATE_UNAVAILABLE`)이 늘었다. 운영 관문이 하나 더 생긴 셈이다.

바뀐 구조:

- 원본은 `quotation/resources/견적서_template.xlsx` 하나뿐이고 데스크톱과 웹이
  같은 파일을 쓴다.
- 배포 직전 `web/scripts/sync_core.py` 가 그 파일을 base64 로 담은
  `web/src/template_data.py` 를 만든다(30 KB → 41 KB, 7.5 MB 번들 대비 무시할
  수준). 생성물은 추적하지 않는다.
- 템플릿 판본은 내용 해시(`sha256-…`)다. `/status` 와 `X-Template-Version` 에
  그대로 실려 추적성은 유지된다.
- 교체는 `.xlsx` 를 고쳐 커밋하는 것이고, 롤백은 그 커밋을 되돌리는 것이다.
- 번들 템플릿이 저장소 원본과 같은지는 테스트가 매번 확인한다.

§8.1 의 "공개 정적 자산으로 노출하지 않는다" 는 지켜진다. 템플릿은 정적 자산
폴더가 아니라 Worker 모듈로만 들어가므로 URL 로 받아 갈 수 없다.

**되돌리는 조건:** 회사별·사용자별 템플릿이 필요해지거나, 개발자를 거치지 않고
템플릿을 교체해야 하는 운영 요건이 확정되면 §8 의 R2 설계로 돌아간다. 그때는
`web/src/template.py` 의 출처만 바꾸면 되고 나머지 층은 그대로다.

### 18.3 변환 1건의 CPU 시간 (네이티브 CPython 실측)

`time.process_time()` 기준, 워밍업 후 평균. I/O 대기는 포함하지 않으므로 Workers
의 CPU 한도와 직접 비교할 수 있다.

| 입력 | 라인 | CPU | Free 한도(10ms) 대비 |
|---|---:|---:|---:|
| `euckr_quote.xml` | 1 | 73 ms | 7배 |
| `new_quote.xml` | 3 | 108 ms | 11배 |
| `upgrade_quote.xml` | 2 | 82 ms | 8배 |
| 합성 대형 (7시트) | 51 | 423 ms | 42배 |

가장 작은 견적서도 Free 한도를 7배 넘는다. Pyodide(WASM)는 네이티브보다 통상
2~5배 느리고 첫 요청의 import 비용이 더해지므로 실제 소요는 이보다 크다.
**§4.2 의 "운영 기준은 Workers Paid" 판단은 실측으로 확정됐다.** Free 에서도
정적 화면과 `/status`·`/config` 는 동작하므로 배포 파이프라인 검증까지는
무료로 진행할 수 있다.
 남은 미검증 항목은 **실제 isolate 의 메모리·CPU 사용량과 도형 보존**
이며, 이는 계정과 R2 템플릿이 준비된 뒤 `wrangler dev` 로 확인한다.

### 18.5 §4 변경 — 무료 계정 운영을 위해 변환을 브라우저로 옮긴다

§4.2 는 "운영 기준은 Workers Paid" 로 잡았고 §18.3 의 실측이 그 판단을
확정했다. 그런데 운영 계정이 **무료 계정** 이라면 그 길이 닫혀 있다. Free 의
요청당 CPU 10 ms 로는 가장 작은 견적서(73 ms)도 만들 수 없고, 이것은 코드를
빨리 만들어서 넘길 수 있는 차이가 아니다(7~42배).

Paid 로 올리지 않고 무료 계정에서 **원활히** 돌리는 길은 하나뿐이다. 변환을
서버에서 빼는 것이다. 그렇다고 변환기를 다시 쓰면 결과가 달라질 위험이 생기고,
그것은 견적서에서 용납되지 않는다. 그래서 **같은 파이썬을 브라우저에서 돌린다.**

    이전   브라우저 --XML--> Worker(Pyodide) --XLSX--> 브라우저
    이후   브라우저(Pyodide) 안에서 시작하고 끝난다. Cloudflare 는 자산만 준다

바뀌지 않는 것:

- 변환 코어(`quotation.core`), 검증·가드(`conversion_adapter`, `limits`),
  응답 계약(`api`), 견적 날짜(`clock`), 템플릿(`template`) — **파일이 같다.**
  사본을 두지 않고 `build_browser_engine.py` 가 `web/src` 를 그대로 담는다.
- 부르는 함수도 같다. `worker.py` 와 `browser/entry.py` 가 둘 다
  `api.convert_response` 를 부른다.
- API 계약(§6)과 화면(§7)의 겉모습.

바뀌는 것:

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

§4.2 의 Container 전환은 하지 않는다. 그것은 Paid 를 전제로 하며 무료 계정
문제를 풀지 못한다. 서버 변환 자체는 버리지 않고 `wrangler.jsonc` 의
`env.server`(Workers Paid 전용)로 남겨 둔다. 화면은 브라우저 엔진을 못 띄웠을
때만 그쪽으로 넘어간다.

#### 결과가 같다는 것을 무엇으로 증명하는가

"같은 코드를 쓴다" 는 설계일 뿐이므로 테스트로 못박는다.

| 테스트 | 지키는 것 |
|---|---|
| `test_browser_engine.py` | 엔진에 담기는 코드와 양식이 저장소 원본과 바이트가 같다. lxml·openpyxl 판본이 `web/pyproject.toml` 과 같다. 받아 오는 파일은 모두 sha256 으로 고정되어 있다 |
| `test_browser_parity.py` | Node 로 엔진을 돌려 만든 견적서가 CPython 산출물과 같다. `.xlsx`(zip) 안의 모든 부품을 바이트로, 그리고 골든 회귀와 같은 비교기(`tools/compare.py`)로 셀 단위로. 오류 사례의 상태 코드·오류 코드도 함께 |
| `test_browser_e2e.py` | 운영과 같은 CSP 를 건 서버에서 실제 Chromium 으로 내려받은 파일이 CPython 산출물과 같다 |

정규화하는 것은 둘뿐이며 둘 다 견적서 내용이 아니다 — 파일 생성 **시각**
(`docProps/core.xml` 의 `dcterms:modified`)과 `<mergeCell>` 의 나열 **순서**
(집합은 같아야 하고, 다르면 테스트가 잡는다). 근거는 `web/tests/xlsx_parity.py`.

#### 이 과정에서 드러난 결함 — Pyodide 의 libxml2 는 EUC-KR 을 모른다

실제로 돌려 보니 EUC-KR 견적서가 통째로 변환되지 않았다.

    XMLSyntaxError: Unsupported encoding EUC-KR, line 1, column 38

Pyodide 의 lxml 이 iconv 없이 빌드되어 있다. **§4 의 Python Worker 로 갔어도
같은 결과였다.** Phase 0 의 게이트(§11)가 `pywrangler sync` 성공까지만 보고
실제 변환을 돌리지 않아 놓쳤다. 2005년 형식 견적 XML 은 EUC-KR 이 흔하므로
그대로 두면 그 견적서들은 웹에서 만들 수 없었다.

`quotation/core/xml_reader.py` 에 좁은 대비책을 두었다. 파싱이 **아예 실패한
경우에 한해**, 선언된 인코딩을 파이썬 표준 코덱(Pyodide 에도 EUC-KR·CP949·
Shift_JIS 등이 모두 있다)으로 디코딩해 UTF-8 로 다시 적고 한 번만 더 읽는다.
문자는 하나도 바뀌지 않으므로 파서가 보는 문서는 iconv 가 있는 데스크톱이 보는
것과 같다. 이미 읽히는 문서에는 이 경로가 닿지 않고, 다시 읽어도 실패하면
처음 오류 문구를 그대로 알린다(원본 프로그램과 같은 문구를 지킨다).

#### 남은 것

- 첫 방문 14.4 MiB 는 Cloudflare 가 압축해 보내지만 여전히 크다. 줄일 여지는
  lxml(1.7 MiB)을 걷어내는 것뿐인데, 파서를 바꾸면 동작이 갈릴 수 있으므로
  하지 않는다.
- WebAssembly 를 못 쓰는 브라우저에서는 `env.server` 배포가 있어야 변환된다.
  무료 계정만 쓸 때는 그런 브라우저를 지원하지 않는다는 뜻이 된다.
