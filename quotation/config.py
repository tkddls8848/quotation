"""설정 저장 — JSON. 구버전 INI 가 있으면 최초 실행 시 1회 이관한다.

원본은 Win32 GetPrivateProfileStringA/WritePrivateProfileStringA (ANSI) 를 썼다.
한글 경로·사용자명에서 깨지므로 UTF-8 JSON 으로 바꾼다.
"""
from __future__ import annotations

import configparser
import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import paths

log = logging.getLogger(__name__)


@dataclass
class Config:
    last_input_dir: str = ""
    last_output_dir: str = ""
    discount: str = ""
    open_folder_when_done: bool = True
    migrated_from_ini: str = ""
    recent_files: list[str] = field(default_factory=list)

    MAX_RECENT = 8

    def remember(self, input_path: Path, output_path: Path):
        self.last_input_dir = str(input_path.parent)
        self.last_output_dir = str(output_path.parent)
        recent = [str(input_path)]
        recent += [p for p in self.recent_files if p != str(input_path)]
        self.recent_files = recent[: self.MAX_RECENT]


def load() -> Config:
    path = paths.config_path()
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            known = {f for f in Config.__dataclass_fields__}
            return Config(**{k: v for k, v in data.items() if k in known})
        except (OSError, ValueError, TypeError) as exc:
            log.warning("설정을 읽지 못해 기본값을 씁니다: %s", exc)
            return Config()

    cfg = Config()
    _migrate_legacy_ini(cfg)
    save(cfg)
    return cfg


def save(cfg: Config) -> None:
    try:
        paths.config_path().write_text(
            json.dumps(asdict(cfg), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError as exc:
        log.warning("설정을 저장하지 못했습니다: %s", exc)


def _migrate_legacy_ini(cfg: Config) -> None:
    """구버전 '견적서생성기.ini' 를 찾아 값을 옮긴다. 실패해도 조용히 넘어간다."""
    for ini in paths.legacy_ini_candidates():
        if not ini.exists():
            continue
        try:
            parser = configparser.ConfigParser(strict=False, interpolation=None)
            # 구 INI 는 EUC-KR(cp949) 이다
            parser.read(ini, encoding="cp949")
        except (OSError, configparser.Error) as exc:
            log.info("구버전 INI 를 읽지 못했습니다 (%s): %s", ini, exc)
            continue

        for section in parser.sections():
            for key, value in parser.items(section):
                low = key.strip().lower()
                if not value:
                    continue
                if "discount" in low or "할인" in low:
                    cfg.discount = value.strip()
                elif "path" in low or "dir" in low or "경로" in low:
                    if Path(value).is_dir():
                        cfg.last_input_dir = value.strip()

        cfg.migrated_from_ini = str(ini)
        log.info("구버전 설정을 이관했습니다: %s", ini)
        return
