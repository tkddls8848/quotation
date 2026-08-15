from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from econfig.errors import InputValidationError
from econfig.ibm_gateway import _control_event, _verify_cfr
from econfig.mapping import WizardIntent, map_quick_configuration
from econfig.models import QuickConfiguration
from econfig.profiles import option_catalog


EXAMPLE = Path(__file__).parents[1] / "examples" / "9080-heu.json"


def load_example() -> dict:
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


def feature_quantities(plan) -> dict[str, int]:
    return {item.code: item.quantity for item in plan.feature_selections}


def test_catalog_exposes_business_facing_presets_and_categories() -> None:
    catalog = option_catalog()

    assert {item["id"] for item in catalog["presets"]} == {
        "starter",
        "balanced",
        "performance",
    }
    assert {item["id"] for item in catalog["categories"]} >= {
        "compute",
        "memory",
        "ethernet",
        "fibre_channel",
    }


def test_quick_choices_expand_to_expected_ibm_intents() -> None:
    spec = QuickConfiguration.from_dict(load_example())
    plan = map_quick_configuration(spec)

    quantities = feature_quantities(plan)
    assert quantities["EDQE"] == 64
    assert quantities["EMFM"] == 16
    assert quantities["EM26"] == 2
    assert quantities["EC7Q"] == 4
    assert quantities["EC72"] == 4
    assert quantities["EN1A"] == 4
    assert plan.resolved_requirements["activated_memory_gb"] == 1024
    assert plan.category_selections


@pytest.mark.parametrize(
    ("change", "expected_path"),
    [
        (("preset", None, "unknown"), "preset"),
        (("country", None, "US"), "country"),
        (("selections", "compute", "128-cores"), "selections.compute"),
        (("selections", "mystery", "x"), "selections.mystery"),
    ],
)
def test_invalid_quick_choice_is_rejected(change, expected_path) -> None:
    data = copy.deepcopy(load_example())
    section, key, value = change
    if key is None:
        data[section] = value
    else:
        data[section][key] = value

    with pytest.raises(InputValidationError) as exc_info:
        QuickConfiguration.from_dict(data)

    assert expected_path in {issue["path"] for issue in exc_info.value.details}


def test_table_control_event_uses_dynamic_component_id() -> None:
    control = {
        "id": 88,
        "type": "Table_Component_Control",
        "componentName": "memory_table",
        "rows": [{"id": "dynamic-emfm", "code": "EMFM", "description": "128GB DDR5"}],
    }
    intent = WizardIntent(
        1,
        "memory",
        "quantity",
        "EMFM",
        ("EMFM",),
        16,
        "memory",
    )

    event = _control_event(control, intent)

    assert event["id"] == 88
    assert event["value"] == {"quantity": 16, "componentID": "dynamic-emfm"}


def test_cfr_verification_requires_requested_hardware_features() -> None:
    plan = map_quick_configuration(QuickConfiguration.from_dict(load_example()))
    pieces = [
        f"08 {item.code}        {item.quantity}"
        for item in plan.feature_selections
        if item.code not in {"9080-HEU", "EM26"}
    ]
    cfr = "0031 test\r\n" + "\r\n".join(pieces)

    result = _verify_cfr(cfr, plan)

    assert result["verified"] is True
    assert not result["essential_missing"]

