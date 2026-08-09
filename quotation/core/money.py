"""금액 파싱 — eConfig MonetaryAmount 전용.

SPEC_CELLMAP.md §1.2

    "88,971.5"  -> Decimal("88971.5")
    "N/C"       -> NO_CHARGE       (셀에 문자열 "N/C" 기록, 합계에서 0)
    "0"         -> Decimal("0")
    None / ""   -> None            (셀 비움)

float 을 쓰지 않는다. 원본 소수점 자릿수를 그대로 보존해야 골든과 일치한다.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Final


class NoCharge:
    """무상(N/C) 표식. 셀에는 "N/C" 문자열로 기록되고 합계에서는 0으로 취급된다."""

    __slots__ = ()


NO_CHARGE: Final = NoCharge()

Amount = Decimal | NoCharge | None


def parse_amount(raw: str | None) -> Amount:
    """MonetaryAmount 텍스트 -> Amount."""
    if raw is None:
        return None
    text = raw.strip()
    if not text:
        return None
    if text == "N/C":
        return NO_CHARGE
    return Decimal(text.replace(",", ""))


def to_decimal(amount: Amount) -> Decimal:
    """합계 계산용. N/C 와 없음은 0 으로 접는다."""
    if isinstance(amount, Decimal):
        return amount
    return Decimal(0)


def is_priced(amount: Amount) -> bool:
    """실제 금액이 붙어 있는가 (N/C·없음 제외)."""
    return isinstance(amount, Decimal)
