"""활성 견적서 템플릿 — IBM 용·레노버 x86 용 두 벌.

템플릿은 Worker 번들 안에 들어 있다. 요청마다 외부 저장소를 읽지 않으므로
네트워크 실패 지점이 없고, 배포된 코드와 템플릿의 판본이 항상 일치한다.

원본은 저장소의 `quotation/resources/견적서_template_IBM.xlsx` 와
`..._Lenovo.xlsx` 뿐이고 데스크톱 앱도 같은 파일을 쓴다. 배포 직전에
`web/scripts/sync_core.py` 가 그 파일들을 `template_data.py` 로 만들어 넣는다.
어느 것을 쓸지는 문서 내용으로 알아낸 모드(`quotation.core.modes.detect`)가
정하며, 화면은 고르지 않는다.

템플릿을 바꾸는 절차:
    1. quotation/resources/견적서_template_{IBM,Lenovo}.xlsx 를 Excel 에서 고친다
    2. python web/scripts/verify_template.py <그 파일> --mode {unix,integrated} 로 검증한다
    3. 커밋하면 배포와 함께 반영된다. 되돌리려면 그 커밋을 되돌린다
"""
from __future__ import annotations

import base64

import errors


class TemplateMissing(RuntimeError):
    """생성 단계를 건너뛰고 배포한 경우."""


def _data():
    try:
        import template_data
    except ImportError as exc:  # pragma: no cover - 배포 사고 방지용
        raise TemplateMissing(
            "template_data.py 가 없습니다. web/scripts/sync_core.py 를 실행하십시오."
        ) from exc
    return template_data


def _entry(mode: str) -> dict:
    try:
        return _data().TEMPLATES[mode]
    except (TemplateMissing, KeyError) as exc:
        raise TemplateMissing(f"{mode} 템플릿이 번들에 없습니다.") from exc


_cache: dict[str, bytes] = {}


def template_bytes(mode: str) -> bytes:
    """모드별 활성 템플릿 바이트.

    Args:
        mode: `quotation.core.modes.UNIX` 또는 `.INTEGRATED`.

    Raises:
        errors.ApiError: TEMPLATE_UNAVAILABLE — 번들에 그 모드의 템플릿이 없다
    """
    if mode not in _cache:
        try:
            _cache[mode] = base64.b64decode(_entry(mode)["b64"])
        except (TemplateMissing, ValueError) as exc:
            raise errors.template_unavailable() from exc
    return _cache[mode]


def template_version(mode: str) -> str:
    """`X-Template-Version` 과 `/status` 에 쓰는 판본. 내용 해시다."""
    try:
        return _entry(mode)["version"]
    except TemplateMissing:
        return "unavailable"
