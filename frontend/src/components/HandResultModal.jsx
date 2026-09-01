import React from 'react';
import CardView from './CardView';
import { Trophy, CheckCircle2, Clock, Eye, EyeOff, Play, Sparkles, X, RefreshCw, Layers } from 'lucide-react';

export default function HandResultModal({
  isOpen,
  handNumber = 1,
  boardCards = [],
  boardCards2 = [],
  allInInitialBoardCount = 0,
  ritEnabled = false,
  handResults = [],
  totalPot = 0,
  selfSeat = null,
  isHost = false,
  buyinChips = 1000,
  readyPlayerIds = [],
  onShowCard,
  onToggleReady,
  onRebuy,
  onStartNextHand,
  onClose,
}) {
  if (!isOpen) return null;

  const isSelfReady = selfSeat && readyPlayerIds?.includes(selfSeat.player_id);
  const isBusted = selfSeat && selfSeat.chips === 0;
  const eligiblePlayers = (handResults || []).filter((r) => !r.is_folded || (r.total_bet || 0) > 0);
  const readyCount = eligiblePlayers.filter((r) => readyPlayerIds?.includes(r.player_id)).length;
  const totalEligible = eligiblePlayers.length;

  const handleToggleCard = (idx) => {
    if (onShowCard) {
      onShowCard({ toggle_index: idx });
    }
  };

  const handleShowAll = () => {
    if (onShowCard) {
      onShowCard({ show_all: true });
    }
  };

  const handleHideAll = () => {
    if (onShowCard) {
      onShowCard({ hide_all: true });
    }
  };

  const hasTwoBoards = (ritEnabled || (boardCards2 && boardCards2.length > 0));
  const initialCount = allInInitialBoardCount || 0;
  const run2Cards = (boardCards2 || []).slice(initialCount);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/85 backdrop-blur-md p-3 sm:p-4 animate-fade-in">
      <div className="relative w-full max-w-3xl bg-gradient-to-b from-slate-900 via-slate-950 to-black border-2 border-amber-500/50 rounded-3xl shadow-2xl overflow-hidden flex flex-col max-h-[92vh]">
        {/* Header */}
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between px-5 py-3 sm:py-4 border-b border-slate-800 bg-slate-900/90 gap-2 sm:gap-0">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-2xl bg-gradient-to-br from-amber-400 to-amber-600 flex items-center justify-center shadow-glow-gold">
              <Trophy className="w-6 h-6 text-slate-950" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base md:text-lg font-black text-amber-400 tracking-wide">
                  第 #{handNumber} 手牌战局结算
                </h2>
                {hasTwoBoards && (
                  <span className="text-[10px] bg-gradient-to-r from-purple-600 to-indigo-600 text-white font-black px-2 py-0.5 rounded-full border border-purple-400/50 shadow flex items-center gap-1">
                    <Layers className="w-3 h-3" />
                    发 2 次牌 (Run It Twice)
                  </span>
                )}
              </div>
              <p className="text-xs text-slate-400">
                底池总额: <strong className="text-amber-300 font-black">${totalPot}</strong>
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3 w-full sm:w-auto justify-between sm:justify-end">
            {/* Board Community Cards */}
            {!hasTwoBoards ? (
              <div className="flex items-center gap-1.5 bg-black/50 p-1.5 sm:p-2 rounded-xl border border-slate-800">
                <span className="text-[11px] font-bold text-slate-400 mr-1 hidden sm:inline">公共牌:</span>
                {boardCards && boardCards.length > 0 ? (
                  boardCards.map((c, i) => <CardView key={i} card={c} size="xs" />)
                ) : (
                  <span className="text-xs text-slate-500 italic">无公共牌</span>
                )}
              </div>
            ) : (
              <div className="flex flex-col gap-1 bg-black/60 p-1.5 rounded-xl border border-purple-500/30 text-xs">
                <div className="flex items-center gap-1">
                  <span className="text-[10px] text-purple-300 font-bold w-12">第1次:</span>
                  {boardCards.map((c, i) => <CardView key={i} card={c} size="xs" />)}
                </div>
                <div className="flex items-center gap-1">
                  <span className="text-[10px] text-indigo-300 font-bold w-12">
                    {initialCount === 0 ? '第2次:' : initialCount === 3 ? '第2次(转/河):' : '第2次(河):'}
                  </span>
                  {run2Cards.map((c, i) => <CardView key={i} card={c} size="xs" />)}
                </div>
              </div>
            )}

            {/* Close Button */}
            {onClose && (
              <button
                onClick={onClose}
                className="w-8 h-8 sm:w-9 sm:h-9 rounded-xl bg-slate-800/80 hover:bg-slate-700 text-slate-400 hover:text-white flex items-center justify-center transition cursor-pointer"
                title="关闭弹窗查看牌桌"
              >
                <X className="w-4 h-4 sm:w-5 sm:h-5" />
              </button>
            )}
          </div>
        </div>

        {/* Body: Player Profit/Loss & Hand Rankings List */}
        <div className="flex-1 overflow-y-auto p-4 md:p-6 flex flex-col gap-3">
          {/* Immediate Re-buy Banner when Chips are Busted */}
          {isBusted && onRebuy && (
            <div className="bg-gradient-to-r from-red-950/90 via-amber-950/90 to-red-950/90 border-2 border-amber-400/80 rounded-2xl p-4 flex flex-col sm:flex-row items-center justify-between gap-3 shadow-glow-gold animate-pulse">
              <div className="flex items-center gap-3 text-center sm:text-left">
                <div className="w-10 h-10 rounded-xl bg-amber-500 flex items-center justify-center text-slate-950 font-black text-xl shadow flex-shrink-0">
                  💸
                </div>
                <div>
                  <div className="text-sm font-black text-amber-300">
                    您的筹码已全部输完 (余额: $0)
                  </div>
                  <div className="text-xs text-slate-300">
                    立即补充买入 ${buyinChips} 筹码，即可继续参加下一局！
                  </div>
                </div>
              </div>
              <button
                onClick={onRebuy}
                className="w-full sm:w-auto px-5 py-2.5 bg-gradient-to-r from-amber-400 via-amber-500 to-amber-600 hover:from-amber-300 hover:to-amber-400 text-slate-950 font-black text-sm rounded-xl shadow-xl transition active:scale-95 cursor-pointer flex items-center justify-center gap-2 flex-shrink-0"
              >
                <RefreshCw className="w-4 h-4" />
                立即补充买入 (${buyinChips})
              </button>
            </div>
          )}

          <div className="text-xs font-black text-slate-400 uppercase tracking-wider flex items-center justify-between px-1">
            <span>玩家战绩与牌型明细</span>
            <span>
              准备进度: <strong className="text-amber-300 font-black">{readyCount}</strong> / {totalEligible} 人已确认
            </span>
          </div>

          <div className="flex flex-col gap-2">
            {(handResults || []).map((res, idx) => {
              const isMe = selfSeat && res.player_id === selfSeat.player_id;
              const isWinner = !!res.is_winner;
              const isReady = readyPlayerIds && readyPlayerIds.includes(res.player_id);
              const playerName = res.name || `玩家 (Seat ${res.seat_index !== undefined ? res.seat_index + 1 : idx + 1})`;

              return (
                <div
                  key={idx}
                  className={`flex flex-col sm:flex-row items-center justify-between p-3 rounded-2xl border transition-all ${
                    isWinner
                      ? 'bg-gradient-to-r from-amber-950/60 via-slate-900/90 to-amber-950/60 border-amber-400 shadow-glow-gold'
                      : isMe
                      ? 'bg-slate-900/90 border-sky-500/50'
                      : 'bg-slate-950/80 border-slate-800'
                  }`}
                >
                  {/* Player Info & Cards */}
                  <div className="flex items-center gap-3 w-full sm:w-auto">
                    <div className="relative flex items-center justify-center flex-shrink-0">
                      <div className="w-10 h-10 rounded-xl bg-slate-800 border border-slate-700 flex items-center justify-center text-xl">
                        {playerName.includes('Admin') ? '👑' : isMe ? '👤' : '🦁'}
                      </div>
                      {isWinner && (
                        <div className="absolute -top-2 -right-1 text-amber-400">
                          <Sparkles className="w-4 h-4 fill-amber-400 animate-spin" />
                        </div>
                      )}
                    </div>

                    <div className="flex flex-col">
                      <div className="flex items-center gap-1.5 flex-wrap">
                        <span className="font-black text-sm text-slate-100">{playerName}</span>
                        {isMe && (
                          <span className="text-[10px] bg-sky-950 text-sky-300 px-1.5 py-0.2 rounded border border-sky-500/40 font-bold">
                            您
                          </span>
                        )}
                        {isWinner && (
                          <span className="text-[10px] bg-amber-500 text-slate-950 px-1.5 py-0.2 rounded font-black">
                            获胜 WINNER
                          </span>
                        )}
                      </div>
                      <div className="flex flex-col gap-0.5 mt-0.5">
                        {!hasTwoBoards ? (
                          <span className="text-xs font-bold text-amber-300">
                            牌型: <strong className="text-white">{res.hand_desc || '未知牌型'}</strong>
                          </span>
                        ) : (
                          <>
                            <span className="text-xs font-bold text-purple-300">
                              第1次牌型: <strong className="text-white">{res.hand_desc || '未知'}</strong>
                              {res.payout_board_1 > 0 && <span className="text-emerald-400 ml-1">(分池 +${res.payout_board_1})</span>}
                            </span>
                            <span className="text-xs font-bold text-indigo-300">
                              第2次牌型: <strong className="text-white">{res.hand_desc_2 || '未知'}</strong>
                              {res.payout_board_2 > 0 && <span className="text-emerald-400 ml-1">(分池 +${res.payout_board_2})</span>}
                            </span>
                          </>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Cards Display & Profit */}
                  <div className="flex items-center gap-4 mt-2 sm:mt-0 w-full sm:w-auto justify-between sm:justify-end">
                    <div className="flex -space-x-3 items-center">
                      {(() => {
                        const shownCards = res.shown_cards || [];
                        const holeCards = res.hole_cards || [];
                        const isSameCard = (a, b) =>
                          a && b && ((a.rank === b.rank && a.suit === b.suit) || (a.notation && a.notation === b.notation));

                        if (isMe && holeCards.length > 0) {
                          if (shownCards.length > 0) {
                            return holeCards.map((c, i) => {
                              const isCardShown = shownCards.some((sc) => isSameCard(sc, c));
                              return (
                                <div key={i} className="relative">
                                  <CardView
                                    card={c}
                                    size="sm"
                                    className={`shadow-lg transition-all ${
                                      isCardShown ? 'ring-2 ring-amber-400 shadow-glow-gold' : 'opacity-40 grayscale-[40%]'
                                    }`}
                                  />
                                  <div
                                    className={`absolute -bottom-1.5 inset-x-0 py-0.2 text-[7px] font-black text-center rounded ${
                                      isCardShown ? 'bg-amber-400 text-slate-950' : 'bg-slate-800 text-slate-400'
                                    }`}
                                  >
                                    {isCardShown ? '已亮' : '私密'}
                                  </div>
                                </div>
                              );
                            });
                          } else {
                            return (
                              <div className="flex items-center gap-1.5">
                                <div className="flex -space-x-3 opacity-60">
                                  {holeCards.map((c, i) => (
                                    <CardView key={i} card={c} size="sm" className="shadow-md" />
                                  ))}
                                </div>
                                <span className="text-[10px] text-slate-500 font-bold bg-slate-800/80 px-1.5 py-0.5 rounded border border-slate-700">
                                  私密
                                </span>
                              </div>
                            );
                          }
                        }

                        if (shownCards.length > 0) {
                          return (
                            <>
                              {shownCards.map((c, i) => (
                                <CardView key={i} card={c} size="sm" className="shadow-lg ring-2 ring-amber-400" />
                              ))}
                              {shownCards.length === 1 && (
                                <CardView isBack size="sm" className="shadow-md rotate-6" />
                              )}
                            </>
                          );
                        }

                        return (
                          <div className="text-[11px] text-slate-500 font-medium italic px-2">
                            {res.is_folded ? '已弃牌' : '未亮牌'}
                          </div>
                        );
                      })()}
                    </div>

                    {/* Net Profit / Loss */}
                    <div className="flex flex-col items-end min-w-[80px]">
                      <span
                        className={`text-base font-black ${
                          res.net_profit > 0
                            ? 'text-emerald-400'
                            : res.net_profit < 0
                            ? 'text-red-400'
                            : 'text-slate-400'
                        }`}
                      >
                        {res.net_profit > 0 ? `+$${res.net_profit}` : res.net_profit < 0 ? `-$${Math.abs(res.net_profit)}` : '$0'}
                      </span>
                      <span className={`text-[11px] font-medium ${res.chips === 0 ? 'text-red-400 font-bold' : 'text-slate-400'}`}>
                        余额: ${res.chips}
                      </span>
                    </div>

                    {/* Ready Status Badge or Quick Rebuy */}
                    <div className="ml-1 sm:ml-2">
                      {isMe && isBusted && onRebuy ? (
                        <button
                          onClick={onRebuy}
                          className="px-2.5 py-1 bg-amber-500 hover:bg-amber-400 text-slate-950 font-black text-xs rounded-lg shadow transition active:scale-95 cursor-pointer flex items-center gap-1"
                        >
                          <RefreshCw className="w-3 h-3" />
                          买入
                        </button>
                      ) : isReady ? (
                        <span className="flex items-center gap-1 text-xs font-bold text-emerald-400 bg-emerald-950/80 px-2 py-1 rounded-lg border border-emerald-500/40">
                          <CheckCircle2 className="w-3.5 h-3.5" />
                          已准备
                        </span>
                      ) : (
                        <span className="flex items-center gap-1 text-xs font-bold text-slate-400 bg-slate-900 px-2 py-1 rounded-lg border border-slate-800">
                          <Clock className="w-3.5 h-3.5 animate-spin" />
                          思考中
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Interactive Card Reveal Selector (for the current seated user) */}
          {selfSeat && selfSeat.hole_cards && selfSeat.hole_cards.length === 2 && (
            <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-4 mt-2 flex flex-col sm:flex-row items-center justify-between gap-3 shadow-xl">
              <div className="flex flex-col gap-1 text-center sm:text-left">
                <div className="flex items-center gap-1.5 justify-center sm:justify-start">
                  <Eye className="w-4 h-4 text-amber-400" />
                  <span className="text-sm font-black text-slate-100">局末亮牌选择 (Show Cards)</span>
                </div>
                <span className="text-xs text-slate-400">
                  点击手牌可单独亮出或隐藏，供所有玩家查看
                </span>
              </div>

              {/* Two Clickable Cards */}
              <div className="flex items-center gap-3">
                {selfSeat.hole_cards.map((card, idx) => {
                  const isCardShown = selfSeat.shown_cards?.some(
                    (sc) =>
                      (sc.rank === card.rank && sc.suit === card.suit) ||
                      (sc.notation && sc.notation === card.notation)
                  );

                  return (
                    <button
                      key={idx}
                      onClick={() => handleToggleCard(idx)}
                      className={`relative group cursor-pointer transition-transform active:scale-95 ${
                        isCardShown ? 'ring-4 ring-amber-400 rounded-lg scale-105' : 'opacity-80 hover:opacity-100'
                      }`}
                      title={isCardShown ? '点击隐藏此牌' : '点击亮出此牌'}
                    >
                      <CardView card={card} size="md" />
                      <div
                        className={`absolute -bottom-2 inset-x-0 py-0.5 rounded text-[10px] font-black text-center shadow ${
                          isCardShown ? 'bg-amber-400 text-slate-950' : 'bg-slate-800 text-slate-300'
                        }`}
                      >
                        {isCardShown ? '已亮出' : '点击亮'}
                      </div>
                    </button>
                  );
                })}
              </div>

              {/* Quick Reveal Buttons */}
              <div className="flex items-center gap-2">
                <button
                  onClick={handleShowAll}
                  className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-amber-300 text-xs font-bold rounded-xl border border-slate-700 transition active:scale-95 cursor-pointer flex items-center gap-1"
                >
                  <Eye className="w-3.5 h-3.5" />
                  全部亮出
                </button>
                <button
                  onClick={handleHideAll}
                  className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-bold rounded-xl border border-slate-700 transition active:scale-95 cursor-pointer flex items-center gap-1"
                >
                  <EyeOff className="w-3.5 h-3.5" />
                  藏牌 (Muck)
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Footer: Confirm Ready / Start Hand Controls */}
        <div className="px-5 sm:px-6 py-3 sm:py-4 border-t border-slate-800 bg-slate-900/95 flex flex-col sm:flex-row items-center justify-between gap-3">
          <div className="text-xs text-slate-400 font-bold text-center sm:text-left">
            {isBusted
              ? '筹码已输光，请先“补充买入”再准备'
              : isHost
              ? '房主可随时点击“立即开局”，或等待全员就绪'
              : '请点击“确认并准备下一局”等待开始'}
          </div>

          <div className="flex items-center gap-3 w-full sm:w-auto">
            {isBusted && onRebuy ? (
              <button
                onClick={onRebuy}
                className="flex-1 sm:flex-none px-6 py-3 bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-400 hover:to-amber-500 text-slate-950 font-black text-sm rounded-xl shadow-glow-gold transition active:scale-95 cursor-pointer flex items-center justify-center gap-2 animate-pulse"
              >
                <RefreshCw className="w-4 h-4" />
                立即补充买入 (${buyinChips})
              </button>
            ) : selfSeat ? (
              <button
                onClick={onToggleReady}
                className={`flex-1 sm:flex-none px-6 py-3 rounded-xl font-black text-sm transition shadow-lg active:scale-95 cursor-pointer flex items-center justify-center gap-2 ${
                  isSelfReady
                    ? 'bg-slate-800 text-emerald-300 border border-emerald-500/50'
                    : 'bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white shadow-glow-cyan'
                }`}
              >
                {isSelfReady ? (
                  <>
                    <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                    已准备 (等待他人)
                  </>
                ) : (
                  <>
                    <CheckCircle2 className="w-4 h-4" />
                    确认并准备下一局
                  </>
                )}
              </button>
            ) : null}

            {isHost && onStartNextHand && (
              <button
                onClick={onStartNextHand}
                className="flex-1 sm:flex-none px-5 py-3 bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-400 hover:to-amber-500 text-slate-950 font-black text-sm rounded-xl shadow-glow-gold transition active:scale-95 cursor-pointer flex items-center justify-center gap-1.5"
              >
                <Play className="w-4 h-4 fill-slate-950" />
                立即开局
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
