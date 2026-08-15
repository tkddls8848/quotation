# IBM Power Quick Config

IBM eConfig 화면에서 Feature와 세부 수량을 일일이 고르는 시간을 줄이는 로컬 도구입니다.

이 도구가 견적 BOM이나 CFR을 자체적으로 만들어 내는 구조가 아닙니다. 사용자는 업무 프리셋 또는
구성요소별 등급만 고르고, 로컬 서비스가 그 요구사항을 현재 IBM eConfig 세션에 적용합니다. 최종
호환성 판단과 CFR 생성은 IBM eConfig 엔진이 담당합니다.

```text
업무 프리셋/카테고리 선택
          ↓
로컬 요구사항 → IBM wizard intent 변환
          ↓
IBM product base·catalog·control ID 동적 탐색
          ↓
IBM eConfig wizard 적용·검증
          ↓
IBM /cfr/get 결과를 .cfr로 다운로드
```

## 현재 지원 범위

- 신규 구성, 국가 KR
- IBM Power E1080 `9080-HEU`
- 컴퓨트: 기본 / 균형 / 고성능
- 메모리: 기본 / 균형 / 대용량
- 부트 NVMe: 미러 / 4개 구성
- Ethernet: 기본 / 이중화 / 고밀도
- Fibre Channel: 없음 / 이중화 / 고밀도
- AIX 7.3 Standard + PowerVM Enterprise
- 3 Year Advanced Expert Care

프리셋은 시작값일 뿐입니다. `업무 시스템`을 고른 뒤 SAN만 `고밀도`로 바꾸는 식으로 각 구성요소를
독립적으로 조정할 수 있습니다.

## 실행

저장소 루트 `C:\quotation\quotation`에서 실행합니다.

```powershell
python -m econfig --host 127.0.0.1 --port 8080
```

브라우저에서 다음 주소를 엽니다.

```text
http://127.0.0.1:8080/
```

JWT가 없으면 화면은 미리보기 전용으로 동작합니다. 카테고리 선택과 IBM에 보낼 목표값/intent는
확인할 수 있지만 `IBM에서 CFR 생성` 버튼은 비활성화됩니다.

## IBM 연결

IBM eConfig Cloud는 이 자동화 용도의 공개 API나 장기 API key를 제공하지 않습니다. 현재 웹앱이
사용하는 만료 시간이 짧은 JWT가 필요합니다.

1. `https://www.ibm.com/services/econfigcloud/`에 정상 로그인합니다.
2. 브라우저 개발자 도구의 Network에서 eConfig API 요청 하나를 선택합니다.
3. 요청의 `Authorization: JWT ...` 헤더에서 토큰 값만 현재 PowerShell 세션에 설정합니다.
4. 같은 PowerShell에서 이 서비스를 시작합니다.

```powershell
$env:IBM_ECONFIG_JWT = '<현재 로그인 세션의 JWT>'
python -m econfig
```

토큰을 파일, `.env`, Git, 브라우저 localStorage 또는 로그에 저장하지 마십시오. 만료되면 새 토큰으로
프로세스를 다시 시작합니다.

JWT claim의 `type`, `country`, `roles`, `latestRole`, `encodeBody`는 자동으로 읽습니다. 필요한 경우만
다음 환경변수로 덮어쓸 수 있습니다.

| 환경변수 | 기본값 / 용도 |
|---|---|
| `IBM_ECONFIG_BASE_URL` | `https://www.ibm.com/services/econfigcloud/api` |
| `IBM_ECONFIG_USER_ROLE` | JWT의 latestRole 또는 첫 role |
| `IBM_ECONFIG_USER_COUNTRY` | JWT country, 없으면 `KR` |
| `IBM_ECONFIG_USER_TYPE` | JWT type, 없으면 `business-partner` |
| `IBM_ECONFIG_USER_NAME` | JWT의 이름, 없으면 `SYSTEM` |
| `IBM_ECONFIG_PRODUCT_BASE_ID` | 자동 탐색이 실패할 때만 현재 POWER product base ID 지정 |
| `IBM_ECONFIG_GEOGRAPHY` | validation geography, 기본 `AP` |
| `IBM_ECONFIG_ENCODE_BODY` | claim 대신 body encoding 강제 지정 (`true`/`false`) |
| `IBM_ECONFIG_KEEP_SESSION` | 디버깅 시 IBM 세션을 종료하지 않음 |
| `IBM_ECONFIG_TIMEOUT_SECONDS` | IBM 요청 timeout, 기본 90초 |

## API

### 선택지

```text
GET /v1/options
```

### IBM 실행 전 미리보기

```text
POST /v1/requests/preview
```

```json
{
  "request_id": "Q-1180",
  "preset": "balanced",
  "country": "KR",
  "language": "ko-KR",
  "selections": {
    "compute": "performance",
    "memory": "balanced",
    "boot_storage": "quad",
    "ethernet": "dense",
    "fibre_channel": "dense",
    "software": "aix-standard",
    "support": "advanced-3y"
  }
}
```

### IBM에서 CFR 생성

```text
POST /v1/requests/generate
```

응답의 `cfr`이 IBM에서 회수한 CFR 본문이고 `file_name`이 다운로드 파일명입니다. 웹 UI는 이를
Blob으로 만들어 바로 내려받습니다. 응답에는 JWT가 포함되지 않습니다.

## 실제 IBM 호출 흐름

현재 eConfig Cloud 웹 클라이언트 2.1.74에서 확인한 호출 계약을 사용합니다.

1. `GET /ng/productBases`
2. `POST /session/start`
3. `GET /products/get_catalog`
4. `GET /products/selected/{dynamic-id}`
5. IBM이 반환한 `server_url/currentWizard`
6. `server_url/currentWizard/updateControl`
7. 필요 시 `GET /configuration/list`, `POST /configuration/event`
8. `POST /cfr/get`
9. `POST /base_edit/validate`, 필요 시 `POST /base_edit/respond_dialog`
10. 검증 뒤 `POST /cfr/get`
11. `GET /session/end`

product base, product, wizard, action, control ID는 응답에서 매번 해석합니다. 코드에 특정 세션 ID를
넣지 않습니다.

## 검증

```powershell
.\.venv\Scripts\python.exe -m pytest -q econfig\tests
```

테스트는 다음을 확인합니다.

- 프리셋과 카테고리 입력 검증
- 카테고리 → 목표 용량 → IBM intent 변환
- 동적 product base/product ID 선택
- table control의 동적 component ID event 생성
- CFR의 핵심 요청 Feature 대조
- 미연결 상태의 명시적 503 응답
- 가짜 IBM gateway를 이용한 전체 API 흐름

## 중요한 한계

IBM endpoint는 공개·버전 고정 API가 아닙니다. IBM이 wizard JSON, 인증 방식 또는 endpoint를 바꾸면
semantic binding을 보정해야 할 수 있습니다. 이 저장소의 자동 테스트는 실제 IBM 계정/JWT를 사용하지
않으므로, 최초 실사용 전에는 보유 계정으로 각 프리셋을 한 번씩 실행해 IBM eConfig에서 다시 열리고
최종 validation을 통과하는지 확인해야 합니다.

필수 하드웨어 intent를 적용하지 못했고 CFR에서도 해당 Feature를 확인하지 못하면 다운로드 가능한
성공으로 위장하지 않고 `ibm_gateway_error`로 중단합니다.

