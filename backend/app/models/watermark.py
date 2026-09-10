"""Validated global watermark configuration."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping


MAX_WATERMARK_TEXT_LENGTH = 200
MIN_WATERMARK_OPACITY = 0.0
MAX_WATERMARK_OPACITY = 1.0
MIN_WATERMARK_DENSITY = 1
MAX_WATERMARK_DENSITY = 8
MIN_WATERMARK_TILT = -45.0
MAX_WATERMARK_TILT = 45.0

DEFAULT_WATERMARK_CONFIG = {
    "text": "HPoker",
    "opacity": 0.12,
    "density": 4,
    "tilt": -20.0,
}


def _finite_number(value: Any, field_name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{field_name}必须是数字")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name}必须是数字") from exc
    if not math.isfinite(number):
        raise ValueError(f"{field_name}必须是有限数字")
    return number


@dataclass(frozen=True)
class WatermarkConfig:
    """The four values needed to render the application-wide watermark."""

    text: str
    opacity: float
    density: int
    tilt: float

    @classmethod
    def from_values(
        cls,
        *,
        text: str,
        opacity: Any,
        density: Any,
        tilt: Any,
    ) -> "WatermarkConfig":
        if not isinstance(text, str):
            raise ValueError("水印文本必须是字符串")
        normalized_text = text.strip()
        if len(normalized_text) > MAX_WATERMARK_TEXT_LENGTH:
            raise ValueError(
                f"水印文本不能超过{MAX_WATERMARK_TEXT_LENGTH}个字符"
            )

        normalized_opacity = _finite_number(opacity, "不透明度")
        if not MIN_WATERMARK_OPACITY <= normalized_opacity <= MAX_WATERMARK_OPACITY:
            raise ValueError("不透明度必须在0到1之间")

        normalized_density = _finite_number(density, "密度")
        if normalized_density != int(normalized_density):
            raise ValueError("密度必须是整数")
        normalized_density = int(normalized_density)
        if not MIN_WATERMARK_DENSITY <= normalized_density <= MAX_WATERMARK_DENSITY:
            raise ValueError(
                f"密度必须在{MIN_WATERMARK_DENSITY}到{MAX_WATERMARK_DENSITY}之间"
            )

        normalized_tilt = _finite_number(tilt, "倾斜角度")
        if not MIN_WATERMARK_TILT <= normalized_tilt <= MAX_WATERMARK_TILT:
            raise ValueError("倾斜角度必须在-45到45度之间")

        return cls(
            text=normalized_text,
            opacity=round(normalized_opacity, 3),
            density=normalized_density,
            tilt=round(normalized_tilt, 1),
        )

    @classmethod
    def default(cls) -> "WatermarkConfig":
        return cls.from_values(**DEFAULT_WATERMARK_CONFIG)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "WatermarkConfig":
        return cls.from_values(
            text=payload.get("text", ""),
            opacity=payload.get("opacity"),
            density=payload.get("density"),
            tilt=payload.get("tilt"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "opacity": self.opacity,
            "density": self.density,
            "tilt": self.tilt,
        }
