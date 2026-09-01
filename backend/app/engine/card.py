"""Poker Card and Suit/Rank definitions.

Provides immutable Card representation, 4-color and 2-color metadata,
and robust string parsing (e.g., 'As', 'Kh', '2d', 'Tc').
"""

from __future__ import annotations
from enum import Enum
from dataclasses import dataclass
from typing import ClassVar, Dict, Tuple


class Suit(str, Enum):
    SPADES = "s"      # ♠ 黑桃
    HEARTS = "h"      # ♥ 红心
    CLUBS = "c"       # ♣ 梅花
    DIAMONDS = "d"    # ♦ 方块

    @property
    def symbol(self) -> str:
        symbols = {
            Suit.SPADES: "♠",
            Suit.HEARTS: "♥",
            Suit.CLUBS: "♣",
            Suit.DIAMONDS: "♦",
        }
        return symbols[self]

    @property
    def color_name(self) -> str:
        # Standard 4-color deck palette (GGPoker style)
        colors = {
            Suit.SPADES: "black",
            Suit.HEARTS: "red",
            Suit.CLUBS: "green",
            Suit.DIAMONDS: "blue",
        }
        return colors[self]

    @property
    def display_name(self) -> str:
        names = {
            Suit.SPADES: "黑桃",
            Suit.HEARTS: "红心",
            Suit.CLUBS: "梅花",
            Suit.DIAMONDS: "方块",
        }
        return names[self]


class Rank(int, Enum):
    TWO = 2
    THREE = 3
    FOUR = 4
    FIVE = 5
    SIX = 6
    SEVEN = 7
    EIGHT = 8
    NINE = 9
    TEN = 10
    JACK = 11
    QUEEN = 12
    KING = 13
    ACE = 14

    @property
    def symbol(self) -> str:
        if self.value <= 9:
            return str(self.value)
        mapping = {10: "T", 11: "J", 12: "Q", 13: "K", 14: "A"}
        return mapping[self.value]

    @property
    def display_name(self) -> str:
        mapping = {
            2: "2", 3: "3", 4: "4", 5: "5", 6: "6", 7: "7", 8: "8", 9: "9",
            10: "10", 11: "J", 12: "Q", 13: "K", 14: "A"
        }
        return mapping[self.value]


_RANK_CHAR_MAP: Dict[str, Rank] = {
    "2": Rank.TWO,
    "3": Rank.THREE,
    "4": Rank.FOUR,
    "5": Rank.FIVE,
    "6": Rank.SIX,
    "7": Rank.SEVEN,
    "8": Rank.EIGHT,
    "9": Rank.NINE,
    "T": Rank.TEN,
    "t": Rank.TEN,
    "10": Rank.TEN,
    "J": Rank.JACK,
    "j": Rank.JACK,
    "Q": Rank.QUEEN,
    "q": Rank.QUEEN,
    "K": Rank.KING,
    "k": Rank.KING,
    "A": Rank.ACE,
    "a": Rank.ACE,
}

_SUIT_CHAR_MAP: Dict[str, Suit] = {
    "s": Suit.SPADES,
    "S": Suit.SPADES,
    "♠": Suit.SPADES,
    "h": Suit.HEARTS,
    "H": Suit.HEARTS,
    "♥": Suit.HEARTS,
    "c": Suit.CLUBS,
    "C": Suit.CLUBS,
    "♣": Suit.CLUBS,
    "d": Suit.DIAMONDS,
    "D": Suit.DIAMONDS,
    "♦": Suit.DIAMONDS,
}


@dataclass(frozen=True, order=False)
class Card:
    """Immutable representation of a playing card."""
    rank: Rank
    suit: Suit

    def __post_init__(self):
        if not isinstance(self.rank, Rank):
            object.__setattr__(self, "rank", Rank(self.rank))
        if not isinstance(self.suit, Suit):
            object.__setattr__(self, "suit", Suit(self.suit))

    @classmethod
    def from_str(cls, card_str: str) -> Card:
        """Parse card from string like 'As', 'Kh', '10s', 'Td', 'A♠'."""
        s = card_str.strip()
        if not s:
            raise ValueError("Empty card string")

        if len(s) == 3 and s.startswith("10"):
            rank_str = "10"
            suit_str = s[2]
        else:
            rank_str = s[0]
            suit_str = s[1:]

        if rank_str not in _RANK_CHAR_MAP:
            raise ValueError(f"Invalid rank in card string: {card_str}")
        if suit_str not in _SUIT_CHAR_MAP:
            raise ValueError(f"Invalid suit in card string: {card_str}")

        return cls(rank=_RANK_CHAR_MAP[rank_str], suit=_SUIT_CHAR_MAP[suit_str])

    @property
    def notation(self) -> str:
        """Compact string representation: e.g. 'As', 'Td'."""
        return f"{self.rank.symbol}{self.suit.value}"

    @property
    def display(self) -> str:
        """Human-readable representation: e.g. 'A♠', 'T♦'."""
        return f"{self.rank.symbol}{self.suit.symbol}"

    def to_dict(self) -> dict:
        """JSON serializable dictionary."""
        return {
            "rank": self.rank.value,
            "rank_symbol": self.rank.symbol,
            "suit": self.suit.value,
            "suit_symbol": self.suit.symbol,
            "color": self.suit.color_name,
            "notation": self.notation,
            "display": self.display,
        }

    def __str__(self) -> str:
        return self.notation

    def __repr__(self) -> str:
        return f"Card('{self.notation}')"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Card):
            return False
        return self.rank == other.rank and self.suit == other.suit

    def __lt__(self, other: Card) -> bool:
        if not isinstance(other, Card):
            return NotImplemented
        return self.rank.value < other.rank.value

    def __hash__(self) -> int:
        return hash((self.rank, self.suit))
