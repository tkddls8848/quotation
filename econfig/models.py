from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

from .errors import InputValidationError
from .profiles import CATEGORIES, category_option, preset_selections


@dataclass(frozen=True)
class QuickConfiguration:
    request_id: str
    preset: str
    selections: dict[str, str]
    country: str = "KR"
    language: str = "ko-KR"
    machine_type: str = "9080"
    machine_model: str = "HEU"

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "QuickConfiguration":
        if not isinstance(raw, Mapping):
            raise InputValidationError(
                "요청 본문은 JSON object여야 합니다.",
                details=[{"path": "$", "message": "object가 필요합니다."}],
            )

        issues: list[dict[str, str]] = []
        request_id = raw.get("request_id")
        if not isinstance(request_id, str) or not request_id.strip():
            issues.append({"path": "request_id", "message": "요청 번호가 필요합니다."})
            request_id = ""

        preset = raw.get("preset", "balanced")
        defaults = preset_selections(preset) if isinstance(preset, str) else None
        if defaults is None:
            issues.append({"path": "preset", "message": "지원하지 않는 프리셋입니다."})
            defaults = preset_selections("balanced") or {}
            preset = "balanced"

        supplied = raw.get("selections", {})
        if not isinstance(supplied, Mapping):
            issues.append({"path": "selections", "message": "object가 필요합니다."})
            supplied = {}

        category_ids = {category["id"] for category in CATEGORIES}
        unknown = sorted(str(key) for key in supplied if key not in category_ids)
        for key in unknown:
            issues.append({"path": f"selections.{key}", "message": "알 수 없는 구성 카테고리입니다."})

        selections = dict(defaults)
        for category in CATEGORIES:
            category_id = category["id"]
            option_id = supplied.get(category_id, selections.get(category_id))
            if not isinstance(option_id, str) or category_option(category_id, option_id) is None:
                issues.append(
                    {
                        "path": f"selections.{category_id}",
                        "message": "지원하지 않는 선택값입니다.",
                    }
                )
                continue
            selections[category_id] = option_id

        country = str(raw.get("country", "KR")).strip().upper()
        if country != "KR":
            issues.append({"path": "country", "message": "현재 빠른 구성 프로필은 KR만 지원합니다."})

        if issues:
            raise InputValidationError("빠른 구성 입력이 올바르지 않습니다.", details=issues)
        return cls(
            request_id=request_id.strip(),
            preset=str(preset),
            selections=selections,
            country=country,
            language=str(raw.get("language", "ko-KR")),
        )

    def expanded_values(self) -> dict[str, Any]:
        values: dict[str, Any] = {}
        for category_id, option_id in self.selections.items():
            option = category_option(category_id, option_id)
            if option:
                values.update(option["values"])
        return values

    @property
    def machine_type_model(self) -> str:
        return f"{self.machine_type}-{self.machine_model}"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

