"""Phase 4 — 변환 오케스트레이션, 설정 이관, 옵션 동작."""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

import pytest
from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from quotation import config as config_mod  # noqa: E402
from quotation import paths  # noqa: E402
from quotation.core import convert, xml_reader  # noqa: E402
from quotation.core.pricing import DiscountError  # noqa: E402
from quotation.core.xml_reader import QuotationXmlError  # noqa: E402

SAMPLES = ROOT / "samples"
FS5045 = SAMPLES / "FS5045_260722.xml"
XROIS = SAMPLES / "X-ROIS 통합서버#2.xml"
TODAY = dt.date(2026, 7, 23)


# --- 리소스 ------------------------------------------------------------------

def test_template_ships_with_package():
    assert paths.template_path().is_file(), "템플릿이 패키지에 포함되어야 한다"


# --- 변환 --------------------------------------------------------------------

def test_convert_writes_next_to_xml_by_default(tmp_path):
    xml = tmp_path / "sample.xml"
    xml.write_bytes(FS5045.read_bytes())
    result = convert.convert(xml, today=TODAY)
    assert result.output == tmp_path / "sample.xlsx"
    assert result.output.is_file()
    assert result.group_count == 3
    assert result.sheet_count == 5


def test_convert_honours_out_dir(tmp_path):
    result = convert.convert(FS5045, out_dir=tmp_path, today=TODAY)
    assert result.output.parent == tmp_path


def test_progress_reaches_100(tmp_path):
    seen: list[tuple[int, str]] = []
    convert.convert(FS5045, out_dir=tmp_path, today=TODAY,
                    progress=lambda p, m: seen.append((p, m)))
    assert seen[0][0] < seen[-1][0]
    assert seen[-1][0] == 100
    # 상태 메시지는 원본 프로그램의 문구를 유지한다
    assert seen[-1][1] == "견적서작성을 완료하였습니다."


def test_bad_discount_rejected_before_writing(tmp_path):
    with pytest.raises(DiscountError):
        convert.convert(FS5045, out_dir=tmp_path, discount="10.25", today=TODAY)
    assert not list(tmp_path.iterdir()), "실패 시 산출물이 남으면 안 된다"


def test_bad_xml_reports_original_message(tmp_path):
    bad = tmp_path / "bad.xml"
    bad.write_text("<CFXML><CFData/></CFXML>", encoding="utf-8")
    with pytest.raises(QuotationXmlError, match="Item을 찾을 수 없습니다"):
        convert.convert(bad, out_dir=tmp_path, today=TODAY)


# --- 옵션 --------------------------------------------------------------------

def test_maintenance_is_never_written(tmp_path):
    """유지정비료는 견적서에서 완전히 제외한다 (2026-07-23 결정).

    X-ROIS XML 에는 MaintenanceUnitListPrice 309 와 PriceTerm 'Y' 가 있다.
    파서는 계속 읽지만 견적서 H·I열에는 아무것도 쓰지 않는다.
    """
    quote = xml_reader.parse(XROIS)
    line3000 = next(i for i in quote.groups[1].items if i.line_number == "3000")
    assert line3000.maintenance == 309, "파싱 자체는 그대로여야 한다"

    out = convert.convert(XROIS, out_dir=tmp_path, today=TODAY).output
    wb = load_workbook(out)

    server = wb["SERVER 1"]
    assert server["H51"].value is None
    assert server["I51"].value is None
    assert wb["TOTAL"]["H10"].value is None

    # H열 어디에도 값이나 합계 수식이 없어야 한다
    for sheet in wb.worksheets:
        for row in range(1, 120):
            for col in ("H", "I"):
                value = sheet[f"{col}{row}"].value
                assert value is None or row <= 7, (
                    f"[{sheet.title}] {col}{row} 에 유지정비료가 남아 있다: {value!r}")


def test_quote_number_keeps_user_edits(tmp_path):
    """B2 는 사용자가 템플릿에서 고치는 자리다. 연도만 갱신하고 나머지는 둔다."""
    from openpyxl import load_workbook as lw

    from quotation.core.writer import ibm_writer

    template = tmp_path / "t.xlsx"
    wb = lw(paths.template_path())
    wb["TOTAL"]["B2"] = "NO : Trialinfo-24-007 (담당 박상인)"
    wb.save(template)

    quote = xml_reader.parse(FS5045)
    out = ibm_writer.write(quote, template, tmp_path / "o.xlsx", today=TODAY)
    assert lw(out)["TOTAL"]["B2"].value == "NO : Trialinfo-26-007 (담당 박상인)"


def test_quote_number_untouched_when_format_differs(tmp_path):
    """형식이 다르면 손대지 않는다."""
    from openpyxl import load_workbook as lw

    from quotation.core.writer import ibm_writer

    template = tmp_path / "t.xlsx"
    wb = lw(paths.template_path())
    wb["TOTAL"]["B2"] = "견적번호 2026-A-17"
    wb.save(template)

    quote = xml_reader.parse(FS5045)
    out = ibm_writer.write(quote, template, tmp_path / "o.xlsx", today=TODAY)
    assert lw(out)["TOTAL"]["B2"].value == "견적번호 2026-A-17"


def test_template_lives_outside_the_exe(tmp_path, monkeypatch):
    """템플릿은 EXE 옆의 고칠 수 있는 파일이어야 한다.

    없으면 번들 사본으로 한 번 만들어 준다. 안에 묻어 두면 견적서 번호와
    담당자 이름을 고칠 수 없다.
    """
    monkeypatch.delenv("QUOTATION_TEMPLATE", raising=False)
    monkeypatch.setattr(paths, "app_dir", lambda: tmp_path)

    target = tmp_path / paths.TEMPLATE_NAME
    assert not target.exists()
    assert paths.template_path() == target
    assert target.exists(), "번들 사본으로 자동 생성되어야 한다"

    # 이미 있으면 덮어쓰지 않는다 (사용자 편집 보존)
    target.write_bytes(b"edited")
    assert paths.template_path().read_bytes() == b"edited"


def test_template_env_override(tmp_path, monkeypatch):
    monkeypatch.setenv("QUOTATION_TEMPLATE", str(tmp_path / "custom.xlsx"))
    assert paths.template_path() == tmp_path / "custom.xlsx"


def test_no_discount_leaves_supply_row_blank(tmp_path):
    """골든 2건 모두 공급가 행이 공란이다."""
    out = convert.convert(FS5045, out_dir=tmp_path, today=TODAY).output
    assert load_workbook(out)["TOTAL"]["G21"].value is None


def test_discount_fills_supply_row(tmp_path):
    """할인을 넣으면 총합계에 (1-할인율) 을 곱한 수식을 쓴다.

    ⚠️ 할인 적용 골든이 없어 수식 형태는 미검증이다 (SPEC_CELLMAP.md §7).
    """
    out = convert.convert(FS5045, out_dir=tmp_path, discount="20",
                          today=TODAY).output
    assert load_workbook(out)["TOTAL"]["G21"].value == "=G20*0.8"


# --- 설정 --------------------------------------------------------------------

def test_config_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "app_data_dir", lambda: tmp_path)
    monkeypatch.setattr(paths, "config_path", lambda: tmp_path / "config.json")

    cfg = config_mod.load()
    cfg.discount = "12.5"
    cfg.remember(Path(r"C:\in\a.xml"), Path(r"C:\out\a.xlsx"))
    config_mod.save(cfg)

    again = config_mod.load()
    assert again.discount == "12.5"
    assert again.last_input_dir == r"C:\in"
    assert again.last_output_dir == r"C:\out"
    assert again.recent_files == [r"C:\in\a.xml"]


def test_config_survives_corruption(tmp_path, monkeypatch):
    path = tmp_path / "config.json"
    monkeypatch.setattr(paths, "app_data_dir", lambda: tmp_path)
    monkeypatch.setattr(paths, "config_path", lambda: path)
    path.write_text("{ 깨진 JSON", encoding="utf-8")
    assert config_mod.load().discount == ""


def test_legacy_ini_is_migrated(tmp_path, monkeypatch):
    ini = tmp_path / "견적서생성기.ini"
    ini.write_bytes("[Setup]\nDiscount=15.5\n".encode("cp949"))
    monkeypatch.setattr(paths, "app_data_dir", lambda: tmp_path)
    monkeypatch.setattr(paths, "config_path", lambda: tmp_path / "config.json")
    monkeypatch.setattr(paths, "legacy_ini_candidates", lambda: [ini])

    cfg = config_mod.load()
    assert cfg.discount == "15.5"
    assert cfg.migrated_from_ini == str(ini)


def test_recent_files_are_capped(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "app_data_dir", lambda: tmp_path)
    monkeypatch.setattr(paths, "config_path", lambda: tmp_path / "config.json")
    cfg = config_mod.Config()
    for n in range(20):
        cfg.remember(Path(rf"C:\in\{n}.xml"), Path(r"C:\out\x.xlsx"))
    assert len(cfg.recent_files) == config_mod.Config.MAX_RECENT
    assert cfg.recent_files[0] == r"C:\in\19.xml"


# --- CLI ---------------------------------------------------------------------

def test_cli_batch(tmp_path, capsys):
    from quotation.__main__ import main
    code = main([str(FS5045), str(XROIS), "-o", str(tmp_path)])
    assert code == 0
    assert len(list(tmp_path.glob("*.xlsx"))) == 2


def test_cli_reports_failure(tmp_path, capsys):
    from quotation.__main__ import main
    bad = tmp_path / "bad.xml"
    bad.write_text("<CFXML/>", encoding="utf-8")
    assert main([str(bad), "-o", str(tmp_path)]) == 1
    assert "CFData을 찾을수 없습니다" in capsys.readouterr().err
