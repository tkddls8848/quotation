"""Rust 이식본이 파이썬 코어와 같은 답을 내는가 (계획 §Phase 1).

이식이 진행되는 동안 파이썬 구현이 기준으로 남는다. 판정은
`tools/rust_parity_pure_rules.py` 가 하고, 여기서는 그것을 테스트 묶음에
얹어 둔다 — Rust 규칙이 갈라지면 평소 `pytest` 에서 바로 붉어진다.

Rust 도구가 없는 자리에서는 건너뛴다. 파이썬 쪽 검사는 그대로 다 돈다.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "tools" / "rust_parity_pure_rules.py"

pytestmark = pytest.mark.skipif(
    shutil.which("cargo") is None,
    reason="cargo 가 없어 Rust 이식본을 대조하지 않는다",
)


def test_pure_rules_match_python_core():
    """money · naming · modes 를 같은 입력으로 대조한다."""
    result = subprocess.run(
        [sys.executable, str(HARNESS)],
        cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
    )
    report = result.stdout.decode("utf-8", "replace")
    assert result.returncode == 0, report
    assert "모두 같습니다" in report
