"""브라우저에서 도는 변환 엔진 자산을 만든다 (결정 decisions/0002).

Cloudflare Workers Free 플랜은 요청당 CPU 10 ms 다. 견적서 한 건을 만드는 데는
가장 작은 입력도 73 ms 가 든다(실측 measurements/runtime.md). 그래서 무료 계정에서는
변환을 브라우저로 옮기고 Cloudflare 는 정적 자산만 내려 준다.

브라우저가 돌리는 것은 **데스크톱과 같은 Rust 코어** 다 (`rust/core`). 그 위의
검증·응답 층도 같은 크레이트에서 온다 (`rust/webapi`). 예전에는 이 자리에
Pyodide 런타임과 파이썬 모듈 14.4 MiB 가 들어갔다 — 지금은 wasm 하나와 글루
JavaScript 하나뿐이다 (약 1.0 MiB).

만드는 것 — 전부 `web/frontend/public/engine/` 아래, 저장소에서 추적하지 않는다.

    quotation_wasm.js           wasm-bindgen 글루 (ES 모듈)
    quotation_wasm_bg.wasm      변환 엔진
    engine.json                 판본·해시 (화면과 테스트가 읽는다)

    python web/scripts/build_browser_engine.py

`wasm-pack` 이 필요하다 (`cargo install wasm-pack`). 이미 만들어 둔 산출물을
그대로 쓰려면 `--no-build` 를 준다.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

WEB = Path(__file__).resolve().parents[1]
ROOT = WEB.parent
CRATE = ROOT / "rust" / "wasm"
PKG = CRATE / "pkg"
OUT = WEB / "frontend" / "public" / "engine"

#: 브라우저로 내보내는 파일. 이 둘이 전부다.
GLUE = "quotation_wasm.js"
WASM = "quotation_wasm_bg.wasm"

#: 전송 크기 상한 (gzip). 근거와 중단 조건은 결정 0008 에 있다.
MAX_TRANSFER_BYTES = int(1.1 * 1024 * 1024)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _gzip_size(data: bytes) -> int:
    import gzip

    return len(gzip.compress(data, 9))


def build_wasm() -> None:
    """`wasm-pack` 으로 브라우저용 꾸러미를 만든다."""
    if shutil.which("wasm-pack") is None:
        raise SystemExit(
            "wasm-pack 이 없습니다. cargo install wasm-pack 으로 설치하십시오.")
    subprocess.run(
        ["wasm-pack", "build", str(CRATE), "--release", "--target", "web",
         "--out-dir", "pkg"],
        cwd=ROOT, check=True)


def template_facts() -> dict[str, dict]:
    """모드별 활성 템플릿. 판본은 내용 해시이고 wasm 안에 같은 파일이 들어 있다."""
    sys.path.insert(0, str(ROOT))
    from quotation.core.resources import TEMPLATE_NAMES

    facts = {}
    for mode, name in TEMPLATE_NAMES.items():
        raw = (ROOT / "quotation" / "resources" / name).read_bytes()
        digest = _sha256(raw)
        facts[mode] = {
            "name": name,
            "sha256": digest,
            "version": f"sha256-{digest[:12]}",
            "size": len(raw),
        }
    return facts


def manifest() -> dict:
    glue = (PKG / GLUE).read_bytes()
    wasm = (PKG / WASM).read_bytes()
    return {
        "engine": "rust-wasm",
        "module": {"file": GLUE, "sha256": _sha256(glue), "size": len(glue)},
        "wasm": {"file": WASM, "sha256": _sha256(wasm), "size": len(wasm),
                 "gzip_size": _gzip_size(wasm)},
        "template": template_facts(),
    }


def stale() -> list[str]:
    """내보낸 자산이 지금 만들 것과 다른 곳. 비어 있으면 최신이다."""
    path = OUT / "engine.json"
    if not path.is_file():
        return ["engine.json (엔진 자산이 없습니다)"]
    if not (PKG / WASM).is_file():
        return ["rust/wasm/pkg (wasm-pack 산출물이 없습니다)"]

    published = json.loads(path.read_text(encoding="utf-8"))
    fresh = manifest()
    problems = []
    for key in ("module", "wasm"):
        name = fresh[key]["file"]
        copied = OUT / name
        if not copied.is_file():
            problems.append(f"{name} (없습니다)")
        elif _sha256(copied.read_bytes()) != fresh[key]["sha256"]:
            problems.append(f"{name} (wasm-pack 산출물과 다릅니다)")
    if published.get("template") != fresh["template"]:
        problems.append("engine.json 의 템플릿 판본이 저장소와 다릅니다")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="만들지 않고 최신 여부만 본다")
    parser.add_argument("--no-build", action="store_true",
                        help="wasm-pack 을 돌리지 않고 있는 산출물을 쓴다")
    args = parser.parse_args()

    if args.check:
        problems = stale()
        for problem in problems:
            print(f"낡음: {problem}")
        print("엔진 자산이 최신입니다." if not problems else
              "python web/scripts/build_browser_engine.py 를 다시 실행하십시오.")
        return 1 if problems else 0

    if not args.no_build:
        print("=== wasm-pack build (rust/wasm)")
        build_wasm()

    OUT.mkdir(parents=True, exist_ok=True)
    for existing in OUT.iterdir():
        if existing.is_file():
            existing.unlink()

    facts = manifest()
    for key in ("module", "wasm"):
        name = facts[key]["file"]
        shutil.copyfile(PKG / name, OUT / name)

    (OUT / "engine.json").write_text(
        json.dumps(facts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    transfer = _gzip_size((OUT / GLUE).read_bytes()) + facts["wasm"]["gzip_size"]
    print(f"=== 완료: {OUT}")
    for mode, template in facts["template"].items():
        print(f"    템플릿[{mode}] {template['version']}")
    print(f"    전송 크기(gzip) {transfer / 1024 / 1024:.3f} MiB "
          f"/ 한도 {MAX_TRANSFER_BYTES / 1024 / 1024:.3f} MiB")
    if transfer > MAX_TRANSFER_BYTES:
        print("전송 크기 한도를 넘었습니다 (결정 0008).")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
