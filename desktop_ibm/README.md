# 데스크톱 앱 (Windows 단일 EXE)

Tkinter 화면과 PyInstaller 빌드 정의가 있는 곳입니다. 변환 규칙은 여기에 없고
저장소 루트의 공용 코어 `quotation/core` 에 있습니다.

```text
desktop_ibm/
  quotation_desktop/
    __main__.py         GUI 진입점 (python -m quotation_desktop)
    ui/main_window.py   메인 화면
    config.py           최근 폴더·결과 열기 설정 (%LOCALAPPDATA%)
    paths.py            EXE·템플릿·설정 경로
  launcher.py           PyInstaller 진입점
  QuotationTool.spec    단일 EXE 빌드 정의
  requirements.txt      코어 의존성 + PyInstaller
  tools/acceptance.ps1  빌드 산출물 인수 테스트
  tests/                데스크톱 전용 테스트
  dist/                 배포본 (EXE). 폴더만 추적하고 내용물은 추적하지 않는다
```

## 실행

```powershell
# 저장소 루트에서
.\.venv\Scripts\python.exe -m pip install -r desktop_ibm\requirements.txt
.\.venv\Scripts\python.exe desktop_ibm\launcher.py            # 개발 실행
.\.venv\Scripts\python.exe -m pytest desktop_ibm\tests -q     # 데스크톱 테스트
```

`launcher.py` 는 저장소 루트와 `desktop_ibm/` 을 `sys.path` 에 얹으므로 별도 설치
없이 그대로 실행됩니다.

## 빌드

```powershell
.\.venv\Scripts\python.exe -m PyInstaller desktop_ibm\QuotationTool.spec --noconfirm --clean `
    --distpath desktop_ibm\dist --workpath desktop_ibm\build
.\desktop_ibm\tools\acceptance.ps1
```

산출물은 `desktop_ibm\dist`, PyInstaller 중간물은 `desktop_ibm\build` 에 냅니다. 둘 다
데스크톱 전용이라 저장소 루트를 어지럽히지 않게 여기로 모았습니다. `dist` 폴더
자체는 `.gitkeep` 으로 남기고 내용물은 추적하지 않습니다.

`desktop_ibm\dist\QuotationTool.exe` 하나만 배포하면 됩니다. 처음 실행할 때 EXE 옆에
`견적서_template.xlsx` 를 만들어 놓고, 이후로는 그 파일을 그대로 씁니다. 원본은
`quotation/resources/견적서_template.xlsx` 이며 spec 이 번들에 넣습니다.

## 템플릿과 설정 위치

| 위치 | 내용 |
|---|---|
| EXE 옆 `견적서_template.xlsx` | 자동 생성되는 사용자 편집용 템플릿 |
| `%LOCALAPPDATA%\QuotationTool\config.json` | 최근 XML 폴더와 결과 자동 열기 설정 |

개발 실행에서는 EXE 옆이 `desktop_ibm/` 폴더입니다. 이 사본은 추적하지 않습니다.

## 웹 앱과의 관계

계획서 §11 Phase 6 에 따라 웹 앱 전환 뒤에도 데스크톱 앱을 일정 기간 복구
수단으로 유지합니다. 두 경로가 같은 결과를 내는지는
`tests/test_bytes_api.py` 가 셀 단위로 대조합니다.
