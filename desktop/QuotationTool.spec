# PyInstaller 빌드 정의 — 무설치 단일 EXE (64bit)
#   .venv\Scripts\pyinstaller.exe desktop\QuotationTool.spec --noconfirm
from pathlib import Path

HERE = Path(SPECPATH)          # desktop/
REPO = HERE.parent             # 저장소 루트 (공용 코어 quotation/ 이 있다)
TEMPLATE = REPO / "quotation" / "resources" / "견적서_template.xlsx"

a = Analysis(
    [str(HERE / "launcher.py")],
    # 데스크톱 패키지(quotation_desktop)와 공용 코어(quotation) 를 모두 찾게 한다.
    pathex=[str(HERE), str(REPO)],
    binaries=[],
    # 템플릿을 번들에 넣는다. paths.resource_dir() 가 sys._MEIPASS/resources 를 본다.
    datas=[(str(TEMPLATE), "resources")],
    hiddenimports=["quotation_desktop.ui.main_window"],
    hookspath=[],
    runtime_hooks=[],
    # 쓰지 않는 무거운 의존성을 뺀다 (openpyxl 이 선택적으로 끌어올 수 있다)
    excludes=[
        "numpy", "pandas", "matplotlib", "PIL", "PySide6", "PyQt5", "PyQt6",
        "pytest", "setuptools", "pip",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)

COMMON = dict(
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

# GUI 용. 콘솔 창을 띄우지 않는다.
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [],
          name="QuotationTool", console=False, **COMMON)
