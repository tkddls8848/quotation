"""레노버 DCSC 요약표 — 구성 파일 안에 눌러 담긴 품목별 실금액.

통합 모드는 처음에 본체 라인 LP 하나로만 금액을 셌다. XML 의 소프트웨어
라인이 자리표 `1` 만 담아서 실금액을 알 길이 없었기 때문이다
(`integrated.py` 머리말).

실금액은 문서 안에 있다. `CFXML/SectionData/GroupData` 가 DCSC 화면의
요약표를 그대로 담고 있으며, **base64 로 적은 gzip XML** 이다. 구성 한 벌이
품목별로 갈라져 있고 소프트웨어에도 제 금액이 붙어 있다.

    <Group_-Product>
      <code>7DGDCTO1WW</code> <type>hardware</type>
      <unitPrice>7.58000014E7</unitPrice>
      <prices><SimplePrice><price>8.31720014E7</price></SimplePrice></prices>
    </Group_-Product>
    <Group_-Product>
      <code>7S0XCTO8WW</code> <type>hipo</type>        <- 소프트웨어
      <unitPrice>840001.0</unitPrice>                  <- 실금액 + 자리표 1
    </Group_-Product>
    …
    <Group_-Product>
      <code>5WS7C20241</code> <type>service</type>
      <unitPrice>5691000.0</unitPrice>                 <- XML 라인 값과 같다
    </Group_-Product>

실파일 27 건 73 개 장비군을 검산해 확인한 사실은 넷이다.

1. 하드웨어 항목의 `prices/SimplePrice/price` 가 **XML 본체 라인의
   UnitListPrice** 와 같다. 장비군과 구성을 짝지을 때 이것을 쓴다.
2. 다음 항등식이 성립한다.

       본체 LP = 하드웨어 + Σ소프트웨어 + Σ서비스 - (소프트웨어 항목 수)

   빼는 값은 소프트웨어마다 하나씩 붙은 자리표 1 원이다. 65 개 장비군이
   짝지어졌고 그중 56 개는 원 단위까지 맞았다. 나머지 9 개는 1~5 원 차이로,
   자리표 개수와 소수 넷째 자리 반올림에서 온다.
3. 서비스 금액은 XML 라인에도 실금액으로 들어 있다. 요약표와 한 건도
   다르지 않았다. 즉 요약표가 새로 알려 주는 것은 **소프트웨어 실금액** 뿐이다.
4. 한 장비군 안의 라인 수량은 모두 같다. 그래서 단가끼리 더하고 빼면 된다.

`GroupData` 는 eConfig 규격이 아니라 DCSC 가 제 상태를 담아 두는 자리다.
문서화된 적이 없고 구성기 판올림에 형태가 바뀔 수 있으므로 **읽지 못하면 조용히
포기** 하고, 통합 모드는 지금까지대로 본체 LP 한 줄만 센다. 요소 이름
(`com.lenovo.awakens.api.request.Group_-Product`)에 기대지 않고 자식 노드의
생김새로 항목을 고르는 것도 같은 이유다.
"""
from __future__ import annotations

import base64
import binascii
import gzip
import io
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from lxml import etree

from .money import Amount, is_priced

#: 요약표가 앉아 있는 자리.
XP_GROUP_DATA = "./SectionData/GroupData"

#: 풀어 놓은 요약표의 최대 크기. 실파일은 7 KiB 안팎이다. 압축 폭탄을 막는다.
MAX_BLOB_BYTES = 8 * 1024 * 1024

#: 소프트웨어 항목마다 붙어 있는 자리표. 실금액은 이만큼 뺀 값이다.
PLACEHOLDER = Decimal(1)

#: 본체 LP 와 요약표 합계가 어긋나도 같은 구성으로 보는 폭(원).
#: 관측된 가장 큰 차이는 5 원이었다 (머리말 2).
TOLERANCE = Decimal(10)

#: 요약표의 `type`. 하드웨어만 H/W 구간이고 `hipo` 가 소프트웨어다.
HARDWARE = "hardware"


@dataclass(frozen=True)
class Config:
    """요약표의 구성 한 벌. 장비군 한 개에 대응한다."""

    #: 하드웨어 항목의 품번. 짝짓기에 쓴다.
    body_part: str
    #: 하드웨어 항목의 `SimplePrice`. 곧 XML 본체 라인의 UnitListPrice 다.
    total: Decimal
    #: 하드웨어가 아닌 품목의 실금액. 품번 -> 금액. 같은 품번이 여러 번
    #: 나오면 더해 둔다 (라인 하나가 한 번만 가져가므로 합계는 어긋나지 않는다).
    prices: dict[str, Decimal]


class Summary:
    """문서 한 건의 요약표.

    구성은 장비군에 한 번씩만 짝지어야 하므로, 가져간 구성은 목록에서 뺀다.
    같은 기종을 여러 대 담으면 금액까지 같은 구성이 여러 벌 나오는데, 그때는
    어느 것을 집어도 결과가 같다.
    """

    def __init__(self, configs: tuple[Config, ...] = ()) -> None:
        self._left = list(configs)

    def __bool__(self) -> bool:
        return bool(self._left)

    def __len__(self) -> int:
        return len(self._left)

    def take(self, part_number: str, total: Amount) -> Config | None:
        """본체 라인에 맞는 구성을 하나 꺼낸다. 없으면 None.

        Args:
            part_number: 본체 라인의 품번. XML 은 하이픈을 넣어 적는다.
            total: 본체 라인의 UnitListPrice.
        """
        if not is_priced(total):
            return None
        key = part_key(part_number)
        for index, config in enumerate(self._left):
            if config.body_part != key:
                continue
            if abs(config.total - total) > TOLERANCE:
                continue
            return self._left.pop(index)
        return None


def part_key(part_number: str) -> str:
    """품번을 대조용으로 다듬는다. XML 은 `7DGD-CTO1WW`, 요약표는 `7DGDCTO1WW`."""
    return part_number.replace("-", "").strip().upper()


def parse(root) -> Summary:
    """문서 뿌리 -> 요약표. 없거나 읽지 못하면 빈 요약표를 준다."""
    blob = _blob(root)
    if blob is None:
        return Summary()
    return Summary(_configs(blob))


def _blob(root):
    """`SectionData/GroupData` 를 풀어 파싱한다. 조금이라도 어긋나면 None."""
    node = root.find(XP_GROUP_DATA)
    if node is None:
        return None
    # DCSC 는 한 줄로 적지만, 사람이 손으로 접어 둔 문서도 읽는다.
    packed64 = "".join((node.text or "").split())
    if not packed64:
        return None
    try:
        packed = base64.b64decode(packed64, validate=True)
    except (binascii.Error, ValueError):
        return None
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(packed)) as unpacked:
            raw = unpacked.read(MAX_BLOB_BYTES + 1)
    except (OSError, EOFError):
        return None
    if not raw or len(raw) > MAX_BLOB_BYTES:
        return None
    try:
        return etree.fromstring(raw, etree.XMLParser(
            load_dtd=False, resolve_entities=False, no_network=True,
            dtd_validation=False, huge_tree=False, recover=False))
    except etree.XMLSyntaxError:
        return None


def _configs(blob) -> tuple[Config, ...]:
    """풀어 놓은 요약표 -> 구성 목록. 문서 등장 순서를 지킨다."""
    ordered: list[str] = []
    buckets: dict[str, list[tuple[str, str, Decimal, Decimal | None]]] = {}
    for item in _items(blob):
        cfg_id, code, kind, unit, total = item
        if cfg_id not in buckets:
            buckets[cfg_id] = []
            ordered.append(cfg_id)
        buckets[cfg_id].append((code, kind, unit, total))

    configs: list[Config] = []
    for cfg_id in ordered:
        bodies = [e for e in buckets[cfg_id] if e[1] == HARDWARE]
        # 하드웨어가 없거나 둘 이상이면 어느 라인에 붙일지 알 수 없다.
        if len(bodies) != 1 or bodies[0][3] is None:
            continue
        code, _kind, _unit, total = bodies[0]
        prices: dict[str, Decimal] = {}
        for part, kind, unit, _total in buckets[cfg_id]:
            if kind == HARDWARE:
                continue
            # 소프트웨어(`hipo`)에만 자리표 1 원이 붙어 있다 (머리말 2).
            real = unit - PLACEHOLDER if _is_software(kind) else unit
            prices[part] = prices.get(part, Decimal(0)) + real
        configs.append(Config(body_part=code, total=total, prices=prices))
    return tuple(configs)


def _is_software(kind: str) -> bool:
    """요약표의 소프트웨어 항목인가. 서비스는 `service` 로 시작한다."""
    return "service" not in kind


def _items(blob):
    """요약표의 품목을 훑는다.

    XStream 이 적어 넣은 요소 이름이 아니라 자식 노드로 고른다. 이름이 바뀌어도
    금액이 있는 품목이면 그대로 읽힌다.
    """
    for el in blob.iter():
        code = _text(el, "./code")
        unit = _number(el, "./unitPrice")
        if not code or unit is None:
            continue
        yield (_text(el, "./id"), part_key(code), _text(el, "./type").lower(),
               unit, _number(el, "./prices/SimplePrice/price"))


def _text(el, path: str) -> str:
    node = el.find(path)
    if node is None or node.text is None:
        return ""
    return node.text.strip()


def _number(el, path: str) -> Decimal | None:
    raw = _text(el, path)
    if not raw:
        return None
    try:
        return Decimal(raw)
    except InvalidOperation:
        return None
