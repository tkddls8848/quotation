# 웹 앱 (Cloudflare Workers)

브라우저에서 eConfig XML 을 고르면 견적서 `.xlsx` 가 만들어져 바로 내려옵니다.
**여러 개를 한 번에 고를 수 있고, XML 하나마다 `.xlsx` 하나가 같은 이름으로
내려옵니다.** 변환은 한 건씩 하므로 한 개만 변환할 때와 결과가 같습니다 —
`web/tests/test_browser_e2e.py` 가 매번 대조합니다.
설계 경위는 [`doc/`](../doc/) 에 성격별로 나눠 두었습니다 —
[계획](../doc/plan/web-app-plan.md),
[결정](../doc/decisions/), [사고](../doc/incidents/),
[실측](../doc/measurements/runtime.md).

## 변환은 브라우저에서 돈다 (무료 계정 기준)

Cloudflare Workers **Free 는 요청당 CPU 10 ms** 다. 견적서 한 건을 만드는 데는
가장 작은 입력도 73 ms, 큰 것은 423 ms 가 든다(실측 measurements/runtime.md). 서버에서
만드는 길은 무료 계정에서 애초에 성립하지 않는다.

그래서 변환을 브라우저로 옮겼다. Cloudflare 는 정적 자산만 내려 준다.

```text
브라우저                                   Cloudflare (정적 자산만)
  ┌──────────────────────────────┐
  │ 화면 (main.ts)               │  ← index.html, js, css
  │   └ 변환 일꾼 (Web Worker)   │
  │       └ engine.js            │  ← /engine/quotation_wasm.js
  │           └ quotation_wasm   │  ← /engine/quotation_wasm_bg.wasm
  │               ├ webapi       │     검증·헤더·오류 문구
  │               ├ core         │     변환 규칙 (데스크톱과 같은 것)
  │               └ 템플릿 두 벌  │     wasm 안에 실려 있다
  └──────────────────────────────┘
     XML 도 결과도 이 안에서만 오간다
```

무료 계정에서 이렇게 하면:

| | |
|---|---|
| 요청당 CPU 한도 (10 ms) | 해당 없음 — Worker 스크립트가 없다 |
| 하루 요청 한도 (10만) | 쓰지 않음 — 정적 자산 요청은 무료·무제한 |
| Worker 스크립트 크기 (3 MiB) | 해당 없음 |
| 배포 도구 | wrangler 만 |
| 업로드한 XML | 브라우저 밖으로 나가지 않는다 |

첫 방문에 변환 엔진 약 1.06 MiB 를 받고(gzip 전송), 그 뒤로는 재검증만 한다.
엔진 기동은 5 ms 안팎이고, 변환 자체는 대표 입력 기준 0.19 초다
(실측 [measurements/runtime.md](../doc/measurements/runtime.md)).

### 결과가 같다는 것은 어떻게 아는가

브라우저가 돌리는 파이썬은 서버가 돌리던 것과 **같은 파일** 이다. 사본을 따로
두지 않고 `web/scripts/build_browser_engine.py` 가 `web/src` 에서 그대로 zip
으로 묶는다. 부르는 함수도 `api.convert_response` 로 같다.

그 위에 테스트 세 겹을 둔다.

| 테스트 | 무엇을 지키는가 |
|---|---|
| `web/tests/test_browser_engine.py` | 담기는 코드·양식이 저장소 원본과 바이트가 같다 |
| `quotation/web/tests/test_browser_parity.py` | 브라우저(WASM)가 만든 견적서가 데스크톱(확장 모듈) 산출물과 같다 — 셀 단위(값·수식·서식·글꼴·채우기·테두리·정렬·병합·인쇄영역·행높이), 부품 목록, 첫 페이지 도형 |
| `web/tests/test_browser_e2e.py` | 운영과 같은 CSP 아래 실제 Chromium 으로 내려받은 파일이 CPython 산출물과 같다 |

정규화하는 것은 딱 둘이고 둘 다 견적서 내용이 아니다 — 파일을 만든 **시각**
(`docProps/core.xml` 의 `dcterms:modified`), 그리고 `<mergeCell>` 의 나열
**순서**(병합 집합은 같고, 다르면 테스트가 잡는다). 근거는
`web/tests/xlsx_parity.py` 에 적어 두었다.

### EUC-KR 문서

2005년 형식 문서는 EUC-KR 이다. 코어가 선언된 인코딩을 직접 읽는다 —
`encoding_rs` 가 EUC-KR 을 기본으로 안다. 예전에는 Pyodide 의 libxml2 에
iconv 가 없어 파이썬 코덱으로 UTF-8 로 옮겨 읽는 우회책이 있었다
([사고 0002](../doc/incidents/0002-pyodide-lxml-euckr.md)). 그 우회책은
엔진을 Rust 로 바꾸면서 사라졌고, 사고 기록은 남긴다.

## 폴더

```text
web/                       셸 — 여기에는 도구의 논리가 없다
  index.html               탭과 빈 칸만 있다
  src/main.ts              탭을 세우고 도구를 처음 열릴 때 불러온다
  src/tabs.ts              탭 전환 (#해시·키보드)
  src/styles.css           공통 색과 틀
  public/engine/           변환 엔진 자산 (생성물, 추적하지 않음)
  scripts/
    cf_build.sh            Cloudflare 빌드 단계
    cf_deploy.sh           Cloudflare 배포 단계
    ensure_wasm_toolchain.sh  Rust·wasm-pack 갖추기 (빌드 이미지에 없다)
  wrangler.jsonc           정적 자산 배포 (무료 계정)
```

도구는 최상위 기능 폴더에 있습니다. 셸은 별명으로만 부릅니다
(`vite.config.ts` 의 `@quotation`, `@converters`).

```text
quotation/web/             견적서 탭
  src/panel.ts             화면 배선, src/panel.html 뼈대, src/quotation.css
  src/engine.js            wasm 을 세우고 convert 를 부른다
  src/convert.worker.ts    변환 Web Worker
  scripts/build_browser_engine.py  엔진 포장 (wasm-pack → web/public/engine)
  scripts/browser_convert.mjs      엔진을 Node 로 돌리는 동일성 검증 구동기
  scripts/verify_template.py       템플릿 검증
  e2e/browser_smoke.mjs    실제 브라우저 스모크
  tests/                   브라우저↔데스크톱 동일성, 실제 Chromium E2E

converters/web/src/        문서 변환기 탭 (panel.ts · converters.css · 변환기들)
  hwpx.ts  zip.ts          HWPX 읽기 (zip 은 제 안에 둔다)
  pdf.ts  pdf-panel.ts     브라우저 PDF 편집기
```

변환 규칙은 여기 없다. `rust/core` 에 한 벌 있고, 브라우저는 그것을 wasm 으로,
데스크톱은 확장 모듈로 부른다. 검증·헤더·오류 문구도 마찬가지다
(`rust/webapi`).

## 개발

```bash
# 1) 변환 코어 확장 (파이썬 테스트가 이것을 부른다)
maturin build --release -m ../quotation/rust/python/Cargo.toml --out ../target/wheels
pip install --force-reinstall ../target/wheels/quotation_rust-*.whl

# 2) 브라우저 변환 엔진 (Rust→WASM, 약 1 MiB)
#    전송 크기가 결정 0008 의 한도를 넘으면 여기서 멈춘다
cargo install wasm-pack                  # 리눅스면 bash web/scripts/ensure_wasm_toolchain.sh
python ../quotation/web/scripts/build_browser_engine.py

# 3) 화면
npm ci && npm run dev                    # 개발 서버 (web/ 에서)
npm run build                            # dist/

# 4) 동일성 검증 — 여기가 붉으면 내보내지 않는다
#    브라우저(WASM) 산출물을 데스크톱(확장) 산출물과 셀 단위로 대조하고,
#    실제 Chromium 으로 받아 본 파일까지 같은 기준으로 본다
pytest ../quotation/web/tests -q
```

## 배포

배포 대상이 둘이고, 무료 계정에서 쓰는 것은 첫째 하나뿐이다.

| 대상 | 명령 | 올라가는 것 |
|---|---|---|
| 기본 (무료) | `bash web/scripts/cf_deploy.sh deploy` | 정적 자산만. Worker 스크립트 없음 |
| 스테이징 (무료) | `... cf_deploy.sh deploy --env staging` | 위와 같음 |

`cf_deploy.sh` 가 대상을 보고 도구를 고른다. 무료 대상이면 `wrangler` 로 끝나고,

자격 증명 없이 설정만 검사하려면:

```bash
cd web
npx wrangler deploy --dry-run --env=""       # 무료 기본 — Worker 스크립트가 없어야 한다
```

CI 의 `bundle` 잡이 매 푸시마다 둘 다 돌린다.

## 배포하는 것은 Workers Builds 하나다

배포는 **Cloudflare Workers Builds** 가 한다 — 대시보드에 연결한 저장소를 보고
짓고 올린다. GitHub Actions 는 **검사만** 한다. 배포 잡을 두면 같은 Worker 에 두 번
배포되며 서로를 덮어쓰므로 두지 않았다
([결정 0017](../doc/decisions/0017-cloudflare-builds-owns-deploys.md)).

그래서 테스트는 배포를 **막지 못한다.** 막고 싶으면 `main` 브랜치 보호에서 CI 의
검사 잡들을 필수 상태 검사로 걸어 통과한 커밋만 `main` 에 들어오게 한다. 그 설정이
없으면 푸시한 것이 그대로 프로덕션으로 나간다.

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
(서버 변환 환경은 없앴다 — [결정 0010](../doc/decisions/0010-retire-the-server-conversion-path.md).) 인자는
그대로 배포 도구까지 전달된다.

프리뷰 빌드를 아예 돌리고 싶지 않으면 Settings → Build → Branch control 에서
프로덕션 브랜치(`main`)만 남긴다. 작업 브랜치 푸시마다 빌드가 도는 것을 막는다.

### 빌드 이미지에 Rust 가 없다

Workers Builds 이미지가 주는 것은 Node·Python·Go·Ruby 다. 변환 엔진은
Rust→WASM 이라 `cargo` 도 `wasm-pack` 도 거기 없다. 그대로 두면 빌드가 2/3 에서
멈춘다.

```
=== 2/3 브라우저 변환 엔진 생성
=== wasm-pack build (rust/wasm)
wasm-pack 이 없습니다. cargo install wasm-pack 으로 설치하십시오.
Failed: error occurred while running build command
```

그래서 `cf_build.sh` 는 엔진을 짓기 전에 `scripts/ensure_wasm_toolchain.sh` 로
**없는 것만** 채운다 — rustup(minimal) 과 `wasm32-unknown-unknown`, 그리고
공식 릴리스의 `wasm-pack` 정적 이진(내려받아 sha256 으로 대조한다). 이미 갖춰진
곳(개발 기계, GitHub Actions)에서는 판본만 찍고 지나간다.

판본을 바꾸려면 Settings → Build → Variables 에 넣는다.

| 변수 | 기본값 | 뜻 |
|---|---|---|
| `RUST_VERSION` | `stable` | rustup 이 세울 툴체인 |
| `WASM_PACK_VERSION` | `0.15.0` | 내려받을 wasm-pack. sha256 이 스크립트에 박혀 있으니 함께 고친다 |

Cloudflare 빌드 캐시가 담는 것은 패키지 관리자 폴더와 프레임워크 산출물뿐이다
(`~/.cargo` 도 `target/` 도 아니다). 매 빌드가 Rust 를 처음부터 짓는다는 뜻이고,
빌드 한도는 20 분이다. 엔진이 그 안에 들어오지 않기 시작하면 그때는 CF 에서
짓는 대신 GitHub Actions 가 지어 배포하도록 옮긴다(아래 절).

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
- 배포는 정적 자산뿐이라 `wrangler deploy` 하나로 끝난다.
  wrangler 만 쓰면 의존성 vendoring 이 빠진다.
- 빌드·배포 순서는 `web/scripts/cf_build.sh`, `web/scripts/cf_deploy.sh` 가 갖고
  있다. 대시보드에 긴 명령을 넣지 않는 이유는 설정과 코드가 어긋나지 않게 하기
  위함이다.
- **설정을 바꾼 뒤에는 새 빌드를 돌려야 한다.** `Retry build` 는 이전 빌드를
  그때의 설정으로 재실행하므로 바뀐 값이 반영되지 않는다.
- `Failed: The build token ... has been deleted or rolled` 는 API 토큰이 아니라
  **Workers Builds 전용 빌드 토큰** 문제다. Settings → Build → Build token 에서
  갱신하고 재시도한다.

## 손으로 배포할 때 쓰는 API 토큰

평소 배포는 Workers Builds 가 하지만, 손으로 올릴 때는 `wrangler` 가 토큰을 찾는다.

```bash
export CLOUDFLARE_API_TOKEN="<토큰>"    # 셸에만 둔다. 파일에 적지 않는다
export CLOUDFLARE_ACCOUNT_ID="<계정 ID>"
bash web/scripts/cf_build.sh
bash web/scripts/cf_deploy.sh deploy
```

이 토큰은 대시보드의 **빌드 토큰과 다른 것**이다. 빌드 토큰은 Workers Builds 가
저장소를 짓고 올릴 때 쓰는 것으로 Settings → Build 에서 관리한다.

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

올리기 전에 `npx wrangler whoami` 를 한 번 돌리면 그 토큰이 무엇을 볼 수 있는지
먼저 확인할 수 있습니다.

## 템플릿 운영

템플릿은 저장소에 IBM 용·레노버 x86 용 두 벌을 둔다. 어느 것을 쓸지는 화면이
고르지 않고 XML 내용(`ProductName` 유무)으로 알아낸다
(`quotation.core.modes.detect`). 데스크톱 앱과 웹이 같은 파일을 쓴다.

```text
quotation/resources/견적서_template_IBM.xlsx      ← IBM 문서용 원본
quotation/resources/견적서_template_Lenovo.xlsx   ← 레노버 x86 문서용 원본
   ├─ 데스크톱: 둘 다 EXE 옆으로 복사되어 사용자가 직접 편집
   └─ 웹: sync_core.py 가 둘 다 web/src/template_data.py 로 만들고
          build_browser_engine.py 가 그것을 quotation-core.zip 에 담는다
```

### 데스크톱과 웹의 양식이 달라 보일 때

변환기는 양식을 뒤틀지 않는다. 머리말 도형·로고·테마를 템플릿에서 **바이트
그대로** 옮기고, 머리말 구간의 행높이·열너비·셀 글꼴·정렬도 그대로 둔다
(`C3` 견적일자만 원본 프로그램과 같게 덮어쓴다). 데스크톱 경로(`write`)와 웹
경로(`build_bytes`)는 같은 템플릿을 주면 **같은 바이트**를 낸다.

**먼저 무엇으로 열어 보셨는지 확인하십시오.** 파일이 같아도 보는 프로그램이
다르면 다르게 보인다. 이 양식은 `굴림`·`Tahoma`·`HY헤드라인M`·`Copperplate
Gothic Bold` 를 쓰는데, 그 글꼴이 없는 환경(모바일 뷰어, 웹 기반 표 편집기,
미리보기)은 제멋대로 다른 글꼴로 바꿔 그린다. 글꼴과 정렬이 어긋나 보이는
사례는 대개 여기서 끝난다. 실제로 한 번 그랬다 — 파일은 멀쩡했고 모바일 앱이
바꿔 그린 것이었다. **판단은 Excel 에서 연 결과로만 한다.**

Excel 에서 열어도 다르다면 그때 서로 다른 템플릿을 의심한다. 방향이 둘이라
헷갈리기 쉽다.

| 어긋남 | 왜 | 바로잡는 법 |
|---|---|---|
| **데스크톱이 낡았다** | `paths.template_path(mode)` 는 EXE 옆에 사본이 **없을 때만** 복사한다. 한 번 만들어진 사본은 새 EXE 를 깔아도 갱신되지 않는다. 저장소 양식이 그 뒤에 바뀌었다면 데스크톱만 옛 양식으로 남는다 | EXE 옆 `견적서_template_IBM.xlsx`(또는 `_Lenovo.xlsx`)를 다른 이름으로 옮기고 앱을 다시 실행한다. 현재 양식이 새로 복사된다 |
| **저장소가 낡았다** | 사용자가 EXE 옆 사본을 고쳤는데 아무도 저장소 원본으로 되돌려 놓지 않았다 | 아래 `--adopt` 로 그 파일을 저장소 원본으로 삼는다 |

어느 쪽인지는 해시로 가른다. 두 값을 견주면 끝난다. `--mode` 는 IBM 문서면
`unix`, 레노버 x86 문서면 `integrated` 다.

```bash
python web/scripts/verify_template.py "<EXE 옆>/견적서_template_IBM.xlsx" --mode unix   # 데스크톱 쪽
python web/scripts/verify_template.py quotation/resources/견적서_template_IBM.xlsx --mode unix
```

칸별로 어디가 다른지까지 보려면 골든 비교기를 그대로 쓴다.

```bash
python tools/compare.py quotation/resources/견적서_template_IBM.xlsx "<EXE 옆>/견적서_template_IBM.xlsx"
```

저장소가 낡은 경우, 쓰고 계신 양식을 저장소에 반영하는 절차:

```bash
# 검증에 합격해야만 그 모드의 원본을 덮고, 파생물(Worker 번들·브라우저 엔진)까지 다시 만든다
python web/scripts/verify_template.py "<EXE 옆>/견적서_template_IBM.xlsx" --mode unix --adopt

# 골든 회귀 테스트
python -m pytest -q

# 커밋하면 배포와 함께 반영된다
git add quotation/resources/견적서_template_IBM.xlsx && git commit
```

저장소에서 직접 고칠 때도 같다. 레노버 x86 양식이면 파일 이름과 `--mode` 를
`_Lenovo.xlsx` / `integrated` 로 바꾼다.

```bash
# 1) Excel 에서 quotation/resources/견적서_template_IBM.xlsx 를 고친다
#    (견적번호는 TOTAL!B2, 담당자·회사는 상단 머리말 도형)

# 2) 검증 — 필수 시트, 도형, 공개 fixture 로 실제 변환까지 해 본다
python web/scripts/verify_template.py quotation/resources/견적서_template_IBM.xlsx --mode unix

# 3) 골든 회귀 테스트
python -m pytest -q

# 4) 커밋하면 배포와 함께 반영된다
```

어느 양식으로 만든 견적서인지는 내용 해시로 구분한다. 변환을 한 번 하면
화면 아래에 그때 **실제로 쓴** 템플릿의 `sha256-…` 이 뜬다(IBM/레노버 중
어느 쪽을 썼는지에 따라 값이 갈린다). 배포 시점의 두 판본은
`/py/engine.json` 의 `template.unix.version` / `template.integrated.version`
에 있고, 데스크톱 쪽 파일의 값은
`python web/scripts/verify_template.py <그 파일> --mode <unix|integrated>` 가
찍어 준다. 두 값이 다르면 서로 다른 양식을 쓰고 있는 것이다.

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

| `openpyxl` | 3.1.5 (데스크톱과 동일) |
| 브라우저 엔진 자산 | 1.06 MiB (gzip, wasm 1.05 + 글루 0.003) |
| 엔진 기동 | 약 5 ms |
| 변환 1건 | 대표 입력 약 0.3 초 (CPython 0.1 초의 3배) |

라이브러리 판본이 갈릴 일이 없습니다 — 변환은 Rust 코어 한 벌이 합니다.
브라우저에서 나온 견적서가 CPython 산출물과 같은지는 CI 의 `browser` 잡이
매 푸시마다 대조합니다.

## 저장 정책

무료 계정 배포에서는 **XML 이 서버로 가지 않습니다.** 변환이 브라우저 안에서
끝나므로 올린 XML 도 만들어진 견적서도 네트워크를 타지 않고, 서버에는 남길
것도 없습니다.

이 성질은 견적서 변환의 것입니다. 문서 변환기의 **HWP → PDF 만** 파일을 별도
변환 서버로 보내며, 그 서버는 이 배포에 들어 있지 않고 따로 돕니다 —
전송 전에 동의를 받고 결과는 15분 뒤 지웁니다
([결정 0016](../doc/decisions/0016-a-server-only-for-hwp-to-pdf.md),
[변환기 README](../converters/README.md)).

변환은 브라우저 안에서만 일어나며 업로드한 XML 은 밖으로 나가지 않습니다.
요청을 처리하는 동안만 메모리에 두었다가 응답과 함께 버리고, 로그에는 요청 ID,
결과 코드, 크기 구간, 품목·그룹 수, 처리 시간, 템플릿 버전만 남깁니다(계획서 §13).
