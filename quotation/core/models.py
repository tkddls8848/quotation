"""도메인 모델 — XML 과 Excel 사이의 중간 표현.

Excel·GUI 에 의존하지 않는 순수 데이터. 전부 frozen 이다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from .money import Amount, to_decimal

# ProductTypeCode 값
HARDWARE = "Hardware"
SOFTWARE = "Software"
SERVICES = "Services"


@dataclass(frozen=True)
class SubLineItem:
    """ProductSubLineItem — 상위 라인의 구성 부품."""

    line_number: str
    txn_type: str
    quantity: int
    part_number: str
    description: str
    unit_price: Amount = None
    maintenance: Amount = None

    def amount(self, parent_quantity: int) -> Decimal:
        """금액 = (서브수량 x 부모수량) x 단가.

        셀 수식 ``=8*E8`` 이 뜻하는 바와 동일하다. 서브 수량은 부모 1대당 수량이다.
        """
        return to_decimal(self.unit_price) * self.quantity * parent_quantity


@dataclass(frozen=True)
class LineItem:
    """ProductLineItem — 견적의 한 줄."""

    line_number: str
    txn_type: str
    group_id: str
    quantity: int
    part_number: str
    description: str
    product_type: str = ""
    unit_price: Amount = None
    price_term: str = ""
    maintenance: Amount = None
    maintenance_term: str = ""
    subs: tuple[SubLineItem, ...] = ()

    @property
    def is_hardware(self) -> bool:
        # Hardware 만 H/W 섹션이다. Services 는 S/W 로 간다
        # (골든 X-ROIS 'EXPERT LABS' 시트 B8 = "S/W", 6911-301 은 Services).
        return self.product_type == HARDWARE

    def own_amount(self) -> Decimal:
        return to_decimal(self.unit_price) * self.quantity

    def amount(self) -> Decimal:
        """자기 금액 + 모든 서브라인 금액."""
        return self.own_amount() + sum(
            (s.amount(self.quantity) for s in self.subs), Decimal(0)
        )

    def maintenance_amount(self) -> Decimal:
        """유지정비료. 수량을 곱하지 않는다 (SPEC_CELLMAP.md §4.3)."""
        return to_decimal(self.maintenance) + sum(
            (to_decimal(s.maintenance) for s in self.subs), Decimal(0)
        )


@dataclass(frozen=True)
class Group:
    """ProprietaryGroupIdentifier 로 묶인 장비군. 상세 시트 1장에 대응한다."""

    group_id: str
    item_key: str
    sheet_name: str
    items: tuple[LineItem, ...]

    @property
    def hardware(self) -> tuple[LineItem, ...]:
        return tuple(i for i in self.items if i.is_hardware)

    @property
    def software(self) -> tuple[LineItem, ...]:
        return tuple(i for i in self.items if not i.is_hardware)

    def sections(self) -> tuple[tuple[str, tuple[LineItem, ...]], ...]:
        """TOTAL 시트의 금액 병합 단위. H/W 구간과 S/W 구간이 각각 별도 소계를 가진다.

        SPEC_CELLMAP.md §3.2 — 골든 X-ROIS TOTAL 은 그룹 2000 을
        G10:G12(H/W, 5,378,973.5) 와 G13:G22(S/W, 600,468.5) 로 나눠 병합한다.
        """
        return tuple(
            (kind, items)
            for kind, items in ((HARDWARE, self.hardware), (SOFTWARE, self.software))
            if items
        )

    def hardware_amount(self) -> Decimal:
        return sum((i.amount() for i in self.hardware), Decimal(0))

    def software_amount(self) -> Decimal:
        return sum((i.amount() for i in self.software), Decimal(0))

    def amount(self) -> Decimal:
        return sum((i.amount() for i in self.items), Decimal(0))

    def maintenance_amount(self) -> Decimal:
        return sum((i.maintenance_amount() for i in self.items), Decimal(0))

    def has_maintenance(self) -> bool:
        return self.maintenance_amount() != 0


@dataclass(frozen=True)
class Shipping:
    name: str
    currency: str
    amount: Amount


@dataclass(frozen=True)
class Quotation:
    """XML 한 건 = 견적서 한 부."""

    document_id: str = ""
    generated_time: str = ""
    price_file_date: str = ""
    configurator_id: str = ""
    checksum: str = ""
    shipping: Shipping | None = None
    groups: tuple[Group, ...] = field(default_factory=tuple)

    def total_amount(self) -> Decimal:
        return sum((g.amount() for g in self.groups), Decimal(0))

    def total_maintenance(self) -> Decimal:
        return sum((g.maintenance_amount() for g in self.groups), Decimal(0))
