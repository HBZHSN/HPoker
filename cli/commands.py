"""Command parsing and bet sizing helpers for the terminal client.

The CLI deliberately keeps command parsing independent from the network and
controller layers.  Apart from making the interactive loop easier to read,
this gives us one source of truth for amount syntax in both tests and the
interactive client.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import re
import shlex
from typing import Dict, Optional, Sequence


class CommandParseError(ValueError):
    """Raised when a command cannot be tokenized safely."""


@dataclass(frozen=True)
class CliCommand:
    """A tokenized user command.

    ``name`` is normalized to lowercase while arguments preserve their
    spelling.  The original input is retained for useful error messages and
    command history.
    """

    name: str
    args: tuple[str, ...] = ()
    raw: str = ""

    @property
    def first_arg(self) -> Optional[str]:
        return self.args[0] if self.args else None


@dataclass(frozen=True)
class CommandSpec:
    """One canonical command and the aliases exposed by a UI scope."""

    name: str
    aliases: tuple[str, ...]
    usage: str
    description: str
    group: str = "通用"
    sidebar: bool = False

    @property
    def tokens(self) -> tuple[str, ...]:
        return (self.name, *self.aliases)


GLOBAL_COMMANDS: tuple[CommandSpec, ...] = (
    CommandSpec("info", ("status", "inspect", "table"), "info [目标]", "查看当前上下文详情", "全局"),
    CommandSpec("refresh", ("redraw", "clear", "cls"), "refresh", "刷新当前界面", "全局"),
    CommandSpec("users", ("userlist",), "users", "查看用户", "全局"),
    CommandSpec("mode", ("view",), "mode <dashboard|stream>", "切换视图", "全局"),
    CommandSpec("color", (), "color <on|off>", "切换颜色", "全局"),
    CommandSpec("help", ("h", "?"), "help", "完整帮助", "全局", True),
    CommandSpec("back", ("q", "quit", "exit"), "q", "返回当前页面", "全局", True),
)


LOBBY_COMMANDS: tuple[CommandSpec, ...] = (
    CommandSpec("join", ("j",), "join <序号|ID>", "加入房间", "房间", True),
    CommandSpec("create", ("new", "c"), "create [选项]", "创建房间", "房间", True),
    CommandSpec("rooms", ("list", "r"), "rooms", "刷新房间", "房间", True),
    CommandSpec("user", ("switch", "login", "logout"), "user", "切换账号", "账户"),
)


ROOM_COMMANDS: tuple[CommandSpec, ...] = (
    CommandSpec("check", ("call", "c"), "check", "过牌 / 跟注", "行动", True),
    CommandSpec("fold", ("f",), "fold", "弃牌", "行动", True),
    CommandSpec("raise", ("bet", "r", "b"), "raise [额度]", "下注 / 加注", "行动", True),
    CommandSpec("allin", ("all-in", "ai", "a"), "allin", "全下", "行动", True),
    CommandSpec("timecard", ("tc", "time"), "timecard", "使用时间卡", "行动"),
    CommandSpec("ready", ("rd",), "ready", "准备", "牌局", True),
    CommandSpec("unready", ("unrd",), "unready", "取消准备", "牌局"),
    CommandSpec("start", ("begin",), "start", "开始下一手", "牌局", True),
    CommandSpec("sit", ("seat",), "sit <座位>", "入座", "座位", True),
    CommandSpec("rebuy", ("rb", "buyin"), "rebuy", "补码", "座位", True),
    CommandSpec("bot", ("addbot", "add_bot", "add-bot", "testbot"), "bot [座位]", "添加测试机器人", "管理"),
    CommandSpec("rit", (), "rit <1|2>", "选择发牌次数", "牌局"),
    CommandSpec("show", ("showall", "s1", "s2", "sa", "muck", "hide"), "show <1|2|all|muck>", "亮牌 / 盖牌", "牌局"),
    CommandSpec("history", ("log",), "history [数量]", "最近动态", "查看"),
    CommandSpec("bill", ("report", "settlement"), "bill", "结算账单", "查看"),
    CommandSpec("export", ("save",), "export [路径]", "导出账单", "查看"),
    CommandSpec("reconnect", ("retry",), "reconnect", "重新连接", "连接"),
    CommandSpec("end", ("endroom",), "end", "结束并结算", "管理"),
    CommandSpec("delete", ("del", "destroy"), "delete", "解散房间", "管理"),
    CommandSpec("leave", ("lobby",), "leave", "返回大厅", "通用", True),
)


COMMANDS_BY_SCOPE: Dict[str, tuple[CommandSpec, ...]] = {
    "lobby": LOBBY_COMMANDS,
    "room": ROOM_COMMANDS,
}


def command_specs(scope: str) -> tuple[CommandSpec, ...]:
    """Return the command catalogue used by parsing, help, and sidebars."""

    return (*COMMANDS_BY_SCOPE.get(scope, ()), *GLOBAL_COMMANDS)


def command_alias_conflicts(scope: str) -> Dict[str, tuple[str, ...]]:
    """Return duplicate tokens in an effective scope for invariant tests."""

    owners: Dict[str, list[str]] = {}
    for spec in command_specs(scope):
        for token in spec.tokens:
            owners.setdefault(token, []).append(spec.name)
    return {
        token: tuple(names)
        for token, names in owners.items()
        if len(set(names)) > 1
    }


def is_global_command(value: str, name: str) -> bool:
    """Check a raw token against one canonical global command."""

    token = value.strip().lower()
    return any(spec.name == name and token in spec.tokens for spec in GLOBAL_COMMANDS)


def normalize_command(command: CliCommand, scope: str) -> CliCommand:
    """Resolve a scope-specific alias to its canonical command name.

    Aliases may intentionally overlap between scopes: ``c`` creates a room in
    the lobby and checks/calls at a table; ``r`` refreshes the lobby and raises
    at a table.  Legacy show-card aliases are converted into explicit args so
    the controller only needs one handler.
    """

    original_name = command.name.lower()
    canonical = original_name
    for spec in command_specs(scope):
        if original_name in spec.tokens:
            canonical = spec.name
            break

    args = command.args
    show_args = {
        "showall": ("all",),
        "sa": ("all",),
        "s1": ("1",),
        "s2": ("2",),
        "muck": ("muck",),
        "hide": ("muck",),
    }
    if scope == "room" and canonical == "show" and original_name in show_args:
        args = (*show_args[original_name], *args)
    return CliCommand(name=canonical, args=args, raw=command.raw)


def parse_command(line: str) -> Optional[CliCommand]:
    """Parse one shell-like command line.

    Quoted room names are supported (for example ``create "Friday game"``),
    and unmatched quotes are reported as a friendly domain error instead of
    leaking :class:`ValueError` from :mod:`shlex`.
    """

    raw = line.strip()
    if not raw:
        return None
    compact_raise = re.fullmatch(r"(?P<name>[rb])(?P<amount>\d+(?:\.\d+)?)", raw, re.IGNORECASE)
    if compact_raise:
        return CliCommand(
            name=compact_raise.group("name").lower(),
            args=(compact_raise.group("amount"),),
            raw=raw,
        )
    try:
        tokens = shlex.split(raw)
    except ValueError as exc:
        raise CommandParseError(f"命令引号未闭合: {exc}") from exc
    if not tokens:
        return None
    return CliCommand(name=tokens[0].lower(), args=tuple(tokens[1:]), raw=raw)


@dataclass(frozen=True)
class BetSizingContext:
    """State needed to resolve a bet/raise amount.

    The backend expects ``BET``/``RAISE`` amounts to be the player's *total
    contribution in the current betting round*, not the extra chips to add.
    ``current_highest_bet`` and ``current_round_bet`` therefore exist so the
    CLI can also understand relative forms such as ``+1bb``.
    """

    pot: int = 0
    minimum: int = 0
    maximum: int = 0
    small_blind: int = 1
    current_round_bet: int = 0
    current_highest_bet: int = 0
    big_blind: Optional[int] = None

    @property
    def unit(self) -> int:
        return max(1, int(self.small_blind or 1))

    @property
    def bb(self) -> int:
        return max(1, int(self.big_blind or self.unit * 2))


_FRACTION_RE = re.compile(
    r"^(?P<numerator>\d+(?:\.\d+)?)/(?P<denominator>\d+(?:\.\d+)?)(?:p|pot)?$",
    re.IGNORECASE,
)
_POT_RE = re.compile(r"^(?P<ratio>\d+(?:\.\d+)?)(?:p|pot)$", re.IGNORECASE)
_UNIT_RE = re.compile(r"^(?P<amount>\d+(?:\.\d+)?)(?P<unit>bb|bigblind|sb|smallblind)$", re.IGNORECASE)
_RELATIVE_RE = re.compile(r"^\+(?P<amount>\d+(?:\.\d+)?)(?P<unit>bb|bigblind|sb|smallblind)?$", re.IGNORECASE)


def _number(value: str) -> Optional[float]:
    """Parse a plain chip amount, accepting commas and a currency prefix."""

    cleaned = value.strip().replace(",", "")
    if cleaned.startswith(("¥", "$")):
        cleaned = cleaned[1:]
    try:
        number = float(cleaned)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _raw_target(token: str, context: BetSizingContext) -> Optional[float]:
    """Resolve syntax to an unbounded target amount."""

    value = token.strip().lower().replace(" ", "")
    if value in {"min", "minimum", "minraise", "min-raise", "minbet", "min-bet"}:
        return float(context.minimum)
    if value in {"all", "allin", "all-in", "max", "maximum"}:
        return float(context.maximum)
    if value in {"p", "pot"}:
        return float(context.pot)

    fraction = _FRACTION_RE.fullmatch(value)
    if fraction:
        denominator = float(fraction.group("denominator"))
        if denominator == 0:
            return None
        return context.pot * float(fraction.group("numerator")) / denominator

    pot_ratio = _POT_RE.fullmatch(value)
    if pot_ratio:
        return context.pot * float(pot_ratio.group("ratio"))

    unit = _UNIT_RE.fullmatch(value)
    if unit:
        multiplier = float(unit.group("amount"))
        unit_name = unit.group("unit").lower()
        return multiplier * (context.bb if unit_name in {"bb", "bigblind"} else context.unit)

    relative = _RELATIVE_RE.fullmatch(value)
    if relative:
        amount = float(relative.group("amount"))
        unit_name = (relative.group("unit") or "chips").lower()
        if unit_name in {"bb", "bigblind"}:
            amount *= context.bb
        elif unit_name in {"sb", "smallblind"}:
            amount *= context.unit
        # A relative raise starts from the current table price.  For an open
        # bet there is no price yet, so the player's current contribution is
        # the natural base.
        base = context.current_highest_bet or context.current_round_bet
        return base + amount

    plain = _number(value)
    # Tiny bare values are far more useful as pot multipliers than as chip
    # amounts.  The legal minimum / blind unit keeps this unambiguous on
    # normal 10/20-style tables: ``r0.5`` means half pot and ``r1`` means pot,
    # while ``raise 200`` remains an exact chip target.
    if plain is not None:
        chip_floor = max(int(context.minimum), context.unit)
        if 0 < plain <= 3 and plain < chip_floor:
            return context.pot * plain
    return plain


def align_bet_amount(amount: int, context: BetSizingContext) -> int:
    """Clamp and snap a target to the configured small-blind chip unit.

    A short stack may have a maximum that is not a multiple of the small
    blind.  In that case the exact maximum is retained, because it represents
    an all-in and the engine explicitly permits that exception.
    """

    minimum = max(0, int(context.minimum))
    maximum = max(minimum, int(context.maximum))
    value = max(minimum, min(maximum, int(amount)))
    if value <= minimum or value >= maximum:
        return value

    unit = context.unit
    # Avoid banker's rounding for predictable poker sizing (e.g. 15 at a 10
    # chip unit should become 20).
    snapped = int(value / unit + 0.5) * unit
    if snapped < minimum:
        snapped = int(math.ceil(minimum / unit) * unit)
    if snapped > maximum:
        snapped = maximum
    return max(minimum, min(maximum, snapped))


def resolve_bet_amount(token: Optional[str], context: BetSizingContext) -> Optional[int]:
    """Resolve a CLI amount token into a legal, step-aligned target.

    Supported forms include:

    * chip amounts: ``120``, ``1,200`` or ``¥120``;
    * short pot ratios below the legal chip floor: ``0.5`` or ``1``;
    * pot fractions: ``1/3p``, ``1/2``, ``2/3p``, ``p``, ``1.5p``;
    * blind multiples: ``2.5bb`` and ``10sb``;
    * relative increments: ``+1bb`` and ``+20``;
    * ``min`` and ``all``/``allin``.
    """

    if token is None or not token.strip():
        return align_bet_amount(context.minimum, context)
    raw = _raw_target(token, context)
    if raw is None or raw < 0:
        return None
    return align_bet_amount(int(raw), context)


def join_command_tokens(tokens: Sequence[str]) -> str:
    """Create a readable command string for history or error output."""

    return " ".join(tokens).strip()
