"""Poker Deck implementation with Cryptographically Secure Pseudo-Random Number Generator (CSPRNG).

Uses Python's secrets module (SystemRandom) to ensure unbiased,
unpredictable shuffling for real-money-grade poker games.
"""

from __future__ import annotations
import secrets
from typing import List, Optional
from backend.app.engine.card import Card, Rank, Suit


class Deck:
    """Standard 52-card poker deck with CSPRNG Fisher-Yates shuffle."""

    def __init__(self, auto_shuffle: bool = True):
        self._cards: List[Card] = []
        self._burned_cards: List[Card] = []
        self._rng = secrets.SystemRandom()
        self.reset(shuffle_now=auto_shuffle)

    def reset(self, shuffle_now: bool = True) -> None:
        """Reset the deck to all 52 standard cards."""
        self._cards = [
            Card(rank=rank, suit=suit)
            for suit in Suit
            for rank in Rank
        ]
        self._burned_cards.clear()
        if shuffle_now:
            self.shuffle()

    def shuffle(self) -> None:
        """Perform a cryptographically secure in-place Fisher-Yates shuffle."""
        self._rng.shuffle(self._cards)

    def draw(self, count: int = 1) -> List[Card]:
        """Draw `count` cards from the top of the deck."""
        if count < 0:
            raise ValueError("Cannot draw negative number of cards")
        if count > len(self._cards):
            raise ValueError(f"Not enough cards in deck to draw {count}. Remaining: {len(self._cards)}")

        drawn = [self._cards.pop() for _ in range(count)]
        return drawn

    def draw_one(self) -> Card:
        """Draw a single card."""
        cards = self.draw(1)
        return cards[0]

    def burn(self) -> Card:
        """Burn one card before dealing community cards (Flop/Turn/River)."""
        card = self.draw_one()
        self._burned_cards.append(card)
        return card

    @property
    def remaining_count(self) -> int:
        """Number of cards remaining in the deck."""
        return len(self._cards)

    @property
    def burned_cards(self) -> List[Card]:
        """List of burned cards in this hand."""
        return list(self._burned_cards)

    def __len__(self) -> int:
        return len(self._cards)

    def __repr__(self) -> str:
        return f"Deck(remaining={len(self._cards)}, burned={len(self._burned_cards)})"
