# PyInstaller 빌드 정의 — 무설치 단일 EXE (64bit)
#   .venv\Scripts\pyinstaller.exe QuotationTool.spec --noconfirm
from pathlib import Path

ROOT = Path(SPECPATH)

a = Analysis(
    [str(ROOT / "launcher.py")],
    pathex=[str(ROOT)],
    binaries=[],
    # 템플릿을 번들에 넣는다. paths.resource_dir() 가 sys._MEIPASS/resources 를 본다.
    datas=[(str(ROOT / "quotation" / "resources"), "resources")],
    hiddenimports=["quotation.ui.main_window"],
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

# 일괄 변환용. 콘솔 EXE 라야 호출 측이 종료를 기다리고 종료 코드를 받는다.
# windowed 빌드는 PowerShell/cmd 가 기다리지 않아 자동화에 쓸 수 없다.
exe_cli = EXE(pyz, a.scripts, a.binaries, a.datas, [],
              name="QuotationTool-cli", console=True, **COMMON)
