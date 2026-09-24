# 데스크톱 앱 (Windows 단일 EXE)

창과 **경로 정책**이 있는 곳입니다. 변환 규칙은 여기에 없고 견적기의 Rust 코어
`quotation/rust/core` 에 있습니다 — 브라우저가 wasm 으로 부르는 그 코어를 여기서는
곧바로 부릅니다.

```text
quotation/desktop/
  Cargo.toml            quotation-core 를 직접 쓴다. 파이썬도 PyO3 다리도 없다
  src/main.rs           진입점. EXE 에 XML 을 끌어다 놓으면 입력란에 채운다
  src/ui.rs             창 (native-windows-gui)
  src/convert.rs        변환 순서·저장 경로 정책·진행률   ← 판단은 여기 있다
  src/paths.rs          EXE 옆 템플릿 사본, %LOCALAPPDATA% 자리
  src/config.rs         config.json (칸 이름은 파이썬 판 그대로다)
  tests/conversion.rs   진짜 XML 한 건을 끝까지 변환해 본다
  tools/acceptance.ps1  빌드 산출물 인수 검사
  dist/                 배포본 (EXE). 폴더만 추적하고 내용물은 추적하지 않는다
```

판단을 창에서 떼어 둔 이유가 있습니다. 창은 시험하기 어렵고, 틀리면 아픈 것은
**어디에 저장하는가**와 **무엇을 사람에게 말하는가**입니다. 그 둘은 `convert.rs`
안의 순수 함수라 `cargo test` 가 그대로 덮습니다.

## 실행과 시험

```powershell
cargo run -p quotation-desktop        # 개발 실행
cargo test -p quotation-desktop       # 판단 + 실제 변환 한 건
```

## 빌드

```powershell
cargo build --release -p quotation-desktop
Copy-Item target\release\QuotationTool.exe quotation\desktop\dist\
.\quotation\desktop\tools\acceptance.ps1
```

`QuotationTool.exe` 하나만 배포하면 됩니다. 기준 템플릿 두 개는 **EXE 안에**
들어 있고(`include_bytes!`), 처음 실행할 때 EXE 옆에 사본을 만들어 이후로는 그
파일을 씁니다. IBM 문서인지 레노버 x86 문서인지는 XML 내용으로 알아내며
(`quotation_core::modes`), 그에 맞는 사본이 자동으로 골라집니다. 원본은
`quotation/python/quotation/resources/견적서_template_{IBM,Lenovo}.xlsx` 입니다.

## 템플릿과 설정 위치

| 위치 | 내용 |
|---|---|
| EXE 옆 `견적서_template_IBM.xlsx` | 자동 생성되는 IBM 문서용 편집 템플릿 |
| EXE 옆 `견적서_template_Lenovo.xlsx` | 자동 생성되는 레노버 x86 문서용 편집 템플릿 |
| `%LOCALAPPDATA%\QuotationTool\config.json` | 최근 XML 폴더와 결과 자동 열기 설정 |

설정 파일의 칸 이름(`last_input_dir`, `open_result_when_done`)은 파이썬 판과
같습니다. 쓰던 사람의 설정을 그대로 읽기 위해서입니다.

개발 실행에서는 "EXE 옆"이 `target\debug` 입니다. 그 사본은 추적하지 않습니다.

## 웹 앱과의 관계

같은 코어를 데스크톱은 네이티브로, 브라우저는 wasm 으로 부릅니다. 두 경로가 같은
견적서를 만드는지는 `quotation/web/tests/test_browser_parity.py` 가 셀 단위로
대조합니다.
