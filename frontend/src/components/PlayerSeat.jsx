import React, { useState, useEffect } from 'react';
import CardView from './CardView';
import { sortCardsLowToHigh } from '../utils/cards';
import { Bot, Crown, RefreshCw, UserPlus, Clock, UserX, BarChart2 } from 'lucide-react';

export default function PlayerSeat({
  seatIndex,
  screenPosition = 0,
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
  onUseTimeCard = null,
  payoutInfo = null,
  street = 'IDLE',
  turnCount = 0,
  actionHistoryLength = 0,
  socialBubble = null,
  bubblePlacement = 'right',
  blindUnit = 10,
}) {
  const isFolded = Boolean(seatData?.is_folded);
  const isAllIn = Boolean(seatData?.is_all_in);
  const hasCards = Boolean(seatData?.has_cards || (seatData?.hole_cards && seatData.hole_cards.length > 0));
  const effectiveIsCurrentTurn = Boolean(isCurrentTurn && hasCards && !isFolded);
  const isWaitingNextHand = !hasCards && !isFolded && !['IDLE', 'HAND_END'].includes(street);
  const bigBlind = blindUnit * 2;

  const baseTimeout = (effectiveIsCurrentTurn && isUsingTimeBank)
    ? (currentTurnDuration || 30)
    : (currentTurnDuration || actionTimeout || 15);
  const [timeLeft, setTimeLeft] = useState(baseTimeout);

  useEffect(() => {
    if (!effectiveIsCurrentTurn) {
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
  }, [effectiveIsCurrentTurn, street, turnCount, actionHistoryLength, baseTimeout, isUsingTimeBank]);

  // Empty seat
  if (!seatData) {
    return (
      <div className="poker-player-seat-empty relative flex flex-col items-center justify-center w-16 h-16 md:w-20 md:h-20 select-none">
        <button
          type="button"
          onClick={() => onSitDown && onSitDown(seatIndex)}
          className="group relative flex flex-col items-center justify-center w-full h-full rounded-xl md:rounded-2xl border border-dashed border-slate-700/60 bg-black/45 hover:border-amber-500/40 hover:bg-amber-950/20 transition-all duration-300 backdrop-blur-sm shadow-inner cursor-pointer"
        >
          <UserPlus className="w-5 h-5 text-slate-400 group-hover:text-amber-400 transition-colors" />
          <span className="text-[10px] md:text-[11px] font-bold text-slate-400 group-hover:text-amber-300 mt-0.5">
            空座 {seatIndex + 1}
          </span>
        </button>
      </div>
    );
  }

  const isSelf = seatData.player_id === currentUserId;
  const isBot = !!seatData.is_bot;
  const isWinner = !!payoutInfo;

  return (
    <div className={`poker-player-seat ${isSelf ? 'poker-player-seat-self' : ''} relative flex flex-col items-center justify-center w-16 h-16 md:w-20 md:h-20 lg:w-24 lg:h-24 select-none`}>
      {/* === SOCIAL REACTION / CHAT BUBBLE (Independent of folded opacity) === */}
      {socialBubble?.type === 'emoji' ? (
        <div
          key={socialBubble.activity_id}
          className={`poker-seat-bubble-anchor absolute top-1/2 -translate-y-1/2 z-40 pointer-events-none ${
            bubblePlacement === 'left'
              ? 'right-[calc(100%+8px)] md:right-[calc(100%+14px)] flex justify-end'
              : 'left-[calc(100%+8px)] md:left-[calc(100%+14px)] flex justify-start'
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
              ? 'right-[calc(100%+8px)] md:right-[calc(100%+14px)] justify-end'
              : 'left-[calc(100%+8px)] md:left-[calc(100%+14px)] justify-start'
          }`}
        >
          <div
            className={`poker-seat-side-chat relative w-max min-w-[44px] md:min-w-[56px] max-w-[140px] sm:max-w-[190px] md:max-w-[280px] lg:max-w-[340px] xl:max-w-[380px] break-words rounded-2xl border border-amber-400/80 md:border-amber-400/90 bg-slate-950/95 px-2.5 py-1.5 md:px-4 md:py-2.5 lg:px-4.5 lg:py-3 text-xs md:text-sm lg:text-[15px] xl:text-base font-bold leading-relaxed text-slate-100 shadow-[0_8px_25px_rgba(0,0,0,0.85)] md:shadow-[0_12px_32px_rgba(0,0,0,0.9)] backdrop-blur-md ${
              bubblePlacement === 'left' ? 'rounded-tr-sm' : 'rounded-tl-sm'
            }`}
            role="status"
            aria-label={`${seatData.name} 说：${socialBubble.message}`}
          >
            <span
              className={`absolute top-1/2 -translate-y-1/2 w-0 h-0 border-y-[5px] md:border-y-[7px] border-y-transparent ${
                bubblePlacement === 'left'
                  ? '-right-[5px] md:-right-[7px] border-l-[5px] md:border-l-[7px] border-l-amber-400/80 md:border-l-amber-400/90'
                  : '-left-[5px] md:-left-[7px] border-r-[5px] md:border-r-[7px] border-r-amber-400/80 md:border-r-amber-400/90'
              }`}
            />
            {socialBubble.message}
          </div>
        </div>
      ) : null}

      {/* Anchor Container for Avatar Card & Floating Badges & Cards (Dimmed & grayscale when folded) */}
      <div className={`poker-player-seat-body relative w-full h-full flex flex-col items-center justify-center transition-all duration-300 ${isFolded ? 'opacity-40 grayscale-[30%]' : isWaitingNextHand ? 'opacity-65' : ''}`}>
        {/* === CENTER TOP STATUS / ACTION / PAYOUT BADGE === */}
        {effectiveIsCurrentTurn ? (
          isUsingTimeBank ? (
            <div className={`absolute -top-8 md:-top-9.5 left-1/2 -translate-x-1/2 z-30 flex items-center gap-1 px-2 md:px-3 py-0.5 rounded-full ${
              timeLeft <= 5
                ? 'bg-red-950/95 border border-red-500 text-red-200 shadow-glow-red animate-bounce'
                : 'bg-gradient-to-r from-purple-950 to-indigo-950 border border-purple-400 text-purple-200 shadow-glow-cyan animate-pulse'
            } text-[10px] md:text-xs font-black whitespace-nowrap transition-all shadow-md`}>
              <Clock className={`w-2.5 h-2.5 md:w-3 md:h-3 ${timeLeft <= 5 ? 'text-red-400 animate-spin' : 'text-purple-300 animate-spin'}`} />
              <span>+{Math.ceil(timeLeft)}s</span>
            </div>
          ) : (
            <div className={`absolute -top-8 md:-top-9.5 left-1/2 -translate-x-1/2 z-30 flex items-center gap-1 px-2 md:px-2.5 py-0.5 rounded-full ${
              timeLeft <= 5
                ? 'bg-red-950/95 border border-red-500 text-red-200 shadow-glow-red animate-bounce scale-105'
                : 'bg-slate-950 border border-amber-400 text-amber-300 shadow-glow-gold animate-pulse'
            } text-[10px] md:text-xs font-black whitespace-nowrap transition-all shadow-md`}>
              <Clock className={`w-2.5 h-2.5 md:w-3 md:h-3 ${timeLeft <= 5 ? 'text-red-400 animate-spin' : 'text-amber-400 animate-spin'}`} />
              <span>{Math.ceil(timeLeft)}s</span>
            </div>
          )
        ) : payoutInfo ? (
          <div className="absolute -top-8 md:-top-9.5 left-1/2 -translate-x-1/2 z-30 bg-gradient-to-r from-emerald-950 via-teal-900 to-emerald-950 text-emerald-300 border border-emerald-400 px-2 md:px-3 py-0.5 rounded-full text-[10px] md:text-xs font-black shadow-glow-cyan animate-bounce whitespace-nowrap">
            +${payoutInfo.amount}
          </div>
        ) : isWaitingNextHand ? (
          <div className="absolute -top-8 md:-top-9.5 left-1/2 -translate-x-1/2 px-2 py-0.5 rounded-full text-[9px] md:text-[10px] font-bold shadow-md z-30 whitespace-nowrap border border-slate-700 bg-slate-900/95 text-slate-400">
            等下局
          </div>
        ) : seatData.current_round_bet > 0 && !seatData.last_action ? (
          <div className="absolute -top-8 md:-top-9.5 left-1/2 -translate-x-1/2 px-2 md:px-2.5 py-0.5 rounded-full text-[10px] md:text-xs font-black shadow-md z-30 whitespace-nowrap border border-amber-500/50 bg-slate-950/95 text-amber-300">
            ${seatData.current_round_bet}
          </div>
        ) : seatData.last_action ? (
          <div
            className={`absolute -top-8 md:-top-9.5 left-1/2 -translate-x-1/2 px-2 md:px-2.5 py-0.5 rounded-full text-[10px] md:text-xs font-black shadow-md z-30 max-w-[85px] md:max-w-[110px] truncate transition-all ${
              seatData.last_action.startsWith('Raise') || seatData.last_action.startsWith('加注')
                ? 'bg-gradient-to-r from-amber-400 to-amber-500 text-slate-950 border-amber-200 shadow-glow-gold'
                : seatData.last_action.startsWith('Bet') || seatData.last_action.startsWith('下注')
                ? 'bg-gradient-to-r from-amber-500 to-amber-600 text-slate-950 border-amber-300 shadow-glow-gold'
                : seatData.last_action.startsWith('All-In') || seatData.last_action.startsWith('全下')
                ? 'bg-gradient-to-r from-red-600 to-rose-600 text-white border-red-300 shadow-glow-red animate-pulse'
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
          <div className="absolute -top-12 md:-top-14 left-1/2 -translate-x-1/2 text-amber-400 z-30 animate-bounce">
            <Crown className="w-4 h-4 md:w-5 md:h-5 fill-amber-400 drop-shadow-[0_0_8px_rgba(251,191,36,0.8)]" />
          </div>
        )}

        {/* === TOP-RIGHT CORNER: Dealer / SB / BB Position Badge & Kick Button === */}
        {(() => {
          const positionBadge = isDealer
            ? { label: 'D', className: 'bg-gradient-to-br from-amber-300 to-amber-500 text-slate-950 ring-amber-600' }
            : isSB
            ? { label: 'SB', className: 'bg-blue-500 text-white ring-blue-700' }
            : isBB
            ? { label: 'BB', className: 'bg-purple-600 text-white ring-purple-800' }
            : null;

          return (
            <>
              {positionBadge && (
                <div className="absolute -top-2 -right-2 z-20 flex items-center">
                  <span
                    className={`w-4 h-4 md:w-5 md:h-5 rounded-full font-black text-[8px] md:text-[10px] flex items-center justify-center shadow-md ring-1 md:ring-2 ring-slate-900 ${positionBadge.className}`}
                  >
                    {positionBadge.label}
                  </span>
                </div>
              )}

              {isHost && canKick && !isSelf && (
                <button
                  type="button"
                  onClick={(event) => {
                    event.stopPropagation();
                    onKick?.(seatData.player_id, seatData.name);
                  }}
                  className={`absolute -top-2.5 ${
                    positionBadge ? '-right-7 md:-right-8' : '-right-2'
                  } z-40 flex h-5 w-5 items-center justify-center rounded-full border border-red-400/80 bg-red-950/95 text-red-300 shadow-lg transition hover:bg-red-800 hover:text-white active:scale-90`}
                  aria-label={`将 ${seatData.name} 移出房间`}
                >
                  <UserX className="h-3 w-3" />
                </button>
              )}
            </>
          );
        })()}

        {/* === TOP-LEFT CORNER: Buy-in Count Badge & Bot Indicator (买入次数与机器人标识) === */}
        <div className="absolute -top-2 -left-2 z-20 flex items-center gap-0.5">
          {/* Buy-in Count Badge (买入次数: 超过 1 次时展示) */}
          {seatData.rebuy_count > 1 && (
            <div
              className="flex items-center gap-0.5 bg-gradient-to-r from-amber-500 via-amber-600 to-amber-700 text-slate-950 px-1 py-0.5 rounded-full border border-amber-300 md:border-2 md:px-1.5 text-[8px] md:text-[9px] font-black shadow-lg ring-1 md:ring-2 ring-slate-900 whitespace-nowrap"
            >
              <RefreshCw className="w-2 h-2 md:w-2.5 md:h-2.5 text-slate-950 stroke-[3]" />
              <span>x{seatData.rebuy_count}</span>
            </div>
          )}

          {isBot && (
            <div
              className="flex items-center gap-0.5 bg-indigo-950/95 text-indigo-200 px-1 py-0.5 rounded-full border border-indigo-400/70 text-[8px] md:text-[9px] font-black shadow-lg ring-1 ring-slate-900 whitespace-nowrap"
            >
              <Bot className="w-2 h-2 md:w-2.5 md:h-2.5" />
              <span>BOT</span>
            </div>
          )}
        </div>

        {/* === BOTTOM-RIGHT CORNER: Time Bank Cards Badge (Self only) === */}
        {isSelf && (
          <button
            type="button"
            onClick={(!isUsingTimeBank && (seatData.time_bank_cards ?? 0) > 0 && onUseTimeCard) ? onUseTimeCard : undefined}
            title={`时间卡: ${seatData.time_bank_cards ?? 3}张 (已玩 ${seatData.hands_played ?? 0} 手，每15手送1张)`}
            className={`absolute -bottom-2 -right-2 z-20 flex items-center gap-0.5 bg-slate-950/95 text-amber-300 px-1.5 py-0.5 rounded-full border border-amber-500/60 text-[8px] md:text-[9px] font-black shadow-lg ring-1 ring-slate-900 whitespace-nowrap ${
              !isUsingTimeBank && (seatData.time_bank_cards ?? 0) > 0 && effectiveIsCurrentTurn
                ? 'cursor-pointer hover:bg-purple-900 hover:text-purple-200 border-purple-400 animate-pulse'
                : 'cursor-default'
            }`}
          >
            <span>x{seatData.time_bank_cards ?? 3}</span>
          </button>
        )}

        {/* === BOTTOM-LEFT CORNER: Equity Assistant Badge (胜率辅助标识) === */}
        {seatData.using_assistant && (
          <div
            className="absolute -bottom-2 -left-2 z-20 flex items-center gap-0.5 bg-gradient-to-r from-purple-600 via-indigo-600 to-purple-700 text-white px-1.5 py-0.5 rounded-full border border-purple-300 text-[8px] md:text-[9px] font-black shadow-glow-cyan ring-1 md:ring-2 ring-slate-900 whitespace-nowrap animate-pulse"
          >
            <BarChart2 className="w-2.5 h-2.5 text-amber-300 stroke-[3]" />
            <span>辅助</span>
          </div>
        )}

        {/* === MAIN AVATAR CARD === */}
        <div
          className={`poker-player-avatar-card relative flex flex-col items-center justify-between w-full h-full rounded-xl md:rounded-2xl border-2 bg-gradient-to-b from-slate-850 via-slate-900 to-slate-950 shadow-2xl p-1 md:p-1.5 transition-all duration-300 overflow-hidden ${
            effectiveIsCurrentTurn && isUsingTimeBank
              ? 'border-purple-400 shadow-glow-cyan scale-105 ring-2 ring-purple-400/80'
              : effectiveIsCurrentTurn
              ? 'border-amber-400 shadow-glow-gold scale-105 ring-2 ring-amber-400/60'
              : isWinner
              ? 'border-emerald-400 shadow-glow-cyan'
              : isSelf
              ? (seatData.using_assistant ? 'border-purple-400 shadow-glow-cyan ring-2 ring-purple-500/60' : 'border-amber-400 shadow-[0_0_15px_rgba(251,191,36,0.35)] ring-2 ring-amber-400/50')
              : seatData.using_assistant
              ? 'border-purple-400 shadow-glow-cyan ring-1 ring-purple-500/50'
              : 'border-slate-700/80'
          }`}
        >
          {/* Avatar Emoji Icon */}
          <div className="text-xl md:text-2xl leading-none select-none mt-0.5">
            {seatData.avatar || '👤'}
          </div>

          {/* Nickname */}
          <div className="text-[10px] md:text-[11px] font-bold text-slate-100 truncate max-w-[58px] md:max-w-[72px] text-center leading-tight">
            {seatData.name}
          </div>

          {/* Chips in Bold Font */}
          <div className="flex items-center gap-0.5 text-amber-300 font-black text-[11px] md:text-xs leading-none mb-0.5">
            <span className="text-[9px] text-amber-400 font-bold">$</span>
            <span>{seatData.chips.toLocaleString()}</span>
          </div>

          {/* Integrated Turn Progress Bar (Bottom Rim of Avatar Card) */}
          {effectiveIsCurrentTurn && (
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
            <div className="absolute inset-0 bg-red-950/90 rounded-xl md:rounded-2xl flex items-center justify-center font-black text-red-400 text-[10px] md:text-xs tracking-wider animate-pulse z-10">
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

        {/* Cards Display */}
        {(() => {
          const shownCards = sortCardsLowToHigh(seatData.shown_cards || []);
          const holeCards = sortCardsLowToHigh(seatData.hole_cards || []);

          const cardContainerClass =
            'poker-player-cards absolute top-[calc(100%-8px)] md:top-[calc(100%+4px)] left-1/2 -translate-x-1/2 flex -space-x-2 md:-space-x-3 z-10';

          if (shownCards.length > 0) {
            if (isSelf && holeCards.length > 0) {
              return (
                <div className={cardContainerClass}>
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
                          size="sm"
                          className={`shadow-lg transition-all ${
                            isShown ? 'ring-2 ring-amber-400 shadow-glow-gold' : 'opacity-50'
                          }`}
                        />
                        <div
                          className={`absolute -bottom-1 inset-x-0 py-0.2 text-[7px] font-black text-center rounded ${
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
              return (
                <div className={cardContainerClass}>
                  {shownCards.map((c, i) => (
                    <CardView key={i} card={c} size="xs" className="shadow-xl ring-1 ring-amber-400" />
                  ))}
                  {shownCards.length === 1 && seatData.has_cards && (
                    <CardView isBack size="xs" className="shadow-md rotate-6" />
                  )}
                </div>
              );
            }
          }

          if (holeCards.length > 0) {
            return (
              <div className={cardContainerClass}>
                {holeCards.map((c, i) => (
                  <CardView
                    key={i}
                    card={c}
                    size={isSelf ? 'sm' : 'xs'}
                    className="shadow-lg"
                  />
                ))}
              </div>
            );
          }

          if (seatData.has_cards && !isFolded) {
            return (
              <div className={cardContainerClass}>
                <CardView isBack size={isSelf ? 'sm' : 'xs'} className="-rotate-6 shadow-md" />
                <CardView isBack size={isSelf ? 'sm' : 'xs'} className="rotate-6 shadow-md" />
              </div>
            );
          }

          return null;
        })()}
      </div>
    </div>
  );
}
