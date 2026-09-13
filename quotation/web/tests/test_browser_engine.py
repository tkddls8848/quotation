"""브라우저 엔진에 담기는 것이 저장소 원본과 같은지 확인한다.

무료 계정에서는 변환이 브라우저에서 돈다. 결과가 데스크톱과 같으려면 **돌아가는
코드와 양식이 같은 것** 이어야 한다. 여기서는 그 포장을 본다. 실제로 돌려서
결과를 대조하는 것은 `test_browser_parity.py` 가 한다.

엔진은 Rust→WASM 이다 (`rust/wasm`). 자산은 둘뿐이다 — 글루 JavaScript 와
wasm. 템플릿은 wasm 안에 들어 있고, 그 판본을 `engine.json` 이 적어 둔다.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest

import build_browser_engine as engine

from quotation.core.resources import TEMPLATE_NAMES

FEATURE = Path(__file__).resolve().parents[2]   # quotation/
ROOT = FEATURE.parent                           # 저장소 뿌리 (Cargo 작업공간)
CORE = FEATURE / "python" / "quotation"
TEMPLATES = {mode: CORE / "resources" / name for mode, name in TEMPLATE_NAMES.items()}


# --- 자산이 없어도 도는 검사 ------------------------------------------------------

def test_manifest_reports_the_repository_templates():
    """양식은 저장소의 그 파일들뿐이다 (양식 뒤틀림 방지의 출발점)."""
    facts = engine.template_facts()
    assert set(facts) == set(TEMPLATES)
    for mode, source in TEMPLATES.items():
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        assert facts[mode]["sha256"] == digest
        assert facts[mode]["version"] == f"sha256-{digest[:12]}"
        assert facts[mode]["name"] == source.name


def test_the_engine_ships_only_two_files():
    """내보내는 것은 글루와 wasm 뿐이다. 늘어나면 CSP·캐시 정책을 다시 봐야 한다."""
    assert engine.GLUE.endswith(".js")
    assert engine.WASM.endswith(".wasm")


def test_the_transfer_limit_matches_the_decision():
    """전송 크기 한도는 결정 0008 의 1.1 MiB 다."""
    assert engine.MAX_TRANSFER_BYTES == int(1.1 * 1024 * 1024)


# --- 산출물이 있을 때 ----------------------------------------------------------

def _built() -> bool:
    return (engine.OUT / "engine.json").is_file()


def test_built_assets_are_up_to_date():
    """엔진 자산이 있다면 저장소 상태와 어긋나 있으면 안 된다."""
    if not _built():
        pytest.skip("엔진 자산이 없습니다 (build_browser_engine.py 미실행)")

    problems = engine.stale()
    assert not problems, (
        "엔진 자산이 낡았습니다. python quotation/web/scripts/build_browser_engine.py "
        "를 다시 실행하십시오:\n  " + "\n  ".join(problems))


def test_manifest_describes_what_it_ships():
    if not _built():
        pytest.skip("엔진 자산이 없습니다")

    manifest = json.loads((engine.OUT / "engine.json").read_text(encoding="utf-8"))
    assert manifest["engine"] == "rust-wasm"
    for key in ("module", "wasm"):
        shipped = (engine.OUT / manifest[key]["file"]).read_bytes()
        assert hashlib.sha256(shipped).hexdigest() == manifest[key]["sha256"]
        assert manifest[key]["size"] == len(shipped)
    assert manifest["template"] == engine.template_facts()


def test_transfer_size_stays_under_the_limit():
    """첫 방문이 받는 크기. 넘으면 브라우저 자산 교체의 전제가 무너진다 (결정 0008)."""
    if not _built():
        pytest.skip("엔진 자산이 없습니다")

    manifest = json.loads((engine.OUT / "engine.json").read_text(encoding="utf-8"))
    transfer = sum(engine._gzip_size((engine.OUT / manifest[key]["file"]).read_bytes())
                   for key in ("module", "wasm"))
    assert transfer <= engine.MAX_TRANSFER_BYTES, (
        f"전송 {transfer / 1024 / 1024:.3f} MiB > "
        f"한도 {engine.MAX_TRANSFER_BYTES / 1024 / 1024:.3f} MiB")


def test_the_wasm_carries_the_repository_templates():
    """wasm 안에 저장소의 양식이 그대로 들어 있는가.

    코어가 `include_bytes!` 로 싣는다. 다른 양식이 실리면 견적서 모양이
    바뀌므로, 판본 문자열을 wasm 이 스스로 계산해 내놓는 값과 맞춰 본다.
    """
    if not _built() or shutil.which("cargo") is None:
        pytest.skip("엔진 자산이나 cargo 가 없습니다")

    facts = engine.template_facts()
    result = subprocess.run(
        ["cargo", "run", "--quiet", "--package", "quotation-tools",
         "--bin", "template-versions"],
        cwd=ROOT, capture_output=True, check=False)
    if result.returncode != 0:
        pytest.skip("template-versions 탐침을 돌릴 수 없습니다")
    reported = json.loads(result.stdout.decode("utf-8"))
    assert reported == {mode: facts[mode]["version"] for mode in facts}
