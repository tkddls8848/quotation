# 결정 0022 — 데스크톱 앱을 Rust 로 옮긴다

- 날짜: 2026-09-24
- 상태: **적용됨**
- 잇는 결정: [결정 0004](0004-resume-rust-wasm-phase0.md),
  [결정 0007](0007-phase0-gates-passed.md)
- 관련 결정: [결정 0021](0021-converters-moves-out.md)

## 결론

데스크톱 앱을 파이썬(Tkinter + PyInstaller)에서 **Rust + native-windows-gui** 로
옮긴다. 변환 규칙은 이미 Rust 한 벌이었고(결정 0004·0007), 파이썬으로 남아 있던
것은 창과 경로 정책뿐이었다. 그 껍데기를 걷는다.

```text
이전   Tkinter 창 → quotation.core(파이썬) → PyO3 확장 → quotation-core(Rust)
지금   nwg 창     → quotation-core(Rust)
```

지우는 것: `quotation_desktop/` 파이썬 패키지 전부(Tkinter 화면·테마·설정·경로),
`launcher.py`, `QuotationTool.spec`, `requirements.txt`, Tkinter 위젯을 찌르던
테스트 두 벌, PyO3 번들 탐침(`tools/pyo3_bundle_probe.py`), 그리고 `pytest.ini`·
`conftest.py` 의 데스크톱 항목.

## 무엇이 좋아지나

| | 이전 | 지금 |
|---|---|---|
| EXE | 12 MiB (CPython 런타임 포함) | **4.07 MB** (MSVC) · 3.49 MB (GNU) |
| 빌드 | maturin 휠 → pip 설치 → PyInstaller | `cargo build --release` |
| 경계 | 파이썬 ↔ PyO3 ↔ Rust | Rust 하나 |
| XML 파싱 | 모드 판별과 변환에서 **두 번** | 한 번 |

PyO3 확장을 PyInstaller 번들에 넣는 일은 이 저장소가 이미 한 번 겪은 자리다
(`hiddenimports`, 번들 탐침). 그 경계가 통째로 없어진다.

## 화면을 다시 짰다

옮기는 김에 화면도 손봤다. 기준으로 삼은 것은 **2005년 원본**
(`pConvertXMLtoExcel`)이다. 그 화면의 골격은 이랬다.

```text
변환할 XML화일 이름                         [열기(O)]
오른쪽의 [열기] 버튼을 눌러서 eConfig 프로그램에서 Export된 XML화일을 선택합니다.
금액 표시 · 일반견적서 / 삼성그룹B2B견적서 · 할인율(%)
견적서 하단에 표시될 Description (최대 4줄)
                                    [변환(C)]  [종료(X)]
```

**한 줄 안내 → 파일 한 칸 → 주 단추**라는 순서를 가져오고, 그 사이에 쌓여 있던
것을 걷었다. 지금은 없는 것(할인율·Description·양식 선택)은 되살리지 않는다 —
양식은 문서를 보고 가리고, 나머지는 템플릿에서 고친다.

걷어낸 것: 본문의 큰 제목과 부제(창틀이 이미 이름을 말한다), "견적서는 XML 과
같은 폴더에 저장됩니다"(안내 한 줄로 합쳤다), 템플릿 두 줄의 긴 경로(작은 단추
둘로 줄이고 경로는 풍선말이 말한다), "Enter 로도 바로 변환합니다"(변환 단추의
풍선말로 옮겼다). 컨트롤이 열다섯에서 열로, 창이 700×474 에서 **566×321** 로
줄었다.

그 밖에 달라진 것 셋.

- **어두운 테마를 직접 칠하지 않는다.** Tkinter 판은 색을 손으로 칠했지만
  native-windows-gui 는 시스템 테마를 그대로 쓴다. 지금은 밝은 창이다.
- **상태를 알리던 작은 색 점이 없다.** 대신 진행 막대 자체가 색으로 말한다 —
  Windows 가 정상·실패 색을 그려 준다(`ProgressBarState`).
- **창 크기를 고정했다.** 늘어날 칸이 없는 화면이다.

동작은 그대로다. 파일 고르기, 완료 후 열기 체크박스, 템플릿 두 벌 바로 열기,
진행률 5·35·45·100, Enter 로 변환, 덮어쓰기 확인, 실패 알림창, 완료 시 알림창
없이 바로 열기, EXE 에 XML 을 끌어다 놓으면 채워지는 입력란. `config.json` 의 칸
이름도 그대로 두어 쓰던 설정을 그대로 읽는다.

## 시험이 달라지는 방식

Tkinter 판의 시험은 위젯을 직접 찔렀다(223줄). Rust GUI 에서는 그 방법이 없다.
대신 **틀리면 아픈 것을 창에서 떼어냈다** — 저장 위치 정책, 덮어쓰기 판단, 사람이
읽을 오류 문구는 `convert.rs` 의 순수 함수이고 `cargo test` 가 덮는다. 창 자체는
`tools/acceptance.ps1` 의 인수 검사(뜨는가, 템플릿을 만드는가)가 본다.

창 자체도 한 번은 실제로 눌러 봤다. EXE 를 XML 인수로 띄우고(끌어다 놓기와 같은
길) Enter 를 보내니 옆에 `.xlsx` 가 떨어졌다. 풍선말이 "Enter 로도 됩니다"라고
말하므로 그 말이 사실인지 확인해 둔다.

통합 시험 하나가 **공개 fixture 를 끝까지 변환한다** — 진짜 `.xlsx` 가 나오는지,
XML 과 같은 폴더에 같은 이름으로 떨어지는지, 진행률이 5·35·45·100 순서로 오는지.

이식 중에 그 시험이 실제로 한 건을 잡았다. `output_name_for(".xml")` 을 파이썬과
다르게 짐작했는데, 파이썬(`Path(".xml").stem`)은 `.xml` 을 이름으로 본다. 두 판이
다른 파일을 만들지 않도록 그 동작을 시험으로 못박았다.

## 무엇을 잃는가

- **어두운 테마.** 필요하면 다시 칠해야 하는데, Win32 공통 컨트롤에서는 라벨까지
  어둡게 하려면 직접 그려야 한다. 그 값이 들 때 다시 본다.
- **파이썬으로 화면을 손보던 손쉬움.** 대신 화면 아닌 부분은 오히려 시험하기
  쉬워졌다.
- 크로스플랫폼 가능성은 잃지 않는다 — 원래 한글 COM 도, `os.startfile` 도
  Windows 전용이었다.

## 빌드 환경 메모

릴리스 EXE 는 CI(windows-latest, MSVC)가 만든다. 로컬에서는 MSVC 없이
**rustup 의 `x86_64-pc-windows-gnu` 툴체인 + MinGW binutils** 로도 빌드·시험이
된다(약 1.5 GB). VS Build Tools 는 5 GB 가 넘고 설치가 중간에 끊기면
`isComplete=False` 로 남아 rustc 가 링커를 아예 찾지 못한다 — 그 경우 GNU 쪽이
훨씬 가볍고 확실하다.
