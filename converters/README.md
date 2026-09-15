# 변환기 (PDF ↔ HWP)

문서 변환 탭. PDF 편집·HWPX 생성·HWPX 읽기는 브라우저 안에서 끝난다.
**HWP(5.0) → PDF 만 파일을 변환 서버로 보낸다** — 그 하나를 브라우저에서 확실하게
할 방법이 없기 때문이다 ([결정 0016](../doc/decisions/0016-a-server-only-for-hwp-to-pdf.md)).

[구현 계획](IMPLEMENTATION_PLAN.md) · [검증 기록·재현 방법](VALIDATION.md)

```text
converters/
  web/src/
    panel.ts          탭 화면 — mountConverters 하나만 셸에 내준다
    pdf-panel.ts      PDF 파일 추가·쪽 선택·순서·회전·분할·다운로드, HWPX 저장
    pdf.ts            pdf-lib 기반 PDF 읽기·쪽 복사·저장·범위 검증
    pdf.test.ts       저장한 PDF 를 다시 열어 병합·분할·순서·회전 확인
    pdf-hwpx.ts       PDF.js 로 쪽을 그리거나 글자를 뽑는다. 한도·진행·취소
    pdf-text.ts       글자 좌표 → 읽는 순서·문단·단순 표 (추정이다)
    pdf-text.test.ts  정렬·표 오인·빈 입력을 고정
    hwpx-writer.ts    쪽마다 구역 하나인 HWPX 패키지를 짓는다
    hwp-pdf-panel.ts  HWP → PDF 화면 — 전송 동의·접수·상태·내려받기·취소
    converters.css    이 기능 전용 스타일
    hwpx.ts           HWPX(OWPML) → 문단·표 → Markdown
    hwpx.test.ts      실제 규격서에서 겪은 것들(ID 잘림·병합 칸 밀림)을 고정
    zip.ts            ZIP 읽기 — HWPX 가 ZIP 이다. zip-slip·압축폭탄 방어 포함
    zip.test.ts
    zip-fixture.ts    테스트용 ZIP 조립기(화면은 부르지 않는다)
    assets/           HWPX 뼈대 파일과 그 출처·라이선스
    hwpx-probe.ts     한 쪽짜리 최소 HWPX 생성기 (probe.html, 개발 검증용)
  web/scripts/
    check-converters.mjs  실제 Chromium 으로 공개 화면을 조작해 산출물을 검사
    check-hwpx.mjs        한 쪽 HWPX 의 패키지 구조·쪽 크기·PNG 픽셀 검사
  server/             HWP → PDF 변환 서버 (이 기능 전용, 따로 돈다)
    app.py            접수·상태·결과·삭제 API. 토큰·한도·보관 기한
    Dockerfile        LibreOffice + H2Orestart 컨테이너
    convert.py        그 컨테이너의 진입점 — 고정 경로, 사용자 인자 없음
    hwptext.py        HWP 본문 글자만 읽는 최소 판독기 (검증 전용)
    smoke.py          실제 변환 + 본문 글자가 살아남았는지 대조
  desktop/
    hwp-to-hwpx.ps1   한글 COM 으로 .hwp → .hwpx (Windows + 한글 설치 필요)
    verify-hwpx.ps1   만든 HWPX 를 한글에서 열어 본다
```

## 어디서 왔나

`hwpx.ts` 와 `zip.ts` 는 **gong-go 저장소의 `converter/`** 에서 옮겨 왔다. 그쪽은
나라장터 공고 첨부(제안요청서·과업내용서)에서 규격표를 뽑으려고 만든 코드이고,
실제 문서 수천 건을 통과했다. 그 저장소는 Cloudflare Worker + R2 로 도는 조회
서비스라 한글 COM 도 HWPX 파서도 쓸 수 없었다 — **쓰는 쪽이 구현을 갖는다**는
같은 규칙(결정 0012)에 따라 이쪽으로 옮기고 저쪽에서는 지웠다.

옮기며 바꾼 것은 둘뿐이다.

- Node 의 `zlib.inflateRawSync` → 브라우저의 `DecompressionStream('deflate-raw')`.
  그래서 `readZip` 과 `hwpxToMarkdown` 이 **비동기**다.
- CommonJS → TypeScript. 규칙·한도·안전 검사는 한 줄도 바꾸지 않았다.

HWPX 를 **쓰는** 쪽(`hwpx-writer.ts`)의 그림 배치 값은 python-hwpx(Apache-2.0)의
말뭉치에서 얻은 OWPML 모양을 따랐다. 출처와 라이선스는 `web/src/assets/` 에 있다.

## 지금 되는 것

| 기능 | 어디서 | 보장하는 것 / 못 하는 것 |
|---|---|---|
| PDF 병합·분할·회전·쪽 순서 | 브라우저 | 합계 64MB·1,000쪽. 암호화 PDF 와 책갈피·양식·전자서명 보존은 지원하지 않는다 |
| PDF → HWPX (이미지) | 브라우저 | 쪽을 그림으로 심는다. 보이는 대로 나오지만 **글자·표를 고칠 수 없다.** 최대 100쪽·출력 64MB |
| PDF → HWPX (텍스트) | 브라우저 | 문단과 단순 표를 다시 짠다. **배치는 추정이다.** 그림·수식·원본 배치는 옮기지 않는다. 표 추정은 켜야 돈다 |
| HWPX → Markdown | 브라우저 | 글의 순서, 표의 칸 구조(colSpan·rowSpan 포함), 글머리표 수를 지킨다. 글꼴·색·쪽 배치는 옮기지 않는다 |
| HWP(5.0) → PDF | **변환 서버** | 공개 문서 36건 중 30건 변환. **그림·글상자 캡션 글자가 빠진다.** 못 여는 문서는 실패로 알린다. 최대 32MB |
| HWP(5.0) → HWPX | 데스크톱 (한글) | `desktop/hwp-to-hwpx.ps1`. 한글이 제 형식을 직접 저장하므로 충실도가 가장 높다 |

두 HWPX 방식을 왜 둘 다 두는지는 [결정 0015](../doc/decisions/0015-both-pdf-to-hwpx-modes.md).
무엇을 어디까지 재 봤는지는 [검증 기록](VALIDATION.md)에 있다 — **한글에서 열어 본
검증은 아직 남아 있다.**

`.hwp` 는 ZIP 이 아니라 OLE 복합 문서라 브라우저에서 열지 않는다. HWPX → Markdown
화면이 그 사실과 함께 위 스크립트를 안내한다 — 조용히 실패하지 않는 것이 이 도구의 규칙이다.

## 아직 없는 것

| 기능 | 브라우저만으로 되는가 | 근거 |
|---|---|---|
| PDF 주석·서명 추가 | 된다 | 아직 구현하지 않았다 |
| 스캔 PDF 의 OCR | 안 된다 | 텍스트 방식은 글자가 있는 PDF 만 받는다. 글자가 없으면 중단·이미지·제외를 고르게 한다 |
| 병합 표·다단의 정확한 재구성 | 되지만 근사 | 좌표에서 되짚는 추정이라 어긋날 수 있다. 확인이 필요한 쪽을 화면에 적는다 |
| HWP → PDF 의 배치 일치 | — | 컨테이너에 함초롬체가 없어 Noto CJK 로 대체된다. 줄바꿈 위치가 달라진다 |

## 규칙

여기 무엇을 만들든 다음을 지킨다.

- 다른 기능(`quotation/`)을 **부르지 않는다.** 반대도 마찬가지다.
- 셸(`web/`)이 `@converters` 별명으로 진입점 하나(`panel.ts` 의 `mountConverters`)만
  부른다. 화면 뼈대·스타일·논리는 이 폴더가 갖는다.
- **기능 바깥에 공유 코드를 두지 않는다.** 다른 기능이 쓸 법한 것이라도 밖으로
  빼지 않고 여기 둔다. 공유는 이 폴더 안에서만 한다 — 밖에 둔 공유부는 거기
  생긴 문제 하나를 여러 기능의 장애로 번지게 한다 (결정 0012).
- 그 탭을 처음 열 때만 코드를 받아 온다. PDF 라이브러리는 무거워서 견적서만
  쓰는 사람이 내려받을 이유가 없다. HWPX 변환기는 그 안에서 또 한 번 미뤄 둔다 —
  단추를 누른 사람만 받는다.
- **무엇을 보장하고 무엇을 보장하지 못하는지 화면에 적는다.** 변환 품질은
  입력에 따라 달라지므로, 그것을 숨기면 신뢰를 잃는다.
- 파일이 브라우저 밖으로 나가는 기능은 **전송 전에 동의를 받는다.** 동의문에
  무엇이 언제까지 서버에 남는지 적는다.

## 고칠 때

표 한 줄이 조용히 빠지는 것이 이 도구에서 가장 나쁜 실패다. 파서나 변환을 고쳤으면
반드시 돌린다.

```bash
npm --prefix web test          # ../converters/web/src/*.test.ts 까지 함께 돈다
npm --prefix web run typecheck
```

화면과 산출물까지 보려면 개발 서버를 띄우고 실제 브라우저로 돌린다.

```bash
npm --prefix web run dev -- --host 127.0.0.1 --port 18574
node converters/web/scripts/check-converters.mjs
```

## 변환 서버

로컬에서만 도는 구성이다. 공개 배포는 하지 않았다.

```powershell
docker build -t quotation-hwp-converter:local converters/server
python -m venv .cache/converter-venv
.cache\converter-venv\Scripts\python.exe -m pip install -r converters/server/requirements.txt
.cache\converter-venv\Scripts\python.exe converters/server/app.py
```

화면은 `localhost`/`127.0.0.1` 에서 열었을 때 `http://127.0.0.1:8788` 을 본다.
다른 주소를 쓰려면 `VITE_HWP_API_URL` 을 준다. 서버에 닿지 못하면 기능을 잠그고
그 사실을 화면에 적는다.

| 환경 변수 | 하는 일 |
|---|---|
| `HWP_BIND`, `HWP_PORT` | 듣는 주소. 루프백이 아니면 `HWP_SERVICE_KEY` 없이는 뜨지 않는다 |
| `HWP_SERVICE_KEY` | 접근키. 주면 화면이 입력란을 띄운다 |
| `HWP_ALLOWED_ORIGINS` | 허용할 출처 목록 |
| `HWP_JOB_ROOT` | 작업 폴더. 기본값은 `.cache/hwp-jobs` |
| `HWP_IMAGE` | 변환 컨테이너 이미지 이름 |

변환은 작업마다 새 컨테이너에서 돈다 — 네트워크 없음, 읽기 전용 루트, 권한 전부
제거, 메모리 1G·CPU 1·프로세스 128·출력 64MB. 원본은 변환이 끝나면 지우고 결과는
15분 뒤 지운다. 서버는 로그를 남기지 않는다.

엔진은 LibreOffice + [H2Orestart](https://github.com/ebandal/H2Orestart)(GPLv3)다.
**필터를 `--infilter` 로 강제하지 말 것** — 탐지 서비스를 거치지 않아 모든 변환이
실패한다. 그 자리에 주석으로 적어 두었다.

검증은 문서를 직접 지정해서 돌린다. 사용자 문서를 자동으로 끌어다 쓰지 않는다.

```powershell
.cache\converter-venv\Scripts\python.exe converters/server/smoke.py <문서.hwp> ...
```

본문 글자가 하나라도 빠지면 실패로 끝난다. 변환 자체를 못 한 문서는 실패로 세되
전체를 붉히지 않는다 — 그것은 사용자에게도 실패로 보이기 때문이다.

## 데스크톱 스크립트

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File converters/desktop/hwp-to-hwpx.ps1 입력.hwp 출력.hwpx
```

한글이 설치된 Windows 에서만 돈다. 한글 COM(`HWPFrame.HwpObject`)을 띄워 열고
HWPX 로 저장한 뒤 반드시 종료한다 — 종료를 빼먹으면 한글 프로세스가 남아 다음
실행이 조용히 멈춘다. 자동화로 여러 건을 돌릴 때는 건마다 시간 제한을 두고,
실패한 건은 건너뛰되 프로세스를 먼저 정리한다.

`verify-hwpx.ps1` 은 만든 HWPX 를 한글에서 열어 보는 검증용이다. HWPX 를 지원하지
않는 한글(8 이하)에서는 재시도하지 않고 검증 환경이 부족하다고 알린다.
