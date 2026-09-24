# 결정 0021 — 문서 변환기를 제 저장소로 내보낸다

- 날짜: 2026-09-24
- 상태: **적용됨**
- 같은 모양의 앞선 결정: [결정 0014](0014-retire-the-fire-calculator.md)
- 잇는 결정: [결정 0012](0012-one-folder-per-feature.md)
- 따라 나가는 기록: [0015](0015-both-pdf-to-hwpx-modes.md),
  [0016](0016-a-server-only-for-hwp-to-pdf.md),
  [0018](0018-browser-only-converters.md),
  [0019](0019-overwrite-not-inplace-pdf-text.md),
  [0020](0020-office-tools-in-converters.md)

## 결론

`converters/` 를 이 저장소에서 내린다. 변환기는 제 저장소에서 산다. 여기는
**견적서 하나만** 한다.

지우는 것: `converters/` 기능 폴더 전부(문서·스프레드시트 형식 변환, PDF 편집과
글자 고치기, 이미지 변환, HWPX 읽기·짓기, ZIP·인코딩, 사무 도구 16개, 한글 COM
스크립트), 그리고 그 기능을 세우던 배선 —

- `web/index.html` 의 탭 막대와 변환기 칸
- `web/src/main.ts` 의 `@converters/panel` 지연 적재
- `web/src/tabs.ts` **통째로**
- `web/src/styles.css` 의 탭 규칙
- `web/vite.config.ts` 의 `@converters` 별명, PDF 자산 플러그인, xlsx 설정,
  변환기 테스트 경로
- `web/tsconfig.json` 의 `@converters/*` 와 변환기 전용 라이브러리 경로
- `web/src/boundaries.test.ts` 의 `converters` 항목
- `web/package.json` 의 `pdf-lib`·`@pdf-lib/fontkit`·`pdfjs-dist`·`fflate`·
  `qrcode-generator`·`xlsx`·`jsdom`·`playwright` — **견적서 화면은 외부 패키지를
  하나도 쓰지 않는다**
- `web/scripts/fetch_fonts.py` 와 `cf_build.sh` 의 글꼴 단계, `web/public/fonts`,
  `web/public/licenses` — PDF 글자 고치기가 심던 한글 글꼴이다
- CI 의 `문서 변환기 — 실제 브라우저` 잡

## 왜 탭까지 없앴나

도구가 하나면 탭 한 개짜리 막대는 아무것도 고르게 하지 않는다. 누를 곳이 하나인
단추를 남겨 두는 것은 화면에 거짓 선택지를 두는 일이다. 그래서 `tabs.ts` 를
내리고 견적서를 칸에 바로 세웠다.

같은 이유로 **늦춰 받는 것도 그만둔다.** 탭이 있을 때는 "견적서만 쓰는 사람이
변환기 코드를 내려받을 이유가 없다"가 지연 적재의 근거였다. 도구가 하나면 그
도구가 곧 이 화면이므로 나눌 이유가 없다.

전송량이 줄었다 — 화면 묶음이 약 900 KB 에서 **13 KB** 가 됐다. PDF·xlsx 엔진과
pdf.js 자산(cmap·글꼴·wasm)이 통째로 빠졌기 때문이다. 변환 엔진(wasm 약 1 MiB)은
견적서의 것이라 그대로 남는다.

## 무엇을 잃는가

- **한 사이트에서 두 도구를 쓰던 편의.** 견적서를 만들다가 옆 탭에서 PDF 를
  손질하던 길이 없어진다. 변환기 저장소가 제 주소를 갖게 되면 그쪽으로 간다.
- **변환기 결정 기록이 가리키는 코드가 여기 없다.** 0015·0016·0018·0019·0020 의
  `../../converters/...` 링크는 이제 이 저장소에서 닿지 않는다. 기록은 **지우지
  않는다** — 그때 무엇을 왜 정했는지가 기록의 값이고, 새 저장소가 그 판단 위에
  서기 때문이다. 0013 을 0014 뒤에도 남겨 둔 것과 같다.

## 이력은 남는다

`converters/` 의 모든 커밋은 이 저장소 이력에 그대로 있다. 새 저장소로 이력째
옮기려면 지우기 전 판본에서 떼어내면 된다.

```bash
git subtree split --prefix=converters -b converters-only <이 커밋 직전>
```

## 바뀌지 않는 것

- **기능마다 최상위 폴더 하나** (결정 0012). 기능이 하나로 줄었다고 규칙이
  바뀌지는 않는다. 셸(`web/`)도 그대로 둔다 — 그것이 배포 단위이고,
  `wrangler.jsonc`·빌드 스크립트·엔진 자산이 거기 붙어 있다.
- 경계는 여전히 `web/src/boundaries.test.ts` 가 지킨다. 지금은 지킬 기능이
  하나뿐이지만, 셸이 기능 속을 들여다보지 못하게 막는 일은 그대로다.
