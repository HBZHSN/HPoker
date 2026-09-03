"""Tests for Balance Ledger System, Test Account Isolation, and Batch Settlement."""

import pytest
from backend.app.services.balance_manager import BalanceManager
from backend.app.services.settlement import SettlementEngine
from backend.app.services.user_manager import UserManager, User


@pytest.fixture
def balance_mgr(tmp_path):
    mgr = BalanceManager(storage_path=":memory:")
    return mgr


@pytest.fixture
def user_mgr(tmp_path):
    mgr = UserManager(storage_path=":memory:")
    return mgr


def test_balance_recording_and_immediate(balance_mgr, user_mgr):
    participants = [
        {"player_id": "u_fwd", "player_name": "fwd", "rebuy_count": 1, "total_buyin_chips": 1000, "final_chips": 1500},
        {"player_id": "u_hx", "player_name": "hx", "rebuy_count": 1, "total_buyin_chips": 1000, "final_chips": 500},
    ]
    report = SettlementEngine.calculate_room_settlement(
        room_id="room-1",
        room_name="现金桌1",
        buyin_chips=1000,
        cash_value=100.0,
        player_data_list=participants,
    )

    # 1. Record as balance
    entry1 = balance_mgr.record_settlement(report, settlement_type="balance", u_mgr=user_mgr)
    assert entry1.status == "unsettled"
    assert entry1.settlement_type == "balance"
    assert entry1.is_test_game is False

    # Check user balances
    balances = balance_mgr.get_user_balances(include_test=False)
    assert len(balances) == 2
    fwd_bal = next(b for b in balances if b.user_id == "u_fwd")
    hx_bal = next(b for b in balances if b.user_id == "u_hx")
    assert fwd_bal.net_cash == 50.0
    assert hx_bal.net_cash == -50.0

    # 2. Record as immediate
    entry2 = balance_mgr.record_settlement(report, settlement_type="immediate", u_mgr=user_mgr)
    assert entry2.status == "settled"
    assert entry2.settlement_type == "immediate"

    # Pending balances should not change because entry2 was settled immediately
    balances2 = balance_mgr.get_user_balances(include_test=False)
    fwd_bal2 = next(b for b in balances2 if b.user_id == "u_fwd")
    assert fwd_bal2.net_cash == 50.0


def test_test_account_and_bot_anti_contamination(balance_mgr, user_mgr):
    # Test game with test1 and a real user fwd
    participants = [
        {"player_id": "u_fwd", "player_name": "fwd", "rebuy_count": 1, "total_buyin_chips": 1000, "final_chips": 1800},
        {"player_id": "u_test1", "player_name": "test1", "rebuy_count": 1, "total_buyin_chips": 1000, "final_chips": 200},
    ]
    report = SettlementEngine.calculate_room_settlement(
        room_id="room-test",
        room_name="测试对局",
        buyin_chips=1000,
        cash_value=100.0,
        player_data_list=participants,
    )

    entry = balance_mgr.record_settlement(report, settlement_type="balance", u_mgr=user_mgr)
    assert entry.is_test_game is True

    # Real balances should NOT be contaminated!
    real_balances = balance_mgr.get_user_balances(include_test=False)
    assert len(real_balances) == 0

    # But if include_test=True, test game data is visible in test view
    all_balances = balance_mgr.get_user_balances(include_test=True)
    assert len(all_balances) == 2
    assert any(b.user_id == "u_test1" and b.is_test for b in all_balances)

    # Test bot game
    bot_participants = [
        {"player_id": "u_hx", "player_name": "hx", "rebuy_count": 1, "total_buyin_chips": 1000, "final_chips": 1200},
        {"player_id": "bot_12345", "player_name": "测试机器人 1", "rebuy_count": 1, "total_buyin_chips": 1000, "final_chips": 800},
    ]
    report_bot = SettlementEngine.calculate_room_settlement(
        room_id="room-bot",
        room_name="人机对局",
        buyin_chips=1000,
        cash_value=100.0,
        player_data_list=bot_participants,
    )
    entry_bot = balance_mgr.record_settlement(report_bot, settlement_type="balance", u_mgr=user_mgr)
    assert entry_bot.is_test_game is True
    assert len(balance_mgr.get_user_balances(include_test=False)) == 0


def test_batch_settlement_and_balance_reset(balance_mgr, user_mgr):
    # Game 1: fwd +50, hx -50
    p1 = [
        {"player_id": "u_fwd", "player_name": "fwd", "rebuy_count": 1, "total_buyin_chips": 1000, "final_chips": 1500},
        {"player_id": "u_hx", "player_name": "hx", "rebuy_count": 1, "total_buyin_chips": 1000, "final_chips": 500},
    ]
    r1 = SettlementEngine.calculate_room_settlement("r1", "局1", 1000, 100.0, p1)
    balance_mgr.record_settlement(r1, settlement_type="balance", u_mgr=user_mgr)

    # Game 2: yy +30, fwd -30
    p2 = [
        {"player_id": "u_yy", "player_name": "yy", "rebuy_count": 1, "total_buyin_chips": 1000, "final_chips": 1300},
        {"player_id": "u_fwd", "player_name": "fwd", "rebuy_count": 1, "total_buyin_chips": 1000, "final_chips": 700},
    ]
    r2 = SettlementEngine.calculate_room_settlement("r2", "局2", 1000, 100.0, p2)
    balance_mgr.record_settlement(r2, settlement_type="balance", u_mgr=user_mgr)

    # Aggregated balances:
    # fwd: +50 - 30 = +20
    # yy: +30
    # hx: -50
    # Total sum is 0 (conserved)
    preview = balance_mgr.preview_batch_settlement(include_test=False)
    assert preview["entry_count"] == 2
    assert len(preview["transactions"]) == 2
    # hx owes 50: pays 30 to yy, 20 to fwd
    txs = preview["transactions"]
    hx_pays_yy = next((t for t in txs if t["from_player_id"] == "u_hx" and t["to_player_id"] == "u_yy"), None)
    hx_pays_fwd = next((t for t in txs if t["from_player_id"] == "u_hx" and t["to_player_id"] == "u_fwd"), None)
    assert hx_pays_yy is not None and hx_pays_yy["amount_cash"] == 30.0
    assert hx_pays_fwd is not None and hx_pays_fwd["amount_cash"] == 20.0

    # Execute batch settlement
    batch = balance_mgr.settle_batch(operator_id="u_admin", operator_name="房主 (Admin)")
    assert batch.total_transferred_cash == 50.0
    assert len(batch.entry_ids) == 2

    # After batch settlement, pending balances for real users are now empty (reset)
    post_balances = balance_mgr.get_user_balances(include_test=False)
    assert len(post_balances) == 0

    # Batches list now contains this batch
    batches = balance_mgr.list_batches()
    assert len(batches) == 1
    assert batches[0]["batch_id"] == batch.batch_id


def test_preset_test_accounts(user_mgr):
    # Verify test1, test2, test3 exist by default
    test1 = user_mgr.get_user("u_test1")
    test2 = user_mgr.get_user("u_test2")
    test3 = user_mgr.get_user("u_test3")

    assert test1 is not None and test1.username == "test1" and test1.is_test_account is True
    assert test2 is not None and test2.username == "test2" and test2.is_test_account is True
    assert test3 is not None and test3.username == "test3" and test3.is_test_account is True

    # Verify password '123'
    u, token = user_mgr.authenticate("test1", "123")
    assert u is not None and u.user_id == "u_test1"
    u2, _ = user_mgr.authenticate("test2", "123")
    assert u2 is not None and u2.user_id == "u_test2"
    u3, _ = user_mgr.authenticate("test3", "123")
    assert u3 is not None and u3.user_id == "u_test3"


def test_balance_rest_api(tmp_path):
    from fastapi.testclient import TestClient
    from backend.main import app
    from backend.app.services.balance_manager import balance_manager
    from backend.app.services.room_manager import room_manager
    from backend.app.models.room import RoomConfig

    client = TestClient(app)

    # 1. Login test1
    login_res = client.post("/api/auth/login", json={"username": "test1", "password": "123"})
    assert login_res.status_code == 200
    assert login_res.json()["user"]["is_test"] is True

    # 2. Query my balance
    my_res = client.get("/api/balance/my?user_id=u_admin")
    assert my_res.status_code == 200
    data = my_res.json()
    assert "pending_net_cash" in data
    assert "records" in data

    # 3. Query overview
    overview_res = client.get("/api/balance/overview?include_test=false")
    assert overview_res.status_code == 200
    assert "user_balances" in overview_res.json()
    assert "preview" in overview_res.json()

    # 4. Settle batch without admin permission should fail
    fail_res = client.post("/api/balance/settle-batch", json={"operator_id": "u_fwd"})
    assert fail_res.status_code == 403

    # 5. Clear test records without admin should fail
    clear_fail = client.delete("/api/balance/test-records?admin_id=u_fwd")
    assert clear_fail.status_code == 403

    # 6. Clear test records with admin
    clear_ok = client.delete("/api/balance/test-records?admin_id=u_admin")
    assert clear_ok.status_code == 200
    assert "deleted_count" in clear_ok.json()

