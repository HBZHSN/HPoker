import React from 'react';
import CardView from './CardView';
import { Crown, DollarSign, RefreshCw, UserPlus } from 'lucide-react';

export default function PlayerSeat({
  seatIndex,
  seatData,
  isCurrentTurn,
  isDealer,
  isSB,
  isBB,
  currentRoundBet = 0,
  onSitDown,
  currentUserId,
  actionTimeout = 15,
  payoutInfo = null,
}) {
  // Empty seat
  if (!seatData) {
    return (
      <div className="flex flex-col items-center justify-center">
        <button
          onClick={() => onSitDown(seatIndex)}
          className="group relative flex flex-col items-center justify-center w-20 h-20 md:w-24 md:h-24 rounded-full border-2 border-dashed border-amber-500/30 bg-black/40 hover:border-amber-400 hover:bg-amber-950/30 transition-all duration-300 backdrop-blur-sm shadow-inner"
        >
          <UserPlus className="w-6 h-6 text-amber-500/60 group-hover:text-amber-400 group-hover:scale-110 transition-transform" />
          <span className="text-[11px] font-medium text-amber-300/70 group-hover:text-amber-300 mt-1">
            入座 {seatIndex + 1}
          </span>
        </button>
      </div>
    );
  }

  const isSelf = seatData.player_id === currentUserId;
  const isWinner = !!payoutInfo;
  const isFolded = seatData.is_folded;
  const isAllIn = seatData.is_all_in;

  return (
    <div className={`relative flex flex-col items-center ${isFolded ? 'opacity-45 grayscale' : ''}`}>
      {/* Position Badges: Dealer, SB, BB */}
      <div className="absolute -top-3 -right-2 z-20 flex gap-1 items-center">
        {isDealer && (
          <span className="w-5 h-5 rounded-full bg-amber-400 text-slate-950 font-black text-[10px] flex items-center justify-center shadow-md ring-1 ring-white">
            D
          </span>
        )}
        {isSB && (
          <span className="w-5 h-5 rounded-full bg-blue-500 text-white font-black text-[10px] flex items-center justify-center shadow-md ring-1 ring-white">
            SB
          </span>
        )}
        {isBB && (
          <span className="w-5 h-5 rounded-full bg-purple-600 text-white font-black text-[10px] flex items-center justify-center shadow-md ring-1 ring-white">
            BB
          </span>
        )}
      </div>

      {/* Main Avatar & Info Circle with Countdown Ring */}
      <div className="relative flex items-center justify-center">
        {/* Countdown Ring SVG when it's player's turn */}
        {isCurrentTurn && (
          <svg className="absolute -inset-1 w-[calc(100%+8px)] h-[calc(100%+8px)] -rotate-90 pointer-events-none z-10">
            <circle
              cx="50%"
              cy="50%"
              r="46%"
              className="fill-none stroke-amber-400 stroke-[3px] animate-pulse"
              strokeDasharray="280"
              strokeDashoffset="0"
              style={{
                animation: `dash ${actionTimeout}s linear forwards, pulse-glow 1.5s infinite`,
              }}
            />
          </svg>
        )}

        {/* Avatar Card */}
        <div
          className={`relative flex flex-col items-center justify-center w-20 h-20 md:w-24 md:h-24 rounded-full border-2 bg-gradient-to-b from-slate-800 to-slate-950 shadow-xl overflow-hidden transition-all duration-300 ${
            isCurrentTurn
              ? 'border-amber-400 shadow-glow-gold scale-105'
              : isWinner
              ? 'border-emerald-400 shadow-glow-cyan'
              : isSelf
              ? 'border-sky-500/80 ring-1 ring-sky-400'
              : 'border-slate-700'
          }`}
        >
          {/* Winner Crown */}
          {isWinner && (
            <div className="absolute top-1 text-amber-400 z-10 animate-bounce">
              <Crown className="w-4 h-4 fill-amber-400" />
            </div>
          )}

          {/* Avatar Icon */}
          <div className="text-2xl md:text-3xl mt-0.5 select-none">
            {seatData.player_id.startsWith('u_admin')
              ? '👑'
              : seatData.player_id.startsWith('u_tom')
              ? '🦈'
              : seatData.player_id.startsWith('u_ivey')
              ? '🦁'
              : seatData.player_id.startsWith('u_antonius')
              ? '🐺'
              : seatData.player_id.startsWith('u_linus')
              ? '🦅'
              : seatData.player_id.startsWith('u_negr')
              ? '🦊'
              : '👤'}
          </div>

          {/* Nickname */}
          <div className="text-[11px] font-semibold text-slate-200 truncate max-w-[70px] text-center leading-tight">
            {seatData.name}
          </div>

          {/* Chips */}
          <div className="flex items-center gap-0.5 text-amber-400 font-extrabold text-[12px] leading-none mt-0.5">
            <span className="text-[10px]">$</span>
            {seatData.chips}
          </div>

          {/* Rebuy Badge Overlay */}
          {seatData.rebuy_count > 1 && (
            <div className="absolute bottom-0.5 bg-amber-900/80 text-amber-300 text-[9px] px-1.5 rounded-full font-medium flex items-center gap-0.5">
              <RefreshCw className="w-2 h-2" />
              x{seatData.rebuy_count}
            </div>
          )}

          {/* All In Badge */}
          {isAllIn && !isFolded && (
            <div className="absolute inset-0 bg-red-950/75 flex items-center justify-center font-black text-red-400 text-xs tracking-wider animate-pulse">
              ALL IN
            </div>
          )}

          {/* Folded Badge */}
          {isFolded && (
            <div className="absolute inset-0 bg-black/60 flex items-center justify-center font-bold text-slate-400 text-xs">
              FOLD
            </div>
          )}
        </div>
      </div>

      {/* Hole Cards */}
      <div className="flex -space-x-4 mt-[-10px] z-10">
        {seatData.hole_cards && seatData.hole_cards.length > 0 ? (
          seatData.hole_cards.map((c, i) => (
            <CardView key={i} card={c} size="sm" className="shadow-md" />
          ))
        ) : seatData.has_cards ? (
          <>
            <CardView isBack size="sm" className="-rotate-6 shadow-md" />
            <CardView isBack size="sm" className="rotate-6 shadow-md" />
          </>
        ) : null}
      </div>

      {/* Shown Cards (if revealed) */}
      {seatData.shown_cards && seatData.shown_cards.length > 0 && !seatData.hole_cards?.length && (
        <div className="flex -space-x-3 mt-1 z-10">
          {seatData.shown_cards.map((c, i) => (
            <CardView key={i} card={c} size="sm" className="shadow-lg ring-1 ring-amber-400" />
          ))}
        </div>
      )}

      {/* Current Round Bet Chip Stack */}
      {currentRoundBet > 0 && (
        <div className="absolute -bottom-6 flex items-center gap-1 bg-black/75 px-2 py-0.5 rounded-full border border-amber-500/40 text-amber-300 text-xs font-bold shadow-md animate-chip-slide z-20">
          <div className="w-2.5 h-2.5 rounded-full bg-amber-400 border border-black shadow-inner" />
          <span>{currentRoundBet}</span>
        </div>
      )}

      {/* Last Action / Payout Tooltip */}
      {payoutInfo ? (
        <div className="absolute -top-7 bg-emerald-950/90 text-emerald-300 border border-emerald-500/50 px-2 py-0.5 rounded-md text-[10px] font-bold shadow-lg animate-bounce z-30 whitespace-nowrap">
          +${payoutInfo.amount} ({payoutInfo.pot_name})
        </div>
      ) : seatData.last_action ? (
        <div className="absolute -top-6 bg-slate-900/90 text-slate-300 border border-slate-700 px-2 py-0.5 rounded-md text-[10px] font-semibold shadow z-20 whitespace-nowrap">
          {seatData.last_action}
        </div>
      ) : null}
    </div>
  );
}
