"""Global watermark configuration persistence and validation tests."""

import pytest

from backend.app.models.watermark import WatermarkConfig
from backend.app.services.watermark_manager import WatermarkManager


def test_watermark_defaults_round_trip_and_trim_text(tmp_path):
    manager = WatermarkManager(database_path=str(tmp_path / "watermark.sqlite3"))

    assert manager.get_config() == WatermarkConfig.default()

    saved = manager.update_config(
        text="  内部使用 · HPoker  ",
        opacity=0.2756,
        density=7,
        tilt=-12.34,
        updated_by="admin-id",
    )
    assert saved.to_dict() == {
        "text": "内部使用 · HPoker",
        "opacity": 0.276,
        "density": 7,
        "tilt": -12.3,
    }

    restored = WatermarkManager(database_path=str(tmp_path / "watermark.sqlite3"))
    assert restored.get_config() == saved


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("text", "x" * 201),
        ("opacity", 1.01),
        ("opacity", -0.01),
        ("density", 0),
        ("density", 8.5),
        ("tilt", -45.1),
        ("tilt", 45.1),
    ],
)
def test_watermark_rejects_out_of_range_values(field, value):
    values = {
        "text": "HPoker",
        "opacity": 0.12,
        "density": 4,
        "tilt": -20,
    }
    values[field] = value

    with pytest.raises(ValueError):
        WatermarkConfig.from_values(**values)


def test_empty_text_is_allowed_to_hide_watermark():
    config = WatermarkConfig.from_values(
        text="   ", opacity=0, density=1, tilt=0
    )
    assert config.text == ""
    assert config.opacity == 0
