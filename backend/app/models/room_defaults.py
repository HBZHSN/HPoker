"""Validated defaults used when a new poker room omits configuration values."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping


MIN_BUYIN_CHIPS = 10
MIN_CASH_VALUE = 0.0
MIN_SMALL_BLIND = 1
MIN_ACTION_TIMEOUT = 5
MAX_ACTION_TIMEOUT = 60
MIN_MAX_SEATS = 2
MAX_MAX_SEATS = 9
MIN_ASSISTANT_WIN_RATIO = 0.1
MAX_ASSISTANT_WIN_RATIO = 1.0

DEFAULT_ROOM_CONFIG = {
    "buyin_chips": 1000,
    "cash_value": 100.0,
    "small_blind": 10,
    "action_timeout": 15,
    "max_seats": 6,
    "assistant_win_ratio": 0.70,
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


def _integer(value: Any, field_name: str) -> int:
    number = _finite_number(value, field_name)
    if number != int(number):
        raise ValueError(f"{field_name}必须是整数")
    return int(number)


@dataclass(frozen=True)
class RoomDefaultConfig:
    """The room fields that administrators can use as creation defaults."""

    buyin_chips: int
    cash_value: float
    small_blind: int
    action_timeout: int
    max_seats: int
    assistant_win_ratio: float

    @classmethod
    def from_values(
        cls,
        *,
        buyin_chips: Any,
        cash_value: Any,
        small_blind: Any,
        action_timeout: Any,
        max_seats: Any,
        assistant_win_ratio: Any,
    ) -> "RoomDefaultConfig":
        normalized_buyin = _integer(buyin_chips, "买入筹码")
        if normalized_buyin < MIN_BUYIN_CHIPS:
            raise ValueError(f"买入筹码不能少于{MIN_BUYIN_CHIPS}")

        normalized_cash = _finite_number(cash_value, "H币")
        if normalized_cash < MIN_CASH_VALUE:
            raise ValueError("H币不能小于0")

        normalized_small_blind = _integer(small_blind, "小盲注")
        if normalized_small_blind < MIN_SMALL_BLIND:
            raise ValueError(f"小盲注必须至少为{MIN_SMALL_BLIND}")

        normalized_timeout = _integer(action_timeout, "行动限时")
        if not MIN_ACTION_TIMEOUT <= normalized_timeout <= MAX_ACTION_TIMEOUT:
            raise ValueError(
                f"行动限时必须在{MIN_ACTION_TIMEOUT}到{MAX_ACTION_TIMEOUT}秒之间"
            )

        normalized_max_seats = _integer(max_seats, "人数")
        if not MIN_MAX_SEATS <= normalized_max_seats <= MAX_MAX_SEATS:
            raise ValueError(
                f"人数必须在{MIN_MAX_SEATS}到{MAX_MAX_SEATS}人之间"
            )

        normalized_assistant_ratio = _finite_number(assistant_win_ratio, "辅助折算")
        if not MIN_ASSISTANT_WIN_RATIO <= normalized_assistant_ratio <= MAX_ASSISTANT_WIN_RATIO:
            raise ValueError("辅助折算必须在10%到100%之间")

        return cls(
            buyin_chips=normalized_buyin,
            cash_value=round(normalized_cash, 2),
            small_blind=normalized_small_blind,
            action_timeout=normalized_timeout,
            max_seats=normalized_max_seats,
            assistant_win_ratio=round(normalized_assistant_ratio, 3),
        )

    @classmethod
    def default(cls) -> "RoomDefaultConfig":
        return cls.from_values(**DEFAULT_ROOM_CONFIG)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "RoomDefaultConfig":
        return cls.from_values(
            buyin_chips=payload.get("buyin_chips"),
            cash_value=payload.get("cash_value"),
            small_blind=payload.get("small_blind"),
            action_timeout=payload.get("action_timeout"),
            max_seats=payload.get("max_seats"),
            assistant_win_ratio=payload.get("assistant_win_ratio"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "buyin_chips": self.buyin_chips,
            "cash_value": self.cash_value,
            "small_blind": self.small_blind,
            "big_blind": self.small_blind * 2,
            "action_timeout": self.action_timeout,
            "max_seats": self.max_seats,
            "assistant_win_ratio": self.assistant_win_ratio,
            "assistant_win_pct": int(round(self.assistant_win_ratio * 100)),
        }
