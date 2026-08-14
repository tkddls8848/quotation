"""두 .xlsx 가 같은 견적서인지 판정하는 규칙 (테스트 보조 모듈).

브라우저 변환과 CPython 변환을 대조하는 곳이 둘이라 규칙을 한 곳에 둔다.

    test_browser_parity.py   Node 로 엔진을 돌려 대조 (파이썬 수준의 동일성)
    test_browser_e2e.py      실제 Chromium 으로 받아 대조 (배선의 동일성)

정규화하는 것은 딱 둘이며 **둘 다 견적서 내용이 아니다.**

    docProps/core.xml 의 <dcterms:modified>
        파일을 만든 시각. 두 번 만들면 언제나 다르다.

    <mergeCell> 의 나열 순서
        병합 집합은 같고 순서만 다르다. openpyxl 이 병합 영역을 집합으로 들고
        있어 순회 순서가 파이썬 판본에 따라 갈린다. Excel 은 순서를 보지 않는다.
        집합 자체가 달라지면 여기서 걸린다.

그 밖에는 한 바이트도 봐준다는 뜻이 아니다. 시트, 스타일, 수식, 그림·도형,
관계 파일까지 전부 그대로 같아야 한다.
"""
from __future__ import annotations

import re
import zipfile
from io import BytesIO

_MERGE = re.compile(rb'<mergeCell ref="[^"]*"/>')
_MODIFIED = re.compile(rb"<dcterms:modified[^>]*>[^<]*</dcterms:modified>")


def normalized_parts(xlsx: bytes) -> dict[str, tuple[bytes, frozenset]]:
    """zip 부품별 (정규화한 내용, 병합 집합)."""
    parts: dict[str, tuple[bytes, frozenset]] = {}
    with zipfile.ZipFile(BytesIO(xlsx)) as archive:
        for name in archive.namelist():
            data = archive.read(name)
            merges = frozenset(_MERGE.findall(data))
            data = _MERGE.sub(b"", data)
            if name == "docProps/core.xml":
                data = _MODIFIED.sub(b"<dcterms:modified/>", data)
            parts[name] = (data, merges)
    return parts


def differences(expected: bytes, actual: bytes) -> list[str]:
    """다른 점을 사람이 읽을 수 있게. 비어 있으면 같은 견적서다."""
    want, got = normalized_parts(expected), normalized_parts(actual)

    problems = []
    for name in sorted(set(want) - set(got)):
        problems.append(f"{name}: 빠졌습니다")
    for name in sorted(set(got) - set(want)):
        problems.append(f"{name}: 없어야 할 것이 들어 있습니다")

    for name in sorted(set(want) & set(got)):
        want_data, want_merges = want[name]
        got_data, got_merges = got[name]
        if want_merges != got_merges:
            problems.append(
                f"{name}: 병합 영역이 다릅니다 "
                f"(빠짐 {sorted(want_merges - got_merges)}, "
                f"더함 {sorted(got_merges - want_merges)})")
        if want_data != got_data:
            problems.append(f"{name}: 내용이 다릅니다 "
                            f"({len(want_data)} bytes vs {len(got_data)} bytes)")
    return problems
