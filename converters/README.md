# 변환기 (문서·이미지·텍스트)

문서 변환 탭. **고른 파일은 이 컴퓨터를 벗어나지 않는다** — 모든 변환이 브라우저
안에서 끝나고 어디로도 올려 보내지 않는다. HWP(5.0) → PDF 에만 있던 변환 서버는
공개할 수 없어 내렸다 ([결정 0018](../doc/decisions/0018-browser-only-converters.md)).

[구현 계획](IMPLEMENTATION_PLAN.md) · [검증 기록·재현 방법](VALIDATION.md)

```text
converters/
  web/src/
    panel.ts          탭 화면 — 변환 고르기와 HWPX→Markdown. 고른 하나만 아래에 세운다
    pdf-panel.ts      PDF 파일 추가·쪽 선택·순서·회전·분할·다운로드, HWPX 저장
    pdf.ts            pdf-lib 기반 PDF 읽기·쪽 복사·저장·범위 검증
    pdf.test.ts       저장한 PDF 를 다시 열어 병합·분할·순서·회전 확인
    pdf-render.ts     PDF.js 로 쪽을 여닫고 그린다 — 아래 둘이 함께 쓴다
    pdf-hwpx.ts       쪽을 그리거나 글자를 뽑아 HWPX 로. 한도·진행·취소
    pdf-images.ts     쪽을 PNG·JPEG 로. 여러 장이면 ZIP 하나로 묶는다
    pdf-text.ts       글자 좌표 → 읽는 순서·문단·단순 표 (추정이다)
    pdf-text.test.ts  정렬·표 오인·빈 입력을 고정
    hwpx-writer.ts    쪽마다 구역 하나인 HWPX 패키지를 짓는다
    images-pdf.ts     그림 여러 장 → PDF 한 벌. 다시 압축하지 않는다
    images-pdf.test.ts  형식 판별·비율 맞춤·그림 아닌 파일 거절
    images-pdf-panel.ts 이미지 → PDF 화면. PNG·JPEG 밖은 캔버스로 바꾼다
    markdown.ts       Markdown·텍스트 → 문단과 표 (DOM 을 쓰지 않는다)
    markdown.test.ts  표 오인·칸 수 어긋남·제어 문자·텍스트 모드를 고정
    text-hwpx-panel.ts  텍스트·Markdown → HWPX 화면
    encoding.ts       CP949 ↔ UTF-8, BOM, 줄바꿈. 쓰기 표는 디코더를 뒤집어 만든다
    encoding.test.ts  판별·왕복·담을 수 없는 글자에서 멈추는지
    encoding-panel.ts 인코딩 변환 화면 — 판별이 추정이면 그렇게 적는다
    zip-panel.ts      ZIP 묶기·풀기 화면
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

아래 표의 "브라우저" 는 전부 **이 컴퓨터 안**이라는 뜻이다. 파일이 나가는 기능은 없다.

| 기능 | 어디서 | 보장하는 것 / 못 하는 것 |
|---|---|---|
| PDF 병합·분할·회전·쪽 순서 | 브라우저 | 합계 64MB·1,000쪽. 암호화 PDF 와 책갈피·양식·전자서명 보존은 지원하지 않는다 |
| PDF → HWPX (이미지) | 브라우저 | 쪽을 그림으로 심는다. 보이는 대로 나오지만 **글자·표를 고칠 수 없다.** 최대 100쪽·출력 64MB |
| PDF → HWPX (텍스트) | 브라우저 | 문단과 단순 표를 다시 짠다. **배치는 추정이다.** 그림·수식·원본 배치는 옮기지 않는다. 표 추정은 켜야 돈다 |
| PDF → 이미지 | 브라우저 | 보이는 대로 그린다. **글자가 그림이 되어** 검색·복사가 안 된다. 최대 200쪽·출력 64MB. 여러 장이면 ZIP |
| 이미지 → PDF | 브라우저 | PNG·JPEG 를 **다시 압축하지 않아** 화질이 그대로다. 그 밖의 형식은 캔버스를 거치므로 한 번 다시 그려진다. OCR 은 하지 않는다. 합계 64MB·200장 |
| 텍스트·Markdown → HWPX | 브라우저 | 글의 순서, 표의 행·열, 목록의 항목 수를 지킨다. **글꼴·크기·색·굵기는 옮기지 않는다.** 그림도 담지 못한다 — 무엇을 버렸는지 화면에 적는다 |
| HWPX → Markdown | 브라우저 | 글의 순서, 표의 칸 구조(colSpan·rowSpan 포함), 글머리표 수를 지킨다. 글꼴·색·쪽 배치는 옮기지 않는다 |
| 인코딩 변환 (CSV·텍스트) | 브라우저 | CP949 ↔ UTF-8, BOM, 줄바꿈. **BOM 이 없으면 판별은 추정이고 화면이 그렇게 적는다.** CP949 에 없는 글자가 있으면 멈춘다 |
| ZIP 묶기·풀기 | 브라우저 | 윈도우가 만든 ZIP 의 CP949 한글 이름도 읽는다. 합계 64MB·500개. 암호 ZIP 과 분할 압축은 열지 않는다 |
| HWP(5.0) → HWPX | 데스크톱 (한글) | `desktop/hwp-to-hwpx.ps1`. 한글이 제 형식을 직접 저장하므로 충실도가 가장 높다 |

두 HWPX 방식을 왜 둘 다 두는지는 [결정 0015](../doc/decisions/0015-both-pdf-to-hwpx-modes.md).
무엇을 어디까지 재 봤는지는 [검증 기록](VALIDATION.md)에 있다 — **한글에서 열어 본
검증은 아직 남아 있다.**

`.hwp` 는 ZIP 이 아니라 OLE 복합 문서라 브라우저에서 열지 않는다. 머리말과
HWPX → Markdown 화면이 그 사실과 함께 데스크톱 스크립트를 안내한다 — 조용히
실패하지 않는 것이 이 도구의 규칙이다.

## 아직 없는 것

| 기능 | 브라우저만으로 되는가 | 근거 |
|---|---|---|
| HWP(5.0) → PDF | 안 된다 | 공개된 HWP 파서는 포맷의 일부만 읽거나 렌더러가 없다. 서버를 들였다가 공개하지 못해 내렸다 ([결정 0018](../doc/decisions/0018-browser-only-converters.md)) |
| DOCX·PPTX → PDF | 근사로만 | 레이아웃 엔진이 필요하다. HTML 을 거치면 배치가 어긋난다 — 충실도를 보장할 수 없는 변환은 내놓지 않는다 |
| DOCX·XLSX 읽기 (→ Markdown·CSV) | 된다 | 규칙에 걸리지 않는 다음 후보. 새 의존성이 붙고, `quotation/` 의 Pyodide·openpyxl 을 부르는 것은 결정 0012 가 막으므로 따로 정해야 한다 |
| PDF 주석·서명 추가 | 된다 | 아직 구현하지 않았다 |
| PDF 에 한글 글자 넣기 (워터마크·쪽번호) | 된다, 값이 든다 | pdf-lib 이 글꼴을 서브셋해 심을 수 있지만 한글 글꼴 파일을 먼저 내려받아야 한다 (수 MB) |
| 스캔 PDF 의 OCR | 안 된다 | 텍스트 방식은 글자가 있는 PDF 만 받는다. 글자가 없으면 중단·이미지·제외를 고르게 한다 |
| 병합 표·다단의 정확한 재구성 | 되지만 근사 | 좌표에서 되짚는 추정이라 어긋날 수 있다. 확인이 필요한 쪽을 화면에 적는다 |
| UTF-8 → CP949 의 완전 변환 | 안 된다 | CP949 에 없는 글자는 적을 수 없다. 조용히 `?` 로 바꾸지 않고 멈춘 뒤 어떤 글자인지 보여 준다 |

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
- **파일을 브라우저 밖으로 내보내지 않는다.** 한 번 예외를 두었다가 도구 전체의
  약속이 약해졌다 (결정 0016 → 0018). 서버가 있어야 하는 기능은 넣지 않는다.

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
