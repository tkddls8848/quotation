"""Worker 테스트 자료.

Workers 런타임 없이 CPython 에서 돈다. `worker.py` 만 런타임 모듈(`workers`)에
의존하므로, 이 테스트들은 순수 층(`api`, `conversion_adapter`)을 직접 부른다.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from quotation.core import resources

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures" / "public"
WEB_SRC = ROOT / "web" / "src"


@pytest.fixture(scope="session")
def fixtures() -> Path:
    return FIXTURES


@pytest.fixture(scope="session")
def template_bytes() -> bytes:
    """운영에서 R2 가 돌려줄 활성 템플릿에 해당한다."""
    return resources.default_template_bytes()


@pytest.fixture(scope="session")
def web_src() -> Path:
    return WEB_SRC
