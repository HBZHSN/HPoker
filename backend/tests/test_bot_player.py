from backend.app.engine.state_machine import ActionType, Street, TableStateMachine
from backend.app.models.room import Room, RoomConfig
from backend.app.services.bot_player import choose_bot_action, execute_bot_action


def make_bot_table() -> TableStateMachine:
    table = TableStateMachine(max_seats=6, small_blind=1, big_blind=2)
    table.sit_down("bot_1", "测试机器人 1", seat_index=0, chips=100, is_bot=True)
    table.sit_down("p2", "Alice", seat_index=1, chips=100)
    table.sit_down("p3", "Bob", seat_index=2, chips=100)
    assert table.start_new_hand() is True
    assert table.current_turn_seat == 0
    return table


def test_bot_seat_is_serialized_and_only_bot_players_get_decisions():
    table = make_bot_table()

    bot_state = table.get_table_state("p2")["seats"][0]
    assert bot_state["is_bot"] is True
    assert choose_bot_action(table, "p2") is None


def test_bot_random_choice_maps_to_fold_call_and_raise():
    table = make_bot_table()

    fold = choose_bot_action(table, "bot_1", chooser=lambda options: "fold")
    assert fold is not None
    assert fold.action is ActionType.FOLD
    assert fold.amount == 0

    call = choose_bot_action(table, "bot_1", chooser=lambda options: "call")
    assert call is not None
    assert call.action is ActionType.CALL
    assert call.amount == 2

    raise_decision = choose_bot_action(table, "bot_1", chooser=lambda options: "raise")
    assert raise_decision is not None
    assert raise_decision.action is ActionType.RAISE
    assert raise_decision.amount == 4


def test_execute_bot_action_uses_the_same_table_rules():
    table = make_bot_table()
    decision = execute_bot_action(table, "bot_1", chooser=lambda options: "raise")

    assert decision is not None
    assert decision.action is ActionType.RAISE
    assert table.pot_manager.get_player_current_bet("bot_1") == 4
    assert table.street is Street.PREFLOP


def test_room_add_test_bot_only_works_between_hands_and_tracks_player():
    room = Room(
        host_player_id="host",
        config=RoomConfig(buyin_chips=100, cash_value=10, small_blind=1, max_seats=6),
    )
    assert room.sit_down_player("host", "Host", seat_index=0) is True

    bot = room.add_test_bot()
    assert bot is not None
    assert bot["is_bot"] is True
    assert bot["name"] == "测试机器人 1"
    assert room.historical_players[bot["player_id"]]["is_bot"] is True

    assert room.table.start_new_hand() is True
    assert room.add_test_bot() is None
