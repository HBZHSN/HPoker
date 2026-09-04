import React, { useState, useEffect } from 'react';
import CardView from './CardView';
import { sortCardsLowToHigh } from '../utils/cards';
import { Bot, Crown, RefreshCw, UserPlus, Clock, UserX, BarChart2 } from 'lucide-react';

export default function PlayerSeat({
  seatIndex,
  seatData,
  isCurrentTurn,
  isDealer,
  isSB,
  isBB,
  onSitDown,
  isHost = false,
  onKick,
  canKick = false,
  currentUserId,
  actionTimeout = 15,
  currentTurnDuration = 15,
  isUsingTimeBank = false,
  payoutInfo = null,
  street = 'IDLE',
  turnCount = 0,
  actionHistoryLength = 0,
  socialBubble = null,
  bubblePlacement = 'right',
}) {
  const baseTimeout = (isCurrentTurn && isUsingTimeBank)
    ? (currentTurnDuration || 30)
    : (currentTurnDuration || actionTimeout || 15);
  const [timeLeft, setTimeLeft] = useState(baseTimeout);

  useEffect(() => {
    if (!isCurrentTurn) {
      setTimeLeft(baseTimeout);
      return;
    }
    setTimeLeft(baseTimeout);
    const startTime = Date.now();
    const totalMs = baseTimeout * 1000;
    const interval = setInterval(() => {
      const elapsed = Date.now() - startTime;
      const remaining = Math.max(0, (totalMs - elapsed) / 1000);
      setTimeLeft(remaining);
      if (remaining <= 0) {
        clearInterval(interval);
      }
    }, 100);

    return () => clearInterval(interval);
  }, [isCurrentTurn, street, turnCount, actionHistoryLength, baseTimeout, isUsingTimeBank]);

  // Empty seat
  if (!seatData) {
    return (
      <div className="relative flex flex-col items-center justify-center w-16 h-16 md:w-20 md:h-20 lg:w-24 lg:h-24 select-none">
        <button
          onClick={() => onSitDown && onSitDown(seatIndex)}
          className="group relative flex flex-col items-center justify-center w-full h-full rounded-2xl border-2 border-dashed border-slate-700/60 bg-black/40 hover:border-amber-500/40 hover:bg-amber-950/20 transition-all duration-300 backdrop-blur-sm shadow-inner cursor-pointer"
        >
          <UserPlus className="w-5 h-5 text-slate-500 group-hover:text-amber-400 transition-colors" />
          <span className="text-[11px] font-bold text-slate-400 group-hover:text-amber-300 mt-1">
            空座 {seatIndex + 1}
          </span>
        </button>
      </div>
    );
  }

  const isSelf = seatData.player_id === currentUserId;
  const isBot = !!seatData.is_bot;
  const isWinner = !!payoutInfo;
  const isFolded = seatData.is_folded;
  const isAllIn = seatData.is_all_in;

  return (
    <div className={`poker-player-seat ${isSelf ? 'poker-player-seat-self' : ''} relative flex flex-col items-center justify-center w-16 h-16 md:w-20 md:h-20 lg:w-24 lg:h-24 select-none ${isFolded ? 'opacity-40 grayscale-[30%]' : ''}`}>
      {/* Anchor Container for Avatar Card & Floating Badges */}
      <div className="relative w-full h-full flex flex-col items-center justify-center">
        {/* === SOCIAL REACTION / CHAT BUBBLE (Displayed beside avatar, not blocking top status) === */}
        {socialBubble?.type === 'emoji' ? (
          <div
            key={socialBubble.activity_id}
            className={`poker-seat-bubble-anchor absolute top-1/2 -translate-y-1/2 z-40 pointer-events-none ${
              bubblePlacement === 'left'
                ? 'right-[calc(100%+8px)] md:right-[calc(100%+12px)] flex justify-end'
                : 'left-[calc(100%+8px)] md:left-[calc(100%+12px)] flex justify-start'
            }`}
          >
            <div
              className="poker-seat-side-emoji text-3xl md:text-4xl lg:text-5xl select-none filter drop-shadow-[0_4px_10px_rgba(0,0,0,0.85)]"
              role="status"
              aria-label={`${seatData.name} 发送了表情 ${socialBubble.emoji}`}
            >
              {socialBubble.emoji}
            </div>
          </div>
        ) : socialBubble?.type === 'chat' ? (
          <div
            key={socialBubble.activity_id}
            className={`poker-seat-bubble-anchor absolute top-1/2 -translate-y-1/2 z-40 pointer-events-none flex ${
              bubblePlacement === 'left'
                ? 'right-[calc(100%+8px)] md:right-[calc(100%+12px)] justify-end'
                : 'left-[calc(100%+8px)] md:left-[calc(100%+12px)] justify-start'
            }`}
          >
            <div
              className={`poker-seat-side-chat relative w-max max-w-[130px] sm:max-w-[170px] md:max-w-[210px] break-words rounded-2xl border border-amber-400/80 bg-slate-950/95 px-2.5 py-1.5 md:px-3 md:py-2 text-[11px] md:text-xs font-bold leading-relaxed text-slate-100 shadow-[0_8px_25px_rgba(0,0,0,0.85)] backdrop-blur-md ${
                bubblePlacement === 'left' ? 'rounded-tr-sm' : 'rounded-tl-sm'
              }`}
              role="status"
              aria-label={`${seatData.name} 说：${socialBubble.message}`}
            >
              <span
                className={`absolute top-1/2 -translate-y-1/2 w-0 h-0 border-y-[5px] border-y-transparent ${
                  bubblePlacement === 'left'
                    ? '-right-[5px] border-l-[5px] border-l-amber-400/80'
                    : '-left-[5px] border-r-[5px] border-r-amber-400/80'
                }`}
              />
              {socialBubble.message}
            </div>
          </div>
        ) : null}

        {/* === CENTER TOP STATUS / ACTION / PAYOUT BADGE === */}
        {isCurrentTurn ? (
          isUsingTimeBank ? (
            <div className={`absolute -top-8 md:-top-10 left-1/2 -translate-x-1/2 z-30 flex items-center gap-1 px-2 md:px-3 py-0.5 md:py-1 rounded-full ${
              timeLeft <= 5
                ? 'bg-red-950/95 border-2 border-red-500 text-red-200 shadow-glow-red animate-bounce'
                : 'bg-gradient-to-r from-purple-950 to-indigo-950 border-2 border-purple-400 text-purple-200 shadow-glow-cyan animate-pulse'
            } text-[10px] md:text-sm font-black whitespace-nowrap transition-all`}>
              <Clock className={`w-3 h-3 md:w-3.5 md:h-3.5 ${timeLeft <= 5 ? 'text-red-400 animate-spin' : 'text-purple-300 animate-spin'}`} />
              <span>时间卡 +{Math.ceil(timeLeft)}s</span>
            </div>
          ) : (
            <div className={`absolute -top-8 md:-top-10 left-1/2 -translate-x-1/2 z-30 flex items-center gap-1 px-2 md:px-3 py-0.5 md:py-1 rounded-full ${
              timeLeft <= 5
                ? 'bg-red-950/95 border-2 border-red-500 text-red-200 shadow-glow-red animate-bounce scale-105'
                : 'bg-slate-950 border-2 border-amber-400 text-amber-300 shadow-glow-gold animate-pulse'
            } text-[10px] md:text-sm font-black whitespace-nowrap transition-all`}>
              <Clock className={`w-3 h-3 md:w-3.5 md:h-3.5 ${timeLeft <= 5 ? 'text-red-400 animate-spin' : 'text-amber-400 animate-spin'}`} />
              <span>{Math.ceil(timeLeft)}s</span>
            </div>
          )
        ) : payoutInfo ? (
          <div className="absolute -top-8 md:-top-10 left-1/2 -translate-x-1/2 z-30 bg-gradient-to-r from-emerald-950 via-teal-900 to-emerald-950 text-emerald-300 border border-emerald-400 md:border-2 px-2 md:px-3.5 py-0.5 md:py-1 rounded-lg md:rounded-xl text-[10px] md:text-sm font-black shadow-glow-cyan animate-bounce whitespace-nowrap">
            +${payoutInfo.amount} ({payoutInfo.pot_name})
          </div>
        ) : seatData.last_action ? (
          <div
            className={`absolute -top-8 md:-top-10 left-1/2 -translate-x-1/2 px-2 md:px-3.5 py-0.5 md:py-1 rounded-full text-[10px] md:text-sm font-black shadow-2xl z-30 whitespace-nowrap border transition-all md:border-2 ${
              seatData.last_action.startsWith('Raise') || seatData.last_action.startsWith('加注')
                ? 'bg-gradient-to-r from-amber-400 via-amber-500 to-yellow-500 text-slate-950 border-amber-200 shadow-glow-gold scale-105'
                : seatData.last_action.startsWith('Bet') || seatData.last_action.startsWith('下注')
                ? 'bg-gradient-to-r from-amber-500 to-amber-600 text-slate-950 border-amber-300 shadow-glow-gold scale-105'
                : seatData.last_action.startsWith('All-In') || seatData.last_action.startsWith('全下')
                ? 'bg-gradient-to-r from-red-600 to-rose-600 text-white border-red-300 shadow-glow-red scale-105 animate-pulse'
                : seatData.last_action.startsWith('Call') || seatData.last_action.startsWith('跟注')
                ? 'bg-gradient-to-r from-emerald-600 to-teal-700 text-white border-emerald-300 shadow-md'
                : seatData.last_action.startsWith('Check') || seatData.last_action.startsWith('过牌')
                ? 'bg-slate-800 text-slate-200 border-slate-500 shadow-md'
                : seatData.last_action.startsWith('Fold') || seatData.last_action.startsWith('弃牌')
                ? 'bg-slate-900 text-slate-400 border-slate-700 shadow-md'
                : 'bg-slate-900/95 text-amber-300 border-amber-500/60 shadow-md'
            }`}
          >
            {seatData.last_action}
          </div>
        ) : null}

        {/* Winner Crown */}
        {isWinner && (
          <div className="absolute -top-10 md:-top-14 left-1/2 -translate-x-1/2 text-amber-400 z-30 animate-bounce">
            <Crown className="w-4 h-4 md:w-5 md:h-5 fill-amber-400 drop-shadow-[0_0_8px_rgba(251,191,36,0.8)]" />
          </div>
        )}

        {isHost && canKick && !isSelf && (
          <button
            type="button"
            onClick={(event) => {
              event.stopPropagation();
              onKick?.(seatData.player_id, seatData.name);
            }}
            className="absolute -top-2 -right-2 z-40 flex h-5 w-5 items-center justify-center rounded-full border border-red-400/80 bg-red-950/95 text-red-300 shadow-lg transition hover:bg-red-800 hover:text-white active:scale-90"
            title="房主移出玩家"
            aria-label={`将 ${seatData.name} 移出房间`}
          >
            <UserX className="h-3 w-3" />
          </button>
        )}

        {/* === TOP-LEFT CORNER: Buy-in Count Badge & Bot Indicator (买入次数与机器人标识) === */}
        <div className="absolute -top-2 -left-2 z-20 flex items-center gap-1">
          {/* Buy-in Count Badge (买入次数: 超过 1 次时展示) */}
          {seatData.rebuy_count > 1 && (
            <div
              className="flex items-center gap-0.5 bg-gradient-to-r from-amber-500 via-amber-600 to-amber-700 text-slate-950 px-1 py-0.5 rounded-full border border-amber-300 md:border-2 md:px-1.5 text-[9px] md:text-[10px] font-black shadow-lg ring-1 md:ring-2 ring-slate-900 whitespace-nowrap"
              title={`买入次数: ${seatData.rebuy_count} 次 (总买入: $${(seatData.total_buyin_chips || seatData.chips).toLocaleString()})`}
            >
              <RefreshCw className="w-2 h-2 md:w-2.5 md:h-2.5 text-slate-950 stroke-[3]" />
              <span>x{seatData.rebuy_count}</span>
            </div>
          )}

          {isBot && (
            <div
              className="flex items-center gap-0.5 bg-indigo-950/95 text-indigo-200 px-1 py-0.5 rounded-full border border-indigo-400/70 text-[9px] md:text-[10px] font-black shadow-lg ring-1 ring-slate-900 whitespace-nowrap"
              title="测试机器人：随机 Call / Fold / Raise"
            >
              <Bot className="w-2 h-2 md:w-2.5 md:h-2.5" />
              <span>BOT</span>
            </div>
          )}
        </div>

        {/* === BOTTOM-RIGHT CORNER: Time Bank Cards Badge (时间卡数量) === */}
        <div
          className="absolute -bottom-2 -right-2 z-20 flex items-center gap-0.5 bg-slate-950/95 text-amber-300 px-1 py-0.5 rounded-full border border-amber-500/60 text-[9px] md:text-[10px] font-black shadow-lg ring-1 ring-slate-900 whitespace-nowrap"
          title={`时间卡: 剩余 ${seatData.time_bank_cards ?? 3} 张 (每张+30秒)`}
        >
          <span>x{seatData.time_bank_cards ?? 3}</span>
        </div>

        {/* === BOTTOM-LEFT CORNER: Equity Assistant Badge (胜率辅助标识) === */}
        {seatData.using_assistant && (
          <div
            className="absolute -bottom-2 -left-2 z-20 flex items-center gap-0.5 bg-gradient-to-r from-purple-600 via-indigo-600 to-purple-700 text-white px-1.5 py-0.5 rounded-full border border-purple-300 md:border-2 text-[9px] md:text-[10px] font-black shadow-glow-cyan ring-1 md:ring-2 ring-slate-900 whitespace-nowrap animate-pulse"
            title="该玩家正在使用胜率辅助功能"
          >
            <BarChart2 className="w-2.5 h-2.5 text-amber-300 stroke-[3]" />
            <span>辅助</span>
          </div>
        )}

        {/* === TOP-RIGHT CORNER: Dealer / SB / BB Position Badges === */}
        <div className="absolute -top-2 -right-2 z-20 flex gap-0.5 md:gap-1 items-center">
          {isDealer && (
            <span
              className="w-4 h-4 md:w-5 md:h-5 rounded-full bg-gradient-to-br from-amber-300 to-amber-500 text-slate-950 font-black text-[8px] md:text-[10px] flex items-center justify-center shadow-md ring-1 md:ring-2 ring-slate-900"
              title="庄家"
            >
              D
            </span>
          )}
          {isSB && (
            <span
              className="w-4 h-4 md:w-5 md:h-5 rounded-full bg-blue-500 text-white font-black text-[8px] md:text-[10px] flex items-center justify-center shadow-md ring-1 md:ring-2 ring-slate-900"
              title="小盲注"
            >
              SB
            </span>
          )}
          {isBB && (
            <span
              className="w-4 h-4 md:w-5 md:h-5 rounded-full bg-purple-600 text-white font-black text-[8px] md:text-[10px] flex items-center justify-center shadow-md ring-1 md:ring-2 ring-slate-900"
              title="大盲注"
            >
              BB
            </span>
          )}
        </div>

        {/* === MAIN AVATAR CARD === */}
        <div
          className={`poker-player-avatar-card relative flex flex-col items-center justify-between w-full h-full rounded-xl md:rounded-2xl border-2 bg-gradient-to-b from-slate-850 via-slate-900 to-slate-950 shadow-2xl p-1 md:p-1.5 transition-all duration-300 overflow-hidden ${
            isCurrentTurn && isUsingTimeBank
              ? 'border-purple-400 shadow-glow-cyan scale-105 ring-2 ring-purple-400/80'
              : isCurrentTurn
              ? 'border-amber-400 shadow-glow-gold scale-105 ring-2 ring-amber-400/60'
              : isWinner
              ? 'border-emerald-400 shadow-glow-cyan'
              : isSelf
              ? (seatData.using_assistant ? 'border-purple-400 shadow-glow-cyan ring-2 ring-purple-500/60' : 'border-sky-400 shadow-lg ring-2 ring-sky-500/50')
              : seatData.using_assistant
              ? 'border-purple-400 shadow-glow-cyan ring-1 ring-purple-500/50'
              : 'border-slate-700/80'
          }`}
        >
          {/* Avatar Emoji Icon */}
          <div className="text-xl md:text-2xl lg:text-3xl leading-none select-none mt-0.5">
            {seatData.avatar || '👤'}
          </div>

          {/* Nickname */}
          <div className="text-[10px] md:text-[11px] lg:text-xs font-bold text-slate-100 truncate max-w-[56px] md:max-w-[72px] lg:max-w-[84px] text-center leading-tight">
            {seatData.name}
          </div>

          {/* Chips in Bold Font */}
          <div className="flex items-center gap-0.5 text-amber-300 font-black text-[11px] md:text-xs lg:text-sm leading-none mb-1">
            <span className="text-[10px] md:text-[11px] text-amber-400 font-bold">$</span>
            <span>{seatData.chips.toLocaleString()}</span>
          </div>

          {/* Integrated Turn Progress Bar (Bottom Rim of Avatar Card) */}
          {isCurrentTurn && (
            <div className="absolute inset-x-0 bottom-0 h-1 bg-slate-950/80 overflow-hidden border-t border-slate-800 md:h-1.5">
              <div
                className={`h-full transition-all duration-100 ${
                  isUsingTimeBank
                    ? 'bg-gradient-to-r from-purple-400 via-indigo-400 to-fuchsia-400 shadow-[0_0_10px_rgba(192,132,252,0.9)]'
                    : timeLeft > (baseTimeout * 0.5)
                    ? 'bg-gradient-to-r from-emerald-400 to-teal-300 shadow-[0_0_8px_rgba(52,211,153,0.8)]'
                    : timeLeft > (baseTimeout * 0.2)
                    ? 'bg-gradient-to-r from-amber-400 to-yellow-400 shadow-[0_0_8px_rgba(251,191,36,0.8)]'
                    : 'bg-gradient-to-r from-red-500 to-rose-500 animate-pulse shadow-[0_0_10px_rgba(244,63,94,1)]'
                }`}
                style={{ width: `${Math.min(100, (timeLeft / (baseTimeout || 15)) * 100)}%` }}
              />
            </div>
          )}

          {/* All In Overlay */}
          {isAllIn && !isFolded && (
            <div className="absolute inset-0 bg-red-950/90 rounded-xl md:rounded-2xl flex items-center justify-center font-black text-red-400 text-[10px] md:text-sm tracking-wider animate-pulse z-10">
              ALL IN
            </div>
          )}

          {/* Folded Overlay */}
          {isFolded && (
            <div className="absolute inset-0 bg-black/75 rounded-xl md:rounded-2xl flex items-center justify-center font-bold text-slate-400 text-[10px] md:text-xs z-10">
              FOLD
            </div>
          )}
        </div>
      </div>

      {/* Cards Display - displayed directly below the avatar */}
      {(() => {
        const shownCards = sortCardsLowToHigh(seatData.shown_cards || []);
        const holeCards = sortCardsLowToHigh(seatData.hole_cards || []);

        if (shownCards.length > 0) {
          if (isSelf && holeCards.length > 0) {
            // For self: show all hole cards, with revealed cards highlighted
            return (
              <div className="poker-player-cards absolute top-[calc(100%+4px)] left-1/2 -translate-x-1/2 flex -space-x-3.5 z-10">
                {holeCards.map((c, i) => {
                  const isShown = shownCards.some(
                    (sc) =>
                      (sc.rank === c.rank && sc.suit === c.suit) ||
                      (sc.notation && sc.notation === c.notation)
                  );
                  return (
                    <div key={i} className="relative">
                      <CardView
                        card={c}
                        size="md"
                        className={`shadow-lg transition-all ${
                          isShown ? 'ring-2 ring-amber-400 shadow-glow-gold' : 'opacity-50'
                        }`}
                      />
                      <div
                        className={`absolute -bottom-1.5 inset-x-0 py-0.2 text-[8px] font-black text-center rounded ${
                          isShown ? 'bg-amber-400 text-slate-950' : 'bg-slate-800 text-slate-400'
                        }`}
                      >
                        {isShown ? '已亮' : '私密'}
                      </div>
                    </div>
                  );
                })}
              </div>
            );
          } else {
            // For opponents: show ONLY revealed cards (+ 1 card back if only 1 of 2 was revealed)
            return (
              <div className="poker-player-cards absolute top-[calc(100%+4px)] left-1/2 -translate-x-1/2 flex -space-x-3 z-10">
                {shownCards.map((c, i) => (
                  <CardView key={i} card={c} size="sm" className="shadow-xl ring-2 ring-amber-400" />
                ))}
                {shownCards.length === 1 && seatData.has_cards && (
                  <CardView isBack size="sm" className="shadow-md rotate-6" />
                )}
              </div>
            );
          }
        }

        if (holeCards.length > 0) {
          return (
            <div className={`poker-player-cards absolute top-[calc(100%+4px)] left-1/2 -translate-x-1/2 flex ${isSelf ? '-space-x-3.5' : '-space-x-3'} z-10`}>
              {holeCards.map((c, i) => (
                <CardView
                  key={i}
                  card={c}
                  size={isSelf ? 'md' : 'sm'}
                  className="shadow-lg"
                />
              ))}
            </div>
          );
        }

        if (seatData.has_cards && !isFolded) {
          return (
            <div className={`poker-player-cards absolute top-[calc(100%+4px)] left-1/2 -translate-x-1/2 flex ${isSelf ? '-space-x-3.5' : '-space-x-3'} z-10`}>
              <CardView isBack size={isSelf ? 'md' : 'sm'} className="-rotate-6 shadow-md" />
              <CardView isBack size={isSelf ? 'md' : 'sm'} className="rotate-6 shadow-md" />
            </div>
          );
        }

        return null;
      })()}

    </div>
  );
}
