# econfig_claude

IBM e-config 구성파일(`.cfr`)을 **로컬에서** 읽고, 비교하고, 고쳐서 다시 쓰는 도구.

포맷을 재구현하지 않는다. e-config Cloud 웹앱이 실제로 쓰는 코덱을 번들에서 그대로 꺼내
Node에서 돌린다. 따라서 IBM이 레코드 레이아웃을 바꿔도 번들만 다시 받으면 따라간다.

## 왜 이 형태인가

e-config에는 "규격을 던지면 CFR을 주는" 공개 API가 없다. 서버 API는 존재하지만
(`www.ibm.com/services/econfigcloud/api/*`, `Authorization: JWT`) 세션 상태를 가진
대화형 제약 해결 엔진이고, IBMid SSO와 Akamai Bot Manager 뒤에 있으며 문서화되지 않았다.

반면 **CFR ↔ JSON 코덱은 전부 클라이언트 측 순수 JS**다. 서버도, 인증도, 네트워크도 필요 없다.
이 저장소는 그 경계선까지만 간다.

## 설치

```bash
cd econfig_claude
npm run fetch      # IBM 번들을 vendor/로 내려받는다 (약 4MB, 커밋하지 않음)
```

## 웹 UI

```bash
npm run serve            # http://127.0.0.1:4173
```

`.cfr`을 끌어놓으면 네 개 탭으로 다룬다:

| 탭 | 하는 일 |
|---|---|
| 구성 | 시스템 → 제품 → feature code 트리 |
| 비교 | 두 구성의 FC 수량 차이 표 |
| **생성** | **스펙대로 FC를 바꿔 새 `.cfr` 생성 + 스펙 JSON 출력** |
| 수정 | FC 하나만 빠르게 수량 변경 |
| 레코드 규격 | 고정폭 레코드 컬럼 맵 |

탭은 `#compare`처럼 해시로 딥링크된다.

**로컬 전용이다.** 서버는 `127.0.0.1`에만 바인딩하고, 업로드한 파일은 메모리에만 있으며
디스크에 쓰지 않는다. 구성파일에는 고객명과 리스트 가격이 들어 있으니 이 경계를 넘기지 마라.
(아티팩트나 외부 호스팅으로는 만들 수 없다 — 코덱이 IBM 번들과 Node를 필요로 한다.)

## CLI

```bash
node bin/econfig.mjs inspect  <file.cfr>
node bin/econfig.mjs gen      <spec.json> [-o out.cfr]
node bin/econfig.mjs spec-of  <file.cfr> [-o spec.json]
node bin/econfig.mjs diff     <a.cfr> <b.cfr>
node bin/econfig.mjs set      <file.cfr> --code EM54 --qty 6 [-o out.cfr]
node bin/econfig.mjs parse    <file.cfr> [-o out.json]
node bin/econfig.mjs build    <file.json> [-o out.cfr]
node bin/econfig.mjs roundtrip <file.cfr|dir>
node bin/econfig.mjs spec     [recordType]
node bin/econfig.mjs serve    [--port 4173]
```

### gen — 스펙으로 CFR 만들기

원래 목표였던 "스펙을 주면 CFR이 나온다"를 **인증 없이 로컬에서** 하는 경로다.

```json
{
  "template": "S1124_1CPU_8c_128GB.cfr",
  "description": "S1124 384GB / 10GbE 4port",
  "products": [{
    "mtm": "9824-42A",
    "mode": "merge",
    "features": {
      "EM54": 6,
      "EB46": { "qty": 4, "description": "10GbE Optical Transceiver SFP+ SR" },
      "ECW0": 0
    }
  }]
}
```

```
$ node bin/econfig.mjs gen spec.json -o out.cfr
  9824-42A  [merge]  01Server1_1_I_9824_42A_HW
    set   EM54       2 -> 6
    add   EB46       0 -> 4
    drop  ECW0       2 -> 0
```

| | |
|---|---|
| `mode: merge` | 적은 코드만 바꾸고 나머지는 템플릿 그대로 (기본값) |
| `mode: replace` | 적은 코드만 남기고 나머지는 전부 제거 |
| 수량 `0` | 해당 코드 제거 |
| 새 코드 | 템플릿에 없어도 추가된다. `description`을 안 주면 경고하고 엔진이 채우도록 비워둔다 |

**왜 템플릿이 필요한가.** 백지에서 만들 수도 있지만(`fromProducts`), 그렇게 나온 문서는
`system_level`이 하드코딩되고 price file·locale·엔진 메타데이터가 전부 합성값이라
e-config가 받아주지 않을 가능성이 높다. 실제 구성파일은 엔진이 넣은 필수 부속과
유효한 문서 헤더를 이미 갖고 있어서, 그 위에서 FC만 바꾸는 쪽이 훨씬 안전하다.

기존 구성을 스펙으로 되뽑을 수도 있다:

```
$ node bin/econfig.mjs spec-of 운영DB.cfr -o spec.json
```

`spec-of` → `gen` 왕복은 원본과 feature 집합이 완전히 일치하는 것을 확인했다.

### diff — 두 구성의 실제 차이

```
$ node bin/econfig.mjs diff S1124_1CPU_8c_128GB.cfr S1124_1CPU_8c_256GB.cfr
  + 9824-42A   EB46      0 ->    8   10GbE Optical Transceiver SFP+ SR
  + 9824-42A   EM54      2 ->    4   64 GB (2x32 GB) DDIMMs, 4000/4800 MHz DDR5
```

견적 검토에서 가장 쓸모가 큰 명령이다. 두 구성파일이 정확히 어느 feature code에서
몇 개나 갈리는지 나온다.

### set — 템플릿 파라미터화

```
$ node bin/econfig.mjs set S1124_1CPU_8c_128GB.cfr --code EM54 --qty 6 -o out/384GB.cfr
  01Server1_1_I_9824_42A_HW  EM54  2 -> 6
```

검증된 기존 구성을 템플릿 삼아 수량만 바꾸는 방식이다. 백지에서 만드는 것보다
훨씬 견고하다 — 필수 부속과 구조가 이미 엔진이 보증한 상태이기 때문.

## 검증 상태

보유한 `.cfr` 12개 전부에 대해 `decode → encode` 후 레코드 다중집합을 비교했다.
**바이트 단위로 동일하지는 않다.** 무엇이 보존되고 무엇이 안 되는지가 중요하다.

| 레코드 | 내용 | 결과 |
|---|---|---|
| 08 / 47 / 96 등 | **BOM** (feature code + 수량) | **12/12 완전 보존** |
| 95 | 제품 식별 | description 필드가 재작성됨 (`Server 1:IBM Power S1124` → `Server 1`) |
| 06 | 엔진 상태 블롭 | 같은 내용이 다른 순서로 재패킹됨 |
| 99 | 체크섬 | 항상 소실 |

```
$ node bin/econfig.mjs roundtrip ~/Downloads
BOM OK     115 recs  06 rewritten x10, 95 rewritten x1, 99 dropped x1  S1124_1CPU_8c_128GB.cfr
...
12/12 preserved the bill of materials exactly
```

편집이 실제로 어디에 반영되는지도 바이트 수준에서 확인했다. `--code EM54 --qty 6`은
레코드 08의 해당 위치 한 곳만 바꾼다:

```
orig: ...EJBU       1EM54       2EN1A       2...
gen : ...EJBU       1EM54       6EN1A       2...
```

## 한계 — 반드시 읽을 것

**1. `set`이 만든 파일은 내부적으로 불일치한다.** ← 가장 중요

레코드 08(BOM)은 새 수량으로 바뀌지만, 레코드 06의 **엔진 상태 블롭은 예전 수량 그대로**다.
검증했다:

```
record 06 (engine state) identical between identity and edited re-encode?  true   ← 반영 안 됨
record 08 (BOM)          identical between identity and edited re-encode?  false  ← 반영됨
```

블롭은 압축된 엔진 내부 상태라 이 코덱이 갱신하지 못한다. 따라서 e-config가 이 파일을
복원할 때 블롭을 신뢰하면 편집이 조용히 무시될 수 있다. **`set` 출력은 e-config에 올려
reconcile로 확인하기 전까지 신뢰하지 말 것.** 사람이 읽는 BOM·비교 용도로는 정확하다.

**2. 생성된 CFR은 검증되지 않았다.**
이 도구는 호환성을 판단하지 않는다. 슬롯 수, 전원, 냉각, 필수 동반 FC, 상호 배타 규칙은
전부 e-config 엔진만 안다. `set`으로 만든 파일은 *제안*이지 *유효한 주문*이 아니다.

**3. 체크섬 레코드(99)가 빠진다.**
웹앱은 체크섬을 서버(`/lms_service/cfr/get_checksum`)에서 받는다. 로컬 재직렬화에는 없다.

**4. 가격이 갱신되지 않는다.**
`document_info.config_creation_date`와 price file 날짜가 원본 그대로 남는다.
수량을 바꿔도 금액은 다시 계산되지 않는다.

**5. 번들 버전에 묶인다.**
`vendor/BUNDLE_INFO.json`에 받은 시점과 앱 버전이 기록된다. 동작이 이상하면
`npm run fetch`로 갱신하고 `roundtrip`을 다시 돌려라.

## CFRJSON 스키마

```js
{
  document_info: {
    version, creating_applic_name, system_level,
    config_creation_date, config_country_code, selected_language, ...
  },
  systems: {
    "01Server1": {
      machine_type: "9824", model: "42A", serial, system_description,
      sections: { initial_order: [{hardware:[uid], software:[uid], services:[]}],
                  base: [], proposed: [], transactions: [] }
    }
  },
  products: {
    "01Server1_1_I_9824_42A_HW": {
      uid, class: "HARDWARE"|"SOFTWARE", type, model, description, quantity,
      messages: [{type, class, text}],
      features: [{ num: "EM54", description, quantity, price_flag, pricing_data }]
    }
  }
}
```

`features[].num`이 feature code다. 제품 uid는 `{system}_{seq}_{section}_{type}_{model}_{HW|SW}`
규칙을 따르며 section 문자는 `I`(initial) / `B`(base) / `P`(proposed).

## 레코드 레이아웃

`.cfr`은 고정폭 텍스트다. 레코드 타입별 컬럼 맵을 뽑을 수 있다:

```
$ node bin/econfig.mjs spec
00  Header                            40 fields
95  Hardware/Software Product Identification  32 fields
96  Hardware/Software Feature Identification   9 fields
99  Check Sum                          1 fields
...

$ node bin/econfig.mjs spec 96
96  Hardware/Software Feature Identification
        3-9    (  7)  NUM  {"type":"NORMAL"}
       10-12   (  3)  >REFERENCE NOTES NUM  {"type":"NORMAL"}
       ...
       51-999  (949)  DESCRIPTION  {"type":"NORMAL"}
```

주의: 수량은 96이 아니라 **08**(Hardware Initial Order)에 `코드 + 우측정렬 수량` 형태로
들어간다. 96은 코드의 설명 텍스트만 담는다.

## 구조

```
scripts/fetch-bundle.mjs   IBM 번들 다운로드
src/runtime.mjs            webpack 모듈 테이블만 가로채는 미니 런타임 (Angular 부팅 안 함)
src/codec.mjs              CFR ↔ CFRJSON + inspect/diff/set/fidelity
src/generate.mjs           스펙 → CFR (템플릿 기반)
src/spec.mjs               고정폭 레코드 레이아웃 추출
src/server.mjs             로컬 HTTP API (의존성 0, node:http만 사용)
web/index.html             단일 파일 UI (외부 리소스 없음)
bin/econfig.mjs            CLI
```

npm 의존성이 없다. `node_modules` 없이 Node 18+ 만으로 돈다.

### HTTP API

| 메서드 | 경로 | 용도 |
|---|---|---|
| POST | `/api/files` | `.cfr` 업로드 (octet-stream, `X-Filename` 헤더) |
| GET | `/api/files` | 목록 |
| DELETE | `/api/files/:id` | 제거 |
| GET | `/api/files/:id/inspect` | 구성 요약 |
| GET | `/api/files/:id/fidelity` | 왕복 충실도 |
| GET | `/api/files/:id/spec` | 구성 → 스펙 스켈레톤 |
| POST | `/api/generate` | 스펙 + 템플릿 → base64 `.cfr` |
| GET | `/api/diff?a=&b=` | FC 차이 |
| POST | `/api/files/:id/set` | 수량 변경 → base64 `.cfr` |
| GET | `/api/spec` | 레코드 규격 |

`src/runtime.mjs`가 핵심 트릭이다. 번들 끝의
`(self.webpackChunk... ||= []).push([[792], {모듈들}, r => r(r.s = 5428)])`에서
세 번째 인자(Angular 부트스트랩)를 버리고 모듈 테이블만 취한다. DOM이 필요 없어진다.

## 범위 밖

- 신규 구성을 백지에서 생성 — 엔진 없이는 불가
- 가격 재계산 — price file은 서버에 있다
- 호환성 검증 — reconcile은 서버 몫
- 서버 API 자동 호출 — JWT · Akamai · 비공개 API. 하지 않는다.
