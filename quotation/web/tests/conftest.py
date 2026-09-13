"""브라우저 경로 테스트 자료.

변환은 브라우저의 Rust→WASM 엔진이 한다. 여기 테스트는 그 엔진을 Node 와 실제
Chromium 에서 돌려 데스크톱 경로(확장 모듈)와 대조한다.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from quotation.core import resources

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures" / "public"
@pytest.fixture(scope="session")
def fixtures() -> Path:
    return FIXTURES


@pytest.fixture(scope="session")
def template_bytes() -> bytes:
    """운영에서 쓰는 그 템플릿. R2 를 걷어낸 뒤로는 번들에 담겨 나간다
    (doc/decisions/0001-template-in-bundle.md)."""
    return resources.default_template_bytes()
