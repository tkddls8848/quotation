"""레노버 x86 구성 파일(통합 모드)의 해석 규칙.

문서 형식은 IBM eConfig Export 와 같다. 다른 것은 **값이 뜻하는 바** 이며,
지금까지 확인된 차이는 둘뿐이다. 두 가지 모두 여기 모아 둔다.

1. 장비 이름이 ProductDescription 이 아니라 ProductName 에 있다.

   한 파일에 SR650 V4 를 열한 대 담으면 열 그룹의 ProductDescription 이 전부
   'ThinkSystem SR650 V4-3yr Base Warranty' 로 같다. 사람이 붙인 이름
   ('백업서버_1식', '웹서버_1식')은 ProductName 에 있고, 손으로 만든 견적서의
   종목 칸도 그 이름을 쓴다.

2. 본체 라인의 UnitListPrice 가 **그 서버 한 대의 전체 LP** 다.

   Lenovo DCSC 가 내려 주는 요약표(Summary)와 대조해서 확인했다. 예를 들어
   그룹 1000 은 요약표에서 다음처럼 갈라지는데,

       ThinkSystem SR650 V4      27,360,001.8
       Red Hat RHEL               5,440,001
       XClarity Controller          840,001
       3Yr Premier 24x7 4Hr       5,691,000
       3Yr KYD Add-On               841,000
       Configuration Instruction          1
                                 ------------
                                 40,172,001.8   <- XML 의 본체 라인 UnitListPrice

   XML 의 소프트웨어 라인은 값이 1(자리표)일 뿐 실제 금액을 담지 않는다.
   그래서 소프트웨어·서비스 라인의 금액을 그대로 더하면 서비스 금액이 두 번
   들어가고 자리표 1원까지 얹힌다.

   갈라 놓을 값은 문서 안에 있다. `SectionData/GroupData` 의 요약표가 품목별
   실금액을 담고 있어서, 소프트웨어·서비스에 제 금액을 적고 하드웨어는 남는
   값으로 잡는다 (`dcsc_summary.py`). 요약표를 못 읽으면 지금까지대로 본체
   라인 하나로만 센다.

   어느 쪽이든 **장비군 합계는 본체 LP 그대로** 이며, 라인은 지우지 않는다.
   무엇이 들어 있는지는 상세 시트에 그대로 남는다.
"""
from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

from . import dcsc_summary
from .models import LineItem
from .money import is_priced, to_decimal
from .naming import product_key


def body_line(items: tuple[LineItem, ...]) -> LineItem | None:
    """그룹의 본체 라인. CPUSIUvalue=1 인 하드웨어 라인이다."""
    return next((i for i in items if i.siu == 1 and i.is_hardware), None)


def group_key(items: tuple[LineItem, ...]) -> str:
    """장비군 이름. 본체 라인의 ProductName 을 먼저 쓴다."""
    line = body_line(items) or items[0]
    return product_key(line.product_name, line.description)


def fold_prices(items: tuple[LineItem, ...],
                summary: dcsc_summary.Summary | None = None,
                ) -> tuple[LineItem, ...]:
    """본체 LP 에 이미 들어 있는 금액을 갈라 놓는다 (머리말 2번).

    값이 붙은 본체 라인이 있을 때만 손댄다. 랙·PDU·케이블처럼 본체 없이
    부품만 들어 있는 그룹은 저마다 제 금액을 가지므로 그대로 둔다.

    Args:
        items: 장비군 한 개의 라인.
        summary: 문서의 요약표. 주면 품목별 실금액을 적고, 없거나 이 장비군에
            맞는 구성이 없으면 하드웨어가 아닌 라인의 금액 칸을 비운다.
    """
    body = body_line(items)
    if body is None or not is_priced(body.unit_price):
        return items
    config = summary.take(body.part_number, body.unit_price) if summary else None
    if config is not None:
        split = _split_prices(items, body, config)
        if split is not None:
            return split
    return tuple(item if item.is_hardware else replace(item, unit_price=None)
                 for item in items)


def _split_prices(items: tuple[LineItem, ...], body: LineItem,
                  config: dcsc_summary.Config) -> tuple[LineItem, ...] | None:
    """요약표의 실금액을 라인에 적고 하드웨어는 남는 값으로 잡는다.

    남는 값에 자리표 몇 원과 소수 넷째 자리 반올림이 모이므로 장비군 합계는
    본체 LP 와 한 푼도 어긋나지 않는다.

    같은 품번이 그 장비군에 두 번 나오면 앞선 라인이 금액을 가져가고 뒤는
    비운다. 합계는 어느 쪽이든 같다.

    Returns:
        고쳐 쓴 라인. 남는 값이 음수면 짝을 잘못 지은 것이므로 None.
    """
    left = dict(config.prices)
    priced: list[LineItem] = []
    others = Decimal(0)
    for item in items:
        if item.is_hardware:
            priced.append(item)
            continue
        price = left.pop(dcsc_summary.part_key(item.part_number), None)
        if not price:  # 요약표에 없거나 자리표뿐인 라인 (Configuration Instruction)
            priced.append(replace(item, unit_price=None))
            continue
        others += price
        priced.append(replace(item, unit_price=price))

    rest = to_decimal(body.unit_price) - others
    if rest < 0:
        return None
    return tuple(replace(item, unit_price=rest) if item is body else item
                 for item in priced)
