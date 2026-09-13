# PyInstaller 빌드 정의 — 무설치 단일 EXE (64bit)
#   .venv\Scripts\pyinstaller.exe quotation\desktop\QuotationTool.spec --noconfirm
from pathlib import Path

HERE = Path(SPECPATH)          # quotation/desktop/
FEATURE = HERE.parent          # quotation/ — 견적기 한 덩어리
PACKAGE = FEATURE / "python"   # 공용 코어 패키지 quotation/ 의 뿌리
RESOURCES = PACKAGE / "quotation" / "resources"
# IBM 문서용·레노버 x86 문서용 두 템플릿 다 번들에 넣는다
# (quotation.core.resources.TEMPLATE_NAMES 와 같은 값).
TEMPLATES = [RESOURCES / "견적서_template_IBM.xlsx",
            RESOURCES / "견적서_template_Lenovo.xlsx"]

a = Analysis(
    [str(HERE / "launcher.py")],
    # 데스크톱 패키지(quotation_desktop)와 공용 코어(quotation) 를 모두 찾게 한다.
    pathex=[str(HERE), str(PACKAGE)],
    binaries=[],
    # 템플릿을 번들에 넣는다. paths.resource_dir() 가 sys._MEIPASS/resources 를 본다.
    datas=[(str(t), "resources") for t in TEMPLATES],
    # 변환 코어는 Rust 확장이다. quotation.core 가 실행 시점에 import 하므로
    # 정적 분석으로는 잡히지 않는다 — 여기서 직접 알려 준다.
    hiddenimports=["quotation_desktop.ui.main_window", "quotation_rust"],
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
