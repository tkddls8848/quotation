from __future__ import annotations

from copy import deepcopy
from typing import Any


PROFILE_VERSION = "power-9080-heu-quick-v2"


# These are deliberately business-facing choices.  The values below are requests sent to
# IBM's rule engine, not a locally asserted orderable bill of material.
CATEGORIES: tuple[dict[str, Any], ...] = (
    {
        "id": "compute",
        "label": "컴퓨트",
        "description": "활성 코어 규모를 고릅니다.",
        "options": (
            {"id": "compact", "label": "기본", "summary": "16 활성 코어", "values": {"activated_cores": 16}},
            {"id": "balanced", "label": "균형", "summary": "32 활성 코어", "values": {"activated_cores": 32}},
            {"id": "performance", "label": "고성능", "summary": "64 활성 코어", "values": {"activated_cores": 64}},
        ),
    },
    {
        "id": "memory",
        "label": "메모리",
        "description": "물리 용량과 활성 용량을 한 묶음으로 고릅니다.",
        "options": (
            {"id": "compact", "label": "기본", "summary": "물리 1TB / 활성 512GB", "values": {"physical_memory_gb": 1024, "activated_memory_gb": 512}},
            {"id": "balanced", "label": "균형", "summary": "물리 2TB / 활성 1TB", "values": {"physical_memory_gb": 2048, "activated_memory_gb": 1024}},
            {"id": "capacity", "label": "대용량", "summary": "물리 4TB / 활성 2TB", "values": {"physical_memory_gb": 4096, "activated_memory_gb": 2048}},
        ),
    },
    {
        "id": "boot_storage",
        "label": "부트 스토리지",
        "description": "800GB NVMe 부트 드라이브 구성을 고릅니다.",
        "options": (
            {"id": "mirror", "label": "미러", "summary": "800GB NVMe 2개", "values": {"boot_nvme_quantity": 2}},
            {"id": "quad", "label": "여유 구성", "summary": "800GB NVMe 4개", "values": {"boot_nvme_quantity": 4}},
        ),
    },
    {
        "id": "ethernet",
        "label": "이더넷",
        "description": "2-port 25/10/1GbE 어댑터 규모를 고릅니다.",
        "options": (
            {"id": "basic", "label": "기본", "summary": "어댑터 1개 / 2포트", "values": {"ethernet_adapter_quantity": 1}},
            {"id": "redundant", "label": "이중화", "summary": "어댑터 2개 / 4포트", "values": {"ethernet_adapter_quantity": 2}},
            {"id": "dense", "label": "고밀도", "summary": "어댑터 4개 / 8포트", "values": {"ethernet_adapter_quantity": 4}},
        ),
    },
    {
        "id": "fibre_channel",
        "label": "SAN",
        "description": "2-port 32Gb Fibre Channel 어댑터 규모를 고릅니다.",
        "options": (
            {"id": "none", "label": "사용 안 함", "summary": "FC 어댑터 없음", "values": {"fc_adapter_quantity": 0}},
            {"id": "redundant", "label": "이중화", "summary": "어댑터 2개 / 4포트", "values": {"fc_adapter_quantity": 2}},
            {"id": "dense", "label": "고밀도", "summary": "어댑터 4개 / 8포트", "values": {"fc_adapter_quantity": 4}},
        ),
    },
    {
        "id": "software",
        "label": "소프트웨어",
        "description": "운영체제와 가상화 번들을 고릅니다.",
        "options": (
            {"id": "aix-standard", "label": "AIX 표준", "summary": "AIX 7.3 Standard + PowerVM Enterprise", "values": {"operating_system": "AIX 7.3 Standard", "virtualization": "PowerVM Enterprise"}},
        ),
    },
    {
        "id": "support",
        "label": "기술지원",
        "description": "Expert Care 서비스 수준을 고릅니다.",
        "options": (
            {"id": "advanced-3y", "label": "Advanced 3년", "summary": "3 Year Advanced Expert Care", "values": {"support": "3Y Advanced Expert Care"}},
        ),
    },
)


PRESETS: tuple[dict[str, Any], ...] = (
    {
        "id": "starter",
        "label": "기본 업무",
        "description": "일반 업무와 소규모 통합용 시작 구성",
        "selections": {"compute": "compact", "memory": "compact", "boot_storage": "mirror", "ethernet": "basic", "fibre_channel": "none", "software": "aix-standard", "support": "advanced-3y"},
    },
    {
        "id": "balanced",
        "label": "업무 시스템",
        "description": "DB·ERP·가상화에 두루 쓰는 균형 구성",
        "selections": {"compute": "balanced", "memory": "balanced", "boot_storage": "mirror", "ethernet": "redundant", "fibre_channel": "redundant", "software": "aix-standard", "support": "advanced-3y"},
    },
    {
        "id": "performance",
        "label": "고성능 DB",
        "description": "코어·메모리·I/O를 크게 잡는 구성",
        "selections": {"compute": "performance", "memory": "capacity", "boot_storage": "quad", "ethernet": "dense", "fibre_channel": "dense", "software": "aix-standard", "support": "advanced-3y"},
    },
)


def option_catalog() -> dict[str, Any]:
    return {
        "profile_version": PROFILE_VERSION,
        "product": {
            "machine_type_model": "9080-HEU",
            "label": "IBM Power E1080",
            "country": "KR",
            "configuration_type": "INITIAL",
        },
        "presets": deepcopy(PRESETS),
        "categories": deepcopy(CATEGORIES),
        "authority": "IBM eConfig rule engine",
    }


def preset_selections(preset_id: str) -> dict[str, str] | None:
    for preset in PRESETS:
        if preset["id"] == preset_id:
            return dict(preset["selections"])
    return None


def category_option(category_id: str, option_id: str) -> dict[str, Any] | None:
    for category in CATEGORIES:
        if category["id"] != category_id:
            continue
        for option in category["options"]:
            if option["id"] == option_id:
                return option
    return None

