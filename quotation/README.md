# 견적기

eConfig Export XML 을 견적서 Excel 화일로 바꾸는 기능. **이 기능에 딸린 것은 전부
이 폴더 안에 있다** — 변환 규칙, 파이썬 얼굴, 데스크톱 앱, 웹 화면, 테스트까지.

```text
quotation/
  rust/                 변환 규칙 — 여기 한 벌뿐이다
    core/               XML 읽기부터 견적서 작성까지
    webapi/             요청 검증·응답 헤더·오류 문구
    wasm/               브라우저 진입점 (wasm-bindgen)
    python/             데스크톱·CI 용 확장 모듈 (PyO3, quotation_rust)
    tools/ roundtrip/   개발용 실행 파일, 템플릿 도형 보존 확인
  python/quotation/     얇은 파이썬 얼굴 (import 경로는 quotation.core)
    core/               convert·modes·xml_reader·resources
    resources/          기준 템플릿 — .xlsx 두 벌이 유일한 원본
  desktop/              Windows 단일 EXE (Tkinter + PyInstaller)
  web/                  견적서 탭 (화면·엔진 포장·동일성 검증)
                        package.json 은 실제 브라우저로 받아 보는 도구(playwright)
                        하나만 갖는다. 화면 빌드는 셸이 한다
  tests/                공개 API 회귀 + 익명화 fixture
  tools/                이 기능의 개발 도구 — 골든 비교(compare.py), 내용
                        비교(xlsx_content.py), 기동 실측, .xls 변환
```

## 다른 기능과의 경계

- 다른 기능(`converters/`)을 **부르지 않는다.** 반대도 마찬가지다.
- 화면은 셸(`web/`)이 내주는 빈 칸 하나에 들어간다. 셸은 `@quotation` 별명으로
  `web/src/panel.ts` 만 부르며, 그 안의 구조는 이 폴더가 알아서 한다.
- 화면 뼈대(`web/src/panel.html`)와 스타일(`web/src/quotation.css`)도 여기 있다.
  견적서 화면을 고칠 때 다른 기능의 파일을 건드릴 일이 없다.
- **기능 바깥에 공유 코드를 두지 않는다.** 다른 기능이 쓸 법한 것이라도 밖으로
  빼지 않고 여기 둔다. 공유는 이 폴더 안에서만 한다 — 밖에 둔 공유부는 거기
  생긴 문제 하나를 여러 기능의 장애로 번지게 한다 (결정 0012).

## 무엇이 어디에 있나

| 하고 싶은 일 | 갈 곳 |
|---|---|
| 변환 규칙을 고친다 | `rust/core/` — 데스크톱과 브라우저가 같은 코어를 부른다 |
| 데스크톱 앱을 고친다 | [`desktop/README.md`](desktop/README.md) |
| 웹 화면을 고친다 | `web/src/panel.ts` |
| 엔진 자산을 다시 만든다 | `python web/scripts/build_browser_engine.py` (저장소 루트에서) |
| 두 경로가 같은지 본다 | `pytest quotation/web/tests -q` |
| 실제 브라우저로 받아 본다 | `npm --prefix quotation/web install` 뒤 위와 같음 |

변환 규칙이 한 벌이라는 것은 테스트가 지킨다. `tests/test_bytes_api.py` 가
경로 입력(데스크톱)과 바이트 입력(웹)을 대조하고,
`web/tests/test_browser_parity.py` 가 브라우저(WASM) 산출물을 데스크톱(확장
모듈) 산출물과 셀 단위로 대조한다.
