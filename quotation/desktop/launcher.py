"""PyInstaller 진입점."""
import sys
from pathlib import Path

# 개발 실행(python desktop/launcher.py)에서도 공용 코어 패키지를 찾게 한다.
# 빌드본에서는 QuotationTool.spec 의 pathex 가 같은 일을 한다.
sys.path[:0] = [str(Path(__file__).resolve().parent),
                str(Path(__file__).resolve().parents[1])]

from quotation_desktop.__main__ import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
