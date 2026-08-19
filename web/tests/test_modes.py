"""변환 모드가 화면에서 코어까지 끊기지 않고 닿는지 (UNIX / 통합).

모드는 견적 내용이 아니라 설정이므로 구조화 로그에 남긴다 (계획서 §13).
"""
from __future__ import annotations

import datetime as dt
from io import BytesIO

import pytest
from openpyxl import load_workbook

import api
import conversion_adapter
import errors

TODAY = dt.date(2026, 8, 19)


def _convert(fixtures, template_bytes, name="integrated_quote.xml", **kwargs):
    upload = api.Upload(filename=name, content=(fixtures / name).read_bytes(),
                        content_type="text/xml")
    params = dict(template_bytes=template_bytes, template_version="v-test",
                  deployment_version="d-test", request_id="req-1", today=TODAY)
    params.update(kwargs)
    return api.convert_response([upload], **params)


def _sheets(response) -> list[str]:
    return load_workbook(BytesIO(response.body)).sheetnames


# --- 기본값 -------------------------------------------------------------------

def test_missing_mode_stays_on_the_unix_path(fixtures, template_bytes):
    """모드를 안 보내는 예전 클라이언트도 지금까지와 같이 돈다."""
    res = _convert(fixtures, template_bytes)
    assert res.status == 200
    assert res.log["mode"] == "unix"


def test_empty_mode_is_the_default(fixtures, template_bytes):
    assert _convert(fixtures, template_bytes, mode="").log["mode"] == "unix"


# --- 모드가 실제로 갈리는지 ------------------------------------------------------

def test_unix_mode_collides_on_the_repeated_model(fixtures, template_bytes):
    res = _convert(fixtures, template_bytes, mode="unix")
    assert res.status == 200
    # 같은 이름 두 장이라 openpyxl 이 뒤에 숫자를 붙인다 — 고치려는 그 증상이다
    assert _sheets(res)[1:3] == ["SAMPLESYSTEM SX100 V4-3YR BASE",
                                 "SAMPLESYSTEM SX100 V4-3YR BASE1"]


def test_integrated_mode_names_each_server(fixtures, template_bytes):
    res = _convert(fixtures, template_bytes, mode="integrated")
    assert res.status == 200
    assert res.log["mode"] == "integrated"
    assert _sheets(res) == ["TOTAL", "백업서버_1식", "메일-스펨_2식",
                            "SAMPLE 42U DEEP STATIC RACK", "template"]


def test_integrated_mode_does_not_double_count(fixtures, template_bytes):
    total = load_workbook(BytesIO(
        _convert(fixtures, template_bytes, mode="integrated").body))["TOTAL"]
    assert total["G8"].value == 40172000   # 본체 LP 하나가 그 서버의 전체 금액
    assert total["G9"].value is None       # S/W·서비스는 금액을 더하지 않는다


# --- 잘못된 값 ----------------------------------------------------------------

def test_unknown_mode_is_a_bad_request(fixtures, template_bytes):
    res = _convert(fixtures, template_bytes, mode="lenovo")
    assert res.status == 400
    assert res.json()["error"]["code"] == errors.INVALID_REQUEST


def test_adapter_rejects_unknown_modes():
    with pytest.raises(errors.ApiError) as caught:
        conversion_adapter.normalize_mode("x86")
    assert caught.value.code == errors.INVALID_REQUEST


def test_adapter_publishes_the_mode_list():
    assert conversion_adapter.DEFAULT_MODE in conversion_adapter.MODES
    assert set(conversion_adapter.MODES) == {"unix", "integrated"}


# --- 배선 (화면 -> 파이썬) -------------------------------------------------------

def test_browser_entry_takes_the_mode(web_src):
    """`entry.convert` 다섯째 인수가 모드다. engine.js 가 그 자리로 넘긴다."""
    entry = (web_src.parent / "browser" / "entry.py").read_text(encoding="utf-8")
    assert 'mode: str = ""' in entry
    assert "mode=mode," in entry

    engine = (web_src.parent / "frontend" / "src" / "engine.js").read_text(
        encoding="utf-8")
    assert "upload.mode ?? ''," in engine


def test_worker_reads_the_mode_field_with_the_sdk_name(web_src):
    """SDK 의 FormData 는 `get_all` 만 확인된 이름이다 (incidents/0001)."""
    body = (web_src / "worker.py").read_text(encoding="utf-8")
    assert 'form.get_all("mode")' in body
    assert 'form.get("mode")' not in body
    assert "mode=mode," in body


def test_the_screen_offers_exactly_the_python_modes():
    """화면의 토글 값과 파이썬 모드 목록이 어긋나면 400 이 난다."""
    from pathlib import Path

    html = (Path(__file__).resolve().parents[1] / "frontend" / "index.html"
            ).read_text(encoding="utf-8")
    for mode in conversion_adapter.MODES:
        assert f'name="mode" value="{mode}"' in html
    assert html.count('name="mode"') == len(conversion_adapter.MODES)
    assert f'value="{conversion_adapter.DEFAULT_MODE}" checked' in html
