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
from typing import Optional, Sequence


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


def parse_command(line: str) -> Optional[CliCommand]:
    """Parse one shell-like command line.

    Quoted room names are supported (for example ``create "Friday game"``),
    and unmatched quotes are reported as a friendly domain error instead of
    leaking :class:`ValueError` from :mod:`shlex`.
    """

    raw = line.strip()
    if not raw:
        return None
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

    return _number(value)


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
