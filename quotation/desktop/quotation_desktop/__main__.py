"""GUI 진입점."""
from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    """GUI를 열고 첫 번째 파일 인수를 XML 입력란에 채운다."""
    argv = sys.argv[1:] if argv is None else argv

    from .ui.main_window import run
    prefill = argv[0] if argv else None
    return run(prefill)


if __name__ == "__main__":
    sys.exit(main())
