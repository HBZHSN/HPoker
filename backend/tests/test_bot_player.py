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


def test_bot_strictly_uses_only_own_visible_information():
    """Verify that the bot only passes visible information to the equity calculator."""
    from backend.app.engine.card import Card
    table = make_bot_table()
    captured_args = {}

    def spy_calculator(**kwargs):
        captured_args.update(kwargs)
        return {
            "equity": {"winRate": 0.5, "tieRate": 0.0, "loseRate": 0.5},
            "potOdds": {"decision": "call", "need_rate": 0.25},
            "outs": {"total_outs": 0},
            "currentHand": {"categoryValue": 1},
        }

    bot_seat = table.seats[0]
    p2_seat = table.seats[1]
    p3_seat = table.seats[2]

    # Pre-set cards
    bot_seat.hole_cards = [Card.from_str("Ah"), Card.from_str("Kd")]
    p2_seat.hole_cards = [Card.from_str("7c"), Card.from_str("2d")]
    p3_seat.hole_cards = [Card.from_str("Qh"), Card.from_str("Qs")]
    table.board_cards = [Card.from_str("Js"), Card.from_str("Ts"), Card.from_str("9s")]

    decision = choose_bot_action(table, "bot_1", equity_calculator=spy_calculator)
    assert decision is not None

    # 1. hero_cards must only contain bot's own hole cards
    assert captured_args["hero_cards"] == bot_seat.hole_cards
    assert p2_seat.hole_cards[0] not in captured_args["hero_cards"]
    assert p3_seat.hole_cards[0] not in captured_args["hero_cards"]

    # 2. board_cards must be the community cards
    assert captured_args["board_cards"] == table.board_cards

    # 3. num_opponents is the number of active opponents (Alice and Bob = 2)
    assert captured_args["num_opponents"] == 2

    # 4. pot_size is current pot
    assert captured_args["pot_size"] == table.pot_manager.total_pot_amount

    # 5. to_call is legal.call_amount
    legal = table.get_legal_actions("bot_1")
    assert captured_args["to_call"] == legal.call_amount


def test_bot_raises_on_high_equity():
    """Bot chooses RAISE when holding dominant equity."""
    table = make_bot_table()

    def high_equity_calculator(**kwargs):
        return {
            "equity": {"winRate": 0.85, "tieRate": 0.0, "loseRate": 0.15},
            "potOdds": {"decision": "call", "need_rate": 0.3},
            "outs": {"total_outs": 0},
            "currentHand": {"categoryValue": 4},  # Trips
        }

    decision = choose_bot_action(table, "bot_1", equity_calculator=high_equity_calculator)
    assert decision is not None
    assert decision.action is ActionType.RAISE
    assert decision.amount == 4  # min_raise_to


def test_bot_calls_on_positive_ev():
    """Bot chooses CALL when equity exceeds required pot odds."""
    table = make_bot_table()

    def positive_ev_calculator(**kwargs):
        return {
            "equity": {"winRate": 0.45, "tieRate": 0.0, "loseRate": 0.55},
            "potOdds": {"decision": "call", "need_rate": 0.30},
            "outs": {"total_outs": 4},
            "currentHand": {"categoryValue": 1},
        }

    decision = choose_bot_action(table, "bot_1", equity_calculator=positive_ev_calculator)
    assert decision is not None
    assert decision.action is ActionType.CALL
    assert decision.amount == 2


def test_bot_folds_on_negative_ev_facing_bet():
    """Bot chooses FOLD when equity is poor and cannot check."""
    table = make_bot_table()

    def poor_equity_calculator(**kwargs):
        return {
            "equity": {"winRate": 0.10, "tieRate": 0.0, "loseRate": 0.90},
            "potOdds": {"decision": "fold", "need_rate": 0.40},
            "outs": {"total_outs": 0},
            "currentHand": {"categoryValue": 1},
        }

    decision = choose_bot_action(table, "bot_1", equity_calculator=poor_equity_calculator)
    assert decision is not None
    assert decision.action is ActionType.FOLD
    assert decision.amount == 0


def test_bot_checks_when_free_and_moderate_equity():
    """Bot chooses CHECK when to_call == 0 and equity is moderate."""
    table = TableStateMachine(max_seats=6, small_blind=1, big_blind=2)
    table.sit_down("p1", "Alice", seat_index=0, chips=100)
    table.sit_down("bot_1", "测试机器人 1", seat_index=1, chips=100, is_bot=True)
    assert table.start_new_hand() is True

    # Preflop: p1 (SB) calls BB, now it's bot's turn with to_call == 0
    table.handle_action("p1", ActionType.CALL)
    assert table.current_turn_seat == 1
    legal = table.get_legal_actions("bot_1")
    assert legal.can_check is True

    def moderate_equity_calculator(**kwargs):
        return {
            "equity": {"winRate": 0.40, "tieRate": 0.0, "loseRate": 0.60},
            "potOdds": None,
            "outs": {"total_outs": 0},
            "currentHand": {"categoryValue": 1},
        }

    decision = choose_bot_action(table, "bot_1", equity_calculator=moderate_equity_calculator)
    assert decision is not None
    assert decision.action is ActionType.CHECK


def test_bot_real_compute_equity_decision():
    """Test full integration with real compute_equity."""
    from backend.app.engine.card import Card
    table = make_bot_table()
    bot_seat = table.seats[0]
    # Give bot pocket Aces (monster hand preflop)
    bot_seat.hole_cards = [Card.from_str("Ah"), Card.from_str("As")]

    decision = choose_bot_action(table, "bot_1")
    assert decision is not None
    # AA preflop has ~85% equity vs 2 random opponents, should raise
    assert decision.action is ActionType.RAISE
    assert decision.amount == 4


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
