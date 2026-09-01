import pytest
from backend.app.engine.card import Card, Rank, Suit
from backend.app.engine.deck import Deck


def test_card_creation_and_properties():
    card = Card(rank=Rank.ACE, suit=Suit.SPADES)
    assert card.rank == Rank.ACE
    assert card.suit == Suit.SPADES
    assert card.notation == "As"
    assert card.display == "A♠"
    assert card.suit.color_name == "black"


def test_card_from_str():
    c1 = Card.from_str("As")
    assert c1 == Card(Rank.ACE, Suit.SPADES)

    c2 = Card.from_str("10h")
    assert c2 == Card(Rank.TEN, Suit.HEARTS)

    c3 = Card.from_str("Td")
    assert c3 == Card(Rank.TEN, Suit.DIAMONDS)

    c4 = Card.from_str("2c")
    assert c4 == Card(Rank.TWO, Suit.CLUBS)

    c5 = Card.from_str("K♥")
    assert c5 == Card(Rank.KING, Suit.HEARTS)


def test_card_dict_serialization():
    card = Card.from_str("Qd")
    data = card.to_dict()
    assert data["rank"] == 12
    assert data["rank_symbol"] == "Q"
    assert data["suit"] == "d"
    assert data["color"] == "blue"
    assert data["notation"] == "Qd"


def test_deck_initialization_and_shuffle():
    deck = Deck()
    assert deck.remaining_count == 52
    assert len(deck) == 52

    # Draw 2 hole cards
    cards = deck.draw(2)
    assert len(cards) == 2
    assert deck.remaining_count == 50

    # Burn 1 card and draw flop (3 cards)
    burned = deck.burn()
    assert deck.remaining_count == 49
    assert len(deck.burned_cards) == 1
    assert deck.burned_cards[0] == burned

    flop = deck.draw(3)
    assert len(flop) == 3
    assert deck.remaining_count == 46


def test_deck_draw_boundary():
    deck = Deck()
    cards = deck.draw(52)
    assert len(cards) == 52
    assert deck.remaining_count == 0

    with pytest.raises(ValueError):
        deck.draw(1)

    deck.reset()
    assert deck.remaining_count == 52
