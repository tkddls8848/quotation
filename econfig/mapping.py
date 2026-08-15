from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .models import QuickConfiguration
from .profiles import PROFILE_VERSION, category_option


@dataclass(frozen=True)
class FeatureSelection:
    code: str
    quantity: int
    description: str
    source: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class WizardIntent:
    order: int
    section: str
    operation: str
    feature_code: str
    semantic_candidates: tuple[str, ...]
    value: int | str | bool
    description: str

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["semantic_candidates"] = list(self.semantic_candidates)
        return value


@dataclass(frozen=True)
class MappingPlan:
    profile_version: str
    request_id: str
    machine_type_model: str
    preset: str
    category_selections: tuple[dict[str, Any], ...]
    resolved_requirements: dict[str, Any]
    feature_selections: tuple[FeatureSelection, ...]
    wizard_intents: tuple[WizardIntent, ...]
    engine_managed: tuple[str, ...]
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_version": self.profile_version,
            "request_id": self.request_id,
            "status": "ready_for_ibm",
            "machine_type_model": self.machine_type_model,
            "preset": self.preset,
            "category_selections": list(self.category_selections),
            "resolved_requirements": self.resolved_requirements,
            "feature_selections": [item.to_dict() for item in self.feature_selections],
            "wizard_intents": [item.to_dict() for item in self.wizard_intents],
            "engine_managed": list(self.engine_managed),
            "warnings": list(self.warnings),
        }


def map_quick_configuration(spec: QuickConfiguration) -> MappingPlan:
    values = spec.expanded_values()
    cores = int(values["activated_cores"])
    physical_memory = int(values["physical_memory_gb"])
    active_memory = int(values["activated_memory_gb"])
    nvme = int(values["boot_nvme_quantity"])
    ethernet = int(values["ethernet_adapter_quantity"])
    fc = int(values["fc_adapter_quantity"])

    features = [
        FeatureSelection("9080-HEU", 1, "IBM Power E1080 model HEU", "product-profile"),
        FeatureSelection("EDQD", 1, "64-core processor card", "profile-rule"),
        FeatureSelection("EDQE", cores, "1 core processor activation", "category:compute"),
        FeatureSelection("EMFM", physical_memory // 128, "128GB DDR5 memory unit", "category:memory"),
        FeatureSelection("EM26", active_memory // 512, "512GB DDR5 memory activation", "category:memory"),
        FeatureSelection("EC7Q", nvme, "800GB NVMe boot drive", "category:boot_storage"),
        FeatureSelection("EC72", ethernet, "2-port 25/10/1GbE adapter", "category:ethernet"),
        FeatureSelection("0265", 1, "AIX Partition Specify", "category:software"),
        FeatureSelection("2146", 1, "Primary OS - AIX", "category:software"),
        FeatureSelection("2375", 1, "AIX 7.3 Base Install", "category:software"),
        FeatureSelection("2377", 1, "AIX 7.3 Standard Edition", "category:software"),
        FeatureSelection("EPVT", 1, "PowerVM Enterprise Edition", "category:software"),
        FeatureSelection("9716", 1, "Korean language group", "profile-rule"),
        FeatureSelection("EXA3", 1, "3 Year Advanced Expert Care", "category:support"),
    ]
    if fc:
        features.append(FeatureSelection("EN1A", fc, "2-port 32Gb Fibre Channel adapter", "category:fibre_channel"))
    features = [feature for feature in features if feature.quantity > 0]

    intents = (
        WizardIntent(10, "machine", "select", "9080-HEU", ("sq_server_mtm_selection_control", "sq_mtm_9080_HEU", "9080 Model HEU", "9080-HEU"), "9080-HEU", "Select the Power E1080 model."),
        WizardIntent(20, "processor", "quantity", "EDQD", ("sq_processor_card_backplane_60way_p11_380w_EDQD", "EDQD"), 1, "Select the processor card."),
        WizardIntent(30, "processor", "quantity", "EDQE", ("sq_one_core_processor_activation_EDQE", "EDQE"), cores, "Set activated cores."),
        WizardIntent(40, "memory", "quantity", "EMFM", ("sq_memory_128gb_4u_16gb_DDR5_2_rank_EMFM", "EMFM"), physical_memory // 128, "Set physical memory units."),
        WizardIntent(50, "memory", "quantity", "EM24/EM26", ("sq_1gb_DDR5_memory_activation_EM24", "512GB DDR5 Memory activation for HEU", "EM26"), active_memory, "Set activated memory in the unit exposed by IBM's wizard."),
        WizardIntent(60, "storage", "quantity", "EC7Q", ("sq_poseidon2_nvme_ssd_boot_drive_EC7Q", "EC7Q"), nvme, "Set boot NVMe quantity."),
        WizardIntent(70, "network", "quantity", "EC72", ("sq_2port_25gb_ethernet_connectx_6_lx_sfp28_no_crypto_pcie4_manatee", "PCIe4 2-Port 25/10/1 GbE", "EC72"), ethernet, "Set Ethernet adapter quantity."),
        WizardIntent(80, "fibre-channel", "quantity", "EN1A", ("sq_pcie3_8x_2port_32gbs_short_fibre_channel_adapter_lp_capable", "PCIe3 32Gb 2-port Fibre Channel", "EN1A"), fc, "Set Fibre Channel adapter quantity."),
        WizardIntent(90, "software", "select", "AIX-7.3-STANDARD", ("sw_rs_version_73", "AIX 7.3 Standard Edition", "2377"), True, "Select AIX 7.3 Standard."),
        WizardIntent(100, "virtualization", "select", "EPVT", ("sq_advanced_power_virtualization_enterprise_EPVT", "EPVT"), True, "Select PowerVM Enterprise."),
        WizardIntent(110, "locale", "select", "9716", ("sq_language_langgroup_korean", "Language Group Specify - Korean", "9716"), True, "Select Korean language group."),
        WizardIntent(120, "support", "select", "EXA3", ("3 YEAR, ADVANCED EXPERT CARE", "EXA3"), True, "Select Advanced Expert Care."),
    )

    category_selections = []
    for category_id, option_id in spec.selections.items():
        option = category_option(category_id, option_id)
        if option:
            category_selections.append(
                {"category": category_id, "option": option_id, "label": option["label"], "summary": option["summary"]}
            )

    return MappingPlan(
        profile_version=PROFILE_VERSION,
        request_id=spec.request_id,
        machine_type_model=spec.machine_type_model,
        preset=spec.preset,
        category_selections=tuple(category_selections),
        resolved_requirements=values,
        feature_selections=tuple(features),
        wizard_intents=intents,
        engine_managed=(
            "전원·PDU·케이블·랙 장착 부품",
            "I/O drawer·fanout·슬롯 배치",
            "필수 동반 feature와 상호 배타 규칙",
            "가격·판매 가능 여부·서비스 종속 항목",
        ),
        warnings=(
            "로컬에서는 요구사항만 정리하며 최종 BOM은 IBM eConfig가 결정합니다.",
            "IBM 카탈로그와 wizard ID는 세션마다 동적으로 해석합니다.",
        ),
    )


# Compatibility alias for callers that imported the old mapper name.
map_9080_heu = map_quick_configuration

