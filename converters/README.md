# 변환기 (PDF ↔ HWP)

문서 변환 탭. HWPX 읽기와 PDF 편집은 브라우저 안에서 처리한다.

```text
converters/
  web/src/
    panel.ts          탭 화면 — mountConverters 하나만 셸에 내준다
    pdf-panel.ts      PDF 파일 추가·쪽 선택·순서·회전·분할·다운로드 화면
    pdf.ts            pdf-lib 기반 PDF 읽기·쪽 복사·저장·범위 검증
    pdf.test.ts       저장한 PDF를 다시 열어 병합·분할·순서·회전 확인
    converters.css    이 기능 전용 스타일
    hwpx.ts           HWPX(OWPML) → 문단·표 → Markdown
    hwpx.test.ts      실제 규격서에서 겪은 것들(ID 잘림·병합 칸 밀림)을 고정
    zip.ts            ZIP 읽기 — HWPX 가 ZIP 이다. zip-slip·압축폭탄 방어 포함
    zip.test.ts
    zip-fixture.ts    테스트용 ZIP 조립기(화면은 부르지 않는다)
  desktop/
    hwp-to-hwpx.ps1   한글 COM 으로 .hwp → .hwpx (Windows + 한글 설치 필요)
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

## 지금 되는 것

| 기능 | 상태 | 보장하는 것 / 못 하는 것 |
|---|---|---|
| PDF 병합·분할·회전·쪽 순서 | **된다** (브라우저 안에서 완결) | 합계 64MB·1,000쪽. 암호화 PDF와 책갈피·양식·전자서명 보존은 지원하지 않는다 |
| HWPX → Markdown | **된다** (브라우저 안에서 완결) | 글의 순서, 표의 칸 구조(colSpan·rowSpan 포함), 글머리표 수를 지킨다. 글꼴·색·쪽 배치는 옮기지 않는다 |
| HWP(5.0) → HWPX | **된다** (Windows + 한글) | `desktop/hwp-to-hwpx.ps1`. 한글이 제 형식을 직접 저장하므로 충실도가 가장 높다 |

`.hwp` 는 ZIP 이 아니라 OLE 복합 문서라 브라우저에서 열지 않는다. 화면이 그
사실과 함께 위 스크립트를 안내한다 — 조용히 실패하지 않는 것이 이 도구의 규칙이다.

## 아직 없는 것

| 기능 | 브라우저만으로 되는가 | 근거 |
|---|---|---|
| PDF 주석·서명 추가 | 된다 | 아직 구현하지 않았다 |
| PDF → HWPX (페이지를 이미지로 심기) | 된다 | 시각은 100% 같고 편집은 안 된다 |
| PDF → HWPX (텍스트 재구성) | 되지만 근사 | 레이아웃 복원은 원리적으로 추정이다 |
| HWP → PDF | **안 된다** | 아래 참조 |

HWP(5.0 바이너리) → PDF 는 브라우저 단독으로 "확실하게" 만들 수 없다. 공개된
파서들은 알파이거나(hwp.js 는 포맷 20% 커버) 렌더러가 없고(hwp-rs, openhwp),
SVG 렌더러가 있는 것은 0.x 이며 글꼴이 없으면 배치가 달라진다(@rhwp/core).
게다가 한글 기본 글꼴인 함초롬체는 웹 재배포 권리가 불분명해서, 대체 글꼴을
쓰면 줄바꿈 위치가 바뀐다.

업계에서 확실하게 도는 경로는 LibreOffice + [H2Orestart](https://github.com/ebandal/H2Orestart)
(GPLv3) 를 얹은 **서버** 하나뿐이다 (`soffice --headless --convert-to pdf`).
그것을 들일지는 아직 정하지 않았다 — 들이는 순간 "파일이 브라우저 밖으로 나가지
않는다"는 이 도구의 성질이 그 기능에서만 깨지므로, 화면에 그것까지 적어야 한다.

## 규칙

여기 무엇을 만들든 다음을 지킨다.

- 다른 기능(`quotation/`)을 **부르지 않는다.** 반대도 마찬가지다.
- 셸(`web/`)이 `@converters` 별명으로 진입점 하나(`panel.ts` 의 `mountConverters`)만
  부른다. 화면 뼈대·스타일·논리는 이 폴더가 갖는다.
- **기능 바깥에 공유 코드를 두지 않는다.** 다른 기능이 쓸 법한 것이라도 밖으로
  빼지 않고 여기 둔다. 공유는 이 폴더 안에서만 한다 — 밖에 둔 공유부는 거기
  생긴 문제 하나를 여러 기능의 장애로 번지게 한다 (결정 0012).
- 그 탭을 처음 열 때만 코드를 받아 온다. PDF 라이브러리는 무거워서 견적서만
  쓰는 사람이 내려받을 이유가 없다.
- **무엇을 보장하고 무엇을 보장하지 못하는지 화면에 적는다.** 변환 품질은
  입력에 따라 달라지므로, 그것을 숨기면 신뢰를 잃는다.

## 고칠 때

표 한 줄이 조용히 빠지는 것이 이 도구에서 가장 나쁜 실패다. 파서를 고쳤으면
반드시 돌린다.

```bash
npm --prefix web test        # ../converters/web/src/*.test.ts 까지 함께 돈다
npm --prefix web run typecheck
```

## 데스크톱 스크립트

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File converters/desktop/hwp-to-hwpx.ps1 입력.hwp 출력.hwpx
```

한글이 설치된 Windows 에서만 돈다. 한글 COM(`HWPFrame.HwpObject`)을 띄워 열고
HWPX 로 저장한 뒤 반드시 종료한다 — 종료를 빼먹으면 한글 프로세스가 남아 다음
실행이 조용히 멈춘다. 자동화로 여러 건을 돌릴 때는 건마다 시간 제한을 두고,
실패한 건은 건너뛰되 프로세스를 먼저 정리한다.
