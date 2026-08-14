"""브라우저에서 도는 변환 엔진 자산을 만든다 (결정 decisions/0002).

Cloudflare Workers Free 플랜은 요청당 CPU 10 ms 다. 견적서 한 건을 만드는 데는
가장 작은 입력도 73 ms 가 든다(실측 measurements/runtime.md). 그래서 무료 계정에서는
변환을 브라우저로 옮기고 Cloudflare 는 정적 자산만 내려 준다. 브라우저가 돌리는
파이썬은 Worker 가 돌리던 것과 **같은 파일** 이다. 그래야 결과가 같다.

만드는 것 — 전부 `web/frontend/public/py/` 아래, 저장소에서 추적하지 않는다.

    pyodide.mjs / pyodide.asm.js / pyodide.asm.wasm      Pyodide 런타임
    python_stdlib.zip / pyodide-lock.json
    lxml-*.whl                  Pyodide 배포판의 wasm32 wheel (Worker 와 같은 판본)
    python-deps.zip             openpyxl·et_xmlfile (PyPI 의 순수 파이썬 wheel)
    quotation-core.zip          web/src 의 파이썬 모듈 + web/browser/entry.py
    engine.json                 판본·해시 (화면과 테스트가 읽는다)

    python web/scripts/sync_core.py            # 먼저 (코어·템플릿 생성)
    python web/scripts/build_browser_engine.py

내려받은 것은 `web/.engine-cache/` 에 sha256 으로 검증해 두고 재사용한다.
망을 타지 않고 만들려면 `PYODIDE_DIST_DIR` 에 Pyodide 배포판 폴더를 준다.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path

WEB = Path(__file__).resolve().parents[1]
ROOT = WEB.parent
SRC = WEB / "src"
BROWSER = WEB / "browser"
OUT = WEB / "frontend" / "public" / "py"
CACHE = WEB / ".engine-cache"

#: Pyodide 배포판. Worker 가 쓰는 것과 같은 판본이라야 lxml 판본이 갈리지 않는다.
#: (pywrangler 가 Pyodide 0.28.3 인덱스에서 lxml 6.0.0 을 받는다 — 실측 measurements/runtime.md)
PYODIDE_VERSION = "0.28.3"
PYODIDE_BASE = f"https://cdn.jsdelivr.net/pyodide/v{PYODIDE_VERSION}/full/"

#: Worker 는 이 폴더 안의 모듈만 번들에 담는다. 브라우저 zip 도 같은 것을 담되
#: Workers 런타임(`workers` 모듈)이 있어야 import 되는 worker.py 만 뺀다.
WORKER_ONLY = {"worker.py"}


@dataclass(frozen=True)
class Asset:
    """내려받을 파일 하나. 크기가 아니라 내용 해시로 확인한다."""

    name: str
    url: str
    sha256: str


#: Pyodide 런타임. 해시는 GitHub 릴리스 `pyodide-0.28.3.tar.bz2` 의 값이다.
#: CDN 과 릴리스가 어긋나면(사고든 변조든) 빌드가 여기서 멈춘다.
RUNTIME = tuple(
    Asset(name, PYODIDE_BASE + name, digest) for name, digest in (
        ("pyodide.mjs",
         "635a6da3218fe4e5668da595acfe8b5ce77453d597d602f19a423dd250653441"),
        ("pyodide.asm.js",
         "b22e5831eade9ff10e6fe2c811c68688cd91f10154377b4f80debcf5bafa1e56"),
        ("pyodide.asm.wasm",
         "5effb6a1a6cc4a1a85bec4622701aa797c031e1de923cbbaf2ad47abdc4ab325"),
        ("python_stdlib.zip",
         "71fee17f88a6260ec8c9c7c063533ee59c021fdc88a1ce76247378d3c4a35f4c"),
        ("pyodide-lock.json",
         "f6e6f42f451f42affbbcddb00e8c9a3278dcbf399f57aab9f3f568839a7ff4a6"),
    ))

#: lxml 은 C 확장이라 Pyodide 배포판의 wasm32 wheel 을 그대로 쓴다.
#: 판본은 web/pyproject.toml 의 것과 같아야 한다 (테스트가 확인한다).
LXML = Asset(
    "lxml-6.0.0-cp313-cp313-pyodide_2025_0_wasm32.whl",
    PYODIDE_BASE + "lxml-6.0.0-cp313-cp313-pyodide_2025_0_wasm32.whl",
    "800ea9c7b35a3bb4c027bd74f16bc878aa946825a3f9627c1906f4c0c1c001dd")

#: openpyxl 과 그 의존성은 순수 파이썬이라 PyPI wheel 을 그대로 푼다.
#: micropip 을 쓰지 않으므로 요청 경로에 망 접근이 없다.
PURE_WHEELS = (
    Asset("openpyxl-3.1.5-py2.py3-none-any.whl",
          "https://files.pythonhosted.org/packages/py2.py3/o/openpyxl/"
          "openpyxl-3.1.5-py2.py3-none-any.whl",
          "5282c12b107bffeef825f4617dc029afaf41d0ea60823bbb665ef3079dc79de2"),
    Asset("et_xmlfile-2.0.0-py3-none-any.whl",
          "https://files.pythonhosted.org/packages/py3/e/et_xmlfile/"
          "et_xmlfile-2.0.0-py3-none-any.whl",
          "7a91720bc756843502c3b7504c77b8fe44217c85c537d85037f0f536151b2caa"),
)

#: 브라우저 zip 에서 뺄 것. dist-info 는 있어도 되지만 서명·기록 파일은 쓸모가 없다.
WHEEL_SKIP_SUFFIXES = (".dist-info/RECORD", ".dist-info/WHEEL")

#: 재현 가능한 zip 을 만들기 위한 고정 타임스탬프 (1980-01-01, zip 의 최소값).
ZIP_EPOCH = (1980, 1, 1, 0, 0, 0)


# --- 내려받기 -----------------------------------------------------------------

def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _local_copy(asset: Asset) -> bytes | None:
    """`PYODIDE_DIST_DIR` 이 있으면 거기서 먼저 찾는다 (망 없이 빌드할 때)."""
    import os

    directory = os.environ.get("PYODIDE_DIST_DIR")
    if not directory:
        return None
    candidate = Path(directory) / asset.name
    return candidate.read_bytes() if candidate.is_file() else None


def fetch(asset: Asset) -> bytes:
    """캐시 -> 로컬 배포판 -> 망 순서로 가져오고 sha256 을 확인한다."""
    cached = CACHE / asset.name
    if cached.is_file():
        data = cached.read_bytes()
        if _sha256(data) == asset.sha256:
            return data
        cached.unlink()  # 깨진 캐시는 버리고 다시 받는다

    data = _local_copy(asset)
    if data is None:
        print(f"  내려받는 중: {asset.name}")
        with urllib.request.urlopen(asset.url, timeout=300) as response:
            data = response.read()

    got = _sha256(data)
    if got != asset.sha256:
        raise SystemExit(
            f"{asset.name} 의 sha256 이 다릅니다.\n"
            f"  기대: {asset.sha256}\n  실제: {got}\n"
            f"  출처: {asset.url}")

    CACHE.mkdir(parents=True, exist_ok=True)
    cached.write_bytes(data)
    return data


# --- zip 만들기 ---------------------------------------------------------------

def zip_bytes(members: list[tuple[str, bytes]]) -> bytes:
    """정렬된 이름과 고정 타임스탬프로 담는다. 같은 입력이면 같은 바이트가 된다."""
    from io import BytesIO

    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(members):
            info = zipfile.ZipInfo(name, date_time=ZIP_EPOCH)
            info.external_attr = 0o644 << 16
            archive.writestr(info, data)
    return buffer.getvalue()


def _write_zip(target: Path, members: list[tuple[str, bytes]]) -> bytes:
    raw = zip_bytes(members)
    target.write_bytes(raw)
    return raw


def core_members() -> list[tuple[str, bytes]]:
    """브라우저가 돌릴 파이썬 모듈.

    `web/src` 의 것은 Worker 가 돌리는 것과 **같은 파일** 이다. 사본을 따로
    만들지 않는다. 여기에 브라우저 진입점 하나만 더한다.
    """
    if not (SRC / "template_data.py").is_file():
        raise SystemExit(
            "web/src/template_data.py 가 없습니다. "
            "python web/scripts/sync_core.py 를 먼저 실행하십시오.")
    if not (SRC / "quotation").is_dir():
        raise SystemExit(
            "web/src/quotation/ 이 없습니다. "
            "python web/scripts/sync_core.py 를 먼저 실행하십시오.")

    members: list[tuple[str, bytes]] = []
    for path in sorted(SRC.glob("*.py")):
        if path.name in WORKER_ONLY:
            continue
        members.append((path.name, path.read_bytes()))
    for path in sorted(SRC.rglob("quotation/**/*.py")):
        members.append((path.relative_to(SRC).as_posix(), path.read_bytes()))
    members.append(("entry.py", (BROWSER / "entry.py").read_bytes()))
    return members


def deps_members() -> list[tuple[str, bytes]]:
    """순수 파이썬 wheel 들의 내용을 그대로 편다."""
    from io import BytesIO

    members: list[tuple[str, bytes]] = []
    for wheel in PURE_WHEELS:
        with zipfile.ZipFile(BytesIO(fetch(wheel))) as archive:
            for info in sorted(archive.infolist(), key=lambda i: i.filename):
                if info.is_dir():
                    continue
                if info.filename.endswith(WHEEL_SKIP_SUFFIXES):
                    continue
                members.append((info.filename, archive.read(info)))
    return members


# --- 빌드 ---------------------------------------------------------------------

def _template_facts() -> dict:
    """번들에 담긴 템플릿의 판본. sync_core.py 가 만든 모듈에서 읽는다."""
    text = (SRC / "template_data.py").read_text(encoding="utf-8")
    facts = {}
    for line in text.splitlines():
        for key in ("TEMPLATE_VERSION", "TEMPLATE_SHA256", "TEMPLATE_SIZE"):
            if line.startswith(f"{key} ="):
                value = line.split("=", 1)[1].strip().strip('"')
                facts[key.lower()] = int(value) if key.endswith("SIZE") else value
    return facts


def stale() -> list[str]:
    """산출물과 저장소가 어긋난 항목. 비어 있으면 최신이다."""
    manifest_path = OUT / "engine.json"
    if not manifest_path.is_file():
        return ["engine.json (엔진 자산이 없습니다)"]

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    problems: list[str] = []

    core = OUT / manifest["core"]["file"]
    if not core.is_file():
        problems.append(manifest["core"]["file"])
    elif _sha256(zip_bytes(core_members())) != _sha256(core.read_bytes()):
        problems.append(f"{manifest['core']['file']} (web/src 와 다릅니다)")

    if manifest.get("pyodide_version") != PYODIDE_VERSION:
        problems.append(f"pyodide {manifest.get('pyodide_version')} != {PYODIDE_VERSION}")
    if manifest["template"] != _template_facts():
        problems.append("template (견적서 양식이 바뀌었습니다)")

    for name in [a.name for a in RUNTIME] + [LXML.name, "python-deps.zip"]:
        if not (OUT / name).is_file():
            problems.append(name)
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clean", action="store_true",
                        help="산출물 폴더를 지우고 다시 만든다")
    parser.add_argument("--check", action="store_true",
                        help="만들지 않고 최신인지만 확인한다 (CI·테스트용)")
    args = parser.parse_args()

    if args.check:
        problems = stale()
        if problems:
            print("엔진 자산이 최신이 아닙니다. "
                  "python web/scripts/build_browser_engine.py 를 실행하십시오.")
            for name in problems:
                print(f"  - {name}")
            return 1
        print(f"엔진 자산 최신 (Pyodide {PYODIDE_VERSION})")
        return 0

    if args.clean and OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True, exist_ok=True)

    print(f"=== Pyodide {PYODIDE_VERSION} 런타임")
    for asset in RUNTIME:
        (OUT / asset.name).write_bytes(fetch(asset))

    print("=== lxml wheel (Worker 와 같은 판본)")
    (OUT / LXML.name).write_bytes(fetch(LXML))

    print("=== python-deps.zip (openpyxl, et_xmlfile)")
    deps = _write_zip(OUT / "python-deps.zip", deps_members())

    print("=== quotation-core.zip (web/src 의 모듈 그대로)")
    members = core_members()
    core = _write_zip(OUT / "quotation-core.zip", members)

    manifest = {
        "pyodide_version": PYODIDE_VERSION,
        "packages": {
            "lxml": {"file": LXML.name, "sha256": LXML.sha256},
            "python_deps": {"file": "python-deps.zip", "sha256": _sha256(deps)},
        },
        "core": {
            "file": "quotation-core.zip",
            "sha256": _sha256(core),
            "modules": sorted(name for name, _ in members),
        },
        "template": _template_facts(),
    }
    (OUT / "engine.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")

    total = sum(p.stat().st_size for p in OUT.iterdir() if p.is_file())
    print(f"=== 완료: {OUT} · {len(members)}개 모듈 · 합계 {total / 1024 / 1024:.1f} MiB")
    print(f"    템플릿 {manifest['template'].get('template_version', '?')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
