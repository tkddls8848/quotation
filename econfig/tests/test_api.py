from __future__ import annotations

import json
import threading
from pathlib import Path
from urllib import request

from econfig.api import EConfigApplication, create_server
from econfig.ibm_gateway import EConfigGateway, HttpEConfigGateway
from econfig.mapping import MappingPlan
from econfig.service import ConfigurationService


EXAMPLE = Path(__file__).parents[1] / "examples" / "9080-heu.json"


def load_example() -> dict:
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


class FakeGateway(EConfigGateway):
    def connection_info(self) -> dict:
        return {"configured": True, "mode": "fake", "country": "KR"}

    def generate_cfr(self, plan: MappingPlan) -> dict:
        assert plan.machine_type_model == "9080-HEU"
        return {
            "status": "completed",
            "request_id": plan.request_id,
            "file_name": f"{plan.request_id}.cfr",
            "cfr": "003120260815 IBM GENERATED",
            "ibm": {"applied": [], "unresolved": [], "navigation_events": 0},
            "validation": {"completed": True},
        }


class ScriptedHttpGateway(HttpEConfigGateway):
    def __init__(self) -> None:
        super().__init__("x.y.z")
        self.ended = False

    def get_product_bases(self):
        return {"success": True, "data": {"pb-power": {"id": "pb-power", "name": "POWER", "description": "Power systems"}}}

    def start_session(self, body):
        assert body["product_base_id"] == "pb-power"
        return {"success": True, "data": {"data": {"id": "session-1", "server_url": "https://sbe.invalid/session-1"}}}

    def get_products_catalog(self):
        return {"data": {"partsList": [{"id": "dynamic-9080", "description": "9080 Model HEU"}]}}

    def select_product(self, product_id):
        assert product_id == "dynamic-9080"
        return {"success": True, "data": {}}

    def _drive_wizards(self, server_url, intents):
        assert server_url.endswith("session-1")
        return {"applied": [item.to_dict() for item in intents], "unresolved": [], "navigation_events": 9}

    def get_config_cfr(self):
        return "0031\r\n" + "\r\n".join(
            [
                "08 EDQD        1",
                "08 EDQE        64",
                "08 EMFM        16",
                "08 EC7Q        4",
                "08 EC72        4",
                "08 EN1A        4",
                "08 0265        1",
                "08 2146        1",
                "08 2375        1",
                "08 2377        1",
                "08 EPVT        1",
                "08 9716        1",
                "08 EXA3        1",
            ]
        )

    def _validate_latest_cfr(self, cfr, plan):
        return {"completed": True, "action": "complete", "dialogs_answered": 0}

    def end_session(self):
        self.ended = True
        return {"success": True}


def test_health_and_options_report_quick_config_state() -> None:
    app = EConfigApplication()

    status, health = app.handle("GET", "/health")
    options_status, options = app.handle("GET", "/v1/options")

    assert status == 200
    assert health["ibm"]["configured"] is False
    assert options_status == 200
    assert options["product"]["machine_type_model"] == "9080-HEU"


def test_preview_endpoint_returns_category_and_ibm_layers() -> None:
    status, body = EConfigApplication().handle(
        "POST", "/v1/requests/preview", load_example()
    )

    assert status == 200
    assert body["status"] == "ready_for_ibm"
    assert body["machine_type_model"] == "9080-HEU"
    assert any(item["category"] == "compute" for item in body["category_selections"])
    assert any(item["code"] == "EDQE" for item in body["feature_selections"])


def test_generate_returns_ibm_cfr_and_request_summary() -> None:
    app = EConfigApplication(ConfigurationService(FakeGateway()))

    status, body = app.handle("POST", "/v1/requests/generate", load_example())

    assert status == 200
    assert body["cfr"].startswith("0031")
    assert body["file_name"] == "Q-1180.cfr"
    assert body["request"]["preset"] == "balanced"


def test_generate_without_gateway_is_explicitly_unavailable() -> None:
    status, body = EConfigApplication().handle(
        "POST", "/v1/requests/generate", load_example()
    )

    assert status == 503
    assert body["error"]["code"] == "gateway_not_configured"


def test_http_gateway_orchestration_resolves_dynamic_ids_and_ends_session() -> None:
    gateway = ScriptedHttpGateway()
    service = ConfigurationService(gateway)

    result = service.generate(load_example())

    assert result["status"] == "completed"
    assert result["ibm"]["product_base_id"] == "pb-power"
    assert result["ibm"]["product_id"] == "dynamic-9080"
    assert result["ibm"]["verification"]["verified"] is True
    assert gateway.ended is True


def test_real_http_server_serves_quick_config_ui_and_preview() -> None:
    server = create_server("127.0.0.1", 0, EConfigApplication())
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        with request.urlopen(f"http://{host}:{port}/", timeout=5) as page_response:
            page = page_response.read().decode("utf-8")
        assert page_response.status == 200
        assert "IBM Power Quick Config" in page
        assert "IBM에서 CFR 생성" in page

        payload = json.dumps(load_example(), ensure_ascii=False).encode("utf-8")
        req = request.Request(
            f"http://{host}:{port}/v1/requests/preview",
            data=payload,
            method="POST",
            headers={"Content-Type": "application/json; charset=utf-8"},
        )
        with request.urlopen(req, timeout=5) as response:
            body = json.loads(response.read().decode("utf-8"))
        assert response.status == 200
        assert body["status"] == "ready_for_ibm"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

