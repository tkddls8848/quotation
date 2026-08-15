from __future__ import annotations

import base64
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterator, Mapping, Sequence
from urllib import error, parse, request

from .errors import GatewayConfigurationError, GatewayRequestError
from .mapping import MappingPlan, WizardIntent


DEFAULT_BASE_URL = "https://www.ibm.com/services/econfigcloud/api"
ID_FIELDS = ("id", "uid", "product_id", "productBaseId", "product_base_id", "server_id")


@dataclass(frozen=True)
class EConfigIdentity:
    user_name: str = "SYSTEM"
    user_type: str = "business-partner"
    user_country: str = "KR"
    user_role: str = "business-partner"
    navigator_language: str = "ko-KR"


class EConfigGateway:
    def connection_info(self) -> dict[str, Any]:
        return {"configured": True, "mode": "test-double"}

    def generate_cfr(self, plan: MappingPlan) -> dict[str, Any]:
        raise NotImplementedError


class HttpEConfigGateway(EConfigGateway):
    """Drive the same stateful endpoints used by the eConfig Cloud web client.

    IBM does not publish this as a stable public API.  All identifiers are therefore
    discovered from the active product base, catalog and wizard instead of being fixed
    in source code.  Failures include the unresolved semantic intent, never the JWT.
    """

    def __init__(
        self,
        jwt: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        identity: EConfigIdentity | None = None,
        encode_body: bool = False,
        timeout_seconds: float = 90.0,
        product_base_id: str = "",
        geography: str = "AP",
        keep_session: bool = False,
    ) -> None:
        if not jwt.strip():
            raise GatewayConfigurationError("IBM_ECONFIG_JWT가 설정되지 않았습니다.")
        self._jwt = jwt.strip()
        self.base_url = base_url.rstrip("/")
        self.identity = identity or EConfigIdentity()
        self.encode_body = encode_body
        self.timeout_seconds = timeout_seconds
        self.product_base_id = product_base_id.strip()
        self.geography = geography
        self.keep_session = keep_session

    @classmethod
    def from_environment(cls) -> "HttpEConfigGateway":
        jwt = os.environ.get("IBM_ECONFIG_JWT", "")
        claims = _jwt_subject(jwt)
        identity = EConfigIdentity(
            user_name=os.environ.get("IBM_ECONFIG_USER_NAME", _claim_name(claims)),
            user_type=os.environ.get("IBM_ECONFIG_USER_TYPE", str(claims.get("type", "business-partner"))),
            user_country=os.environ.get("IBM_ECONFIG_USER_COUNTRY", str(claims.get("country", "KR"))),
            user_role=os.environ.get(
                "IBM_ECONFIG_USER_ROLE",
                str(claims.get("latestRole") or _first(claims.get("roles")) or "business-partner"),
            ),
            navigator_language=os.environ.get("IBM_ECONFIG_LANGUAGE", "ko-KR"),
        )
        claim_encode = bool(claims.get("encodeBody", False))
        encode_body = _env_bool("IBM_ECONFIG_ENCODE_BODY", claim_encode)
        return cls(
            jwt,
            base_url=os.environ.get("IBM_ECONFIG_BASE_URL", DEFAULT_BASE_URL),
            identity=identity,
            encode_body=encode_body,
            timeout_seconds=float(os.environ.get("IBM_ECONFIG_TIMEOUT_SECONDS", "90")),
            product_base_id=os.environ.get("IBM_ECONFIG_PRODUCT_BASE_ID", ""),
            geography=os.environ.get("IBM_ECONFIG_GEOGRAPHY", "AP"),
            keep_session=_env_bool("IBM_ECONFIG_KEEP_SESSION", False),
        )

    def connection_info(self) -> dict[str, Any]:
        return {
            "configured": True,
            "mode": "ibm-econfig-cloud",
            "base_url": self.base_url,
            "country": self.identity.user_country,
            "role": self.identity.user_role,
            "body_encoding": self.encode_body,
            "product_base_override": bool(self.product_base_id),
        }

    def generate_cfr(self, plan: MappingPlan) -> dict[str, Any]:
        product_base = self._resolve_product_base(self.get_product_bases())
        product_base_id = self.product_base_id or _item_id(product_base)
        if not product_base_id:
            raise GatewayRequestError(
                "IBM product base ID를 찾지 못했습니다.", details={"product_base": _safe_summary(product_base)}
            )

        session: Mapping[str, Any] | None = None
        session_id = ""
        server_url = ""
        trace: dict[str, Any] = {
            "product_base_id": product_base_id,
            "product_id": "",
            "session_id": "",
            "applied": [],
            "unresolved": [],
            "navigation_events": 0,
        }
        try:
            session = self.start_session(
                {
                    "product_base_id": product_base_id,
                    "role": self.identity.user_role,
                    "origin": "CONFIG_STARTER",
                    "beopt_date": datetime.now().strftime("%Y%m%d"),
                    "is_upgrade": False,
                    "is_restore": False,
                    "repository_id": "",
                    "cpq_folder_id": "",
                    "lms_cart_id": "",
                    "ce_id_list": "",
                    "trace_status": "",
                    "existing_session_id": "",
                    "appVersion": "v2",
                }
            )
            session_data = _deep_data(session)
            session_id = str(session_data.get("id", ""))
            server_url = str(session_data.get("server_url", "")).rstrip("/")
            if not session_id or not server_url:
                raise GatewayRequestError(
                    "IBM eConfig 세션 응답에 id 또는 server_url이 없습니다.",
                    details={"response": _safe_summary(session)},
                )
            trace["session_id"] = session_id

            catalog = self.get_products_catalog()
            product = self._resolve_product(catalog, plan.machine_type_model)
            product_id = _item_id(product)
            if not product_id:
                raise GatewayRequestError(
                    f"IBM catalog에서 {plan.machine_type_model} product ID를 찾지 못했습니다.",
                    details={"candidate": _safe_summary(product)},
                )
            trace["product_id"] = product_id
            self.select_product(product_id)

            drive = self._drive_wizards(server_url, plan.wizard_intents)
            trace.update(drive)

            cfr = self.get_config_cfr()
            validation = self._validate_latest_cfr(cfr, plan)
            if validation.get("completed"):
                cfr = self.get_config_cfr()

            verification = _verify_cfr(cfr, plan)
            trace["verification"] = verification
            unresolved_required = [
                item for item in drive["unresolved"] if item.get("section") in {"machine", "processor", "memory", "storage", "network", "fibre-channel"}
            ]
            if unresolved_required and not verification["verified"]:
                raise GatewayRequestError(
                    "IBM wizard에 일부 필수 선택을 적용하지 못했습니다.",
                    details={
                        "unresolved": unresolved_required,
                        "verification": verification,
                        "applied": drive["applied"],
                    },
                )

            fully_verified = (
                validation.get("completed")
                and verification["verified"]
                and not verification["missing"]
            )
            return {
                "status": "completed" if fully_verified else "requires_review",
                "request_id": plan.request_id,
                "file_name": _safe_file_name(plan.request_id) + ".cfr",
                "cfr": cfr,
                "ibm": trace,
                "validation": validation,
            }
        finally:
            if session_id and not self.keep_session:
                try:
                    self.end_session()
                except GatewayRequestError:
                    pass

    def get_product_bases(self) -> Mapping[str, Any]:
        return self._require_mapping(self._request("GET", "/ng/productBases"))

    def start_session(self, body: Mapping[str, Any]) -> Mapping[str, Any]:
        return self._require_mapping(self._request("POST", "/session/start", body))

    def get_configuration_list(self) -> Mapping[str, Any]:
        return self._require_mapping(self._request("GET", "/configuration/list"))

    def get_products_catalog(self) -> Mapping[str, Any]:
        return self._require_mapping(self._request("GET", "/products/get_catalog"))

    def select_product(self, product_id: str) -> Mapping[str, Any]:
        path = "/products/selected/" + parse.quote(product_id, safe="")
        return self._require_mapping(self._request("GET", path))

    def send_configuration_event(self, body: Mapping[str, Any]) -> Mapping[str, Any]:
        return self._require_mapping(self._request("POST", "/configuration/event", body))

    def get_config_cfr(self) -> str:
        response = self._request(
            "POST",
            "/cfr/get",
            {
                "user_name": self.identity.user_name,
                "compare_with_original": False,
                "rpo_dif": "",
                "user_timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
                "description": "Generated by quick configuration",
            },
        )
        cfr = _find_cfr(response)
        if not cfr:
            raise GatewayRequestError(
                "IBM /cfr/get 응답에서 CFR 본문을 찾지 못했습니다.",
                details={"response": _safe_summary(response)},
            )
        return cfr

    def end_session(self) -> Mapping[str, Any]:
        return self._require_mapping(self._request("GET", "/session/end"))

    def _drive_wizards(
        self, server_url: str, intents: Sequence[WizardIntent]
    ) -> dict[str, Any]:
        pending = [intent for intent in intents if intent.value not in (0, False, "")]
        applied: list[dict[str, Any]] = []
        navigation_events = 0
        stale_fingerprints: dict[str, int] = {}

        for _ in range(160):
            if not pending:
                break
            wizard = self._current_wizard(server_url)
            if wizard:
                matched = self._find_intent_control(wizard, pending)
                if matched:
                    intent, control = matched
                    event = _control_event(control, intent)
                    self._request_url("POST", f"{server_url}/currentWizard/updateControl", {"controls": [event]})
                    applied.append(
                        {
                            "order": intent.order,
                            "section": intent.section,
                            "feature_code": intent.feature_code,
                            "control": _control_name(control),
                            "value": intent.value,
                        }
                    )
                    pending.remove(intent)
                    continue

                fingerprint = _wizard_fingerprint(wizard)
                stale_fingerprints[fingerprint] = stale_fingerprints.get(fingerprint, 0) + 1
                if stale_fingerprints[fingerprint] > 2:
                    break
                self._request_url(
                    "POST",
                    f"{server_url}/currentWizard/updateControl",
                    {"controls": [_navigation_event(wizard)]},
                )
                navigation_events += 1
                continue

            opened = self._open_matching_wizard(pending)
            if not opened:
                break

        return {
            "applied": applied,
            "unresolved": [intent.to_dict() for intent in pending],
            "navigation_events": navigation_events,
        }

    def _current_wizard(self, server_url: str) -> Any | None:
        try:
            response = self._request_url("GET", f"{server_url}/currentWizard")
        except GatewayRequestError as exc:
            details = exc.details if isinstance(exc.details, Mapping) else {}
            if details.get("status") in {400, 404, 409}:
                return None
            raise
        return _deep_data(response)

    def _find_intent_control(
        self, wizard: Any, pending: Sequence[WizardIntent]
    ) -> tuple[WizardIntent, Mapping[str, Any]] | None:
        controls = [item for _path, item in _walk(wizard) if _looks_like_control(item)]
        best: tuple[int, WizardIntent, Mapping[str, Any]] | None = None
        for intent in pending:
            for control in controls:
                score = _semantic_score(control, intent)
                if score and (best is None or score > best[0]):
                    best = (score, intent, control)
        if best is None:
            return None
        return best[1], best[2]

    def _open_matching_wizard(self, pending: Sequence[WizardIntent]) -> bool:
        response = self.get_configuration_list()
        data = _deep_data(response)
        wizards = data.get("wizards", []) if isinstance(data, Mapping) else []
        if not isinstance(wizards, Sequence) or isinstance(wizards, (str, bytes)):
            return False
        best: tuple[int, Mapping[str, Any], Mapping[str, Any]] | None = None
        for wizard in wizards:
            if not isinstance(wizard, Mapping):
                continue
            actions = wizard.get("actions", [])
            if not isinstance(actions, Sequence):
                continue
            action = next(
                (
                    value
                    for value in actions
                    if isinstance(value, Mapping)
                    and (value.get("sb_default_action_B") or str(value.get("name", "")).lower() == "edit")
                ),
                None,
            )
            if not isinstance(action, Mapping):
                continue
            text = _search_text(wizard)
            score = max((_text_intent_score(text, intent) for intent in pending), default=0)
            if score and (best is None or score > best[0]):
                best = (score, wizard, action)
        if best is None:
            return False
        _score, wizard, action = best
        self.send_configuration_event(
            {
                "wizardID": wizard.get("id"),
                "actionID": action.get("id"),
                "actionName": action.get("name", "Edit"),
            }
        )
        return True

    def _validate_latest_cfr(self, cfr: str, plan: MappingPlan) -> dict[str, Any]:
        body = {
            "CFR": cfr,
            "diff": "[]",
            "geography": self.geography,
            "country": self.identity.user_country,
            "mode": "INITIAL",
            "system_id": "",
            "beopt_date": datetime.now().strftime("%Y%m%d"),
            "trace_status": "",
        }
        response = self._require_mapping(self._request("POST", "/base_edit/validate", body))
        value: Mapping[str, Any] = _deep_data(response)
        dialogs = 0
        while str(value.get("action", "")).lower() == "showdialog" and dialogs < 12:
            answer = _default_dialog_answer(value)
            response = self._require_mapping(
                self._request("POST", "/base_edit/respond_dialog", answer)
            )
            value = _deep_data(response)
            dialogs += 1
        action = str(value.get("action", "")).lower()
        return {
            "completed": action == "complete",
            "action": action or "unknown",
            "dialogs_answered": dialogs,
            "message": str(value.get("message", "")),
            "profile_version": plan.profile_version,
        }

    def _resolve_product_base(self, response: Mapping[str, Any]) -> Mapping[str, Any]:
        data: Any = response.get("data", response)
        candidates: list[Mapping[str, Any]] = []
        if isinstance(data, Mapping):
            for key, value in data.items():
                if isinstance(value, Mapping):
                    item = dict(value)
                    item.setdefault("id", key)
                    candidates.append(item)
        if self.product_base_id:
            for candidate in candidates:
                if _item_id(candidate) == self.product_base_id:
                    return candidate
            return {"id": self.product_base_id, "name": "POWER override"}
        ranked = sorted(
            ((_product_base_score(item), item) for item in candidates),
            key=lambda value: value[0],
            reverse=True,
        )
        if not ranked or ranked[0][0] <= 0:
            raise GatewayRequestError(
                "IBM product base 목록에서 POWER 구성을 찾지 못했습니다.",
                details={"candidates": [_safe_summary(item) for item in candidates[:12]]},
            )
        return ranked[0][1]

    def _resolve_product(self, response: Mapping[str, Any], mtm: str) -> Mapping[str, Any]:
        data = _deep_data(response)
        best: tuple[int, Mapping[str, Any]] | None = None
        wanted = mtm.lower()
        machine_type, model = wanted.split("-", 1)
        for _path, item in _walk(data):
            if not _item_id(item):
                continue
            text = _search_text(item)
            score = 0
            if wanted in text:
                score += 200
            if machine_type in text:
                score += 40
            if re.search(rf"(?<![a-z0-9]){re.escape(model)}(?![a-z0-9])", text):
                score += 60
            if score and (best is None or score > best[0]):
                best = (score, item)
        if best is None:
            raise GatewayRequestError(
                f"IBM product catalog에서 {mtm}을 찾지 못했습니다.",
                details={"catalog_keys": sorted(data) if isinstance(data, Mapping) else []},
            )
        return best[1]

    def _request(
        self, method: str, path: str, body: Mapping[str, Any] | None = None
    ) -> Any:
        return self._request_url(method, f"{self.base_url}/{path.lstrip('/')}", body)

    def _request_url(
        self, method: str, url: str, body: Mapping[str, Any] | None = None
    ) -> Any:
        encoded: bytes | None = None
        if body is not None:
            outgoing: Mapping[str, Any] = body
            if self.encode_body:
                compact = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
                outgoing = {"bodyEncoded": base64.b64encode(compact).decode("ascii")}
            encoded = json.dumps(outgoing, ensure_ascii=False).encode("utf-8")
        req = request.Request(
            url,
            data=encoded,
            method=method,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": f"JWT {self._jwt}",
                "User-Agent": "econfig-quick-config/0.2",
            },
        )
        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as response:
                raw = response.read()
        except error.HTTPError as exc:
            response_body = exc.read().decode("utf-8", errors="replace")
            raise GatewayRequestError(
                f"IBM eConfig가 HTTP {exc.code}을 반환했습니다.",
                details={"status": exc.code, "body": response_body[:2000], "endpoint": _redact_url(url)},
            ) from exc
        except error.URLError as exc:
            raise GatewayRequestError(
                "IBM eConfig에 연결할 수 없습니다.",
                details={"reason": str(exc.reason), "endpoint": _redact_url(url)},
            ) from exc
        try:
            parsed = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise GatewayRequestError(
                "IBM eConfig 응답이 JSON이 아닙니다.",
                details={"body": raw[:1000].decode("utf-8", errors="replace"), "endpoint": _redact_url(url)},
            ) from exc
        if isinstance(parsed, Mapping) and parsed.get("success") is False:
            raise GatewayRequestError(
                str(parsed.get("user_message") or parsed.get("message") or "IBM eConfig 요청이 실패했습니다."),
                details={"response": _safe_summary(parsed), "endpoint": _redact_url(url)},
            )
        return parsed

    @staticmethod
    def _require_mapping(value: Any) -> Mapping[str, Any]:
        if not isinstance(value, Mapping):
            raise GatewayRequestError("IBM eConfig 응답이 object가 아닙니다.")
        return value


def _walk(value: Any, path: str = "$") -> Iterator[tuple[str, Mapping[str, Any]]]:
    if isinstance(value, Mapping):
        yield path, value
        for key, child in value.items():
            yield from _walk(child, f"{path}.{key}")
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, child in enumerate(value):
            yield from _walk(child, f"{path}[{index}]")


def _deep_data(value: Any) -> Any:
    current = value
    for _ in range(4):
        if not isinstance(current, Mapping):
            return current
        child = current.get("data")
        if isinstance(child, Mapping) and len(current) <= 6:
            current = child
            continue
        return current
    return current


def _item_id(item: Mapping[str, Any]) -> str:
    for field in ID_FIELDS:
        value = item.get(field)
        if isinstance(value, (str, int)) and str(value).strip():
            return str(value)
    return ""


def _search_text(item: Mapping[str, Any]) -> str:
    return json.dumps(item, ensure_ascii=False, sort_keys=True, default=str).lower()


def _product_base_score(item: Mapping[str, Any]) -> int:
    text = _search_text(item)
    score = 0
    if str(item.get("name", "")).upper() == "POWER":
        score += 200
    if "power" in text:
        score += 80
    if "9080" in text or "e1080" in text:
        score += 40
    if item.get("special_model") is True:
        score -= 20
    return score


def _looks_like_control(item: Mapping[str, Any]) -> bool:
    return bool(_control_name(item) and item.get("type") and ("id" in item or "ctrl_id_F" in item))


def _control_name(control: Mapping[str, Any]) -> str:
    return str(control.get("componentName") or control.get("component_name") or control.get("name") or "")


def _semantic_score(control: Mapping[str, Any], intent: WizardIntent) -> int:
    name = _control_name(control).lower()
    text = _search_text(control)
    score = 0
    for candidate in intent.semantic_candidates:
        value = candidate.lower()
        if value and name == value:
            score = max(score, 400 + len(value))
        elif value and value in name:
            score = max(score, 300 + len(value))
        elif value and value in text:
            score = max(score, 120 + len(value))
    feature = intent.feature_code.lower()
    if feature and re.search(rf"(?<![a-z0-9]){re.escape(feature)}(?![a-z0-9])", text):
        score = max(score, 80)
    return score


def _text_intent_score(text: str, intent: WizardIntent) -> int:
    score = 0
    for candidate in (*intent.semantic_candidates, intent.section, intent.feature_code):
        value = candidate.lower()
        if value and value in text:
            score = max(score, 20 + len(value))
    return score


def _control_event(control: Mapping[str, Any], intent: WizardIntent) -> dict[str, Any]:
    control_id = control.get("id", control.get("ctrl_id_F", 0))
    control_type = str(control.get("type", ""))
    control_name = _control_name(control)
    kind = _control_kind(control)
    value: Any = intent.value

    if "table" in kind:
        row = _best_option(control, intent)
        row_id = row.get("id") if row else None
        if row_id is None and row:
            row_id = row.get("componentID", row.get("component_id"))
        if row_id is not None:
            value = {"quantity": int(intent.value), "componentID": row_id}
    elif kind in {"dropdown", "listbox", "checklist", "selection"} or isinstance(intent.value, str):
        option = _best_option(control, intent)
        if option:
            value = _option_value(option)
    elif intent.operation == "select" and isinstance(intent.value, bool):
        option = _best_option(control, intent)
        if option:
            value = _option_value(option)

    return {
        "id": control_id,
        "type": control_type,
        "value": value,
        "isDblClick": False,
        "ctl": {
            "id": control_id,
            "name": control_name,
            "label": str(control.get("displayName") or control.get("label") or ""),
            "control": kind,
            "value_desc": str(intent.value),
            "checked": bool(intent.value) if kind in {"checkbox", "checklist"} else False,
        },
    }


def _control_kind(control: Mapping[str, Any]) -> str:
    explicit = str(control.get("control", "")).lower()
    if explicit:
        return explicit
    value = str(control.get("type", "")).lower()
    for needle, kind in (
        ("table", "table"),
        ("dropdown", "dropdown"),
        ("list", "listbox"),
        ("check", "checklist"),
        ("boolean", "checkbox"),
        ("range", "spinner"),
        ("float", "spinner"),
        ("integer", "spinner"),
        ("selection", "selection"),
    ):
        if needle in value:
            return kind
    return "input"


def _best_option(control: Mapping[str, Any], intent: WizardIntent) -> Mapping[str, Any] | None:
    best: tuple[int, Mapping[str, Any]] | None = None
    wanted = str(intent.value).lower()
    for path, option in _walk(control):
        if option is control or not any(key in option for key in ("key", "value", "id", "componentID", "component_id")):
            continue
        text = _search_text(option)
        score = 0
        if wanted and wanted in text:
            score += 100
        for candidate in (*intent.semantic_candidates, intent.feature_code):
            value = candidate.lower()
            if value and value in text:
                score += 60 + len(value)
        if "option" in path.lower() or "column" in path.lower() or "row" in path.lower():
            score += 10
        if score and (best is None or score > best[0]):
            best = (score, option)
    return best[1] if best else None


def _option_value(option: Mapping[str, Any]) -> Any:
    for key in ("key", "id", "componentID", "component_id", "value"):
        value = option.get(key)
        if value not in (None, "") and not isinstance(value, Mapping):
            return value
    return True


def _navigation_event(wizard: Any) -> dict[str, Any]:
    text = json.dumps(wizard, ensure_ascii=False, default=str)
    if "Finish_Control" in text:
        return {
            "id": 1,
            "type": "Finish_Control",
            "value": "Finish_Control",
            "ctl": {"id": 2, "control": "button", "label": "Finish_Control", "name": "Finish_Control", "value_desc": "Finish"},
        }
    return {
        "id": 2,
        "type": "OK_Control",
        "value": "OK_Control",
        "ctl": {"id": 2, "control": "button", "label": "OK_Control", "name": "OK_Control", "value_desc": "OK"},
    }


def _wizard_fingerprint(wizard: Any) -> str:
    if not isinstance(wizard, Mapping):
        return str(type(wizard))
    names = [_control_name(item) for _path, item in _walk(wizard) if _looks_like_control(item)]
    return "|".join(names[:30]) + ":" + str(wizard.get("currentPanelIndex", ""))


def _default_dialog_answer(value: Mapping[str, Any]) -> dict[str, Any]:
    dialog = value.get("dialog", value)
    answer: Any = True
    if isinstance(dialog, Mapping):
        options = dialog.get("options")
        if isinstance(options, Sequence) and not isinstance(options, (str, bytes)) and options:
            first = next((item for item in options if not isinstance(item, Mapping) or item.get("enabled", True)), options[0])
            answer = _option_value(first) if isinstance(first, Mapping) else first
        elif "default" in dialog:
            answer = dialog["default"]
    return {"answer": answer, "origin": value.get("origin", "SBENGINE")}


def _find_cfr(value: Any) -> str:
    if isinstance(value, str):
        return value if value.startswith(("0031", "0020")) else ""
    if isinstance(value, Mapping):
        for key in ("cfr", "CFR", "source_file", "sourceFile", "output_file"):
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate.startswith(("0031", "0020")):
                return candidate
        for child in value.values():
            candidate = _find_cfr(child)
            if candidate:
                return candidate
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for child in value:
            candidate = _find_cfr(child)
            if candidate:
                return candidate
    return ""


def _verify_cfr(cfr: str, plan: MappingPlan) -> dict[str, Any]:
    expected: list[dict[str, Any]] = []
    verified: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    for feature in plan.feature_selections:
        if feature.code in {"9080-HEU", "EM26"}:
            continue
        item = {"code": feature.code, "quantity": feature.quantity}
        expected.append(item)
        match = re.search(rf"(?<![A-Z0-9]){re.escape(feature.code)}\s+0*{feature.quantity}(?!\d)", cfr)
        if match:
            verified.append(item)
        else:
            missing.append(item)
    essential_codes = {"EDQD", "EDQE", "EMFM", "EC7Q", "EC72"}
    if any(item["code"] == "EN1A" for item in expected):
        essential_codes.add("EN1A")
    essential_missing = [item for item in missing if item["code"] in essential_codes]
    return {
        "verified": not essential_missing,
        "checked": len(expected),
        "matched": len(verified),
        "missing": missing,
        "essential_missing": essential_missing,
    }


def _safe_summary(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _safe_summary(child)
            for key, child in list(value.items())[:20]
            if str(key).lower() not in {"authorization", "jwt", "token", "refresh_token"}
        }
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_safe_summary(child) for child in list(value)[:12]]
    if isinstance(value, str) and len(value) > 300:
        return value[:300] + "…"
    return value


def _safe_file_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip(".-")
    return cleaned or "configuration"


def _redact_url(url: str) -> str:
    parsed = parse.urlsplit(url)
    return parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))


def _jwt_subject(jwt: str) -> Mapping[str, Any]:
    try:
        payload = jwt.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        decoded = json.loads(base64.urlsafe_b64decode(payload).decode("utf-8"))
        subject = decoded.get("sub", {}) if isinstance(decoded, Mapping) else {}
        return subject if isinstance(subject, Mapping) else {}
    except (IndexError, ValueError, UnicodeDecodeError, json.JSONDecodeError):
        return {}


def _claim_name(claims: Mapping[str, Any]) -> str:
    first_name = str(claims.get("firstName", "")).strip()
    last_name = str(claims.get("lastName", "")).strip()
    return (first_name + " " + last_name).strip() or "SYSTEM"


def _first(value: Any) -> Any:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)) and value:
        return value[0]
    return None


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}
