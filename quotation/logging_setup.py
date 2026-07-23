"""로그 설정 — 일자별 파일. 원본은 로그가 없어 장애 원인 추적이 불가능했다."""
from __future__ import annotations

import logging
import logging.handlers
import sys

from . import paths

_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"


def setup(level: int = logging.INFO, *, console: bool = True) -> None:
    root = logging.getLogger()
    if root.handlers:
        return
    root.setLevel(level)

    handler = logging.handlers.TimedRotatingFileHandler(
        paths.log_dir() / "quotation.log",
        when="midnight", backupCount=30, encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter(_FORMAT))
    root.addHandler(handler)

    # PyInstaller --windowed 는 stderr 가 없을 수 있다
    if console and sys.stderr is not None:
        stream = logging.StreamHandler(sys.stderr)
        stream.setFormatter(logging.Formatter(_FORMAT))
        root.addHandler(stream)
