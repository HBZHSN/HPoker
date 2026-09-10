"""Global watermark configuration persistence and validation tests."""

import pytest
from fastapi import HTTPException

from backend.app.api.endpoints import (
    WatermarkUpdateRequest,
    get_watermark_config,
    update_watermark_config,
)
from backend.app.models.watermark import WatermarkConfig
from backend.app.models.user import User
from backend.app.services.watermark_manager import WatermarkManager
from backend.app.services.user_manager import user_manager


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


def test_watermark_api_is_readable_but_only_admin_can_update():
    user_manager._users["admin-user"] = User(
        user_id="admin-user",
        username="admin-user",
        nickname="管理员",
        avatar="👑",
        is_admin=True,
    )
    user_manager._users["regular-user"] = User(
        user_id="regular-user",
        username="regular-user",
        nickname="普通用户",
        avatar="👤",
    )
    user_manager._tokens.update(
        {"admin-token": "admin-user", "regular-token": "regular-user"}
    )

    assert get_watermark_config() == WatermarkConfig.default().to_dict()

    request = WatermarkUpdateRequest(
        text="仅限内部使用",
        opacity=0.25,
        density=6,
        tilt=18,
    )
    with pytest.raises(HTTPException) as missing_auth:
        update_watermark_config(req=request, authorization=None, token=None)
    assert missing_auth.value.status_code == 401

    with pytest.raises(HTTPException) as regular_user:
        update_watermark_config(
            req=request,
            authorization="Bearer regular-token",
        )
    assert regular_user.value.status_code == 403

    assert update_watermark_config(
        req=request,
        authorization="Bearer admin-token",
    ) == request.model_dump()
    assert get_watermark_config() == request.model_dump()


def test_watermark_api_rejects_invalid_payload_before_writing():
    with pytest.raises(ValueError):
        WatermarkUpdateRequest(
            text="x",
            opacity=0.1,
            density=9,
            tilt=0,
        )
    assert get_watermark_config() == WatermarkConfig.default().to_dict()
