"""공용 코어를 Worker 번들 안으로 복사한다.

Worker 는 `main` 이 있는 폴더 아래 모듈만 번들에 담는다. 공용 코어는 저장소
루트의 `quotation/` 에 있으므로 배포 직전에 `web/src/quotation/` 으로 복사한다.
복사본은 저장소에서 추적하지 않는다(.gitignore).

    python web/scripts/sync_core.py           복사
    python web/scripts/sync_core.py --check   복사본이 최신인지만 확인 (CI 용)

심볼릭 링크를 쓰지 않는 이유: 개발이 Windows 에서도 이루어진다.
"""
from __future__ import annotations

import argparse
import filecmp
import shutil
import sys
from pathlib import Path

WEB = Path(__file__).resolve().parents[1]
ROOT = WEB.parent
SOURCE = ROOT / "quotation"
TARGET = WEB / "src" / "quotation"

#: 템플릿 리소스는 R2 에서 오므로 번들에 넣지 않는다 (§8.1).
EXCLUDE_DIRS = {"__pycache__", "resources"}


def _wanted() -> list[Path]:
    files = []
    for path in sorted(SOURCE.rglob("*.py")):
        relative = path.relative_to(SOURCE)
        if EXCLUDE_DIRS & set(relative.parts):
            continue
        files.append(relative)
    return files


def sync() -> list[Path]:
    if TARGET.exists():
        shutil.rmtree(TARGET)
    copied = []
    for relative in _wanted():
        destination = TARGET / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(SOURCE / relative, destination)
        copied.append(relative)
    return copied


def check() -> list[Path]:
    """복사본과 원본이 다른 파일 목록. 비어 있으면 최신이다."""
    stale = []
    for relative in _wanted():
        destination = TARGET / relative
        if not destination.exists() or not filecmp.cmp(
                SOURCE / relative, destination, shallow=False):
            stale.append(relative)

    if TARGET.exists():
        wanted = set(_wanted())
        for path in TARGET.rglob("*.py"):
            if path.relative_to(TARGET) not in wanted:
                stale.append(path.relative_to(TARGET))
    return stale


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="복사만 확인하고 바꾸지 않는다")
    args = parser.parse_args()

    if args.check:
        stale = check()
        if stale:
            print("코어 복사본이 최신이 아닙니다. python web/scripts/sync_core.py 를 실행하십시오.")
            for relative in stale:
                print(f"  - {relative.as_posix()}")
            return 1
        print(f"코어 복사본 최신 ({len(_wanted())}개 모듈)")
        return 0

    copied = sync()
    print(f"{SOURCE} -> {TARGET} : {len(copied)}개 모듈 복사")
    return 0


if __name__ == "__main__":
    sys.exit(main())
