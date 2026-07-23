"""할인율 검증 및 공급가 계산.

할인율 규칙은 원본 Form1 의 입력 검증을 그대로 옮긴 것이다.
  - 99 초과 불가        "할인율은 99보다 클수 없습니다."
  - 소수점 1자리까지     "할인율은 소숫점 1자리만 입력 가능합니다."

⚠️ 할인이 적용된 골든 샘플이 아직 없다. 셀 수식 `*(1-J행)` 형태만 EXE 문자열로
   확인된 상태이므로, writer 연동은 샘플 확보 후 검증한다 (REFACTORING_PLAN.md §7).
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

MAX_DISCOUNT = Decimal("99")
DISCOUNT_STEP = Decimal("0.1")


class DiscountError(ValueError):
    """할인율 입력이 규칙에 어긋날 때."""


def parse_discount(raw: str | float | Decimal | None) -> Decimal:
    """사용자 입력 -> 할인율(%). 빈 값은 0."""
    if raw is None:
        return Decimal(0)
    if isinstance(raw, Decimal):
        value = raw
    else:
        text = str(raw).strip().rstrip("%").strip()
        if not text:
            return Decimal(0)
        try:
            value = Decimal(text)
        except InvalidOperation as exc:
            raise DiscountError("할인율을 숫자로 입력하십시오.") from exc

    if value < 0:
        raise DiscountError("할인율은 0보다 작을 수 없습니다.")
    if value > MAX_DISCOUNT:
        raise DiscountError("할인율은 99보다 클수 없습니다.")
    if value != value.quantize(DISCOUNT_STEP):
        raise DiscountError("할인율은 소숫점 1자리만 입력 가능합니다.")
    return value


def discount_rate(percent: Decimal) -> Decimal:
    """할인율(%) -> 배율. 25.5 -> Decimal('0.745')"""
    return Decimal(1) - (percent / Decimal(100))


def apply_discount(amount: Decimal, percent: Decimal) -> Decimal:
    """공급가 = 금액 x (1 - 할인율)."""
    return amount * discount_rate(percent)


def round_won(amount: Decimal) -> Decimal:
    """표시용 반올림. 셀 서식이 #,##0 이므로 정수로 접는다.

    VB6 는 Banker's rounding 이지만 Excel 표시 반올림은 half-up 이다.
    셀에는 원본 값을 그대로 쓰고 Excel 이 표시만 반올림하므로, 이 함수는
    검산·로그용이다.
    """
    return amount.quantize(Decimal(1), rounding=ROUND_HALF_UP)
