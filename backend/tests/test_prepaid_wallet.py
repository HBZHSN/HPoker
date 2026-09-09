import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.app.models.user import User
from backend.app.models.room import Room, RoomConfig
from backend.app.services.balance_manager import balance_manager, BalanceManager
from backend.app.services.user_manager import user_manager


@pytest.fixture
def wallet():
    for uid in ('admin', 'real'):
        user_manager._users[uid] = User(uid, uid, uid, '👤', is_admin=uid == 'admin')
    user_manager._tokens.update({'admin-token': 'admin', 'real-token': 'real'})
    return balance_manager


def change(wallet, amount='100', kind='deposit', request_id='one', **kwargs):
    return wallet.admin_wallet_change(user_id='real', amount=amount, kind=kind,
                                      operator_id='admin', request_id=request_id, **kwargs)


def test_deposit_withdraw_restart_and_idempotency(wallet):
    change(wallet)
    change(wallet)
    assert wallet.available_cents('real') == 10000
    with pytest.raises(ValueError):
        change(wallet, amount='101')
    change(wallet, amount='100', kind='withdraw', request_id='two')
    assert BalanceManager(database_path=wallet.storage_path).available_cents('real') == 0
    with pytest.raises(ValueError):
        change(wallet, amount='0.01', kind='withdraw', request_id='three')


@pytest.mark.parametrize('amount', ['0', '-1', 'NaN', 'Infinity', '0.001', 'abc', '100000001'])
def test_invalid_amounts(wallet, amount):
    with pytest.raises(ValueError):
        change(wallet, amount=amount)
    assert wallet.available_cents('real') == 0


def test_buyin_rebuy_cashout_and_insufficient_funds(wallet):
    room = Room('real', RoomConfig(), room_id='prepaid-room')
    with pytest.raises(ValueError, match='余额不足'):
        room.sit_down_player('real', 'real', 0)
    assert not room.table.active_seated_players
    change(wallet)
    assert room.sit_down_player('real', 'real', 0)
    assert wallet.available_cents('real') == 0
    with pytest.raises(ValueError):
        change(wallet, kind='withdraw', request_id='withdraw')
    assert room.leave_player('real')
    assert wallet.available_cents('real') == 10000
    room.cash_out_all_players()
    assert wallet.available_cents('real') == 10000


def test_storage_failure_rolls_back(wallet, monkeypatch):
    def fail():
        raise OSError('disk failure')
    monkeypatch.setattr(wallet, 'save_to_storage', fail)
    with pytest.raises(OSError):
        change(wallet)
    assert wallet.available_cents('real') == 0


def test_api_admin_only_and_no_reset(wallet):
    client = TestClient(app)
    payload = dict(user_id='real', amount='20', kind='deposit', request_id='api')
    assert client.post('/api/balance/wallet-change', json=payload).status_code == 401
    assert client.post('/api/balance/wallet-change', json=payload, headers={'Authorization': 'Bearer real-token'}).status_code == 403
    assert client.post('/api/balance/wallet-change', json=payload, headers={'Authorization': 'Bearer admin-token'}).status_code == 200
    result = client.get('/api/balance/my', headers={'Authorization': 'Bearer real-token'})
    assert result.json()['available_cash'] == 20
    assert client.delete('/api/balance/all-records', headers={'Authorization': 'Bearer admin-token'}).status_code == 410


def test_failed_rebuy_restores_seat(wallet):
    change(wallet)
    room = Room('real', RoomConfig(), room_id='rebuy-room')
    room.sit_down_player('real', 'real', 0)
    room.table.seats[0].chips = 0
    before = room.to_checkpoint_dict()
    with pytest.raises(ValueError, match='余额不足'):
        room.rebuy_player('real')
    assert room.to_checkpoint_dict() == before
    assert wallet.available_cents('real') == 0


def test_checkpoint_failure_restores_wallet(wallet, monkeypatch):
    from backend.app.services.room_manager import room_manager
    change(wallet)
    room = room_manager.create_room('real', RoomConfig())
    def fail(*args, **kwargs):
        raise OSError('checkpoint failure')
    monkeypatch.setattr(room_manager, 'checkpoint_room', fail)
    with pytest.raises(OSError):
        room_manager.transact_room(room.room_id, lambda r: r.sit_down_player('real', 'real', 0))
    assert wallet.available_cents('real') == 10000
    assert not room.table.active_seated_players


def test_legacy_debt_is_not_wallet_cash(wallet):
    entry = change(wallet)
    entry.entry_kind = 'settlement'
    entry.status = 'unsettled'
    assert wallet.available_cents('real') == 0
    assert wallet.get_user_records('real')


def test_concurrent_withdrawals_cannot_overdraw(wallet):
    from concurrent.futures import ThreadPoolExecutor
    from backend.app.api.endpoints import change_wallet, WalletChangeRequest
    from fastapi import HTTPException
    change(wallet)
    def withdraw(index):
        try:
            change_wallet(WalletChangeRequest(user_id='real', amount='70', kind='withdraw', request_id=str(index)), authorization='Bearer admin-token', token=None)
            return True
        except HTTPException:
            return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(withdraw, [1, 2])) == [False, True]
    assert wallet.available_cents('real') == 3000


def test_legacy_table_refunds_stay_historical(wallet):
    change(wallet)
    room = Room('real', RoomConfig(), room_id='legacy-room')
    room.sit_down_player('real', 'real', 0)
    debit = next(e for e in wallet._entries.values() if e.entry_kind == 'wallet_buyin')
    debit.entry_kind = 'buyin'
    assert room.leave_player('real')
    assert wallet.available_cents('real') == 10000
    with pytest.raises(ValueError, match='旧账牌桌'):
        room.sit_down_player('real', 'real', 0)


def test_create_room_insufficient_funds_and_ws_stable_spectate(wallet):
    from backend.app.services.room_manager import room_manager
    client = TestClient(app)

    # 1. Real user with 0 balance tries to create a cash room -> rejected with 400
    res = client.post('/api/rooms', json={
        'room_name': '高额桌',
        'buyin_chips': 1000,
        'cash_value': 100,
        'small_blind': 10,
        'action_timeout': 15,
        'max_seats': 6,
    }, headers={'Authorization': 'Bearer real-token'})
    assert res.status_code == 400
    assert '可用余额不足' in res.json()['detail']

    # 2. Real user with 0 balance can create an entertainment (cash_value=0) room
    play_res = client.post('/api/rooms', json={
        'room_name': '娱乐桌',
        'buyin_chips': 1000,
        'cash_value': 0,
        'small_blind': 10,
        'action_timeout': 15,
        'max_seats': 6,
    }, headers={'Authorization': 'Bearer real-token'})
    assert play_res.status_code == 200
    assert play_res.json()['room_id']

    # 3. Create cash room by admin, real user connects with 0 balance:
    # Does NOT crash websocket in reconnect loop; receives error and remains spectator
    admin_room = room_manager.create_room('admin', RoomConfig(buyin_chips=1000, cash_value=100))
    with client.websocket_connect(f'/ws/{admin_room.room_id}/real?token=real-token') as ws:
        # User receives state update and personal error message
        msgs = []
        for _ in range(5):
            msg = ws.receive_json()
            msgs.append(msg)
            if msg.get('event') == 'ERROR_MESSAGE':
                break
        error_msg = next((m for m in msgs if m.get('event') == 'ERROR_MESSAGE'), None)
        assert error_msg is not None
        assert '可用余额不足' in error_msg['payload']['message']

        # User is spectator, not seated
        assert not any(s and s['player_id'] == 'real' for s in admin_room.to_dict()['table']['seats'])

        # Explicit SIT_DOWN also rejected with error message without closing connection
        ws.send_json({'event': 'SIT_DOWN', 'payload': {'seat_index': 1}})
        reply = ws.receive_json()
        assert reply['event'] == 'ERROR_MESSAGE'
        assert '可用余额不足' in reply['payload']['message']

