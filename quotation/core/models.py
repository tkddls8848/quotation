"""XML과 Excel 사이에서 사용하는 견적 데이터 모델."""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from .money import Amount, to_decimal

# ProductTypeCode 값
HARDWARE = "Hardware"
SOFTWARE = "Software"
SERVICES = "Services"

#: 증설 견적에서 견적 대상이 아닌 TransactionType.
#: BASE 는 기존 구성, PROPOSED 는 증설 후 구성이다. 둘 다 참조용이라 견적서에
#: 넣지 않는다. 실제 견적 대상은 UPGRADE / DISCO / NEW 등 나머지다.
REFERENCE_TXN = frozenset({"BASE", "PROPOSED"})

#: 제거되는 부품. 수량을 음수로 적고 붉게 표시한다.
REMOVE_TXN = "REMOVE"


@dataclass(frozen=True)
class SubLineItem:
    """ProductSubLineItem — 상위 라인의 구성 부품."""

    txn_type: str
    quantity: int
    part_number: str
    description: str
    unit_price: Amount = None

    @property
    def is_removal(self) -> bool:
        """제거되는 부품인가. XML 의 수량은 양수이고 표시할 때 음수로 바꾼다."""
        return self.txn_type == REMOVE_TXN

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
    subs: tuple[SubLineItem, ...] = ()
    #: CPUSIUvalue. 1 이면 장비 본체 라인이다 (증설 견적의 장비군 판별에 쓴다).
    siu: int = 0

    @property
    def is_reference(self) -> bool:
        """기존(BASE)·증설후(PROPOSED) 구성. 견적서에 넣지 않는다."""
        return self.txn_type in REFERENCE_TXN

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

@dataclass(frozen=True)
class Quotation:
    """XML 한 건 = 견적서 한 부."""

    groups: tuple[Group, ...] = field(default_factory=tuple)

    def total_amount(self) -> Decimal:
        return sum((g.amount() for g in self.groups), Decimal(0))
