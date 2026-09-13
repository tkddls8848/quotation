"""공용 코어 테스트에서 쓰는 자료.

실데이터(`samples/`)는 저장소에 담지 않는다. 여기서 쓰는 fixture 는 전부
`tests/fixtures/public/` 의 익명화 자료다.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from quotation.core import resources

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "public"


@pytest.fixture(scope="session")
def fixtures() -> Path:
    return FIXTURES


@pytest.fixture(scope="session")
def template_bytes() -> bytes:
    return resources.default_template_bytes()


@pytest.fixture(scope="session")
def template_path() -> Path:
    return resources.default_template_path()
