"""Unit tests for the Texas Hold'em Equity Calculator and Decision Engine."""

import pytest
from backend.app.engine.card import Card, Rank, Suit
from backend.app.engine.equity import compute_equity, _identify_outs, _mc_equity, _exact_river_1v1


def test_river_1v1_exact_enumeration():
    """On river vs 1 opponent, equity is computed via exact enumeration of all 990 hands."""
    hero = [Card.from_str("Ah"), Card.from_str("Kd")]
    # Board with nut broadway straight
    board = [Card.from_str("Qh"), Card.from_str("Jc"), Card.from_str("Th"), Card.from_str("2c"), Card.from_str("3s")]

    res = compute_equity(hero, board, num_opponents=1)
    eq = res["equity"]
    assert eq["strategy"] == "exact"
    # Hero holds nut straight (broadway A-K-Q-J-T). No opponent can beat it; only tie if opponent has K
    assert eq["winRate"] > 0.85
    assert eq["loseRate"] == 0.0
    assert abs(eq["winRate"] + eq["tieRate"] + eq["loseRate"] - 1.0) < 1e-6


def test_multi_opponent_equity_monotonicity():
    """Win rate strictly decreases as number of active opponents increases in multi-way pots."""
    hero = [Card.from_str("Ah"), Card.from_str("8c")]
    board = [Card.from_str("As"), Card.from_str("7d"), Card.from_str("2c"), Card.from_str("3h"), Card.from_str("4d")]

    res1 = compute_equity(hero, board, num_opponents=1)
    res2 = compute_equity(hero, board, num_opponents=2)
    res4 = compute_equity(hero, board, num_opponents=4)

    # Against 1 opponent, top pair ~70% win rate
    assert res1["equity"]["winRate"] > 0.60
    # Against 2 opponents, win rate drops significantly
    assert res1["equity"]["winRate"] > res2["equity"]["winRate"]
    # Against 4 opponents, win rate drops to under 25%
    assert res2["equity"]["winRate"] > res4["equity"]["winRate"]
    assert res4["equity"]["winRate"] < 0.25


def test_flush_draw_outs_and_hit_rates():
    """Flush draw on flop has exactly 9 outs and mathematically exact hit rates."""
    hero = [Card.from_str("Ah"), Card.from_str("Kh")]
    board = [Card.from_str("7h"), Card.from_str("2h"), Card.from_str("Jc")]

    res = compute_equity(hero, board, num_opponents=1)
    outs = res["outs"]
    assert outs is not None

    flush_cat = next((c for c in outs["categories"] if "同花" in c["name"]), None)
    assert flush_cat is not None
    assert flush_cat["outs"] == 9

    # On flop (47 remaining unseen cards):
    # turn hit pct: 9 / 47 ≈ 0.1915
    assert abs(outs["turn_hit_pct"] - (9.0 / 47.0)) < 1e-4
    # river hit pct: 1 - (38/47)*(37/46) ≈ 0.3497
    expected_river_hit = 1.0 - (38.0 / 47.0) * (37.0 / 46.0)
    assert abs(outs["river_hit_pct"] - expected_river_hit) < 1e-4


def test_straight_draw_classification():
    """Correctly distinguish OESD (8 outs), Gutshot (4 outs), Wheel (4 outs), Broadway (4 outs), and Double Gutshot (8 outs)."""
    # 1. Open-ended (5-6 on 7-8-2) -> 8 outs (4s and 9s)
    res_oesd = compute_equity([Card.from_str("5h"), Card.from_str("6h")], [Card.from_str("7c"), Card.from_str("8d"), Card.from_str("2s")])
    cat_oesd = next((c for c in res_oesd["outs"]["categories"] if "顺子" in c["name"]), None)
    assert cat_oesd is not None
    assert cat_oesd["name"] == "两头顺子"
    assert cat_oesd["outs"] == 8

    # 2. Gutshot (5-6 on 7-9-2) -> 4 outs (8s)
    res_gut = compute_equity([Card.from_str("5h"), Card.from_str("6h")], [Card.from_str("7c"), Card.from_str("9d"), Card.from_str("2s")])
    cat_gut = next((c for c in res_gut["outs"]["categories"] if "顺子" in c["name"]), None)
    assert cat_gut is not None
    assert cat_gut["name"] == "卡门顺子"
    assert cat_gut["outs"] == 4

    # 3. Wheel draw (A-2 on 3-4-K) -> 4 outs (only 5s, cannot wrap below Ace)
    res_wheel = compute_equity([Card.from_str("Ah"), Card.from_str("2h")], [Card.from_str("3c"), Card.from_str("4d"), Card.from_str("Ks")])
    cat_wheel = next((c for c in res_wheel["outs"]["categories"] if "顺子" in c["name"]), None)
    assert cat_wheel is not None
    assert cat_wheel["name"] == "卡门顺子"
    assert cat_wheel["outs"] == 4

    # 4. Broadway draw (A-K on Q-J-2) -> 4 outs (only 10s, cannot wrap above Ace)
    res_broad = compute_equity([Card.from_str("Ah"), Card.from_str("Kh")], [Card.from_str("Qc"), Card.from_str("Jd"), Card.from_str("2s")])
    cat_broad = next((c for c in res_broad["outs"]["categories"] if "顺子" in c["name"]), None)
    assert cat_broad is not None
    assert cat_broad["name"] == "卡门顺子"
    assert cat_broad["outs"] == 4

    # 5. Double Gutshot (5-7 on 8-9-J) -> 8 outs (6s and 10s)
    res_dg = compute_equity([Card.from_str("5h"), Card.from_str("7h")], [Card.from_str("8c"), Card.from_str("9d"), Card.from_str("Jc")])
    cat_dg = next((c for c in res_dg["outs"]["categories"] if "顺子" in c["name"]), None)
    assert cat_dg is not None
    assert cat_dg["name"] == "双卡顺子"
    assert cat_dg["outs"] == 8


def test_set_to_full_house_or_quads():
    """Set on unpaired flop has exactly 7 outs to improve (6 to Full House, 1 to Quads)."""
    hero = [Card.from_str("7h"), Card.from_str("7s")]
    board = [Card.from_str("7c"), Card.from_str("Kd"), Card.from_str("2s")]

    res = compute_equity(hero, board, num_opponents=1)
    outs = res["outs"]
    assert outs is not None
    cat = next((c for c in outs["categories"] if "葫芦" in c["name"]), None)
    assert cat is not None
    assert cat["outs"] == 7  # 3 Ks, 3 2s, 1 7


def test_straight_flush_draw_deduplication():
    """Open-ended straight flush draw has 15 unique outs (9 flush + 8 straight - 2 overlap)."""
    hero = [Card.from_str("8h"), Card.from_str("9h")]
    board = [Card.from_str("6h"), Card.from_str("7h"), Card.from_str("2d")]

    res = compute_equity(hero, board, num_opponents=1)
    outs = res["outs"]
    assert outs is not None
    assert outs["total_outs"] == 15


def test_turn_stage_outs_and_hit_rate():
    """On turn, turn_hit_pct is None and river_hit_pct is outs / 46."""
    hero = [Card.from_str("5h"), Card.from_str("6h")]
    board = [Card.from_str("7c"), Card.from_str("8d"), Card.from_str("2s"), Card.from_str("Kd")]

    res = compute_equity(hero, board, num_opponents=1)
    outs = res["outs"]
    assert outs is not None
    assert outs["turn_hit_pct"] is None
    assert abs(outs["river_hit_pct"] - (8.0 / 46.0)) < 1e-4


def test_pot_odds_positive_ev_call():
    """Call recommended when equity exceeds required pot odds."""
    hero = [Card.from_str("Ah"), Card.from_str("As")]
    board = [Card.from_str("7c"), Card.from_str("8d"), Card.from_str("2s")]
    # Pot 100, call 20 -> need 16.7%
    res = compute_equity(hero, board, num_opponents=1, pot_size=100, to_call=20)
    po = res["potOdds"]
    assert po is not None
    assert po["decision"] == "call"
    assert po["pot_odds_ratio_str"] == "5.0:1"
    assert abs(po["need_rate"] - (20.0 / 120.0)) < 1e-4
    assert "赔率划算" in po["reason"]


def test_pot_odds_huge_allin_fold_with_draw():
    """Fold recommended when facing huge all-in even when holding an 8-out draw."""
    hero = [Card.from_str("5h"), Card.from_str("6h")]
    board = [Card.from_str("7c"), Card.from_str("8d"), Card.from_str("2s"), Card.from_str("Kd")]
    # Opponent shoves 10,000 into 100 pot -> need 99%
    res = compute_equity(hero, board, num_opponents=1, pot_size=100, to_call=10000)
    po = res["potOdds"]
    assert po is not None
    assert po["decision"] == "fold"
    assert "赔率不划算" in po["reason"]
