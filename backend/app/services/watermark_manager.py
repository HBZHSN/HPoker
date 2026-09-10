"""Durable global watermark settings."""

from __future__ import annotations

from typing import Any, Optional

from backend.app.database import SQLiteDatabase
from backend.app.models.watermark import WatermarkConfig


class WatermarkManager:
    """Read and update the one global watermark configuration."""

    def __init__(self, database_path: Optional[str] = None):
        self._database = SQLiteDatabase(database_path)
        self.storage_path = self._database.path

    def get_config(self) -> WatermarkConfig:
        stored = self._database.load_watermark()
        if not stored:
            return WatermarkConfig.default()
        return WatermarkConfig.from_values(
            text=stored["text_content"],
            opacity=stored["opacity"],
            density=stored["density"],
            tilt=stored["tilt"],
        )

    def update_config(
        self,
        *,
        text: str,
        opacity: Any,
        density: Any,
        tilt: Any,
        updated_by: Optional[str],
    ) -> WatermarkConfig:
        config = WatermarkConfig.from_values(
            text=text,
            opacity=opacity,
            density=density,
            tilt=tilt,
        )
        self._database.save_watermark(config.to_dict(), updated_by=updated_by)
        return config

    def reset_to_defaults(self) -> WatermarkConfig:
        config = WatermarkConfig.default()
        self._database.save_watermark(config.to_dict(), updated_by=None)
        return config


watermark_manager = WatermarkManager()
