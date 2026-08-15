from __future__ import annotations

from typing import Any, Mapping

from .errors import GatewayConfigurationError
from .ibm_gateway import EConfigGateway
from .mapping import map_quick_configuration
from .models import QuickConfiguration
from .profiles import option_catalog


class ConfigurationService:
    def __init__(self, gateway: EConfigGateway | None = None) -> None:
        self.gateway = gateway

    def options(self) -> dict[str, Any]:
        return option_catalog()

    def connection_info(self) -> dict[str, Any]:
        if self.gateway is None:
            return {
                "configured": False,
                "mode": "preview-only",
                "required_environment": "IBM_ECONFIG_JWT",
            }
        return self.gateway.connection_info()

    def preview(self, raw: Mapping[str, Any]) -> dict[str, Any]:
        spec = QuickConfiguration.from_dict(raw)
        return map_quick_configuration(spec).to_dict()

    def generate(self, raw: Mapping[str, Any]) -> dict[str, Any]:
        if self.gateway is None:
            raise GatewayConfigurationError(
                "IBM에서 CFR을 생성하려면 로그인된 eConfig 세션의 IBM_ECONFIG_JWT가 필요합니다."
            )
        spec = QuickConfiguration.from_dict(raw)
        plan = map_quick_configuration(spec)
        result = self.gateway.generate_cfr(plan)
        result["request"] = {
            "profile_version": plan.profile_version,
            "machine_type_model": plan.machine_type_model,
            "preset": plan.preset,
            "category_selections": list(plan.category_selections),
            "resolved_requirements": plan.resolved_requirements,
        }
        return result

