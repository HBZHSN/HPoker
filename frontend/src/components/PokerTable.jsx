import React, { useState, useEffect, useMemo } from 'react';
import PlayerSeat from './PlayerSeat';
import CardView from './CardView';
import ActionBar from './ActionBar';
import ShowCardsModal from './ShowCardsModal';
import SettlementModal from './SettlementModal';
import { soundEngine } from '../sound/SoundEngine';
import {
  Volume2,
  VolumeX,
  RefreshCw,
  LogOut,
  PowerOff,
  Play,
  Share2,
  Users,
  Clock,
  Sparkles,
} from 'lucide-react';

export default function PokerTable({
  room,
  currentUser,
  onSendWsEvent,
  onLeaveRoom,
}) {
  const [isMuted, setIsMuted] = useState(false);
  const [showCardsVisible, setShowCardsVisible] = useState(false);
  const [settlementOpen, setSettlementOpen] = useState(false);

  const table = room?.table;
  const isHost = room?.host_player_id === currentUser?.user_id;

  // Toggle Mute
  const toggleMute = () => {
    const next = !isMuted;
    setIsMuted(next);
    soundEngine.setMuted(next);
  };

  // Find self in seats
  const selfSeat = useMemo(() => {
    if (!table?.seats) return null;
    return table.seats.find((s) => s && s.player_id === currentUser?.user_id);
  }, [table?.seats, currentUser?.user_id]);

  // Handle Hand End show card prompt
  useEffect(() => {
    if (table?.street === 'HAND_END' && selfSeat && selfSeat.hole_cards?.length === 2) {
      setShowCardsVisible(true);
    } else {
      setShowCardsVisible(false);
    }
  }, [table?.street, selfSeat]);

  // Handle Settlement report prompt
  useEffect(() => {
    if (room?.is_ended && room?.settlement_report) {
      setSettlementOpen(true);
    }
  }, [room?.is_ended, room?.settlement_report]);

  // Seat placement geometry (oval coordinates in percentages)
  const maxSeats = room?.config?.max_seats || 6;
  const seatPositions = useMemo(() => {
    if (maxSeats === 6) {
      return [
        { top: '80%', left: '50%' }, // Seat 0 (Bottom Center - typically user)
        { top: '68%', left: '15%' }, // Seat 1 (Bottom Left)
        { top: '25%', left: '15%' }, // Seat 2 (Top Left)
        { top: '10%', left: '50%' }, // Seat 3 (Top Center)
        { top: '25%', left: '85%' }, // Seat 4 (Top Right)
        { top: '68%', left: '85%' }, // Seat 5 (Bottom Right)
      ];
    }
    // 9 Seats layout
    return [
      { top: '82%', left: '50%' }, // 0
      { top: '75%', left: '22%' }, // 1
      { top: '50%', left: '10%' }, // 2
      { top: '22%', left: '22%' }, // 3
      { top: '10%', left: '42%' }, // 4
      { top: '10%', left: '58%' }, // 5
      { top: '22%', left: '78%' }, // 6
      { top: '50%', left: '90%' }, // 7
      { top: '75%', left: '78%' }, // 8
    ];
  }, [maxSeats]);

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

  const handlePlayerAction = (action, amount = 0) => {
    onSendWsEvent('PLAYER_ACTION', { action, amount });
  };

  const handleShowCard = (cardIndex, showAll) => {
    onSendWsEvent('SHOW_CARD', { card_index: cardIndex, show_all: showAll });
    setShowCardsVisible(false);
  };

  return (
    <div className="relative w-full h-screen max-h-screen overflow-hidden flex flex-col justify-between bg-gradient-to-b from-[#080b11] to-[#040507]">
      {/* Top Navigation Bar */}
      <header className="flex items-center justify-between px-4 py-2 bg-slate-950/80 border-b border-slate-800/80 backdrop-blur-md z-30">
        <div className="flex items-center gap-3">
          <button
            onClick={onLeaveRoom}
            className="flex items-center gap-1 px-3 py-1.5 bg-slate-900 hover:bg-slate-800 text-slate-300 rounded-xl text-xs font-semibold border border-slate-700 transition"
          >
            <LogOut className="w-3.5 h-3.5" />
            大厅
          </button>

          <div className="flex flex-col">
            <div className="flex items-center gap-2">
              <h1 className="text-sm font-black text-amber-400 tracking-wide">
                {room?.config?.room_name || 'GGPoker 现金桌'}
              </h1>
              <span className="text-[10px] bg-amber-950 text-amber-300 px-2 py-0.5 rounded-full border border-amber-500/30">
                盲注: ${room?.config?.small_blind}/${room?.config?.big_blind}
              </span>
            </div>
            <span className="text-[10px] text-slate-400">
              买入: ${room?.config?.buyin_chips} = ¥{room?.config?.cash_value} · 超时: {room?.config?.action_timeout}s
            </span>
          </div>
        </div>

        {/* Top Right Controls */}
        <div className="flex items-center gap-2">
          {/* Sound Toggle */}
          <button
            onClick={toggleMute}
            className="p-2 bg-slate-900 hover:bg-slate-800 text-slate-300 rounded-xl border border-slate-700 transition"
            title={isMuted ? '取消静音' : '静音'}
          >
            {isMuted ? <VolumeX className="w-4 h-4 text-red-400" /> : <Volume2 className="w-4 h-4 text-amber-400" />}
          </button>

          {/* Rebuy Button (for seated player) */}
          {selfSeat && (
            <button
              onClick={handleRebuy}
              className="flex items-center gap-1 px-3 py-1.5 bg-gradient-to-r from-amber-600 to-amber-700 hover:from-amber-500 hover:to-amber-600 text-slate-950 rounded-xl text-xs font-black shadow-md transition"
              title="补充买入筹码"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              Re-buy (${room?.config?.buyin_chips})
            </button>
          )}

          {/* Stand Up Button */}
          {selfSeat && (
            <button
              onClick={handleStandUp}
              className="flex items-center gap-1 px-3 py-1.5 bg-slate-900 hover:bg-slate-800 text-slate-300 rounded-xl text-xs font-semibold border border-slate-700 transition"
            >
              站起
            </button>
          )}

          {/* Host End Room Button */}
          {isHost && !room?.is_ended && (
            <button
              onClick={handleEndRoom}
              className="flex items-center gap-1 px-3 py-1.5 bg-red-900/80 hover:bg-red-800 text-red-200 rounded-xl text-xs font-bold border border-red-500/40 shadow transition"
            >
              <PowerOff className="w-3.5 h-3.5" />
              结束房间并结算
            </button>
          )}
        </div>
      </header>

      {/* Main Poker Table Felt Area */}
      <main className="relative flex-1 w-full max-w-5xl mx-auto flex items-center justify-center p-2 md:p-6 select-none">
        {/* Table Exterior Border Ring (Leather & Wood Armrest) */}
        <div className="relative w-full h-[85%] max-h-[560px] rounded-[160px] md:rounded-[220px] bg-gradient-to-b from-[#2a1e17] via-[#1a130e] to-[#0c0806] p-3 md:p-4 shadow-table border-[3px] border-[#3d2c22]">
          {/* Inner Golden Line */}
          <div className="w-full h-full rounded-[145px] md:rounded-[205px] border border-amber-600/30 p-2 md:p-3 bg-gradient-to-b from-[#0a2016] to-[#04110b] relative shadow-inner overflow-hidden">
            {/* Felt Texture Pattern */}
            <div className="absolute inset-0 opacity-15 bg-[radial-gradient(#2ecc71_1px,transparent_1px)] [background-size:12px_12px] pointer-events-none" />

            {/* GGPoker Center Logo Watermark */}
            <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none opacity-20">
              <span className="text-4xl md:text-5xl font-black tracking-widest text-amber-500 font-serif">
                GGPOKER
              </span>
              <span className="text-xs tracking-widest text-amber-300 uppercase mt-1">
                HIGH STAKES CASH GAME
              </span>
            </div>

            {/* Center Table Area: Board Cards & Pots */}
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 z-10">
              {/* Street & Total Pot Badge */}
              <div className="flex flex-col items-center gap-1">
                <div className="flex items-center gap-2 bg-black/60 px-3 py-1 rounded-full border border-amber-500/30 backdrop-blur-md shadow-lg">
                  <span className="text-xs font-semibold text-slate-300">
                    {table?.street === 'PREFLOP'
                      ? '翻牌前 (Preflop)'
                      : table?.street === 'FLOP'
                      ? '翻牌圈 (Flop)'
                      : table?.street === 'TURN'
                      ? '转牌圈 (Turn)'
                      : table?.street === 'RIVER'
                      ? '河牌圈 (River)'
                      : table?.street === 'SHOWDOWN'
                      ? '摊牌比牌 (Showdown)'
                      : table?.street === 'HAND_END'
                      ? '牌局结束'
                      : '等待开局'}
                  </span>
                  <div className="w-1 h-1 rounded-full bg-amber-400" />
                  <span className="text-sm font-black text-amber-400">
                    总底池: ${table?.total_pot || 0}
                  </span>
                </div>

                {/* Side Pots display if multiple pots exist */}
                {table?.pots && table.pots.length > 1 && (
                  <div className="flex items-center gap-2">
                    {table.pots.map((p, i) => (
                      <span
                        key={i}
                        className="text-[10px] font-bold bg-amber-950/70 text-amber-300 px-2 py-0.5 rounded-md border border-amber-500/20"
                      >
                        {p.name}: ${p.amount}
                      </span>
                    ))}
                  </div>
                )}
              </div>

              {/* Community Board Cards */}
              <div className="flex items-center gap-1.5 md:gap-2 min-h-[70px] px-4 py-2 bg-black/40 rounded-2xl border border-white/5 backdrop-blur-sm shadow-inner">
                {table?.board_cards && table.board_cards.length > 0 ? (
                  table.board_cards.map((card, i) => (
                    <CardView key={i} card={card} size="md" className="shadow-lg" />
                  ))
                ) : (
                  <div className="flex gap-2 opacity-30">
                    {[1, 2, 3, 4, 5].map((_, i) => (
                      <div
                        key={i}
                        className="w-11 h-16 border-2 border-dashed border-slate-600 rounded-md flex items-center justify-center text-[10px] text-slate-500 font-bold"
                      >
                        {i < 3 ? 'FLOP' : i === 3 ? 'TURN' : 'RIVER'}
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Start Hand Prompt / Button */}
              {table?.street in { IDLE: 1, HAND_END: 1 } && (
                <button
                  onClick={handleStartGame}
                  className="flex items-center gap-1.5 px-4 py-2 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white text-xs font-black rounded-xl shadow-glow-cyan transition active:scale-95 animate-pulse"
                >
                  <Play className="w-3.5 h-3.5 fill-white" />
                  开始下一手牌
                </button>
              )}
            </div>

            {/* Seated Players Overlay */}
            {seatPositions.map((pos, idx) => {
              const seatData = table?.seats?.[idx] || null;
              const isCurrentTurn = table?.current_turn_seat === idx;
              const isDealer = table?.dealer_seat === idx;
              const isSB = table?.sb_seat === idx;
              const isBB = table?.bb_seat === idx;
              const payout = table?.payouts?.find((p) => p.player_id === seatData?.player_id);

              return (
                <div
                  key={idx}
                  className="absolute -translate-x-1/2 -translate-y-1/2 z-20"
                  style={{ top: pos.top, left: pos.left }}
                >
                  <PlayerSeat
                    seatIndex={idx}
                    seatData={seatData}
                    isCurrentTurn={isCurrentTurn}
                    isDealer={isDealer}
                    isSB={isSB}
                    isBB={isBB}
                    onSitDown={handleSitDown}
                    currentUserId={currentUser?.user_id}
                    actionTimeout={room?.config?.action_timeout || 15}
                    payoutInfo={payout}
                  />
                </div>
              );
            })}
          </div>
        </div>
      </main>

      {/* Bottom Action Bar Area */}
      <footer className="w-full px-4 pb-3 z-30">
        {selfSeat && table?.current_turn_seat === selfSeat.seat_index && table?.legal_actions ? (
          <ActionBar
            legalActions={table.legal_actions}
            totalPot={table.total_pot}
            bigBlind={room?.config?.big_blind || 10}
            onAction={handlePlayerAction}
          />
        ) : null}
      </footer>

      {/* Show Cards Modal when hand ends */}
      {showCardsVisible && (
        <ShowCardsModal
          holeCards={selfSeat?.hole_cards}
          onShowCard={handleShowCard}
          onClose={() => setShowCardsVisible(false)}
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
