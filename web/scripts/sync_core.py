"""Worker 번들에 들어갈 것을 저장소에서 만들어 낸다.

Worker 는 `main` 이 있는 폴더 아래 모듈만 번들에 담는다. 그래서 배포 직전에
두 가지를 `web/src/` 로 만들어 넣는다. 둘 다 저장소에서 추적하지 않는다.

    quotation/          공용 코어 사본
    template_data.py    견적서 템플릿 (base64, IBM·Lenovo x86 두 벌)

템플릿의 유일한 원본은 `quotation/resources/견적서_template_IBM.xlsx` 와
`..._Lenovo.xlsx` 다(`quotation.core.resources.TEMPLATE_NAMES`). 데스크톱 앱과
웹이 같은 파일을 쓴다. 여기서 파생물을 만들 뿐 사본을 따로 두지 않는다.

    python web/scripts/sync_core.py           생성
    python web/scripts/sync_core.py --check   최신인지만 확인 (CI 용)

심볼릭 링크를 쓰지 않는 이유: 개발이 Windows 에서도 이루어진다.
"""
from __future__ import annotations

import argparse
import base64
import filecmp
import hashlib
import shutil
import sys
import textwrap
from pathlib import Path

WEB = Path(__file__).resolve().parents[1]
ROOT = WEB.parent
SOURCE = ROOT / "quotation"
TARGET = WEB / "src" / "quotation"

sys.path.insert(0, str(ROOT))
from quotation.core.resources import TEMPLATE_NAMES  # noqa: E402

TEMPLATE_SOURCES = {mode: SOURCE / "resources" / name
                   for mode, name in TEMPLATE_NAMES.items()}
TEMPLATE_MODULE = WEB / "src" / "template_data.py"

#: 리소스 폴더는 코어 사본에 넣지 않는다. 템플릿은 template_data.py 로 따로 담는다.
EXCLUDE_DIRS = {"__pycache__", "resources"}


def _wanted() -> list[Path]:
    files = []
    for path in sorted(SOURCE.rglob("*.py")):
        relative = path.relative_to(SOURCE)
        if EXCLUDE_DIRS & set(relative.parts):
            continue
        files.append(relative)
    return files


def _template_entry_text(mode: str, source: Path) -> str:
    """`TEMPLATES` 딕셔너리 한 항목의 본문."""
    raw = source.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    encoded = base64.b64encode(raw).decode("ascii")
    body = "\n".join(f'        "{line}"'
                     for line in textwrap.wrap(encoded, 76))
    return (
        f'    "{mode}": {{\n'
        f'        "name": "{source.name}",\n'
        f'        "sha256": "{digest}",\n'
        f'        "version": "sha256-{digest[:12]}",\n'
        f'        "size": {len(raw)},\n'
        '        "b64": (\n'
        f"{body}\n"
        "        ),\n"
        "    },\n"
    )


def _template_module_text() -> str:
    """템플릿 바이트를 담은 파이썬 모듈 본문. 모드마다 한 항목씩이다."""
    entries = "".join(_template_entry_text(mode, TEMPLATE_SOURCES[mode])
                      for mode in TEMPLATE_NAMES)
    return (
        '"""생성 파일 — 직접 고치지 마십시오.\n\n'
        "web/scripts/sync_core.py 가 quotation/resources/견적서_template_{IBM,Lenovo}.xlsx\n"
        "에서 만듭니다. 템플릿을 바꾸려면 그 .xlsx 를 바꾸고 다시 생성하십시오.\n"
        '"""\n'
        "\n"
        "TEMPLATES = {\n"
        f"{entries}"
        "}\n"
    )


def sync() -> tuple[list[Path], str]:
    if TARGET.exists():
        shutil.rmtree(TARGET)
    copied = []
    for relative in _wanted():
        destination = TARGET / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(SOURCE / relative, destination)
        copied.append(relative)

    text = _template_module_text()
    TEMPLATE_MODULE.write_text(text, encoding="utf-8")
    return copied, text


def check() -> list[str]:
    """생성물과 원본이 어긋난 항목. 비어 있으면 최신이다."""
    stale: list[str] = []
    for relative in _wanted():
        destination = TARGET / relative
        if not destination.exists() or not filecmp.cmp(
                SOURCE / relative, destination, shallow=False):
            stale.append(relative.as_posix())

    if TARGET.exists():
        wanted = set(_wanted())
        for path in TARGET.rglob("*.py"):
            if path.relative_to(TARGET) not in wanted:
                stale.append(path.relative_to(TARGET).as_posix())

    if not TEMPLATE_MODULE.exists():
        stale.append(TEMPLATE_MODULE.name)
    elif TEMPLATE_MODULE.read_text(encoding="utf-8") != _template_module_text():
        stale.append(TEMPLATE_MODULE.name)
    return stale


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="생성만 확인하고 바꾸지 않는다")
    args = parser.parse_args()

    if args.check:
        stale = check()
        if stale:
            print("생성물이 최신이 아닙니다. python web/scripts/sync_core.py 를 실행하십시오.")
            for name in stale:
                print(f"  - {name}")
            return 1
        print(f"생성물 최신 (코어 {len(_wanted())}개 모듈 + 템플릿)")
        return 0

    copied, _ = sync()
    total = sum(source.stat().st_size for source in TEMPLATE_SOURCES.values())
    names = ", ".join(source.name for source in TEMPLATE_SOURCES.values())
    print(f"{SOURCE} -> {TARGET} : {len(copied)}개 모듈 복사")
    print(f"{names} -> {TEMPLATE_MODULE.name} : {total:,} bytes 내장")
    return 0


if __name__ == "__main__":
    sys.exit(main())
