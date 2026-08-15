from __future__ import annotations

from typing import Any


class EConfigError(Exception):
    code = "econfig_error"
    status = 500

    def __init__(self, message: str, *, details: Any = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details

    def to_dict(self) -> dict[str, Any]:
        error: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.details is not None:
            error["details"] = self.details
        return {"error": error}


class InputValidationError(EConfigError):
    code = "invalid_configuration"
    status = 422


class GatewayConfigurationError(EConfigError):
    code = "gateway_not_configured"
    status = 503


class GatewayRequestError(EConfigError):
    code = "ibm_gateway_error"
    status = 502

