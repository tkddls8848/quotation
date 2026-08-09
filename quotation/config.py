"""최근 입력 폴더와 결과 열기 옵션을 JSON으로 저장한다."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from . import paths


@dataclass
class Config:
    last_input_dir: str = ""
    open_result_when_done: bool = True

    def remember(self, input_path: Path):
        self.last_input_dir = str(input_path.parent)


def load() -> Config:
    path = paths.config_path()
    return Config(**json.loads(path.read_text(encoding="utf-8"))) if path.exists() else Config()


def save(cfg: Config) -> None:
    paths.config_path().write_text(
        json.dumps(asdict(cfg), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
