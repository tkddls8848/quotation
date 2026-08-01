"""GUI 진입점."""
from __future__ import annotations

import sys

from . import logging_setup


def main(argv: list[str] | None = None) -> int:
    """GUI를 열고 첫 번째 파일 인수를 XML 입력란에 채운다."""
    argv = sys.argv[1:] if argv is None else argv
    logging_setup.setup()

    from .ui.main_window import run
    prefill = next((a for a in argv if not a.startswith("-")), None)
    return run(prefill)


if __name__ == "__main__":
    sys.exit(main())
