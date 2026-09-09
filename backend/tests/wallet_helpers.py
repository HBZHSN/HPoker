"""Assertions about table cash movements, independent of initial admin funding."""
from types import SimpleNamespace
from backend.app.services.balance_manager import balance_manager


def table_balances(**kwargs):
    totals = {}
    for entry in balance_manager._entries.values():
        if entry.entry_kind not in {'wallet_buyin', 'wallet_cashout', 'wallet_mode_change'}:
            continue
        for p in entry.participants:
            totals[p.player_id] = round(totals.get(p.player_id, 0) + p.net_cash, 2)
    return [SimpleNamespace(user_id=uid, net_cash=value) for uid, value in sorted(totals.items(), key=lambda item: -item[1]) if value]


def table_entries():
    return [e for e in balance_manager._entries.values() if e.entry_kind != 'wallet_deposit']
