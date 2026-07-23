"""IBM 견적서 생성 — SPEC_CELLMAP.md §2~§5.

원본 VB6 의 MakeServerSheet / MakeTotalSheet / DecorateTOTSheet / WriteExcel 을
대체한다. Excel 프로세스를 전혀 사용하지 않는다 (openpyxl 파일 조작만).

처리 순서가 중요하다.
    1) 값 기록      2) 장식(decorate)      3) 병합
병합을 먼저 하면 openpyxl 이 덮인 셀의 스타일을 버려 장식이 어긋난다.
"""
from __future__ import annotations

import datetime as dt
from copy import copy
from decimal import Decimal
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.styles import Alignment, Font
from openpyxl.workbook import Workbook
from openpyxl.worksheet.worksheet import Worksheet

from ..models import Group, LineItem, Quotation
from ..money import NO_CHARGE, Amount, is_priced
from .decorate import Layout, decorate

SHEET_TOTAL = "TOTAL"
SHEET_TEMPLATE = "template"

FIRST_DATA_ROW = 8
TRAILER_ROWS = 2

# --- 라벨 (공백 개수까지 원본과 동일해야 한다) ----------------------------------
LBL_SUBTOTAL = "합                   계"
LBL_HW_TOTAL = "합                   계(HardWare)"
LBL_SW_TOTAL = "합                   계(SoftWare)"
LBL_GRAND = "총        합       계"
LBL_SUPPLY = "공        급       가"
LBL_HW = "H/W"
LBL_SW = "S/W"

# --- 서식 --------------------------------------------------------------------
FMT_TEXT = "@"
FMT_TOTAL_NUM = "#,##0_);[Red]\\(#,##0\\)"
FMT_DETAIL_NUM = '_-* #,##0_-;\\-* #,##0_-;_-* "-"_-;_-@_-'
FMT_DETAIL_MA = "#,##0_ "

FONT_DATA = Font(name="Tahoma", size=9)
FONT_DATA_BOLD = Font(name="Tahoma", size=9, bold=True)
FONT_LABEL = Font(name="돋움", size=9, bold=True)
# 원본 EXE 문자열의 "Tahoma" / "HY헤드라인M" 이 이 두 셀을 가리킨다.
# 템플릿은 정반대(C1=HY헤드라인M, C3=Tahoma/10)이므로 반드시 덮어써야 한다.
FONT_TITLE = Font(name="Tahoma", size=18, bold=True)
FONT_DATE = Font(name="HY헤드라인M", size=9)

LEFT = Alignment(horizontal="left")
CENTER = Alignment(horizontal="center", vertical="center")
CENTER_WRAP = Alignment(horizontal="center", vertical="center", wrap_text=True)
RIGHT = Alignment(horizontal="right", vertical="center")
GENERAL = Alignment(vertical="center")


def _put(ws: Worksheet, coord: str, value, *, fmt: str | None = None,
         align: Alignment | None = None, font: Font | None = None,
         bold: bool | None = None):
    """셀 기록. font 를 주지 않으면 템플릿 글꼴을 유지하고 bold 만 조정한다."""
    cell = ws[coord]
    cell.value = value
    if fmt is not None:
        cell.number_format = fmt
    if align is not None:
        cell.alignment = align
    if font is not None:
        cell.font = font
    elif bold is not None:
        kept = copy(cell.font)
        kept.b = bold
        cell.font = kept
    return cell


def _num(value: Decimal):
    """Decimal -> Excel 수치. 정수는 int 로 써야 골든과 일치한다."""
    if value == value.to_integral_value():
        return int(value)
    return float(value)


def _amount_cell(ws: Worksheet, coord: str, amount: Amount, fmt: str):
    if amount is NO_CHARGE:
        _put(ws, coord, "N/C", fmt=fmt, font=FONT_DATA)
    elif is_priced(amount):
        _put(ws, coord, _num(amount), fmt=fmt, font=FONT_DATA)


def _merge(pending: list[str], col: str, top: int, bottom: int):
    if bottom > top:
        pending.append(f"{col}{top}:{col}{bottom}")


def _merge_across(pending: list[str], left: str, right: str, row: int):
    pending.append(f"{left}{row}:{right}{row}")


# --- TOTAL 시트 ---------------------------------------------------------------

def _write_total_sheet(ws: Worksheet, quote: Quotation, today: dt.date,
                       discount: Decimal, with_ma: bool):
    merges: list[str] = []
    lay = Layout(first_row=FIRST_DATA_ROW)

    _put(ws, "B2", f"NO : Trialinfo-{today:%y}-", align=LEFT)
    _put(ws, "C3", today.isoformat(), fmt=FMT_TEXT, align=LEFT, font=FONT_DATE)

    row = FIRST_DATA_ROW
    subtotal_rows: list[int] = []

    for group in quote.groups:
        group_start = row

        for kind, items in group.sections():
            sec_start = row
            for item in items:
                _put(ws, f"C{row}", item.part_number, fmt=FMT_TEXT, font=FONT_DATA)
                _put(ws, f"D{row}", item.description, font=FONT_DATA)
                _put(ws, f"E{row}", item.quantity, font=FONT_DATA)
                if kind != "Hardware":
                    lay.blue_rows.append(row)
                row += 1
            sec_end = row - 1

            amount = sum((i.amount() for i in items), Decimal(0))
            if amount != 0:
                _put(ws, f"F{sec_start}", f"=G{sec_start}/E{sec_start}",
                     fmt=FMT_TOTAL_NUM, font=FONT_DATA)
                _put(ws, f"G{sec_start}", _num(amount),
                     fmt=FMT_TOTAL_NUM, font=FONT_DATA)
            _merge(merges, "F", sec_start, sec_end)
            _merge(merges, "G", sec_start, sec_end)

        group_end = row - 1

        maintenance = group.maintenance_amount()
        if with_ma and maintenance != 0:
            _put(ws, f"H{group_start}", _num(maintenance),
                 fmt=FMT_TOTAL_NUM, font=FONT_DATA)
        _merge(merges, "H", group_start, group_end)

        _put(ws, f"C{row}", LBL_SUBTOTAL, fmt=FMT_TEXT, font=FONT_LABEL)
        _merge_across(merges, "C", "F", row)
        _put(ws, f"G{row}", f"=SUM(G{group_start}:G{group_end})",
             fmt=FMT_TOTAL_NUM, font=FONT_DATA_BOLD)
        _put(ws, f"H{row}", f"=SUM(H{group_start}:H{group_end})",
             fmt=FMT_TOTAL_NUM, font=FONT_DATA_BOLD)
        subtotal_rows.append(row)
        lay.cf_rows.append(row)
        lay.cyan_rows.append(row)

        _put(ws, f"B{group_start}", group.item_key, align=CENTER_WRAP,
             font=FONT_DATA_BOLD)
        _merge(merges, "B", group_start, row)
        lay.bands.append((group_start, row))
        row += 1

    _write_footer(ws, row, subtotal_rows, FMT_TOTAL_NUM, merges, lay,
                  ma_fmt=FMT_TOTAL_NUM, discount=discount)
    return merges, lay


# --- 상세 시트 ----------------------------------------------------------------

def _write_detail_sheet(ws: Worksheet, group: Group, today: dt.date,
                        discount: Decimal, with_ma: bool):
    merges: list[str] = []
    lay = Layout(first_row=FIRST_DATA_ROW, fix_header_bottom=True,
                 blue_includes_label=True, top_black=True)

    _put(ws, "C1", f"({group.sheet_name})", fmt=FMT_TEXT, align=CENTER_WRAP,
         font=FONT_TITLE)
    _put(ws, "C3", today.isoformat(), fmt=FMT_TEXT, align=LEFT, font=FONT_DATE)

    row = FIRST_DATA_ROW
    section_total_rows: list[int] = []

    for kind, items in group.sections():
        sec_start = row
        is_hw = kind == "Hardware"
        block_rows: list[int] = []

        for item in items:
            block_start = row
            row = _write_item_block(ws, item, row, is_hw, with_ma, lay)
            if is_hw:
                # H/W 만 블록별 합계행을 가진다. 서브라인이 없으면 스페이서 1행.
                last = max(row - 1, block_start + 1)
                if last >= row:
                    lay.spacer_rows.extend(range(row, last + 1))
                row = last + 1
                _put(ws, f"C{row}", LBL_SUBTOTAL, fmt=FMT_TEXT, font=FONT_LABEL)
                _merge_across(merges, "C", "F", row)
                _put(ws, f"G{row}", f"=SUM(G{block_start}:G{last})",
                     fmt=FMT_DETAIL_NUM, font=FONT_DATA)
                _put(ws, f"H{row}", f"=SUM(H{block_start}:H{last})",
                     fmt=FMT_DETAIL_MA, font=FONT_DATA)
                block_rows.append(row)
                lay.cf_rows.append(row)
                lay.yellow_rows.append(row)
                row += 1

        _put(ws, f"C{row}", LBL_HW_TOTAL if is_hw else LBL_SW_TOTAL,
             fmt=FMT_TEXT, font=FONT_LABEL)
        _merge_across(merges, "C", "F", row)
        if is_hw:
            _put(ws, f"G{row}", f"=SUM({','.join(f'G{r}' for r in block_rows)})",
                 fmt=FMT_DETAIL_NUM, font=FONT_DATA)
            _put(ws, f"H{row}",
                 f"=SUM({','.join(f'H{r}' for r in block_rows)})",
                 fmt=FMT_DETAIL_MA, font=FONT_DATA)
        else:
            # S/W 는 블록별 합계 없이 구간 전체를 한 번에 더한다
            _put(ws, f"G{row}", f"=SUM(G{sec_start}:G{row - 1})",
                 fmt=FMT_DETAIL_NUM, font=FONT_DATA)
        section_total_rows.append(row)
        lay.cf_rows.append(row)
        lay.cyan_rows.append(row)

        _put(ws, f"B{sec_start}", LBL_HW if is_hw else LBL_SW, align=CENTER,
             font=FONT_DATA_BOLD)
        _merge(merges, "B", sec_start, row)
        lay.bands.append((sec_start, row))
        lay.yellow_labels.append(sec_start)
        if not is_hw:
            lay.blue_rows.extend(range(sec_start, row + 1))
        row += 1

    _write_footer(ws, row, section_total_rows, FMT_DETAIL_NUM, merges, lay,
                  ma_fmt=FMT_DETAIL_MA, discount=discount)
    return merges, lay


def _write_item_block(ws: Worksheet, item: LineItem, row: int, is_hw: bool,
                      with_ma: bool, lay: Layout) -> int:
    base = row
    _put(ws, f"C{row}", item.part_number, fmt=FMT_TEXT, font=FONT_DATA)
    _put(ws, f"D{row}", item.description, font=FONT_DATA)
    _put(ws, f"E{row}", item.quantity, font=FONT_DATA)
    _amount_cell(ws, f"F{row}", item.unit_price, FMT_DETAIL_NUM)
    _write_g(ws, row, item.unit_price)
    if with_ma and is_priced(item.maintenance):
        _put(ws, f"H{row}", _num(item.maintenance), fmt=FMT_DETAIL_MA,
             font=FONT_DATA)
        if item.maintenance_term:
            _put(ws, f"I{row}", item.maintenance_term, font=FONT_DATA)
            lay.i_filled_rows.append(row)
    row += 1

    for sub in item.subs:
        _put(ws, f"C{row}", sub.part_number, fmt=FMT_TEXT, font=FONT_DATA)
        _put(ws, f"D{row}", sub.description, font=FONT_DATA)
        _put(ws, f"E{row}", _sub_quantity(sub.quantity, base, item, is_hw), font=FONT_DATA)
        _amount_cell(ws, f"F{row}", sub.unit_price, FMT_DETAIL_NUM)
        _write_g(ws, row, sub.unit_price)
        if with_ma and is_priced(sub.maintenance):
            _put(ws, f"H{row}", _num(sub.maintenance), fmt=FMT_DETAIL_MA,
                 font=FONT_DATA)
        row += 1

    return row


def _sub_quantity(quantity: int, base: int, item: LineItem, is_hw: bool):
    """서브라인 수량 셀. 골든이 세 형태를 쓴다 (SPEC_CELLMAP.md §4.5).

        H/W + 기준행에 가격 있음 -> "=8*E8"   부모 수량 상대 참조
        H/W + 기준행이 N/C       -> "=1"      참조 없는 수식
        S/W                      -> 1         상수
    """
    if not is_hw:
        return quantity
    if is_priced(item.unit_price):
        return f"={quantity}*E{base}"
    return f"={quantity}"


def _write_g(ws: Worksheet, row: int, price: Amount):
    if price is NO_CHARGE:
        _put(ws, f"G{row}", "N/C", fmt=FMT_DETAIL_NUM, font=FONT_DATA)
    elif is_priced(price):
        _put(ws, f"G{row}", f"=E{row}*F{row}", fmt=FMT_DETAIL_NUM,
             font=FONT_DATA)


# --- 공통 꼬리말 --------------------------------------------------------------

def _write_footer(ws: Worksheet, row: int, subtotal_rows: list[int], fmt: str,
                  merges: list[str], lay: Layout, *, ma_fmt: str,
                  discount: Decimal):
    _put(ws, f"B{row}", LBL_GRAND, align=CENTER, font=FONT_LABEL)
    _merge_across(merges, "B", "F", row)
    if len(subtotal_rows) == 1:
        g_formula = f"=G{subtotal_rows[0]}"
        h_formula = f"=H{subtotal_rows[0]}"
    else:
        g_formula = f"=SUM({','.join(f'G{r}' for r in subtotal_rows)})"
        h_formula = f"=SUM({','.join(f'H{r}' for r in subtotal_rows)})"
    _put(ws, f"G{row}", g_formula, fmt=fmt, font=FONT_DATA_BOLD)
    _put(ws, f"H{row}", h_formula, fmt=ma_fmt, align=GENERAL,
         font=FONT_DATA_BOLD)
    lay.grand_row = row
    lay.bf_rows.append(row)
    grand_row = row
    row += 1

    _put(ws, f"B{row}", LBL_SUPPLY, align=CENTER, font=FONT_LABEL)
    _merge_across(merges, "B", "F", row)
    # 할인이 없으면 공급가는 공란이다 (골든 2건 모두 그러하다).
    # ⚠️ 할인 적용 골든이 없어 이 수식은 미검증이다 (SPEC_CELLMAP.md §7).
    if discount:
        rate = (Decimal(1) - discount / Decimal(100)).normalize()
        _put(ws, f"G{row}", f"=G{grand_row}*{rate}", fmt=fmt, align=GENERAL,
             font=FONT_DATA_BOLD)
        _put(ws, f"H{row}", f"=H{grand_row}*{rate}", fmt=ma_fmt, align=GENERAL,
             font=FONT_DATA_BOLD)
    lay.supply_row = row
    lay.bf_rows.append(row)
    row += 1

    merges.append(f"B{row}:H{row + TRAILER_ROWS - 1}")
    ws.print_area = f"$A$1:$H${row + TRAILER_ROWS - 1}"


# --- 진입점 ------------------------------------------------------------------

def _finish(ws: Worksheet, merges: list[str], lay: Layout) -> None:
    """장식 후 병합. 순서를 지켜야 골든과 같아진다."""
    decorate(ws, lay)
    for ref in merges:
        ws.merge_cells(ref)


def build(quote: Quotation, template: str | Path,
          *, today: dt.date | None = None, discount: Decimal = Decimal(0),
          include_maintenance: bool = True) -> Workbook:
    today = today or dt.date.today()
    wb = load_workbook(template)

    total_ws = wb[SHEET_TOTAL]
    template_ws = wb[SHEET_TEMPLATE]

    # 템플릿의 H7('DESCRIPTION') 을 지우고 H6:H7 을 병합한다. 복사 전에 해야
    # 상세 시트와 잔존 template 시트가 모두 골든과 같아진다.
    template_ws["H7"].value = None
    template_ws.merge_cells("H6:H7")

    _finish(total_ws, *_write_total_sheet(total_ws, quote, today, discount,
                                          include_maintenance))

    details = []
    for group in quote.groups:
        ws = wb.copy_worksheet(template_ws)
        ws.title = group.sheet_name
        _finish(ws, *_write_detail_sheet(ws, group, today, discount,
                                         include_maintenance))
        details.append(ws)

    template_ws.sheet_state = "hidden"
    wb._sheets = [total_ws, *details, template_ws]
    return wb


def write(quote: Quotation, template: str | Path, out_path: str | Path,
          *, today: dt.date | None = None, discount: Decimal = Decimal(0),
          include_maintenance: bool = True) -> Path:
    wb = build(quote, template, today=today, discount=discount,
               include_maintenance=include_maintenance)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)
    return out
