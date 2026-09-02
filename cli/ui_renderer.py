"""UI Renderer for low-profile, clean, and elegant CLI gameplay."""

from __future__ import annotations

import sys
from typing import Any, Dict, Iterable, List, Optional

from cli.text_utils import clip_display, display_width, pad_display


class Colors:
    """Low-profile ANSI colors."""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    UNDERLINE = "\033[4m"

    # Subtle Foreground
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    # Bright / Soft
    BRIGHT_BLACK = "\033[90m"
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"

    # Background
    BG_DARK = "\033[40m"
    BG_BLUE = "\033[44m"


class PokerUiRenderer:
    """Renders poker game components in a clean, discreet terminal style."""

    TABLE_INNER_WIDTH = 96

    def __init__(self, enable_color: Optional[bool] = None, mode: str = "dashboard"):
        if enable_color is None:
            self.enable_color = sys.stdout.isatty()
        else:
            self.enable_color = enable_color
        self.mode = mode  # "dashboard" or "stream"

    def c(self, text: str, color_code: str) -> str:
        """Apply ANSI color if enabled."""
        if not self.enable_color:
            return text
        return f"{color_code}{text}{Colors.RESET}"

    @staticmethod
    def _int(value: Any, default: int = 0) -> int:
        """Convert API values defensively for rendering and arithmetic."""

        try:
            return int(float(value))
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _text(value: Any, default: str = "") -> str:
        return default if value is None else str(value)

    def _styled_status(self, text: str, *, positive: bool = False, negative: bool = False) -> str:
        if positive:
            return self.c(text, Colors.BRIGHT_GREEN + Colors.BOLD)
        if negative:
            return self.c(text, Colors.BRIGHT_RED + Colors.BOLD)
        return text

    @staticmethod
    def _display_width(text: str) -> int:
        """Measure visible columns, excluding ANSI color escape sequences."""

        return display_width(text)

    @staticmethod
    def _pad_display(text: Any, width: int) -> str:
        """Pad by terminal columns instead of Python code-point count."""

        return pad_display(str(text), width)

    @classmethod
    def _columns(cls, values: Iterable[Any], widths: Iterable[int]) -> str:
        return " ".join(cls._pad_display(value, width) for value, width in zip(values, widths))

    @classmethod
    def _table_line(cls, content: Any = "") -> str:
        content_width = cls.TABLE_INNER_WIDTH - 2
        return f"│ {pad_display(str(content), content_width)} │"

    @classmethod
    def _table_separator(cls) -> str:
        return f"├{'─' * cls.TABLE_INNER_WIDTH}┤"

    @classmethod
    def _table_top(cls, content: str) -> str:
        clipped = clip_display(content, cls.TABLE_INNER_WIDTH)
        return f"┌{clipped}{'─' * max(0, cls.TABLE_INNER_WIDTH - display_width(clipped))}┐"

    @classmethod
    def _table_bottom(cls) -> str:
        return f"└{'─' * cls.TABLE_INNER_WIDTH}┘"

    def clear_screen(self):
        """Clear terminal screen without excessive flicker."""
        if self.mode == "dashboard":
            # ANSI escape sequence to clear screen and home cursor
            sys.stdout.write("\033[2J\033[H")
            sys.stdout.flush()

    def format_card(self, card_dict: Optional[Dict[str, Any]]) -> str:
        """Format a single card with suit and rank."""
        if not card_dict:
            return "[??]"

        rank = card_dict.get("rank_symbol") or str(card_dict.get("rank", ""))
        suit_sym = card_dict.get("suit_symbol") or ""
        suit = card_dict.get("suit") or ""

        # Fallback if symbols missing
        if not suit_sym:
            s_map = {"s": "♠", "h": "♥", "c": "♣", "d": "♦"}
            suit_sym = s_map.get(str(suit).lower(), str(suit))

        card_str = f"{rank}{suit_sym}"

        if not self.enable_color:
            return f"[{card_str}]"

        color_name = card_dict.get("color", "")
        if color_name == "red" or suit in ("h", "H", "♥"):
            styled = self.c(card_str, Colors.BRIGHT_RED + Colors.BOLD)
        elif color_name == "blue" or suit in ("d", "D", "♦"):
            styled = self.c(card_str, Colors.BRIGHT_BLUE + Colors.BOLD)
        elif color_name == "green" or suit in ("c", "C", "♣"):
            styled = self.c(card_str, Colors.BRIGHT_GREEN + Colors.BOLD)
        else:
            styled = self.c(card_str, Colors.BRIGHT_WHITE + Colors.BOLD)

        return f"[{styled}]"

    def format_cards(self, cards: List[Dict[str, Any]]) -> str:
        """Format a list of cards side-by-side."""
        if not cards:
            return "(无)"
        return " ".join(self.format_card(c) for c in cards)

    def format_street_name(self, street: str) -> str:
        """Translate street name to readable Chinese."""
        mapping = {
            "IDLE": "等待开局 (IDLE)",
            "PREFLOP": "翻牌前 (Preflop)",
            "FLOP": "翻牌圈 (Flop)",
            "TURN": "转牌圈 (Turn)",
            "RIVER": "河牌圈 (River)",
            "RIT_DECISION": "多次发牌协商 (Run It Twice)",
            "SHOWDOWN": "摊牌比牌 (Showdown)",
            "HAND_END": "本局结算 (Hand End)",
        }
        return mapping.get(street, street)

    def render_lobby(
        self,
        current_user: Dict[str, Any],
        rooms: List[Dict[str, Any]],
        server_url: str = "",
    ) -> str:
        """Render the room lobby."""
        lines = []
        user_name = current_user.get("nickname") or current_user.get("username", "Unknown")
        user_id = current_user.get("user_id", "")
        is_admin = bool(current_user.get("is_admin", False))

        title = f" HPoker 游戏大厅 | 当前登录: {user_name} ({user_id}) "
        sep = "=" * max(68, len(title) + 4)
        lines.append(self.c(sep, Colors.CYAN))
        lines.append(self.c(f"  {title}", Colors.BOLD + Colors.BRIGHT_WHITE))
        lines.append(self.c(sep, Colors.CYAN))
        lines.append("")

        if not rooms:
            lines.append("  当前没有进行中的房间。")
            lines.append("  输入 " + self.c("c", Colors.BRIGHT_GREEN) + " 或 " + self.c("create", Colors.BRIGHT_GREEN) + " 创建新房间，或 " + self.c("r", Colors.BRIGHT_CYAN) + " 刷新列表。")
        else:
            lines.append(f"  当前活跃房间列表 ({len(rooms)} 个):")
            lines.append(self.c("  " + "-" * 66, Colors.DIM))
            header = f"  {'序号':<4} {'房间名称':<16} {'房间ID':<10} {'盲注':<10} {'买入筹码':<10} {'座位/状态':<12}"
            lines.append(self.c(header, Colors.BOLD))
            lines.append(self.c("  " + "-" * 66, Colors.DIM))

            for idx, r in enumerate(rooms, start=1):
                r_id = r.get("room_id", "")
                r_name = r.get("room_name") or r.get("config", {}).get("room_name", "德州现金桌")
                cfg = r.get("config", {})
                sb = cfg.get("small_blind", 10)
                bb = sb * 2
                buyin = cfg.get("buyin_chips", 1000)
                max_s = cfg.get("max_seats", 6)
                seats_count = r.get("seated_players_count", r.get("seated_count", 0))
                status = "进行中" if not r.get("is_ended", False) else "已结束"

                # Truncate room name if too long
                r_name_disp = (r_name[:14] + "..") if len(r_name) > 16 else r_name
                blinds_disp = f"{sb}/{bb}"
                seats_disp = f"{seats_count}/{max_s} ({status})"

                row = f"  [{idx:<2}] {r_name_disp:<16} {r_id:<10} {blinds_disp:<10} {buyin:<10} {seats_disp:<12}"
                lines.append(row)

            lines.append(self.c("  " + "-" * 66, Colors.DIM))

        lines.append("")
        lines.append(self.c("  操作指令:", Colors.BOLD))
        if rooms:
            lines.append("    • 输入 " + self.c("1", Colors.BRIGHT_YELLOW) + " ~ " + self.c(str(len(rooms)), Colors.BRIGHT_YELLOW) + " : 快速加入对应序号房间")
        lines.append("    • " + self.c("join <序号|room_id>", Colors.BRIGHT_GREEN) + " : 加入指定房间")
        lines.append("    • " + self.c("create [选项]", Colors.BRIGHT_GREEN) + " : 创建房间（默认值可直接回车）")
        lines.append("    • " + self.c("rooms / refresh", Colors.BRIGHT_CYAN) + " : 刷新房间列表")
        lines.append("    • " + self.c("info <序号|room_id>", Colors.WHITE) + " : 查看房间详情，不入座")
        lines.append("    • " + self.c("users", Colors.WHITE) + "             : 查看可登录用户")
        lines.append("    • " + self.c("mode [dashboard|stream]", Colors.CYAN) + " : 切换显示模式")
        lines.append("    • " + self.c("user / logout", Colors.BRIGHT_MAGENTA) + " : 切换用户登录")
        lines.append("    • " + self.c("help", Colors.BRIGHT_WHITE) + "             : 查看大厅帮助")
        lines.append("    • " + self.c("quit", Colors.BRIGHT_RED) + " 或 " + self.c("q", Colors.BRIGHT_RED) + " : 退出程序")
        if is_admin:
            lines.append("    • 管理员可通过牌桌内 " + self.c("delete", Colors.BRIGHT_RED) + " 解散房间")
        lines.append("")

        return "\n".join(lines)

    def render_table_dashboard(
        self,
        room: Dict[str, Any],
        current_user_id: str,
    ) -> str:
        """Render complete poker table dashboard."""
        lines = []
        r_id = room.get("room_id", "")
        table = room.get("table", {})
        cfg = room.get("config", {})
        r_name = cfg.get("room_name") or room.get("room_name") or "德州扑克"
        sb = self._int(cfg.get("small_blind", table.get("small_blind", 10)), 10)
        bb = self._int(cfg.get("big_blind", table.get("big_blind", sb * 2)), sb * 2)
        timeout_sec = self._int(cfg.get("action_timeout", 15), 15)
        host_id = room.get("host_player_id", "")
        is_ended = room.get("is_ended", False)

        hand_num = table.get("hand_number", 0)
        street = table.get("street", "IDLE")
        total_pot = table.get("total_pot", 0)
        pots = table.get("pots", [])
        board_cards = table.get("board_cards", [])
        board_cards_2 = table.get("board_cards_2", [])
        rit_enabled = table.get("rit_enabled", False)
        current_turn_seat = table.get("current_turn_seat")
        dealer_seat = table.get("dealer_seat")
        sb_seat = table.get("sb_seat")
        bb_seat = table.get("bb_seat")
        seats = table.get("seats", [])
        legal_actions = table.get("legal_actions") or {}
        action_history = table.get("action_history", [])
        hand_results = table.get("hand_results", [])
        ready_player_ids = table.get("ready_player_ids", [])
        current_turn_duration = self._int(table.get("current_turn_duration", timeout_sec), timeout_sec)
        is_using_time_bank = bool(table.get("is_using_time_bank", False))

        # Header bar.  Every line uses the same visible width; Chinese text,
        # suit symbols and emoji are measured in terminal columns below.
        header_title = f"HPoker 现金桌: {r_name} (ID: {r_id})"
        blinds_info = f"盲注: {sb}/{bb} | 超时: {timeout_sec}s"
        lines.append(self.c(self._table_top(f"─ {header_title} ─ {blinds_info} "), Colors.CYAN))

        # Room / Street status
        street_desc = self.format_street_name(street)
        pot_info = f"总底池: {total_pot}"
        if len(pots) > 1:
            pots_breakdown = ", ".join(f"池#{i+1}:{p.get('amount', 0)}" for i, p in enumerate(pots))
            pot_info += f" ({pots_breakdown})"

        status_line = f"局号: #{hand_num:<3} | 阶段: {street_desc} | {pot_info}"
        lines.append(self._table_line(status_line))

        # Board cards
        board_str = self.format_cards(board_cards)
        if rit_enabled and board_cards_2:
            board_str_2 = self.format_cards(board_cards_2)
            lines.append(self._table_line(f"公共牌 [板1]: {board_str}"))
            lines.append(self._table_line(f"公共牌 [板2]: {board_str_2}"))
        else:
            lines.append(self._table_line(f"公共牌: {board_str}"))

        lines.append(self.c(self._table_separator(), Colors.CYAN))

        # Seats table header
        seat_hdr = self._columns(
            ("座号", "玩家", "筹码(买入)", "本轮下注", "位置", "手牌/状态"),
            (6, 18, 18, 10, 8, 29),
        )
        lines.append(self.c(self._table_line(seat_hdr), Colors.BOLD))
        lines.append(self.c(self._table_line("-" * (self.TABLE_INNER_WIDTH - 2)), Colors.DIM))

        # Render seats
        self_is_my_turn = False
        my_seat_index = None

        for idx, s in enumerate(seats):
            if not s:
                empty_row = self._columns(
                    (f"[{idx}]", "(空座)", "-", "-", "", "-"),
                    (6, 18, 18, 10, 8, 29),
                )
                lines.append(self.c(self._table_line(empty_row), Colors.DIM))
                continue

            p_id = s.get("player_id", "")
            p_name = s.get("name", "Player")
            p_chips = self._int(s.get("chips", 0))
            p_rebuy = self._int(s.get("rebuy_count", 1), 1)
            p_cur_bet = self._int(s.get("current_round_bet", 0))
            is_folded = bool(s.get("is_folded", False))
            is_all_in = bool(s.get("is_all_in", False))
            hole_cards = s.get("hole_cards", [])
            shown_cards = s.get("shown_cards", [])
            last_action = s.get("last_action", "")
            time_cards = self._int(s.get("time_bank_cards", 0))

            is_self = (p_id == current_user_id)
            if is_self:
                my_seat_index = idx

            is_turn = (current_turn_seat == idx and street not in ("IDLE", "HAND_END", "SHOWDOWN", "RIT_DECISION"))
            if is_turn and is_self:
                self_is_my_turn = True

            # Indicator
            turn_mark = "▶" if is_turn else " "
            seat_label = f"[{idx}]{turn_mark}"

            # Name formatting
            name_disp = p_name
            if is_self:
                name_disp += " (你)"
            if p_id == host_id:
                name_disp += "👑"
            if self._display_width(name_disp) > 16:
                name_disp = f"{clip_display(name_disp, 14)}.."

            # Chips & buyins
            total_buyin = self._int(s.get("total_buyin_chips", 0))
            buyin_note = f"/{total_buyin}" if total_buyin else ""
            chips_disp = f"{p_chips} ({p_rebuy}买{buyin_note})"

            # Position
            pos_tags = []
            if dealer_seat == idx:
                pos_tags.append("D")
            if sb_seat == idx:
                pos_tags.append("SB")
            if bb_seat == idx:
                pos_tags.append("BB")
            pos_str = "/".join(pos_tags) if pos_tags else ""

            # Status / Cards
            status_desc = ""
            if is_folded:
                status_desc = self.c("Folded (弃牌)", Colors.DIM)
            elif is_all_in:
                status_desc = self.c("ALL-IN (全下)", Colors.BRIGHT_RED + Colors.BOLD)
            elif is_self and hole_cards:
                status_desc = self.format_cards(hole_cards)
            elif shown_cards:
                status_desc = self.format_cards(shown_cards) + " (亮牌)"
            elif street in ("SHOWDOWN", "HAND_END"):
                status_desc = last_action or "已盖牌"
            elif street == "IDLE":
                is_ready = p_id in ready_player_ids
                status_desc = self.c("[已准备]", Colors.BRIGHT_GREEN) if is_ready else self.c("[未准备]", Colors.YELLOW)
            else:
                if last_action:
                    status_desc = last_action
                else:
                    status_desc = "等待行动"

            if is_turn:
                tb_note = "+30s卡" if is_using_time_bank else f"{current_turn_duration}s"
                status_desc += f" {self.c('⏱️' + tb_note, Colors.BRIGHT_YELLOW)}"

            row_str = self._columns(
                (seat_label, name_disp, chips_disp, p_cur_bet, pos_str, status_desc),
                (6, 18, 18, 10, 8, 29),
            )
            lines.append(self._table_line(row_str))

        lines.append(self.c(self._table_separator(), Colors.CYAN))

        # Recent action history
        lines.append(self._table_line("最近动态:"))
        if not action_history:
            lines.append(self._table_line("  (暂无操作记录)"))
        else:
            for item in action_history[-4:]:
                p_name = item.get("player_name") or next(
                    (
                        seat.get("name", seat.get("player_id", ""))
                        for seat in seats
                        if seat and seat.get("player_id") == item.get("player_id")
                    ),
                    item.get("player_id", "玩家"),
                )
                act = item.get("action", "")
                amt = item.get("amount", 0)
                st = item.get("street", "")
                amt_str = f" {amt}" if amt > 0 else ""
                lines.append(self._table_line(f"  • {p_name}: {act}{amt_str} [{st}]"))

        # Hand Results (if hand ended)
        if street in ("HAND_END", "SHOWDOWN") and hand_results:
            lines.append(self.c(self._table_separator(), Colors.CYAN))
            lines.append(self.c(self._table_line("🏆 本手结算详情:"), Colors.BOLD + Colors.BRIGHT_YELLOW))
            for res in hand_results:
                name = res.get("name", "")
                payout = res.get("payout_amount", 0)
                net = res.get("net_profit", 0)
                h_desc = res.get("hand_desc", "")
                h_desc_2 = res.get("hand_desc_2")
                is_w = res.get("is_winner", False)
                shown = res.get("shown_cards", [])

                win_tag = self.c("【赢家】", Colors.BRIGHT_GREEN + Colors.BOLD) if is_w else ""
                net_str = f"+{net}" if net > 0 else str(net)
                shown_str = self.format_cards(shown) if shown else ""

                rit_extra = f" | 板2: {h_desc_2}" if h_desc_2 else ""
                lines.append(self._table_line(f"  {win_tag}{name}: 收益 {net_str} ({h_desc}{rit_extra}) {shown_str}"))

        # Legal actions bar
        lines.append(self.c(self._table_separator(), Colors.CYAN))

        if is_ended:
            lines.append(self.c(self._table_line("牌局已由房主结束并生成结算账单。输入 [bill] 或 [report] 查看账单。"), Colors.BRIGHT_YELLOW))
        elif street == "RIT_DECISION":
            lines.append(self.c(self._table_line("🎲 全下多次发牌(RIT)协商中: 输入 [rit 1] 发1次牌 / [rit 2] 发2次牌"), Colors.BRIGHT_MAGENTA + Colors.BOLD))
        elif street == "IDLE":
            is_host = (current_user_id == host_id)
            is_ready = current_user_id in ready_player_ids
            ready_hint = "[unready]取消准备" if is_ready else "[ready]准备"
            host_hint = " | [start/s]开局" if is_host else ""
            rebuy_hint = " | [rebuy/rb]重买补码"
            leave_hint = " | [leave]离开房间"
            end_hint = " | [end]结束房间结算" if is_host else ""
            lines.append(self._table_line(f"准备阶段: {self.c(ready_hint, Colors.BRIGHT_GREEN)}{host_hint}{rebuy_hint}{leave_hint}{end_hint}"))
        elif street in ("HAND_END", "SHOWDOWN"):
            is_host = (current_user_id == host_id)
            ready_hint = "[ready]准备下一手"
            host_hint = " | [start/s]直接发牌" if is_host else ""
            show_hint = " | 秀牌: [show 1] [show 2] [show all] [muck]"
            rebuy_hint = " | [rebuy]重买"
            end_hint = " | [end]结束结算" if is_host else ""
            lines.append(self._table_line(f"结算秀牌: {self.c(ready_hint, Colors.BRIGHT_GREEN)}{host_hint}{show_hint}{rebuy_hint}{end_hint}"))
        elif self_is_my_turn:
            action_tips = []
            if legal_actions.get("can_check"):
                action_tips.append(self.c("[c]过牌 (Check)", Colors.BRIGHT_GREEN))
            if legal_actions.get("can_call"):
                c_amt = legal_actions.get("call_amount", 0)
                action_tips.append(self.c(f"[c]跟注 {c_amt} (Call)", Colors.BRIGHT_GREEN))
            if legal_actions.get("can_fold"):
                action_tips.append(self.c("[f]弃牌 (Fold)", Colors.BRIGHT_RED))

            if legal_actions.get("can_bet"):
                b_min = legal_actions.get("min_bet", 0)
                b_max = legal_actions.get("max_bet", 0)
                action_tips.append(self.c(f"[r/b <额度>]下注({b_min}~{b_max})", Colors.BRIGHT_YELLOW))
            elif legal_actions.get("can_raise"):
                r_min = legal_actions.get("min_raise_to", legal_actions.get("min_raise", 0))
                r_max = legal_actions.get("max_raise_to", legal_actions.get("max_raise", 0))
                action_tips.append(self.c(f"[r <额度>]加注({r_min}~{r_max})", Colors.BRIGHT_YELLOW))

            if legal_actions.get("can_all_in"):
                a_amt = legal_actions.get("all_in_amount", 0)
                action_tips.append(self.c(f"[a/allin]全下({a_amt})", Colors.BRIGHT_MAGENTA))

            # Time card
            my_seat = seats[my_seat_index] if my_seat_index is not None and my_seat_index < len(seats) else None
            my_tc = my_seat.get("time_bank_cards", 0) if my_seat else 0
            if my_tc > 0:
                action_tips.append(self.c(f"[tc]时间卡({my_tc}张)", Colors.CYAN))

            lines.append(self._table_line("▶ " + self.c("轮到你行动:", Colors.BOLD + Colors.BRIGHT_WHITE) + " " + " | ".join(action_tips)))

            # Pot bet shortcuts
            if legal_actions.get("can_bet") or legal_actions.get("can_raise"):
                p_half = int(total_pot * 0.5)
                p_two_thirds = int(total_pot * 0.67)
                p_pot = total_pot
                p_hint = f"快捷尺度: [bet/raise 1/3p] | [1/2p]={p_half} | [2/3p]={p_two_thirds} | [p]={p_pot} | [1.5p] [2p] [3p] [allin]"
                lines.append(self.c(self._table_line(p_hint), Colors.DIM))
        else:
            lines.append(self._table_line("等待其他玩家行动... (输入 [h] 查看帮助, [rebuy] 补码, [leave] 离开)"))

        lines.append(self.c(self._table_bottom(), Colors.CYAN))

        return "\n".join(lines)

    def render_stream_event(self, event_type: str, data: Dict[str, Any], current_user_id: str) -> Optional[str]:
        """Render a single concise stream log line for ultra low-profile mode."""
        if event_type == "ROOM_STATE":
            table = data.get("table", {})
            street = table.get("street", "")
            hand_num = table.get("hand_number", 0)
            cur_seat = table.get("current_turn_seat")
            seats = table.get("seats", [])
            total_pot = table.get("total_pot", 0)
            board = self.format_cards(table.get("board_cards", []))

            # Find current player
            cur_p = seats[cur_seat] if (cur_seat is not None and cur_seat < len(seats)) else None
            cur_name = cur_p.get("name", "无") if cur_p else "无"
            is_me = (cur_p and cur_p.get("player_id") == current_user_id)

            if is_me and street not in ("IDLE", "HAND_END", "SHOWDOWN", "RIT_DECISION"):
                my_cards = self.format_cards(cur_p.get("hole_cards", []))
                legal = table.get("legal_actions") or {}
                choices = []
                if legal.get("can_check"):
                    choices.append("check")
                if legal.get("can_call"):
                    choices.append(f"call {legal.get('call_amount', 0)}")
                if legal.get("can_bet") or legal.get("can_raise"):
                    choices.append("bet/raise <额度>")
                if legal.get("can_all_in"):
                    choices.append("allin")
                choice_text = " | ".join(choices)
                return f"[HPoker] ▶ 轮到你行动! 手牌: {my_cards} | 公共牌: {board} | 底池: {total_pot} | 可选: {choice_text}"

            if street == "IDLE":
                return f"[HPoker] 等待开局 | 入座 {sum(1 for seat in seats if seat)}/{len(seats)}"
            if street in ("HAND_END", "SHOWDOWN"):
                return f"[HPoker] 第 {hand_num} 手 {self.format_street_name(street)} | 底池: {total_pot}"
            turn_text = f"行动: {cur_name}" if cur_name != "无" else "等待行动"
            return f"[HPoker] 第 {hand_num} 手 {self.format_street_name(street)} | 公共牌: {board} | 底池: {total_pot} | {turn_text}"

        elif event_type == "ACTION_EVENT":
            p_name = data.get("player_name", "玩家")
            act = data.get("action", "")
            amt = data.get("amount", 0)
            amt_str = f" {amt}" if amt > 0 else ""
            return f"[HPoker] {p_name} -> {act}{amt_str}"

        return None

    def render_users(self, users: Iterable[Dict[str, Any]]) -> str:
        """Render a login selector without ever displaying passwords/tokens."""

        rows = list(users)
        lines = [self.c("可登录用户", Colors.BOLD + Colors.CYAN), self.c("-" * 48, Colors.DIM)]
        if not rows:
            lines.append("  暂无用户或服务不可用。")
        else:
            for index, user in enumerate(rows, start=1):
                username = user.get("username", "")
                nickname = user.get("nickname", username)
                role = "管理员" if user.get("is_admin") else "玩家"
                lines.append(f"  {index:>2}. {username:<14} {nickname:<18} {role}")
        return "\n".join(lines)

    def render_room_details(self, room: Dict[str, Any]) -> str:
        """Render a compact room preview used by the lobby ``info`` command."""

        config = room.get("config", {})
        table = room.get("table", {})
        room_name = config.get("room_name") or room.get("room_name") or "德州扑克"
        small_blind = self._int(config.get("small_blind", table.get("small_blind", 10)), 10)
        big_blind = self._int(config.get("big_blind", small_blind * 2), small_blind * 2)
        seats = table.get("seats", [])
        status = "已结束" if room.get("is_ended") else self.format_street_name(table.get("street", "IDLE"))
        lines = [
            self.c(f"房间详情: {room_name}", Colors.BOLD + Colors.CYAN),
            f"  ID: {room.get('room_id', '')} | 状态: {status}",
            f"  盲注: {small_blind}/{big_blind} | 买入: {config.get('buyin_chips', 1000)} 筹码 / ¥{float(config.get('cash_value', 100.0)):.2f}",
            f"  座位: {sum(1 for seat in seats if seat)}/{config.get('max_seats', len(seats) or 6)} | 操作时限: {config.get('action_timeout', 15)}s",
            self.c("  玩家", Colors.BOLD),
        ]
        seated = [seat for seat in seats if seat]
        if not seated:
            lines.append("    （暂无入座玩家）")
        else:
            for seat in seated:
                tags = []
                if seat.get("player_id") == room.get("host_player_id"):
                    tags.append("房主")
                if seat.get("is_all_in"):
                    tags.append("All-in")
                if seat.get("is_folded"):
                    tags.append("弃牌")
                tag_text = f" [{', '.join(tags)}]" if tags else ""
                lines.append(f"    [{seat.get('seat_index', '?')}] {seat.get('name', seat.get('player_id', '玩家'))} · {seat.get('chips', 0)} 筹码{tag_text}")
        return "\n".join(lines)

    def render_action_history(self, room: Dict[str, Any], limit: int = 10) -> str:
        """Render the latest actions with player names resolved from seats."""

        table = room.get("table", {})
        seats = table.get("seats", [])
        names = {seat.get("player_id"): seat.get("name", seat.get("player_id", "玩家")) for seat in seats if seat}
        history = table.get("action_history", [])[-max(1, min(int(limit), 50)):]
        lines = [self.c("最近动态", Colors.BOLD + Colors.CYAN)]
        if not history:
            lines.append("  （暂无操作记录）")
            return "\n".join(lines)
        for item in history:
            name = item.get("player_name") or names.get(item.get("player_id"), item.get("player_id", "玩家"))
            amount = self._int(item.get("amount", 0))
            suffix = f" {amount}" if amount else ""
            lines.append(f"  · {name}: {item.get('action', '')}{suffix} [{item.get('street', '')}]")
        return "\n".join(lines)

    def render_help(self, scope: str = "lobby") -> str:
        """Render discoverable command help for the lobby or a room."""

        if scope == "room":
            return "\n".join([
                self.c("牌桌命令", Colors.BOLD + Colors.CYAN),
                "  check / call / c              过牌或跟注",
                "  fold / f                      弃牌",
                "  bet [额度] / raise [额度] / r  下注或加注；默认最小额",
                "  bet 1/3p | 1/2p | 2/3p | p   底池比例快捷下注",
                "  bet 2.5bb | +1bb | allin      盲注倍数、相对加注或全下",
                "  sit <座位> / stand            入座 / 起立（座位从 0 开始）",
                "  ready / unready               准备或取消准备",
                "  start                         房主开始下一手",
                "  rebuy                         筹码为 0 时补码",
                "  tc                            使用 1 张时间卡 (+30s)",
                "  rit 1 / rit 2                 全下后选择发 1 次或 2 次",
                "  show 1 / show 2 / show all    亮出手牌；muck 盖牌",
                "  info / status                 查看当前牌桌快照",
                "  history [数量]                查看操作记录",
                "  mode [dashboard|stream]       切换视图；color [on|off] 切换颜色",
                "  reconnect                     断线重连",
                "  bill                          查看结算；end（房主）结束并结算",
                "  delete（房主/管理员）         解散房间并让所有人退出",
                "  redraw / clear                重新绘制；help；leave 返回大厅",
            ])
        return "\n".join([
            self.c("大厅命令", Colors.BOLD + Colors.CYAN),
            "  <序号> / join <序号|room_id>  快速加入房间",
            "  create / c                   交互式创建房间",
            "  create --name ...             以选项快速创建（见 create help）",
            "  info <序号|room_id>           查看房间详情",
            "  rooms / refresh               刷新房间列表",
            "  users                         查看可登录用户",
            "  mode [dashboard|stream]       切换视图；color [on|off] 切换颜色",
            "  user / logout                 切换账号",
            "  help；quit / q                查看帮助或退出",
        ])

    # Compatibility alias for integrations that used the old naming.
    render_command_help = render_help

    def render_settlement_report(self, report: Dict[str, Any]) -> str:
        """Render final room settlement bill and minimal transfer route."""
        lines = []
        r_name = report.get("room_name", "现金桌")
        r_id = report.get("room_id", "")
        ratio = report.get("chip_to_cash_ratio", 0.1)
        players = report.get("player_records") or report.get("player_settlements", [])
        transfers = report.get("transactions") or report.get("transfers", [])

        title = f" 战局终局结算报表: {r_name} (ID: {r_id}) "
        lines.append("")
        lines.append(self.c("=" * 76, Colors.GREEN))
        lines.append(self.c(f"  {title}", Colors.BOLD + Colors.BRIGHT_WHITE))
        lines.append(self.c("=" * 76, Colors.GREEN))
        lines.append("")

        lines.append(self.c("  1. 玩家收支总览表:", Colors.BOLD))
        lines.append(self.c("  " + "-" * 72, Colors.DIM))
        hdr = f"  {'玩家':<16} {'买入次数':<10} {'总买入(元)':<14} {'最终筹码':<12} {'净盈亏(元)':<12}"
        lines.append(self.c(hdr, Colors.BOLD))
        lines.append(self.c("  " + "-" * 72, Colors.DIM))

        for p in players:
            name = p.get("player_name", "")
            rebuy = p.get("rebuy_count", 1)
            buyin_cash = p.get("total_buyin_cash", 0.0)
            final_chips = p.get("final_chips", 0)
            net_cash = p.get("net_cash") if p.get("net_cash") is not None else p.get("net_profit_cash", 0.0)

            if net_cash > 0:
                net_str = self.c(f"+{net_cash:.2f}", Colors.BRIGHT_GREEN + Colors.BOLD)
            elif net_cash < 0:
                net_str = self.c(f"{net_cash:.2f}", Colors.BRIGHT_RED + Colors.BOLD)
            else:
                net_str = f"{net_cash:.2f}"

            row = f"  {name:<16} {rebuy:<10} {buyin_cash:<14.2f} {final_chips:<12} {net_str}"
            lines.append(row)

        lines.append(self.c("  " + "-" * 72, Colors.DIM))
        lines.append("")

        lines.append(self.c("  2. 最精简转账支付路线 (最小债务流算法):", Colors.BOLD))
        lines.append(self.c("  " + "-" * 72, Colors.DIM))

        if not transfers:
            lines.append("  (所有玩家收支平衡，无需转账)")
        else:
            for t in transfers:
                from_p = t.get("from_player_name", "")
                to_p = t.get("to_player_name", "")
                amt_cash = t.get("amount_cash", 0.0)
                amt_chips = t.get("amount_chips", 0)
                line_str = f"  • {self.c(from_p, Colors.BRIGHT_RED)}  ── 应转账 ──▶  {self.c(f'¥ {amt_cash:.2f}', Colors.BRIGHT_YELLOW + Colors.BOLD)} (折合{amt_chips}筹码) ──▶  {self.c(to_p, Colors.BRIGHT_GREEN)}"
                lines.append(line_str)

        lines.append(self.c("  " + "-" * 72, Colors.DIM))
        lines.append(self.c("  (注: 纯纯现金局结算账单，输家按上述清单直接向赢家微信/支付宝转账即可)", Colors.DIM))
        lines.append("")

        return "\n".join(lines)
