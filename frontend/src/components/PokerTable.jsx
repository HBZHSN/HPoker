import React, { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import PlayerSeat from './PlayerSeat';
import CommunityBoard from './CommunityBoard';
import ActionBar from './ActionBar';
import CardView from './CardView';
import HandResultModal from './HandResultModal';
import TableSocialControls from './TableSocialControls';
import EquityDrawer, { EquityTrigger } from './EquityDrawer';
import { sortCardsLowToHigh } from '../utils/cards';
import { soundEngine } from '../sound/SoundEngine';
import {
  Volume2,
  VolumeX,
  RefreshCw,
  LogOut,
  Play,
  Clock,
  CheckCircle2,
  Trash2,
  Bot,
} from 'lucide-react';

const STREET_LABELS = {
  PREFLOP: '翻牌前',
  FLOP: '翻牌圈',
  TURN: '转牌圈',
  RIVER: '河牌圈',
  RIT_DECISION: '发牌次数',
  SHOWDOWN: '摊牌',
  HAND_END: '牌局结束',
};

const buildSeatPositions = (seatCount) => {
  const count = Math.max(2, Math.min(9, Number(seatCount) || 6));
  const horizontalRadius = 42;
  const verticalRadius = 42;
  return Array.from({ length: count }, (_, index) => {
    const angle = (Math.PI / 2) + ((Math.PI * 2 * index) / count);
    return {
      top: `${50 + (verticalRadius * Math.sin(angle))}%`,
      left: `${50 + (horizontalRadius * Math.cos(angle))}%`,
    };
  });
};

export default function PokerTable({
  room,
  currentUser,
  socialHistory = [],
  seatSocialBubbles = {},
  onSendWsEvent,
  onLeaveRoom,
}) {
  const [isMuted, setIsMuted] = useState(false);
  const [handResultDismissed, setHandResultDismissed] = useState(false);
  const [isRevealingBoard, setIsRevealingBoard] = useState(false);
  const [leaveRequested, setLeaveRequested] = useState(false);
  const [isEquityOpen, setIsEquityOpen] = useState(false);

  const table = room?.table;
  const isHost = room?.host_player_id === currentUser?.user_id;

  // Reset handResultDismissed on new hand
  useEffect(() => {
    if (table?.street !== 'HAND_END') {
      setHandResultDismissed(false);
    }
  }, [table?.street, table?.hand_number]);

  useEffect(() => {
    if (table?.street !== 'HAND_END' || table?.board_cards_revealed) {
      setIsRevealingBoard(false);
    }
  }, [table?.street, table?.hand_number, table?.board_cards_revealed]);

  // Toggle Mute
  const toggleMute = () => {
    const next = !isMuted;
    setIsMuted(next);
    soundEngine.setMuted(next);
  };

  // Find user's own seat index in table.seats
  const selfSeatIndex = useMemo(() => {
    if (!table?.seats || !currentUser?.user_id) return -1;
    return table.seats.findIndex((s) => s && s.player_id === currentUser.user_id);
  }, [table?.seats, currentUser?.user_id]);

  const selfSeat = selfSeatIndex >= 0 ? table.seats[selfSeatIndex] : null;
  const orderedHoleCards = useMemo(
    () => sortCardsLowToHigh(selfSeat?.hole_cards || []),
    [selfSeat?.hole_cards]
  );

  // Active opponents still in-hand (not folded, has cards, not self)
  const numOpponents = useMemo(() => {
    if (!table?.seats || !currentUser?.user_id) return 0;
    return table.seats.filter(
      (s) =>
        s &&
        s.player_id !== currentUser.user_id &&
        s.has_cards &&
        !s.is_folded
    ).length;
  }, [table?.seats, currentUser?.user_id]);

  const botCount = (table?.seats || []).filter((seat) => seat?.is_bot).length;
  const showPotBreakdown = useMemo(() => {
    const inHandSeats = (table?.seats || []).filter(
      (seat) => seat?.has_cards && !seat.is_folded && !seat.is_sitting_out
    );
    const hasAllInPlayer = inHandSeats.some((seat) => seat.is_all_in);
    const hasPlayerStillBetting = inHandSeats.some((seat) => !seat.is_all_in);
    return (table?.pots?.length || 0) > 1 && hasAllInPlayer && hasPlayerStillBetting;
  }, [table?.pots, table?.seats]);
  const canAddTestBot =
    isHost &&
    !room?.is_ended &&
    ['IDLE', 'HAND_END'].includes(table?.street) &&
    (table?.seats || []).some((seat) => !seat);
  const canRebuy = Boolean(
    selfSeat &&
    selfSeat.chips === 0 &&
    ['IDLE', 'HAND_END'].includes(table?.street)
  );

  // Visual positions are generated for every supported table size. Position 0
  // remains bottom-center so rotating the real seats always keeps the viewer's
  // own seat in the familiar hero position.
  const maxSeats = Math.max(2, Math.min(9, Number(room?.config?.max_seats) || 6));
  const visualScreenPositions = useMemo(() => buildSeatPositions(maxSeats), [maxSeats]);

  // Map visual screen position (0..maxSeats-1) to actual table seat index
  // If user is seated, visual position 0 always maps to selfSeatIndex (perspective rotation)
  const getTableSeatIndex = (screenIdx) => {
    if (selfSeatIndex >= 0) {
      return (selfSeatIndex + screenIdx) % maxSeats;
    }
    return screenIdx;
  };

  // Actions
  const handleSitDown = (seatIndex) => {
    onSendWsEvent('SIT_DOWN', { seat_index: seatIndex });
  };

  const handleLeaveTable = () => {
    if (leaveRequested) return;
    if (!selfSeat) {
      onLeaveRoom({ notifyServer: false });
      return;
    }
    if (
      !['IDLE', 'HAND_END'].includes(table?.street) &&
      (selfSeat.is_all_in || table?.street === 'RIT_DECISION')
    ) {
      return;
    }
    setLeaveRequested(true);
    onSendWsEvent('STAND_UP', {});
  };

  useEffect(() => {
    if (leaveRequested && !selfSeat) {
      onLeaveRoom({ notifyServer: false });
    }
  }, [leaveRequested, selfSeat, onLeaveRoom]);

  const handleRebuy = () => {
    onSendWsEvent('REBUY', {});
  };

  const handleStartGame = () => {
    onSendWsEvent('START_GAME', {});
  };

  const handleAddTestBot = () => {
    if (canAddTestBot) {
      onSendWsEvent('ADD_TEST_BOT', {});
    }
  };

  const handleRevealBoard = () => {
    if (table?.street !== 'HAND_END' || table?.board_cards_revealed || isRevealingBoard) {
      return;
    }
    setIsRevealingBoard(true);
    onSendWsEvent('REVEAL_BOARD_CARDS', {});
  };

  const handleUseAssistant = useCallback(() => {
    if (selfSeat && !selfSeat.using_assistant) {
      onSendWsEvent?.('USE_EQUITY_ASSISTANT', { active: true });
    }
  }, [selfSeat, onSendWsEvent]);

  const handleToggleEquity = useCallback(() => {
    setIsEquityOpen((prev) => {
      const next = !prev;
      if (next && table?.street !== 'HAND_END') {
        if (selfSeat && !selfSeat.using_assistant) {
          onSendWsEvent?.('USE_EQUITY_ASSISTANT', { active: true });
        }
      }
      return next;
    });
  }, [table?.street, selfSeat, onSendWsEvent]);

  const handleKickPlayer = (playerId, playerName) => {
    if (!isHost || playerId === currentUser?.user_id) return;
    if (window.confirm(`确定要将 ${playerName || '该玩家'} 移出房间吗？`)) {
      onSendWsEvent('KICK_PLAYER', { target_player_id: playerId });
    }
  };

  const handleDeleteRoom = () => {
    if (window.confirm('确定解散房间吗？所有在桌筹码将自动兑回余额。')) {
      onSendWsEvent('DELETE_ROOM', {});
    }
  };

  const handlePlayerAction = (action, amount = 0) => {
    onSendWsEvent('PLAYER_ACTION', { action, amount });
  };

  const currentTurnPlayer = useMemo(() => {
    if (table?.current_turn_seat === null || table?.current_turn_seat === undefined) return null;
    return table?.seats?.[table.current_turn_seat] || null;
  }, [table?.current_turn_seat, table?.seats]);

  const isMyTurn = useMemo(() => {
    return !!(selfSeat && table?.current_turn_seat === selfSeat.seat_index);
  }, [selfSeat, table?.current_turn_seat]);

  // Turn Countdown Audio Effect (5 seconds remaining warning). RIT voting
  // intentionally has no countdown; it waits for every contender's choice.
  const lastPlayedSecondRef = useRef(null);

  useEffect(() => {
    // Only active during an ongoing betting round.
    const isOngoingTurn =
      table?.street &&
      !['IDLE', 'RIT_DECISION', 'SHOWDOWN', 'HAND_END'].includes(table.street) &&
      (table.current_turn_seat !== null && table.current_turn_seat !== undefined);

    if (!isOngoingTurn) {
      lastPlayedSecondRef.current = null;
      return;
    }

    const duration = table?.is_using_time_bank
      ? (table?.current_turn_duration || 30)
      : (table?.current_turn_duration || room?.config?.action_timeout || 15);

    const startTime = Date.now();
    const totalMs = duration * 1000;
    lastPlayedSecondRef.current = null;

    const interval = setInterval(() => {
      const elapsed = Date.now() - startTime;
      const remainingSec = Math.max(0, (totalMs - elapsed) / 1000);
      const secondsCeil = Math.ceil(remainingSec);

      if (secondsCeil <= 5 && secondsCeil >= 1) {
        if (lastPlayedSecondRef.current !== secondsCeil) {
          lastPlayedSecondRef.current = secondsCeil;
          soundEngine.play('countdown', {
            secondsLeft: secondsCeil,
            isMyTurn,
          });
        }
      }
    }, 100);

    return () => {
      clearInterval(interval);
      lastPlayedSecondRef.current = null;
    };
  }, [
    table?.street,
    table?.current_turn_seat,
    table?.turn_count,
    table?.action_history?.length,
    table?.is_using_time_bank,
    table?.current_turn_duration,
    room?.config?.action_timeout,
    isMyTurn,
  ]);

  return (
    <div className="poker-table-root relative w-full h-screen max-h-screen overflow-hidden flex flex-col justify-between bg-gradient-to-b from-[#080b11] via-[#040507] to-[#020304]">
      {/* Top Navigation Bar */}
      <header className="poker-table-header flex items-center justify-between px-4 py-2 bg-slate-950/90 border-b border-slate-800/80 backdrop-blur-md z-30 flex-shrink-0">
        <div className="flex items-center gap-3">
          <button
            onClick={handleLeaveTable}
            disabled={Boolean(
              leaveRequested ||
              (
                selfSeat &&
                !['IDLE', 'HAND_END'].includes(table?.street) &&
                (selfSeat.is_all_in || table?.street === 'RIT_DECISION')
              )
            )}
            className="flex items-center gap-1 px-3 py-1.5 bg-slate-900 hover:bg-slate-800 disabled:opacity-40 disabled:cursor-not-allowed text-slate-300 rounded-xl text-xs font-bold border border-slate-700 transition active:scale-95 cursor-pointer shadow"
          >
            <LogOut className="w-3.5 h-3.5 text-amber-400" />
            <span className="hidden sm:inline">大厅</span>
            <span className="sm:hidden">离开</span>
          </button>

          <div className="poker-table-room-summary flex flex-col">
            <div className="flex items-center gap-2">
              <h1 className="text-sm md:text-base font-black text-amber-400 tracking-wide">
                {room?.config?.room_name || 'HPoker 现金桌'}
              </h1>
              <span className="poker-table-room-blinds text-[11px] bg-amber-950/90 text-amber-300 px-2 py-0.5 rounded-full border border-amber-500/40 font-bold">
                盲注: ${room?.config?.small_blind}/${room?.config?.big_blind}
              </span>
              {room?.config?.assistant_win_ratio !== undefined && room?.config?.assistant_win_ratio < 1.0 && (
                <span
                  className="text-[11px] bg-purple-950/90 text-purple-300 px-2 py-0.5 rounded-full border border-purple-500/40 font-bold"
                >
                  辅助折算: {Math.round(room.config.assistant_win_ratio * 100)}%
                </span>
              )}
            </div>
            <span className="poker-table-room-buyin text-[11px] text-slate-400">
              买入: ${room?.config?.buyin_chips} = ¥{room?.config?.cash_value} · 超时: {room?.config?.action_timeout}s
            </span>
          </div>
        </div>

        {/* Top Right Controls */}
        <div className="flex items-center gap-2">
          {/* Sound Toggle */}
          <button
            onClick={toggleMute}
            className="p-2 bg-slate-900 hover:bg-slate-800 text-slate-300 rounded-xl border border-slate-700 transition active:scale-95 cursor-pointer shadow"
            title={isMuted ? '取消静音' : '静音'}
          >
            {isMuted ? <VolumeX className="w-4 h-4 text-red-400" /> : <Volume2 className="w-4 h-4 text-amber-400" />}
          </button>

          {/* Rebuy Button (only when all chips are lost, chips === 0) */}
          {canRebuy && (
            <button
              onClick={handleRebuy}
              className="flex items-center gap-1 px-3 py-1.5 bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-400 hover:to-amber-500 text-slate-950 rounded-xl text-xs font-black shadow-glow-gold transition active:scale-95 cursor-pointer animate-pulse"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              Re-buy (${room?.config?.buyin_chips})
            </button>
          )}

          {/* Test bot control is intentionally visible to the host only. */}
          {isHost && !room?.is_ended && (
            <button
              onClick={handleAddTestBot}
              disabled={!canAddTestBot}
              className="flex items-center gap-1 px-3 py-1.5 rounded-xl text-xs font-bold border transition active:scale-95 shadow bg-indigo-950/80 hover:bg-indigo-900 text-indigo-200 border-indigo-400/50 disabled:bg-slate-900/70 disabled:hover:bg-slate-900/70 disabled:text-slate-600 disabled:border-slate-800 disabled:cursor-not-allowed"
            >
              <Bot className="w-3.5 h-3.5" />
              <span>机器人</span>
              {botCount > 0 && <span>×{botCount}</span>}
            </button>
          )}

          {/* Equity / Win Rate Trigger Button */}
          <EquityTrigger
            isOpen={isEquityOpen}
            onToggle={handleToggleEquity}
          />

          {/* Host Delete/Disband Room Button */}
          {(isHost || currentUser?.is_admin) && !room?.is_ended && (
            <button
              onClick={handleDeleteRoom}
              className="flex items-center gap-1 px-3 py-1.5 bg-red-950/80 hover:bg-red-900 text-red-300 hover:text-white rounded-xl text-xs font-bold border border-red-500/40 shadow transition active:scale-95 cursor-pointer"
            >
              <Trash2 className="w-3.5 h-3.5" />
              解散
            </button>
          )}
        </div>
      </header>

      {/* Main Body: Left Equity Panel + Center Poker Table Felt + Right Action Console Sidebar */}
      <div className="poker-table-body flex-1 flex flex-col lg:flex-row overflow-hidden min-h-0 w-full">
        {/* Left Side: Equity / Win Rate Panel (Auto-compresses poker table) */}
        {isEquityOpen && (
          <EquityDrawer
            isOpen={isEquityOpen}
            onClose={() => setIsEquityOpen(false)}
            holeCards={selfSeat?.hole_cards || []}
            boardCards={table?.board_cards || []}
            street={table?.street || 'IDLE'}
            numOpponents={numOpponents}
            potSize={table?.total_pot || 0}
            toCall={Math.max(
              0,
              (table?.current_round_highest_bet || 0) -
                (selfSeat?.current_round_bet || 0)
            )}
            isSeated={Boolean(selfSeat)}
            isFolded={Boolean(selfSeat?.is_folded)}
            handNumber={table?.hand_number || 0}
            onUseAssistant={handleUseAssistant}
          />
        )}

        {/* Center: Main Poker Table Felt Area */}
        <main className="poker-table-main relative flex-1 w-full h-full flex items-center justify-center p-3 pb-8 md:p-6 md:pb-12 select-none min-h-0 min-w-0 overflow-visible transition-all duration-300">
          {/* Table Exterior Border Ring (Leather & Wood Armrest) */}
          <div className={`poker-table-shell relative w-full h-[88%] md:h-[90%] max-h-[660px] rounded-[170px] md:rounded-[230px] bg-gradient-to-b from-[#2e2018] via-[#1a130e] to-[#0c0806] p-3 md:p-4 shadow-table border-[4px] border-[#3f2e24] overflow-visible transition-all duration-300 ${
            isEquityOpen ? 'max-w-[1100px]' : ''
          }`}>
            {/* Table Felt Background & Texture (clipped cleanly inside the inner oval) */}
            <div className="absolute inset-3 md:inset-4 rounded-[155px] md:rounded-[215px] border-2 border-amber-600/35 bg-gradient-to-b from-[#0a2318] via-[#061810] to-[#030e09] shadow-inner overflow-hidden pointer-events-none">
              {/* Felt Texture Pattern */}
              <div className="absolute inset-0 opacity-15 bg-[radial-gradient(#2ecc71_1.5px,transparent_1.5px)] [background-size:14px_14px]" />

              {/* HPoker Center Logo Watermark */}
              <div className="absolute inset-0 flex flex-col items-center justify-center opacity-20">
                <span className="text-4xl md:text-6xl font-black tracking-widest text-amber-500 font-serif">
                  HPOKER
                </span>
              </div>
            </div>

            {/* Inner Content Area (Overlay, Seats, Center Area - NOT clipped, allowing overflow) */}
            <div className="poker-table-inner relative w-full h-full">
              {/* Center Table Area: Board Cards, Pots & Next Hand Countdown */}
              <div className="poker-table-center absolute inset-0 flex flex-col items-center justify-center gap-3 z-10 pointer-events-none">
                {/* Street & Total Pot Badge */}
                <div className="poker-table-pot-summary flex flex-col items-center gap-1.5 pointer-events-auto">
                  <div className="poker-table-pot-badge flex items-center gap-3 bg-slate-950/85 px-4 py-1.5 rounded-full border-2 border-amber-500/40 backdrop-blur-md shadow-2xl">
                    <span className="text-xs md:text-sm font-bold text-slate-300">
                      {STREET_LABELS[table?.street] || '等待开局'}
                    </span>
                    <div className="w-1.5 h-1.5 rounded-full bg-amber-400" />
                    <span className="text-base md:text-xl font-black text-amber-300 tracking-wide">
                      底池: ${table?.total_pot || 0}
                    </span>
                  </div>

                  {/* Pot tiers only matter while an all-in player is capped and
                      at least one other contender can keep betting. */}
                  {showPotBreakdown && (
                    <div className="poker-table-side-pots flex items-center gap-2">
                      {table.pots.map((p, i) => (
                        <span
                          key={i}
                          className="text-xs font-bold bg-amber-950/80 text-amber-300 px-2.5 py-0.5 rounded-md border border-amber-500/30 shadow"
                        >
                          {p.name}: ${p.amount}
                        </span>
                      ))}
                    </div>
                  )}
                </div>

                {/* On phones the board stays in the sticky summary instead of
                    taking space in the middle of the felt. */}
                <div className="poker-table-center-board">
                  <CommunityBoard
                    boardCards={table?.board_cards || []}
                    boardCards2={table?.board_cards_2 || []}
                    boardCardsFull={table?.board_cards_full || []}
                    boardCards2Full={table?.board_cards_2_full || []}
                    allInInitialBoardCount={table?.all_in_initial_board_count || 0}
                    ritEnabled={table?.rit_enabled || false}
                    street={table?.street || 'IDLE'}
                    boardCardsRevealed={table?.board_cards_revealed || false}
                    onReveal={handleRevealBoard}
                    isRevealing={isRevealingBoard}
                    size={isEquityOpen ? 'md' : 'lg'}
                  />
                </div>

                {/* Start Hand / Ready / Rebuy Prompt */}
                {table?.street in { IDLE: 1, HAND_END: 1 } && (
                  <div className="poker-table-lobby-actions flex flex-col sm:flex-row items-center gap-2 mt-1 pointer-events-auto">
                    {table?.street === 'HAND_END' && handResultDismissed && (
                      <button
                        onClick={() => setHandResultDismissed(false)}
                        className="px-4 py-2 bg-slate-900 hover:bg-slate-800 border border-amber-500/50 text-amber-300 text-xs font-bold rounded-xl shadow transition active:scale-95 cursor-pointer"
                      >
                        查看本局结算
                      </button>
                    )}
                    {selfSeat && selfSeat.chips === 0 ? (
                      <button
                        onClick={handleRebuy}
                        className="flex items-center gap-2 px-5 py-2.5 bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-400 hover:to-amber-500 text-slate-950 text-xs md:text-sm font-black rounded-xl shadow-glow-gold transition active:scale-95 cursor-pointer animate-pulse"
                      >
                        <RefreshCw className="w-4 h-4" />
                        补码 (${room?.config?.buyin_chips || 1000})
                      </button>
                    ) : isHost ? (
                      <button
                        onClick={handleStartGame}
                        className="flex items-center gap-2 px-5 py-2.5 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white text-xs md:text-sm font-black rounded-xl shadow-glow-cyan transition active:scale-95 cursor-pointer animate-pulse"
                      >
                        <Play className="w-4 h-4 fill-white" />
                        {table?.street === 'HAND_END' ? '下一局' : '开始'}
                      </button>
                    ) : selfSeat ? (
                      <button
                        onClick={() => {
                          const isReady = table?.ready_player_ids?.includes(selfSeat.player_id);
                          onSendWsEvent('PLAYER_READY', { ready: !isReady });
                        }}
                        className={`flex items-center gap-2 px-5 py-2.5 rounded-xl text-xs md:text-sm font-black transition active:scale-95 cursor-pointer shadow-lg ${
                          table?.ready_player_ids?.includes(selfSeat.player_id)
                            ? 'bg-slate-800 text-emerald-300 border border-emerald-500/50'
                            : 'bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white shadow-glow-cyan'
                        }`}
                      >
                        <CheckCircle2 className="w-4 h-4" />
                        {table?.ready_player_ids?.includes(selfSeat.player_id)
                          ? '已准备'
                          : '准备下一局'}
                      </button>
                    ) : (
                      <div className="px-4 py-2 bg-slate-900/80 border border-slate-700 text-slate-400 text-xs font-bold rounded-xl">
                        等待房主开局
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Interactive Center RIT Decision Overlay */}
              {table?.street === 'RIT_DECISION' && table?.rit_status === 'VOTING' && (
                <div className="absolute inset-0 z-30 flex items-center justify-center p-4 bg-black/65 backdrop-blur-sm animate-fade-in">
                  <div className="max-w-md w-full bg-gradient-to-b from-slate-900 via-slate-950 to-purple-950 border-2 border-purple-500/80 rounded-3xl p-5 shadow-2xl flex flex-col gap-3.5 text-center">
                    <div className="flex items-center justify-center gap-2 text-amber-400 font-black text-base md:text-lg">
                      全下后发牌次数
                    </div>

                    {/* Contender cards and vote progress stay visible together so
                        players can make an informed runout choice. */}
                    <div className="grid grid-cols-2 gap-2 bg-black/50 p-2.5 rounded-2xl border border-slate-800 max-h-48 overflow-y-auto">
                      {(table?.rit_voters || []).map((voterId) => {
                        const voterSeat = table?.seats?.find((s) => s && s.player_id === voterId);
                        const voterName = voterSeat ? voterSeat.name : voterId;
                        const vote = table?.rit_votes?.[voterId];
                        const visibleCards = sortCardsLowToHigh(
                          voterSeat?.shown_cards?.length
                            ? voterSeat.shown_cards
                            : voterSeat?.player_id === selfSeat?.player_id
                            ? voterSeat?.hole_cards || []
                            : []
                        );
                        return (
                          <div
                            key={voterId}
                            className={`min-w-0 px-2.5 py-2 rounded-xl border flex flex-col items-center gap-1.5 ${
                              vote === 2
                                ? 'bg-purple-950/90 text-purple-300 border-purple-500/60 shadow'
                                : vote === 1
                                ? 'bg-amber-950/90 text-amber-300 border-amber-500/60 shadow'
                                : 'bg-slate-900 text-slate-400 border-slate-700 animate-pulse'
                            }`}
                          >
                            <div className="flex items-center gap-1.5 min-w-0 max-w-full">
                              <span className="text-base leading-none flex-shrink-0">{voterSeat?.avatar || '👤'}</span>
                              <span className="text-xs font-black truncate">{voterName}</span>
                            </div>
                            <div className="flex -space-x-2 min-h-[42px] items-center" aria-label={`${voterName}的手牌`}>
                              {visibleCards.length > 0 ? visibleCards.map((card, cardIndex) => (
                                <CardView key={cardIndex} card={card} size="xs" className="shadow-lg" />
                              )) : (
                                <span className="text-[10px] text-slate-500">等待亮牌</span>
                              )}
                            </div>
                            <span className="text-[10px] font-bold">
                              {vote === 2 ? '发 2 次' : vote === 1 ? '发 1 次' : '未选择'}
                            </span>
                          </div>
                        );
                      })}
                    </div>

                    {/* Voter Action Buttons */}
                    {selfSeat && table?.rit_voters?.includes(selfSeat.player_id) ? (
                      <div className="grid grid-cols-2 gap-3 mt-1">
                        <button
                          onClick={() => onSendWsEvent('RIT_CHOICE', { choice: 1 })}
                          className={`py-3 px-3 rounded-2xl font-black text-sm transition active:scale-95 cursor-pointer flex flex-col items-center justify-center border-2 ${
                            table?.rit_votes?.[selfSeat.player_id] === 1
                              ? 'bg-amber-500 text-slate-950 border-amber-300 shadow-glow-gold'
                              : 'bg-slate-800 hover:bg-slate-700 text-amber-300 border-amber-500/50'
                          }`}
                        >
                          <span className="text-base font-black">发 1 次</span>
                        </button>

                        <button
                          onClick={() => onSendWsEvent('RIT_CHOICE', { choice: 2 })}
                          className={`py-3 px-3 rounded-2xl font-black text-sm transition active:scale-95 cursor-pointer flex flex-col items-center justify-center border-2 ${
                            table?.rit_votes?.[selfSeat.player_id] === 2
                              ? 'bg-gradient-to-r from-purple-600 to-indigo-600 text-white border-purple-300 shadow-glow-cyan'
                              : 'bg-slate-800 hover:bg-slate-700 text-purple-300 border-purple-500/50'
                          }`}
                        >
                          <span className="text-base font-black">发 2 次</span>
                        </button>
                      </div>
                    ) : (
                      <div className="text-xs text-slate-400 font-bold py-1 flex items-center justify-center gap-1.5">
                        <Clock className="w-3.5 h-3.5 text-purple-400" />
                        等待其他玩家
                      </div>
                    )}
                    {selfSeat && table?.rit_voters?.includes(selfSeat.player_id) && table?.rit_votes?.[selfSeat.player_id] !== undefined && (
                      <div className="text-xs text-slate-400 font-bold flex items-center justify-center gap-1.5">
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                        已选择
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Seated Players Overlay (Auto-rotated so user is at Screen Pos 0 / Bottom) */}
              {visualScreenPositions.map((pos, screenIdx) => {
                const seatIdx = getTableSeatIndex(screenIdx);
                const seatData = table?.seats?.[seatIdx] || null;
                const isCurrentTurn = table?.current_turn_seat === seatIdx;
                const isDealer = table?.dealer_seat === seatIdx;
                const isSB = table?.sb_seat === seatIdx;
                const isBB = table?.bb_seat === seatIdx;
                const payout = table?.payouts?.find((p) => p.player_id === seatData?.player_id);
                const socialBubble = seatSocialBubbles[seatData?.player_id] || null;
                const seatLeftPercent = parseFloat(pos.left);
                const bubblePlacement = seatLeftPercent > 50 ? 'left' : 'right';

                return (
                  <div
                    key={screenIdx}
                    className={`poker-table-seat-anchor absolute -translate-x-1/2 -translate-y-1/2 ${
                      socialBubble ? 'z-35' : 'z-20'
                    }`}
                    data-screen-position={screenIdx}
                    style={{ top: pos.top, left: pos.left }}
                  >
                    <PlayerSeat
                      seatIndex={seatIdx}
                      seatData={seatData}
                      isCurrentTurn={isCurrentTurn}
                      isDealer={isDealer}
                      isSB={isSB}
                      isBB={isBB}
                      onSitDown={handleSitDown}
                      isHost={isHost}
                      onKick={handleKickPlayer}
                      canKick={Boolean(
                        isHost &&
                        seatData &&
                        seatData.player_id !== currentUser?.user_id &&
                        (
                          ['IDLE', 'HAND_END'].includes(table?.street) ||
                          !seatData.is_all_in
                        )
                      )}
                      currentUserId={currentUser?.user_id}
                      actionTimeout={room?.config?.action_timeout || 15}
                      currentTurnDuration={table?.current_turn_duration || room?.config?.action_timeout || 15}
                      isUsingTimeBank={table?.is_using_time_bank || false}
                      payoutInfo={payout}
                      street={table?.street || 'IDLE'}
                      turnCount={table?.turn_count || 0}
                      actionHistoryLength={table?.action_history?.length || 0}
                      socialBubble={socialBubble}
                      bubblePlacement={bubblePlacement}
                    />
                  </div>
                );
              })}
            </div>
          </div>
        </main>

        {/* Right Side: Action & Betting Console Sidebar */}
        <aside className={`poker-table-actions w-full h-auto lg:h-full flex-shrink-0 bg-slate-950/95 border-t lg:border-t-0 lg:border-l border-slate-800/90 shadow-2xl overflow-y-auto p-3 lg:p-4 z-20 transition-all duration-300 ${
          isEquityOpen ? 'lg:w-80 xl:w-96 2xl:w-[410px]' : 'lg:w-96 xl:w-[410px]'
        }`}>
          {/* On mobile this becomes the sticky summary while the action console scrolls. */}
          <div className="poker-mobile-sticky-info" aria-label="牌局重要信息">
            <div className="poker-mobile-sticky-info__header">
              <span>{STREET_LABELS[table?.street] || '等待开局'}</span>
              <span>底池 ${table?.total_pot || 0}</span>
            </div>

            <div className="poker-mobile-sticky-info__content">
              <CommunityBoard
                boardCards={table?.board_cards || []}
                boardCards2={table?.board_cards_2 || []}
                boardCardsFull={table?.board_cards_full || []}
                boardCards2Full={table?.board_cards_2_full || []}
                allInInitialBoardCount={table?.all_in_initial_board_count || 0}
                ritEnabled={table?.rit_enabled || false}
                street={table?.street || 'IDLE'}
                boardCardsRevealed={table?.board_cards_revealed || false}
                onReveal={handleRevealBoard}
                isRevealing={isRevealingBoard}
                size="xs"
                compact
              />

              {selfSeat && (
                <div className="poker-mobile-sticky-hand">
                  <div className="poker-mobile-sticky-hand__label">
                    <span>我的牌</span>
                    <span>${selfSeat.chips}</span>
                  </div>
                  <div className="flex -space-x-2">
                    {orderedHoleCards.length > 0 ? (
                      orderedHoleCards.map((card, index) => (
                        <CardView key={index} card={card} size="xs" className="shadow-lg" />
                      ))
                    ) : (
                      <span className="text-[10px] text-slate-500">暂无手牌</span>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>

          <ActionBar
            legalActions={table?.legal_actions}
            totalPot={table?.total_pot || 0}
            smallBlind={room?.config?.small_blind || 10}
            buyinChips={room?.config?.buyin_chips || 1000}
            onAction={handlePlayerAction}
            selfSeat={selfSeat}
            onRebuy={handleRebuy}
            canRebuy={canRebuy}
            currentTurnPlayer={currentTurnPlayer}
            isMyTurn={isMyTurn}
            street={table?.street || 'IDLE'}
            actionHistory={table?.action_history || []}
            actionTimeout={room?.config?.action_timeout || 15}
            currentTurnDuration={table?.current_turn_duration || room?.config?.action_timeout || 15}
            isUsingTimeBank={table?.is_using_time_bank || false}
            onUseTimeCard={() => onSendWsEvent('USE_TIME_CARD', {})}
            seats={table?.seats || []}
            turnCount={table?.turn_count || 0}
            currentRoundHighestBet={table?.current_round_highest_bet || 0}
            handNumber={table?.hand_number || 0}
          />
        </aside>
      </div>

      <TableSocialControls
        activities={socialHistory}
        currentUserId={currentUser?.user_id}
        canReact={Boolean(selfSeat)}
        onSendChat={(message) => onSendWsEvent('CHAT_MESSAGE', { message })}
        onSendEmoji={(emoji) => onSendWsEvent('EMOJI_REACTION', { emoji })}
      />

      {/* Hand Result Settlement & Card Reveal Modal */}
      {table?.street === 'HAND_END' && !handResultDismissed && table?.hand_results && table.hand_results.length > 0 && (
        <HandResultModal
          isOpen={true}
          handNumber={table.hand_number}
          boardCards={table.board_cards}
          boardCards2={table.board_cards_2}
          boardCardsFull={table.board_cards_full}
          boardCards2Full={table.board_cards_2_full}
          allInInitialBoardCount={table.all_in_initial_board_count || 0}
          ritEnabled={table.rit_enabled}
          boardCardsRevealed={table.board_cards_revealed || false}
          handResults={table.hand_results}
          totalPot={table.total_pot}
          selfSeat={selfSeat}
          isHost={isHost}
          buyinChips={room?.config?.buyin_chips || 1000}
          readyPlayerIds={table.ready_player_ids || []}
          onShowCard={(payload) => onSendWsEvent('SHOW_CARD', payload)}
          onRevealBoard={handleRevealBoard}
          isRevealingBoard={isRevealingBoard}
          onToggleReady={() => {
            const isReady = table.ready_player_ids?.includes(selfSeat?.player_id);
            onSendWsEvent('PLAYER_READY', { ready: !isReady });
          }}
          onRebuy={handleRebuy}
          onStartNextHand={handleStartGame}
          onLeaveTable={handleLeaveTable}
          isLeaving={leaveRequested}
          onClose={() => setHandResultDismissed(true)}
        />
      )}

    </div>
  );
}
