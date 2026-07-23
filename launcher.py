"""PyInstaller 진입 스크립트.

`quotation/__main__.py` 를 직접 진입점으로 주면 패키지 컨텍스트 없이
`__main__` 으로 실행되어 상대 임포트가 깨진다. 절대 임포트로 감싼다.
"""
import sys

from quotation.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
