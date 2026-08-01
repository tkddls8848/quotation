"""로그 설정 — 일자별 파일. 원본은 로그가 없어 장애 원인 추적이 불가능했다."""
from __future__ import annotations

import logging
import logging.handlers

from . import paths

_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"


def setup(level: int = logging.INFO) -> None:
    root = logging.getLogger()
    if root.handlers:
        return
    root.setLevel(level)

    try:
        handler = logging.handlers.TimedRotatingFileHandler(
            paths.log_dir() / "quotation.log",
            when="midnight", backupCount=30, encoding="utf-8",
        )
        handler.setFormatter(logging.Formatter(_FORMAT))
        root.addHandler(handler)
    except OSError:
        pass

    if not root.handlers:
        root.addHandler(logging.NullHandler())
