import React, { useState, useEffect, useMemo, useRef } from 'react';
import PlayerSeat from './PlayerSeat';
import CardView from './CardView';
import ActionBar from './ActionBar';
import HandResultModal from './HandResultModal';
import SettlementModal from './SettlementModal';
import { soundEngine } from '../sound/SoundEngine';
import {
  Volume2,
  VolumeX,
  RefreshCw,
  LogOut,
  PowerOff,
  Play,
  Clock,
  CheckCircle2,
  Trash2,
} from 'lucide-react';

export default function PokerTable({
  room,
  currentUser,
  onSendWsEvent,
  onLeaveRoom,
}) {
  const [isMuted, setIsMuted] = useState(false);
  const [settlementOpen, setSettlementOpen] = useState(false);
  const [handResultDismissed, setHandResultDismissed] = useState(false);

  const table = room?.table;
  const isHost = room?.host_player_id === currentUser?.user_id;

  // Reset handResultDismissed on new hand
  useEffect(() => {
    if (table?.street !== 'HAND_END') {
      setHandResultDismissed(false);
    }
  }, [table?.street, table?.hand_number]);

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

  // Handle Settlement report prompt
  useEffect(() => {
    if (room?.is_ended && room?.settlement_report) {
      setSettlementOpen(true);
    }
  }, [room?.is_ended, room?.settlement_report]);

  // Visual Screen Positions (Clockwise starting from 0 = Bottom Center User Position)
  const maxSeats = room?.config?.max_seats || 6;
  const visualScreenPositions = useMemo(() => {
    if (maxSeats === 6) {
      return [
        { top: '92%', left: '50%', betDirection: 'top' },    // Screen Pos 0 (Bottom Center - Hero)
        { top: '68%', left: '15%', betDirection: 'right' },  // Screen Pos 1 (Bottom Left)
        { top: '24%', left: '15%', betDirection: 'right' },  // Screen Pos 2 (Top Left)
        { top: '11%', left: '50%', betDirection: 'bottom' }, // Screen Pos 3 (Top Center)
        { top: '24%', left: '85%', betDirection: 'left' },   // Screen Pos 4 (Top Right)
        { top: '68%', left: '85%', betDirection: 'left' },   // Screen Pos 5 (Bottom Right)
      ];
    }
    // 9 Seats layout
    return [
      { top: '93%', left: '50%', betDirection: 'top' },    // 0 Bottom (Hero)
      { top: '76%', left: '16%', betDirection: 'right' },  // 1 Bottom Left
      { top: '48%', left: '9%', betDirection: 'right' },   // 2 Mid Left
      { top: '20%', left: '16%', betDirection: 'bottom' }, // 3 Top Left
      { top: '10%', left: '37%', betDirection: 'bottom' }, // 4 Top Left-Center
      { top: '10%', left: '63%', betDirection: 'bottom' }, // 5 Top Right-Center
      { top: '20%', left: '84%', betDirection: 'bottom' }, // 6 Top Right
      { top: '48%', left: '91%', betDirection: 'left' },   // 7 Mid Right
      { top: '76%', left: '84%', betDirection: 'left' },   // 8 Bottom Right
    ];
  }, [maxSeats]);

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

  const handleStandUp = () => {
    if (selfSeat) {
      onSendWsEvent('STAND_UP', { seat_index: selfSeat.seat_index });
    }
  };

  const handleRebuy = () => {
    onSendWsEvent('REBUY', {});
  };

  const handleStartGame = () => {
    onSendWsEvent('START_GAME', {});
  };

  const handleEndRoom = () => {
    if (window.confirm('确定要结束房间并生成结算清单吗？')) {
      onSendWsEvent('END_ROOM', {});
    }
  };

  const handleDeleteRoom = () => {
    if (window.confirm('确定要解散并删除该房间吗？删除后所有玩家将返回大厅。')) {
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

  // Turn Countdown Audio Effect (5 seconds remaining warning)
  const lastPlayedSecondRef = useRef(null);

  useEffect(() => {
    // Only active during ongoing betting rounds or RIT voting
    const isOngoingTurn =
      table?.street &&
      !['IDLE', 'SHOWDOWN', 'HAND_END'].includes(table.street) &&
      (table.current_turn_seat !== null && table.current_turn_seat !== undefined);

    const isRIT = table?.street === 'RIT_DECISION' || table?.rit_status === 'VOTING';

    if (!isOngoingTurn && !isRIT) {
      lastPlayedSecondRef.current = null;
      return;
    }

    const duration = isRIT
      ? 8
      : table?.is_using_time_bank
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
          const isUserTurn = isRIT
            ? (table?.rit_voters?.includes(currentUser?.user_id) && table?.rit_votes?.[currentUser?.user_id] === undefined)
            : isMyTurn;
          soundEngine.play('countdown', {
            secondsLeft: secondsCeil,
            isMyTurn: isUserTurn,
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
    currentUser?.user_id,
    table?.rit_status,
  ]);

  return (
    <div className="relative w-full h-screen max-h-screen overflow-hidden flex flex-col justify-between bg-gradient-to-b from-[#080b11] via-[#040507] to-[#020304]">
      {/* Top Navigation Bar */}
      <header className="flex items-center justify-between px-4 py-2 bg-slate-950/90 border-b border-slate-800/80 backdrop-blur-md z-30 flex-shrink-0">
        <div className="flex items-center gap-3">
          <button
            onClick={onLeaveRoom}
            className="flex items-center gap-1 px-3 py-1.5 bg-slate-900 hover:bg-slate-800 text-slate-300 rounded-xl text-xs font-bold border border-slate-700 transition active:scale-95 cursor-pointer shadow"
          >
            <LogOut className="w-3.5 h-3.5 text-amber-400" />
            大厅
          </button>

          <div className="flex flex-col">
            <div className="flex items-center gap-2">
              <h1 className="text-sm md:text-base font-black text-amber-400 tracking-wide">
                {room?.config?.room_name || 'HPoker 现金桌'}
              </h1>
              <span className="text-[11px] bg-amber-950/90 text-amber-300 px-2 py-0.5 rounded-full border border-amber-500/40 font-bold">
                盲注: ${room?.config?.small_blind}/${room?.config?.big_blind}
              </span>
            </div>
            <span className="text-[11px] text-slate-400">
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
          {selfSeat && selfSeat.chips === 0 && (
            <button
              onClick={handleRebuy}
              className="flex items-center gap-1 px-3 py-1.5 bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-400 hover:to-amber-500 text-slate-950 rounded-xl text-xs font-black shadow-glow-gold transition active:scale-95 cursor-pointer animate-pulse"
              title="筹码已输完，补充买入"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              Re-buy (${room?.config?.buyin_chips})
            </button>
          )}

          {/* Stand Up Button */}
          {selfSeat && (
            <button
              onClick={handleStandUp}
              className="flex items-center gap-1 px-3 py-1.5 bg-slate-900 hover:bg-slate-800 text-slate-300 rounded-xl text-xs font-bold border border-slate-700 transition active:scale-95 cursor-pointer shadow"
            >
              站起
            </button>
          )}

          {/* Host End Room Button */}
          {isHost && !room?.is_ended && (
            <button
              onClick={handleEndRoom}
              className="flex items-center gap-1 px-3 py-1.5 bg-red-900/80 hover:bg-red-800 text-red-200 rounded-xl text-xs font-bold border border-red-500/40 shadow transition active:scale-95 cursor-pointer"
            >
              <PowerOff className="w-3.5 h-3.5" />
              结束房间并结算
            </button>
          )}

          {/* Host Delete/Disband Room Button */}
          {(isHost || currentUser?.is_admin) && (
            <button
              onClick={handleDeleteRoom}
              className="flex items-center gap-1 px-3 py-1.5 bg-red-950/80 hover:bg-red-900 text-red-300 hover:text-white rounded-xl text-xs font-bold border border-red-500/40 shadow transition active:scale-95 cursor-pointer"
              title="解散并删除房间"
            >
              <Trash2 className="w-3.5 h-3.5" />
              解散房间
            </button>
          )}
        </div>
      </header>

      {/* Main Body: Left Poker Table Felt + Right Action Console Sidebar */}
      <div className="flex-1 flex flex-col lg:flex-row overflow-hidden min-h-0 w-full">
        {/* Left Side: Main Poker Table Felt Area */}
        <main className="relative flex-1 w-full h-full flex items-center justify-center p-3 pb-8 md:p-6 md:pb-12 select-none min-h-0 min-w-0 overflow-visible">
          {/* Table Exterior Border Ring (Leather & Wood Armrest) */}
          <div className="relative w-full h-[88%] md:h-[90%] max-h-[660px] rounded-[170px] md:rounded-[230px] bg-gradient-to-b from-[#2e2018] via-[#1a130e] to-[#0c0806] p-3 md:p-4 shadow-table border-[4px] border-[#3f2e24] overflow-visible">
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
            <div className="relative w-full h-full">
              {/* Center Table Area: Board Cards, Pots & Next Hand Countdown */}
              <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 z-10 pointer-events-none">
                {/* Street & Total Pot Badge */}
                <div className="flex flex-col items-center gap-1.5 pointer-events-auto">
                  <div className="flex items-center gap-3 bg-slate-950/85 px-4 py-1.5 rounded-full border-2 border-amber-500/40 backdrop-blur-md shadow-2xl">
                    <span className="text-xs md:text-sm font-bold text-slate-300">
                      {table?.street === 'PREFLOP'
                        ? '翻牌前'
                        : table?.street === 'FLOP'
                        ? '翻牌圈'
                        : table?.street === 'TURN'
                        ? '转牌圈'
                        : table?.street === 'RIVER'
                        ? '河牌圈'
                        : table?.street === 'RIT_DECISION'
                        ? '发牌次数'
                        : table?.street === 'SHOWDOWN'
                        ? '摊牌'
                        : table?.street === 'HAND_END'
                        ? '牌局结束'
                        : '等待开局'}
                    </span>
                    <div className="w-1.5 h-1.5 rounded-full bg-amber-400" />
                    <span className="text-base md:text-xl font-black text-amber-300 tracking-wide">
                      底池: ${table?.total_pot || 0}
                    </span>
                  </div>

                  {/* Side Pots display if multiple pots exist */}
                  {table?.pots && table.pots.length > 1 && (
                    <div className="flex items-center gap-2">
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

                {/* Community Board Cards */}
                {table?.rit_enabled || (table?.board_cards_2 && table.board_cards_2.length > 0) ? (
                  <div className="flex flex-col gap-2 bg-black/60 p-3 rounded-2xl border border-purple-500/40 backdrop-blur-md shadow-2xl">
                    {/* Board 1 */}
                    <div className="flex items-center gap-2">
                      <span className="text-[11px] font-black text-purple-300 px-2 py-0.5 bg-purple-950/90 rounded border border-purple-500/30 flex-shrink-0">
                        第 1 次:
                      </span>
                      <div className="flex items-center gap-1.5 md:gap-2">
                        {table.board_cards.map((card, i) => (
                          <CardView key={i} card={card} size="md" className="shadow-lg" />
                        ))}
                        {Array.from({ length: Math.max(0, 5 - (table.board_cards?.length || 0)) }).map((_, i) => (
                          <div key={i} className="w-12 h-16 md:w-14 md:h-20 border border-dashed border-slate-700 rounded-lg flex items-center justify-center text-[10px] text-slate-600 font-bold">
                            ?
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* Board 2 (Only display remaining cards that were newly dealt for run 2, skipping shared cards) */}
                    {(() => {
                      const initialCount = table?.all_in_initial_board_count || 0;
                      const run2Cards = (table.board_cards_2 || []).slice(initialCount);
                      const expectedRun2Total = 5 - initialCount;

                      return (
                        <div className="flex items-center gap-2">
                          <span className="text-[11px] font-black text-indigo-300 px-2 py-0.5 bg-indigo-950/90 rounded border border-indigo-500/30 flex-shrink-0">
                            {initialCount === 0 ? '第 2 次:' : initialCount === 3 ? '第 2 次 (转/河):' : '第 2 次 (河牌):'}
                          </span>
                          <div className="flex items-center gap-1.5 md:gap-2">
                            {run2Cards.map((card, i) => (
                              <CardView key={i} card={card} size="md" className="shadow-lg" />
                            ))}
                            {Array.from({ length: Math.max(0, expectedRun2Total - run2Cards.length) }).map((_, i) => (
                              <div key={i} className="w-12 h-16 md:w-14 md:h-20 border border-dashed border-slate-700 rounded-lg flex items-center justify-center text-[10px] text-slate-600 font-bold">
                                ?
                              </div>
                            ))}
                          </div>
                        </div>
                      );
                    })()}
                  </div>
                ) : (
                  <div className="flex items-center gap-2 md:gap-3 min-h-[85px] px-4 py-2.5 bg-black/40 rounded-2xl border border-white/10 backdrop-blur-sm shadow-2xl">
                    {table?.board_cards && table.board_cards.length > 0 ? (
                      table.board_cards.map((card, i) => (
                        <CardView key={i} card={card} size="lg" className="shadow-xl" />
                      ))
                    ) : (
                      <div className="flex gap-2 md:gap-3 opacity-30">
                        {[1, 2, 3, 4, 5].map((_, i) => (
                          <div
                            key={i}
                            className="w-16 h-24 md:w-20 md:h-28 border-2 border-dashed border-slate-600 rounded-xl flex items-center justify-center text-xs md:text-sm text-slate-400 font-bold"
                          >
                            {i < 3 ? 'FLOP' : i === 3 ? 'TURN' : 'RIVER'}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {/* Start Hand / Ready / Rebuy Prompt */}
                {table?.street in { IDLE: 1, HAND_END: 1 } && (
                  <div className="flex flex-col sm:flex-row items-center gap-2 mt-1 pointer-events-auto">
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
              {(table?.street === 'RIT_DECISION' || table?.rit_status === 'VOTING') && (
                <div className="absolute inset-0 z-30 flex items-center justify-center p-4 bg-black/65 backdrop-blur-sm animate-fade-in">
                  <div className="max-w-md w-full bg-gradient-to-b from-slate-900 via-slate-950 to-purple-950 border-2 border-purple-500/80 rounded-3xl p-5 shadow-2xl flex flex-col gap-3.5 text-center">
                    <div className="flex items-center justify-center gap-2 text-amber-400 font-black text-base md:text-lg">
                      全下后发牌次数
                    </div>
                    <p className="text-xs text-slate-300 leading-relaxed">
                      双方均选 <strong className="text-purple-300">2 次</strong> 时平分底池；有一人选 <strong className="text-amber-300">1 次</strong> 则发 1 次。
                    </p>

                    {/* Contender Votes Progress */}
                    <div className="flex flex-wrap items-center justify-center gap-2 bg-black/50 p-2.5 rounded-2xl border border-slate-800">
                      {(table?.rit_voters || []).map((voterId) => {
                        const voterSeat = table?.seats?.find((s) => s && s.player_id === voterId);
                        const voterName = voterSeat ? voterSeat.name : voterId;
                        const vote = table?.rit_votes?.[voterId];
                        return (
                          <span
                            key={voterId}
                            className={`text-xs font-black px-3 py-1 rounded-xl border flex items-center gap-1.5 ${
                              vote === 2
                                ? 'bg-purple-950/90 text-purple-300 border-purple-500/60 shadow'
                                : vote === 1
                                ? 'bg-amber-950/90 text-amber-300 border-amber-500/60 shadow'
                                : 'bg-slate-900 text-slate-400 border-slate-700 animate-pulse'
                            }`}
                          >
                            <span>{voterName}:</span>
                            <span>
                              {vote === 2 ? '发 2 次' : vote === 1 ? '发 1 次' : '未选择'}
                            </span>
                          </span>
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
                        <Clock className="w-3.5 h-3.5 animate-spin text-purple-400" />
                        等待选择
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

                return (
                  <div
                    key={screenIdx}
                    className="absolute -translate-x-1/2 -translate-y-1/2 z-20"
                    style={{ top: pos.top, left: pos.left }}
                  >
                    <PlayerSeat
                      seatIndex={seatIdx}
                      seatData={seatData}
                      isCurrentTurn={isCurrentTurn}
                      isDealer={isDealer}
                      isSB={isSB}
                      isBB={isBB}
                      currentRoundBet={seatData?.current_round_bet || 0}
                      onSitDown={handleSitDown}
                      currentUserId={currentUser?.user_id}
                      actionTimeout={room?.config?.action_timeout || 15}
                      currentTurnDuration={table?.current_turn_duration || room?.config?.action_timeout || 15}
                      isUsingTimeBank={table?.is_using_time_bank || false}
                      payoutInfo={payout}
                      betDirection={pos.betDirection}
                      street={table?.street || 'IDLE'}
                      turnCount={table?.turn_count || 0}
                      actionHistoryLength={table?.action_history?.length || 0}
                    />
                  </div>
                );
              })}
            </div>
          </div>
        </main>

        {/* Right Side: Action & Betting Console Sidebar */}
        <aside className="w-full lg:w-96 xl:w-[410px] h-auto lg:h-full flex-shrink-0 bg-slate-950/95 border-t lg:border-t-0 lg:border-l border-slate-800/90 shadow-2xl overflow-y-auto p-3 lg:p-4 z-20">
          <ActionBar
            legalActions={table?.legal_actions}
            totalPot={table?.total_pot || 0}
            bigBlind={room?.config?.big_blind || 10}
            buyinChips={room?.config?.buyin_chips || 1000}
            onAction={handlePlayerAction}
            selfSeat={selfSeat}
            onRebuy={handleRebuy}
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
          />
        </aside>
      </div>

      {/* Hand Result Settlement & Card Reveal Modal */}
      {table?.street === 'HAND_END' && !handResultDismissed && table?.hand_results && table.hand_results.length > 0 && (
        <HandResultModal
          isOpen={true}
          handNumber={table.hand_number}
          boardCards={table.board_cards}
          boardCards2={table.board_cards_2}
          allInInitialBoardCount={table.all_in_initial_board_count || 0}
          ritEnabled={table.rit_enabled}
          handResults={table.hand_results}
          totalPot={table.total_pot}
          selfSeat={selfSeat}
          isHost={isHost}
          buyinChips={room?.config?.buyin_chips || 1000}
          readyPlayerIds={table.ready_player_ids || []}
          onShowCard={(payload) => onSendWsEvent('SHOW_CARD', payload)}
          onToggleReady={() => {
            const isReady = table.ready_player_ids?.includes(selfSeat?.player_id);
            onSendWsEvent('PLAYER_READY', { ready: !isReady });
          }}
          onRebuy={handleRebuy}
          onStartNextHand={handleStartGame}
          onClose={() => setHandResultDismissed(true)}
        />
      )}

      {/* Final Settlement Report Modal */}
      {settlementOpen && (
        <SettlementModal
          report={room?.settlement_report}
          onClose={() => {
            setSettlementOpen(false);
            onLeaveRoom();
          }}
        />
      )}
    </div>
  );
}
