import React, { useState, useEffect, useRef } from 'react';
import CardView from './CardView';
import {
  ChevronUp,
  ChevronDown,
  Flame,
  Clock,
  Play,
  Zap,
  History,
  Shield,
  CheckCircle2,
  XCircle,
  RefreshCw,
  AlertCircle,
  Layers,
} from 'lucide-react';

export default function ActionBar({
  legalActions,
  totalPot = 0,
  bigBlind = 10,
  smallBlind = 5,
  buyinChips = 1000,
  onAction,
  disabled = false,
  selfSeat = null,
  isHost = false,
  readyPlayerIds = [],
  onToggleReady,
  onRebuy,
  currentTurnPlayer = null,
  isMyTurn = false,
  street = 'IDLE',
  actionHistory = [],
  onStartGame,
  actionTimeout = 15,
  currentTurnDuration = 15,
  isUsingTimeBank = false,
  onUseTimeCard,
  seats = [],
  ritStatus = null,
  ritVoters = [],
  ritVotes = {},
  onRitChoice,
  turnCount = 0,
}) {
  const minVal = legalActions?.can_bet ? legalActions.min_bet : (legalActions?.min_raise_to || 0);
  const maxVal = legalActions?.can_bet ? legalActions.max_bet : (legalActions?.max_raise_to || 0);

  const [raiseAmount, setRaiseAmount] = useState(minVal || 0);
  const effectiveTimeout = (isUsingTimeBank || (currentTurnPlayer && isUsingTimeBank))
    ? (currentTurnDuration || 30)
    : (currentTurnDuration || actionTimeout || 15);
  const [turnTimeLeft, setTurnTimeLeft] = useState(effectiveTimeout);

  // Sync raiseAmount whenever minVal or maxVal changes
  useEffect(() => {
    if (minVal > 0) {
      setRaiseAmount((prev) => {
        if (!prev || prev < minVal || prev > maxVal) {
          return minVal;
        }
        return prev;
      });
    }
  }, [minVal, maxVal, legalActions?.can_bet, legalActions?.can_raise]);

  // Turn timer countdown in sidebar
  useEffect(() => {
    if (!currentTurnPlayer) {
      setTurnTimeLeft(effectiveTimeout);
      return;
    }
    setTurnTimeLeft(effectiveTimeout);
    const startTime = Date.now();
    const totalMs = effectiveTimeout * 1000;
    const interval = setInterval(() => {
      const elapsed = Date.now() - startTime;
      const remaining = Math.max(0, (totalMs - elapsed) / 1000);
      setTurnTimeLeft(remaining);
      if (remaining <= 0) {
        clearInterval(interval);
      }
    }, 100);

    return () => clearInterval(interval);
  }, [currentTurnPlayer?.player_id, street, turnCount, actionHistory?.length, effectiveTimeout, isUsingTimeBank]);

  const currentAmount = Math.max(minVal, Math.min(maxVal, raiseAmount || minVal));

  const currentAmountRef = useRef(currentAmount);
  currentAmountRef.current = currentAmount;
  const legalActionsRef = useRef(legalActions);
  legalActionsRef.current = legalActions;

  // Keyboard shortcuts (PC)
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (disabled || !legalActionsRef.current || !isMyTurn) return;
      if (['input', 'textarea'].includes(e.target.tagName.toLowerCase())) return;

      const legal = legalActionsRef.current;
      if (e.code === 'KeyF' && legal.can_fold) {
        onAction('FOLD');
      } else if (e.code === 'Space') {
        e.preventDefault();
        if (legal.can_check) {
          onAction('CHECK');
        } else if (legal.can_call) {
          onAction('CALL', legal.call_amount);
        }
      } else if (e.code === 'KeyR' && (legal.can_bet || legal.can_raise)) {
        const act = legal.can_bet ? 'BET' : 'RAISE';
        onAction(act, currentAmountRef.current);
      } else if (e.code === 'KeyA' && legal.can_all_in) {
        onAction('ALL_IN', legal.all_in_amount);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [disabled, onAction, isMyTurn]);

  // Preset Bet Sizing helpers
  const applyPresetRatio = (ratio) => {
    let target = Math.round(totalPot * ratio);
    if (target < minVal) target = minVal;
    if (target > maxVal) target = maxVal;
    setRaiseAmount(target);
  };

  const applyBBMultiplier = (mult) => {
    let target = Math.round(mult * bigBlind);
    if (target < minVal) target = minVal;
    if (target > maxVal) target = maxVal;
    setRaiseAmount(target);
  };

  const adjustBB = (multiplier) => {
    let next = currentAmount + multiplier * bigBlind;
    if (next < minVal) next = minVal;
    if (next > maxVal) next = maxVal;
    setRaiseAmount(next);
  };

  const handleRaiseSubmit = () => {
    if (!legalActions) return;
    const act = legalActions.can_bet ? 'BET' : 'RAISE';
    onAction(act, currentAmount);
  };

  // Helper to lookup player name by ID
  const getPlayerName = (pid) => {
    const p = seats.find((s) => s && s.player_id === pid);
    return p ? p.name : pid;
  };

  const formatActionName = (act, amt) => {
    switch (act) {
      case 'FOLD':
        return '弃牌 Fold';
      case 'CHECK':
        return '过牌 Check';
      case 'CALL':
        return `跟注 Call $${amt}`;
      case 'BET':
        return `下注 Bet $${amt}`;
      case 'RAISE':
        return `加注 Raise to $${amt}`;
      case 'ALL_IN':
        return `全下 All-In $${amt}`;
      case 'POST_SB':
        return `小盲 SB $${amt}`;
      case 'POST_BB':
        return `大盲 BB $${amt}`;
      default:
        return act;
    }
  };

  return (
    <div className="flex flex-col gap-3 w-full h-full text-slate-100 select-none">
      {/* 1. Turn Status & Countdown Banner */}
      <div
        className={`p-3 rounded-2xl border transition-all duration-300 ${
          isMyTurn && isUsingTimeBank
            ? 'bg-gradient-to-r from-purple-950/90 via-slate-900 to-indigo-950 border-purple-400 shadow-glow-cyan'
            : isMyTurn
            ? 'bg-gradient-to-r from-amber-950/80 to-slate-900 border-amber-400 shadow-glow-gold'
            : currentTurnPlayer
            ? 'bg-slate-900/90 border-slate-700/80'
            : 'bg-slate-900/60 border-slate-800'
        }`}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            {isMyTurn ? (
              <span className="flex h-3 w-3 relative">
                <span className={`animate-ping absolute inline-flex h-full w-full rounded-full ${isUsingTimeBank ? 'bg-purple-400' : 'bg-amber-400'} opacity-75`}></span>
                <span className={`relative inline-flex rounded-full h-3 w-3 ${isUsingTimeBank ? 'bg-purple-500' : 'bg-amber-500'}`}></span>
              </span>
            ) : (
              <Clock className="w-4 h-4 text-slate-400" />
            )}
            <span className="text-sm font-black tracking-wide">
              {isMyTurn && isUsingTimeBank
                ? '⚡ 正在使用时间卡延时 (+30s)'
                : isMyTurn
                ? '⚡ 轮到您的行动回合！'
                : currentTurnPlayer
                ? `等待 ${currentTurnPlayer.name} 行动...`
                : street === 'HAND_END'
                ? `本手牌局已结束`
                : '牌桌等待开局'}
            </span>
          </div>

          {currentTurnPlayer && (
            <div className={`flex items-center gap-1 px-2.5 py-0.5 rounded-full border text-xs font-black ${
              isUsingTimeBank
                ? 'bg-purple-950 border-purple-400/70 text-purple-200 shadow-glow-cyan'
                : 'bg-slate-950/80 border-amber-500/40 text-amber-300'
            }`}>
              <Clock className={`w-3 h-3 ${isUsingTimeBank ? 'text-purple-300' : 'text-amber-400'} animate-spin`} />
              <span>{Math.ceil(turnTimeLeft)}s</span>
            </div>
          )}
        </div>

        {/* Real-time turn progress bar */}
        {currentTurnPlayer && (
          <div className="w-full h-2 bg-slate-950 rounded-full overflow-hidden border border-slate-800 mt-2">
            <div
              className={`h-full transition-all duration-100 rounded-full ${
                isUsingTimeBank
                  ? 'bg-gradient-to-r from-purple-400 via-indigo-400 to-fuchsia-400 shadow-[0_0_10px_rgba(192,132,252,0.9)]'
                  : turnTimeLeft > 7
                  ? 'bg-gradient-to-r from-emerald-500 to-teal-400'
                  : turnTimeLeft > 3
                  ? 'bg-gradient-to-r from-amber-400 to-yellow-500'
                  : 'bg-gradient-to-r from-red-500 to-rose-600 animate-pulse'
              }`}
              style={{ width: `${Math.min(100, (turnTimeLeft / effectiveTimeout) * 100)}%` }}
            />
          </div>
        )}

        {/* Manual Time Card Button inside My Turn banner */}
        {isMyTurn && (
          <div className="flex items-center justify-between mt-2 pt-2 border-t border-slate-800/80">
            <div className="flex items-center gap-1.5 text-xs text-slate-300 font-bold">
              <span>⏱️ 时间卡:</span>
              <span className="text-amber-400 font-black">{selfSeat?.time_bank_cards ?? 3} 张</span>
              <span className="text-slate-500 text-[10px]">(每张+30s)</span>
            </div>
            {!isUsingTimeBank && (selfSeat?.time_bank_cards ?? 0) > 0 && onUseTimeCard ? (
              <button
                onClick={onUseTimeCard}
                className="px-2.5 py-1 bg-gradient-to-r from-purple-700 to-indigo-700 hover:from-purple-600 hover:to-indigo-600 text-purple-100 rounded-lg text-xs font-black border border-purple-400/50 shadow-md transition active:scale-95 cursor-pointer flex items-center gap-1"
                title="立即消耗1张时间卡，延长30秒思考时间"
              >
                <Clock className="w-3 h-3 text-purple-300 animate-spin" />
                <span>使用时间卡 (+30s)</span>
              </button>
            ) : isUsingTimeBank ? (
              <span className="text-[11px] font-black text-purple-300 animate-pulse">
                时间卡思考中 (+30s)
              </span>
            ) : (
              <span className="text-[10px] text-slate-500 font-medium">
                时间卡已耗尽
              </span>
            )}
          </div>
        )}

        {/* Hand End Notice */}
        {street === 'HAND_END' && (
          <div className="flex items-center justify-between mt-2 pt-2 border-t border-slate-800">
            <span className="text-xs text-slate-400 font-bold">
              {isHost ? '房主可随时开局' : '本局已结束，请准备'}
            </span>
            {isHost && onStartGame ? (
              <button
                onClick={onStartGame}
                className="px-3 py-1 bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-400 hover:to-amber-500 text-slate-950 rounded-lg text-xs font-black shadow-glow-gold transition active:scale-95 cursor-pointer flex items-center gap-1"
              >
                <Play className="w-3 h-3 fill-slate-950" />
                立即开局
              </button>
            ) : selfSeat && onToggleReady ? (
              <button
                onClick={onToggleReady}
                className={`px-3 py-1 rounded-lg text-xs font-black shadow transition active:scale-95 cursor-pointer flex items-center gap-1 ${
                  readyPlayerIds?.includes(selfSeat.player_id)
                    ? 'bg-slate-800 text-emerald-300 border border-emerald-500/50'
                    : 'bg-emerald-600 hover:bg-emerald-500 text-white'
                }`}
              >
                <CheckCircle2 className="w-3 h-3" />
                {readyPlayerIds?.includes(selfSeat.player_id) ? '已准备' : '确认准备'}
              </button>
            ) : null}
          </div>
        )}
      </div>

      {/* 2. Rebuy Alert Card (Only when player has 0 chips) */}
      {selfSeat && selfSeat.chips === 0 && (
        <div className="bg-gradient-to-r from-red-950/90 via-amber-950/90 to-red-950/90 border-2 border-amber-500/80 rounded-2xl p-3 flex items-center justify-between shadow-glow-gold">
          <div className="flex flex-col gap-0.5">
            <span className="text-xs font-black text-amber-300 flex items-center gap-1">
              <AlertCircle className="w-3.5 h-3.5 text-amber-400" />
              筹码已输尽 ($0)
            </span>
            <span className="text-[11px] text-slate-300 font-medium">
              补充买入后可继续参与游戏
            </span>
          </div>
          {onRebuy && (
            <button
              onClick={onRebuy}
              className="px-3.5 py-1.5 bg-gradient-to-r from-amber-400 to-amber-500 hover:from-amber-300 hover:to-amber-400 text-slate-950 text-xs font-black rounded-xl shadow-lg transition active:scale-95 cursor-pointer flex items-center gap-1"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              Re-buy (${buyinChips})
            </button>
          )}
        </div>
      )}

      {/* 3. My Hand & Chips Overview Card */}
      {selfSeat && (
        <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-3 flex items-center justify-between shadow-lg">
          <div className="flex flex-col gap-1">
            <div className="flex items-center gap-1.5">
              <span className="text-sm font-black text-slate-100">{selfSeat.name}</span>
              <span className="text-[10px] bg-slate-800 text-sky-300 px-1.5 py-0.5 rounded border border-sky-500/30 font-bold">
                本人
              </span>
            </div>
            <div className="flex items-baseline gap-1">
              <span className="text-xs text-slate-400 font-bold">筹码:</span>
              <span className={`text-base md:text-lg font-black ${selfSeat.chips === 0 ? 'text-red-400' : 'text-amber-400'}`}>
                ${selfSeat.chips}
              </span>
            </div>
            <div className="flex items-center gap-1.5 mt-0.5">
              <span className="text-[10px] text-slate-400 font-bold">时间卡:</span>
              <span className="text-[11px] text-amber-300 font-black bg-slate-950 px-2 py-0.2 rounded-full border border-amber-500/30 flex items-center gap-1">
                <span>⏱️ {selfSeat.time_bank_cards ?? 3} / 5</span>
              </span>
            </div>
          </div>

          {/* My Hole Cards Preview */}
          <div className="flex -space-x-3">
            {selfSeat.hole_cards && selfSeat.hole_cards.length === 2 ? (
              selfSeat.hole_cards.map((c, i) => (
                <CardView key={i} card={c} size="md" className="shadow-xl" />
              ))
            ) : (
              <div className="text-xs text-slate-500 font-medium italic">暂无手牌</div>
            )}
          </div>
        </div>
      )}

      {/* RIT Voting Controls in Sidebar */}
      {(street === 'RIT_DECISION' || ritStatus === 'VOTING') && (
        <div className="bg-gradient-to-br from-purple-950/90 via-slate-900 to-indigo-950/90 border-2 border-purple-400/70 rounded-2xl p-3.5 flex flex-col gap-2.5 shadow-glow-gold animate-fade-in">
          <div className="flex items-center gap-1.5 text-xs font-black text-purple-300">
            <Layers className="w-4 h-4 text-purple-400" />
            ALL-IN 发牌次数协商 (Run It Once / Twice)
          </div>
          <p className="text-[11px] text-slate-300 leading-tight">
            双方均同意发 2 次将平分底池并分别发两副牌；任意一人选择 1 次则只发 1 次。
          </p>

          {selfSeat && ritVoters?.includes(selfSeat.player_id) ? (
            <div className="grid grid-cols-2 gap-2 mt-1">
              <button
                onClick={() => onRitChoice && onRitChoice(1)}
                className={`py-2.5 px-2 rounded-xl font-black text-xs transition active:scale-95 cursor-pointer flex flex-col items-center justify-center border-2 ${
                  ritVotes?.[selfSeat.player_id] === 1
                    ? 'bg-amber-500 text-slate-950 border-amber-300 shadow-glow-gold'
                    : 'bg-slate-800/90 hover:bg-slate-700 text-amber-300 border-amber-500/50'
                }`}
              >
                <span className="font-black text-sm">发 1 次</span>
                <span className="text-[10px] opacity-80 font-medium">Run It Once</span>
              </button>

              <button
                onClick={() => onRitChoice && onRitChoice(2)}
                className={`py-2.5 px-2 rounded-xl font-black text-xs transition active:scale-95 cursor-pointer flex flex-col items-center justify-center border-2 ${
                  ritVotes?.[selfSeat.player_id] === 2
                    ? 'bg-purple-600 text-white border-purple-300 shadow-glow-cyan'
                    : 'bg-slate-800/90 hover:bg-slate-700 text-purple-300 border-purple-500/50'
                }`}
              >
                <span className="font-black text-sm">发 2 次</span>
                <span className="text-[10px] opacity-80 font-medium">Run It Twice</span>
              </button>
            </div>
          ) : (
            <div className="text-center py-2 text-xs text-slate-400 font-bold bg-slate-950/60 rounded-xl">
              正在等待对决玩家选择发牌次数...
            </div>
          )}
        </div>
      )}

      {/* 4. Main Action Buttons Grid */}
      <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-3 flex flex-col gap-2.5 shadow-xl">
        <div className="text-xs font-extrabold text-slate-400 uppercase tracking-wider flex items-center gap-1">
          <Zap className="w-3.5 h-3.5 text-amber-400" />
          决策操作台 (Action Controls)
        </div>

        <div className="grid grid-cols-2 gap-2">
          {/* Fold Button */}
          <button
            onClick={() => onAction('FOLD')}
            disabled={disabled || !isMyTurn || !legalActions?.can_fold}
            className="flex flex-col items-center justify-center py-3 px-2 bg-gradient-to-b from-red-800 to-red-950 hover:from-red-700 hover:to-red-900 disabled:opacity-35 disabled:cursor-not-allowed text-white font-extrabold rounded-xl border-2 border-red-500/40 shadow-lg active:scale-95 transition cursor-pointer"
          >
            <span className="text-base font-black tracking-wide">弃牌</span>
            <span className="text-[11px] text-red-300/80 font-medium">Fold [F]</span>
          </button>

          {/* Check or Call Button */}
          {legalActions?.can_check ? (
            <button
              onClick={() => onAction('CHECK')}
              disabled={disabled || !isMyTurn}
              className="flex flex-col items-center justify-center py-3 px-2 bg-gradient-to-b from-emerald-600 to-emerald-950 hover:from-emerald-500 hover:to-emerald-900 disabled:opacity-35 disabled:cursor-not-allowed text-white font-extrabold rounded-xl border-2 border-emerald-400/50 shadow-lg active:scale-95 transition cursor-pointer"
            >
              <span className="text-base font-black tracking-wide">过牌</span>
              <span className="text-[11px] text-emerald-300/80 font-medium">Check [Space]</span>
            </button>
          ) : (
            <button
              onClick={() => onAction('CALL', legalActions?.call_amount || 0)}
              disabled={disabled || !isMyTurn || !legalActions?.can_call}
              className="flex flex-col items-center justify-center py-3 px-2 bg-gradient-to-b from-emerald-600 to-emerald-950 hover:from-emerald-500 hover:to-emerald-900 disabled:opacity-35 disabled:cursor-not-allowed text-white font-extrabold rounded-xl border-2 border-emerald-400/50 shadow-lg active:scale-95 transition cursor-pointer"
            >
              <span className="text-base font-black tracking-wide">
                跟注 ${legalActions?.call_amount || 0}
              </span>
              <span className="text-[11px] text-emerald-300/80 font-medium">Call [Space]</span>
            </button>
          )}

          {/* Bet or Raise Button */}
          <button
            onClick={handleRaiseSubmit}
            disabled={disabled || !isMyTurn || (!legalActions?.can_bet && !legalActions?.can_raise)}
            className="flex flex-col items-center justify-center py-3 px-2 bg-gradient-to-b from-amber-500 to-amber-900 hover:from-amber-400 hover:to-amber-800 disabled:opacity-35 disabled:cursor-not-allowed text-white font-black rounded-xl border-2 border-amber-300/70 shadow-lg active:scale-95 transition cursor-pointer shadow-glow-gold"
          >
            <span className="text-base font-black tracking-wide text-amber-200">
              {legalActions?.can_bet ? `下注 $${currentAmount}` : `加注至 $${currentAmount}`}
            </span>
            <span className="text-[11px] text-amber-300/80 font-medium">
              {legalActions?.can_bet ? 'Bet [R]' : 'Raise [R]'}
            </span>
          </button>

          {/* All In Button */}
          <button
            onClick={() => onAction('ALL_IN', legalActions?.all_in_amount || 0)}
            disabled={disabled || !isMyTurn || !legalActions?.can_all_in}
            className="flex flex-col items-center justify-center py-3 px-2 bg-gradient-to-b from-purple-800 to-red-950 hover:from-purple-700 hover:to-red-900 disabled:opacity-35 disabled:cursor-not-allowed text-amber-300 font-black rounded-xl border-2 border-purple-400/50 shadow-lg active:scale-95 transition cursor-pointer"
          >
            <span className="text-base font-black tracking-wide flex items-center gap-1">
              <Flame className="w-4 h-4 text-amber-400 fill-amber-400" />
              全下 ${legalActions?.all_in_amount || 0}
            </span>
            <span className="text-[11px] text-purple-300/80 font-medium">All-In [A]</span>
          </button>
        </div>
      </div>

      {/* 4. Raise / Bet Sizing Console */}
      <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-3 flex flex-col gap-2.5 shadow-xl">
        <div className="flex items-center justify-between">
          <span className="text-xs font-extrabold text-slate-400 uppercase tracking-wider">
            加注额度调整 (Raise Sizing)
          </span>
          <div className="flex items-center gap-1 bg-slate-950 px-2.5 py-0.5 rounded-lg border border-amber-500/40">
            <span className="text-amber-400 font-black text-sm">$</span>
            <input
              type="number"
              min={minVal}
              max={maxVal}
              step={bigBlind}
              value={currentAmount}
              disabled={!isMyTurn || (!legalActions?.can_bet && !legalActions?.can_raise)}
              onChange={(e) => setRaiseAmount(Number(e.target.value))}
              className="w-16 bg-transparent text-right font-black text-amber-300 text-sm focus:outline-none"
            />
          </div>
        </div>

        {/* Preset Ratio Buttons (Row 1: Pot fractions) */}
        <div className="grid grid-cols-3 gap-1.5">
          <button
            onClick={() => setRaiseAmount(minVal)}
            disabled={!isMyTurn || (!legalActions?.can_bet && !legalActions?.can_raise)}
            className="px-2 py-1.5 bg-slate-800 hover:bg-slate-700 disabled:opacity-40 text-amber-300 rounded-lg text-xs font-bold border border-slate-700 transition active:scale-95 cursor-pointer"
          >
            Min (${minVal})
          </button>
          <button
            onClick={() => applyPresetRatio(1 / 3)}
            disabled={!isMyTurn || (!legalActions?.can_bet && !legalActions?.can_raise)}
            className="px-2 py-1.5 bg-slate-800 hover:bg-slate-700 disabled:opacity-40 text-slate-200 rounded-lg text-xs font-bold border border-slate-700 transition active:scale-95 cursor-pointer"
          >
            1/3 底池
          </button>
          <button
            onClick={() => applyPresetRatio(1 / 2)}
            disabled={!isMyTurn || (!legalActions?.can_bet && !legalActions?.can_raise)}
            className="px-2 py-1.5 bg-slate-800 hover:bg-slate-700 disabled:opacity-40 text-slate-200 rounded-lg text-xs font-bold border border-slate-700 transition active:scale-95 cursor-pointer"
          >
            1/2 底池
          </button>
        </div>

        {/* Preset Ratio Buttons (Row 2: Pot, 2/3, All-in) */}
        <div className="grid grid-cols-3 gap-1.5">
          <button
            onClick={() => applyPresetRatio(2 / 3)}
            disabled={!isMyTurn || (!legalActions?.can_bet && !legalActions?.can_raise)}
            className="px-2 py-1.5 bg-slate-800 hover:bg-slate-700 disabled:opacity-40 text-slate-200 rounded-lg text-xs font-bold border border-slate-700 transition active:scale-95 cursor-pointer"
          >
            2/3 底池
          </button>
          <button
            onClick={() => applyPresetRatio(1.0)}
            disabled={!isMyTurn || (!legalActions?.can_bet && !legalActions?.can_raise)}
            className="px-2 py-1.5 bg-slate-800 hover:bg-slate-700 disabled:opacity-40 text-slate-200 rounded-lg text-xs font-bold border border-slate-700 transition active:scale-95 cursor-pointer"
          >
            底池 (Pot)
          </button>
          <button
            onClick={() => setRaiseAmount(maxVal)}
            disabled={!isMyTurn || (!legalActions?.can_bet && !legalActions?.can_raise)}
            className="px-2 py-1.5 bg-gradient-to-r from-red-900 to-amber-900 hover:from-red-800 hover:to-amber-800 disabled:opacity-40 text-amber-300 rounded-lg text-xs font-black border border-amber-500/40 transition active:scale-95 cursor-pointer flex items-center justify-center gap-0.5"
          >
            <Flame className="w-3 h-3 text-red-400 fill-red-400" />
            Max (All-In)
          </button>
        </div>

        {/* BB Multipliers */}
        <div className="grid grid-cols-4 gap-1.5">
          <button
            onClick={() => applyBBMultiplier(2.5)}
            disabled={!isMyTurn || (!legalActions?.can_bet && !legalActions?.can_raise)}
            className="px-1.5 py-1 bg-slate-800 hover:bg-slate-700 disabled:opacity-40 text-slate-300 rounded-lg text-[11px] font-bold border border-slate-700 transition"
          >
            2.5 BB
          </button>
          <button
            onClick={() => applyBBMultiplier(3)}
            disabled={!isMyTurn || (!legalActions?.can_bet && !legalActions?.can_raise)}
            className="px-1.5 py-1 bg-slate-800 hover:bg-slate-700 disabled:opacity-40 text-slate-300 rounded-lg text-[11px] font-bold border border-slate-700 transition"
          >
            3 BB
          </button>
          <button
            onClick={() => applyBBMultiplier(4)}
            disabled={!isMyTurn || (!legalActions?.can_bet && !legalActions?.can_raise)}
            className="px-1.5 py-1 bg-slate-800 hover:bg-slate-700 disabled:opacity-40 text-slate-300 rounded-lg text-[11px] font-bold border border-slate-700 transition"
          >
            4 BB
          </button>
          <button
            onClick={() => applyBBMultiplier(5)}
            disabled={!isMyTurn || (!legalActions?.can_bet && !legalActions?.can_raise)}
            className="px-1.5 py-1 bg-slate-800 hover:bg-slate-700 disabled:opacity-40 text-slate-300 rounded-lg text-[11px] font-bold border border-slate-700 transition"
          >
            5 BB
          </button>
        </div>

        {/* Slider & Stepper Controls */}
        <div className="flex items-center gap-2 mt-1">
          <button
            onClick={() => adjustBB(-1)}
            disabled={!isMyTurn || (!legalActions?.can_bet && !legalActions?.can_raise)}
            className="px-2 py-1 bg-slate-800 hover:bg-slate-700 disabled:opacity-40 text-slate-200 rounded-lg border border-slate-700 text-xs font-bold active:scale-95 shadow"
            title="-1 BB"
          >
            -1BB
          </button>

          <input
            type="range"
            min={minVal}
            max={maxVal}
            step={bigBlind}
            value={currentAmount}
            disabled={!isMyTurn || (!legalActions?.can_bet && !legalActions?.can_raise)}
            onChange={(e) => setRaiseAmount(Number(e.target.value))}
            className="w-full h-2.5 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-amber-400 disabled:opacity-40"
          />

          <button
            onClick={() => adjustBB(1)}
            disabled={!isMyTurn || (!legalActions?.can_bet && !legalActions?.can_raise)}
            className="px-2 py-1 bg-slate-800 hover:bg-slate-700 disabled:opacity-40 text-slate-200 rounded-lg border border-slate-700 text-xs font-bold active:scale-95 shadow"
            title="+1 BB"
          >
            +1BB
          </button>
        </div>
      </div>

      {/* 5. Live Action History Feed (战局动态) */}
      <div className="flex-1 bg-slate-900/90 border border-slate-800 rounded-2xl p-3 flex flex-col gap-2 shadow-xl min-h-[140px] max-h-[220px] overflow-hidden">
        <div className="text-xs font-extrabold text-slate-400 uppercase tracking-wider flex items-center gap-1.5 flex-shrink-0">
          <History className="w-3.5 h-3.5 text-sky-400" />
          战局动态 (Live Hand Log)
        </div>

        <div className="flex-1 overflow-y-auto pr-1 flex flex-col gap-1.5 text-xs">
          {actionHistory && actionHistory.length > 0 ? (
            actionHistory.map((item, idx) => (
              <div
                key={idx}
                className="flex items-center justify-between py-1 px-2 rounded-lg bg-slate-950/60 border border-slate-800/80"
              >
                <div className="flex items-center gap-1.5 truncate">
                  <span className="font-bold text-slate-200 truncate max-w-[90px]">
                    {getPlayerName(item.player_id)}
                  </span>
                  <span className="text-[10px] text-slate-500 uppercase font-mono">
                    [{item.street}]
                  </span>
                </div>
                <span
                  className={`font-black whitespace-nowrap ${
                    item.action === 'FOLD'
                      ? 'text-red-400'
                      : item.action === 'CHECK'
                      ? 'text-slate-400'
                      : item.action === 'CALL'
                      ? 'text-emerald-400'
                      : item.action === 'ALL_IN'
                      ? 'text-purple-400'
                      : 'text-amber-400'
                  }`}
                >
                  {formatActionName(item.action, item.amount)}
                </span>
              </div>
            ))
          ) : (
            <div className="text-slate-500 text-xs text-center py-4 italic">暂无本局行动记录</div>
          )}
        </div>
      </div>
    </div>
  );
}


