import React, { useState, useEffect, useRef } from 'react';
import CardView from './CardView';
import { sortCardsLowToHigh } from '../utils/cards';
import {
  ChevronUp,
  ChevronDown,
  Flame,
  Clock,
  Zap,
  History,
  RefreshCw,
  AlertCircle,
} from 'lucide-react';

export default function ActionBar({
  legalActions,
  totalPot = 0,
  smallBlind = 10,
  buyinChips = 1000,
  onAction,
  disabled = false,
  selfSeat = null,
  onRebuy,
  currentTurnPlayer = null,
  isMyTurn = false,
  street = 'IDLE',
  actionHistory = [],
  actionTimeout = 15,
  currentTurnDuration = 15,
  isUsingTimeBank = false,
  onUseTimeCard,
  seats = [],
  turnCount = 0,
}) {
  const blindUnit = Math.max(1, Number(smallBlind) || 1);
  const bigBlind = blindUnit * 2;
  const minVal = legalActions?.can_bet ? legalActions.min_bet : (legalActions?.min_raise_to || 0);
  const maxVal = legalActions?.can_bet ? legalActions.max_bet : (legalActions?.max_raise_to || 0);
  const alignedMinVal = minVal > 0 ? Math.ceil(minVal / blindUnit) * blindUnit : 0;
  const alignedMaxVal = maxVal > 0 ? Math.floor(maxVal / blindUnit) * blindUnit : 0;
  const hasAlignedRange = alignedMinVal <= alignedMaxVal;
  const sizingMin = hasAlignedRange ? alignedMinVal : minVal;
  const sizingMax = hasAlignedRange ? alignedMaxVal : maxVal;

  const alignAmount = (value) => {
    const numericValue = Number(value);
    if (!Number.isFinite(numericValue)) return sizingMin || 0;
    if (!hasAlignedRange) {
      return Math.max(minVal, Math.min(maxVal, numericValue));
    }
    const snapped = Math.round(numericValue / blindUnit) * blindUnit;
    return Math.max(alignedMinVal, Math.min(alignedMaxVal, snapped));
  };

  const [raiseAmount, setRaiseAmount] = useState(minVal || 0);
  const effectiveTimeout = (isUsingTimeBank || (currentTurnPlayer && isUsingTimeBank))
    ? (currentTurnDuration || 30)
    : (currentTurnDuration || actionTimeout || 15);
  const [turnTimeLeft, setTurnTimeLeft] = useState(effectiveTimeout);

  // Sync raiseAmount whenever minVal or maxVal changes
  useEffect(() => {
    if (minVal > 0) {
      setRaiseAmount((prev) => {
        const next = !prev || prev < minVal || prev > maxVal ? minVal : prev;
        return alignAmount(next);
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

  const currentAmount = alignAmount(raiseAmount || minVal);
  const orderedHoleCards = sortCardsLowToHigh(selfSeat?.hole_cards || []);

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
  const calcPresetAmount = (ratio) => {
    const target = Math.round((totalPot * ratio) / blindUnit) * blindUnit;
    return alignAmount(target);
  };

  const applyPresetRatio = (ratio) => {
    const target = calcPresetAmount(ratio);
    setRaiseAmount(target);
  };

  const calcBBAmount = (mult) => {
    return alignAmount(Math.round(mult * bigBlind));
  };

  const applyBBMultiplier = (mult) => {
    const target = calcBBAmount(mult);
    setRaiseAmount(target);
  };

  const adjustBB = (multiplier) => {
    setRaiseAmount(alignAmount(currentAmount + multiplier * bigBlind));
  };

  const potPresets = [
    { label: '1/3 底池', ratio: 1 / 3 },
    { label: '1/2 底池', ratio: 1 / 2 },
    { label: '2/3 底池', ratio: 2 / 3 },
    { label: '底池', ratio: 1.0 },
    { label: '1.5底池', ratio: 1.5 },
    { label: '2底池', ratio: 2.0 },
    { label: '3底池', ratio: 3.0 },
    { label: '全下', isMax: true },
  ];

  const bbPresets = [
    { label: '2.5 BB', mult: 2.5 },
    { label: '3 BB', mult: 3 },
    { label: '4 BB', mult: 4 },
    { label: '5 BB', mult: 5 },
  ];

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
    <div className="poker-action-bar flex flex-col gap-2 lg:gap-3 w-full h-full text-slate-100 select-none">
      {/* 1. Turn Status & Countdown Banner */}
      <div
        className={`poker-action-turn-status ${isMyTurn ? 'poker-action-turn-status-self' : ''} p-2 lg:p-3 rounded-xl lg:rounded-2xl border transition-all duration-300 ${
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
          <div className="flex items-center gap-1.5 lg:gap-2">
            {isMyTurn ? (
              <span className="flex h-2.5 w-2.5 lg:h-3 lg:w-3 relative">
                <span className={`animate-ping absolute inline-flex h-full w-full rounded-full ${isUsingTimeBank ? 'bg-purple-400' : 'bg-amber-400'} opacity-75`}></span>
                <span className={`relative inline-flex rounded-full h-2.5 w-2.5 lg:h-3 lg:w-3 ${isUsingTimeBank ? 'bg-purple-500' : 'bg-amber-500'}`}></span>
              </span>
            ) : (
              <Clock className="w-3.5 h-3.5 lg:w-4 lg:h-4 text-slate-400" />
            )}
            <span className="text-xs lg:text-sm font-black tracking-wide">
              {isMyTurn && isUsingTimeBank
                ? '时间卡 +30 秒'
                : isMyTurn
                ? '轮到你'
                : currentTurnPlayer
                ? `等待 ${currentTurnPlayer.name}`
                : street === 'HAND_END'
                ? '本局结束'
                : '等待开局'}
            </span>
          </div>

          {currentTurnPlayer && (
            <div className={`flex items-center gap-1 px-2 py-0.5 rounded-full border text-[11px] lg:text-xs font-black transition-all ${
              turnTimeLeft <= 5
                ? 'bg-red-950/90 border-red-500 text-red-200 shadow-glow-red animate-bounce'
                : isUsingTimeBank
                ? 'bg-purple-950 border-purple-400/70 text-purple-200 shadow-glow-cyan'
                : 'bg-slate-950/80 border-amber-500/40 text-amber-300'
            }`}>
              <Clock className={`w-2.5 h-2.5 lg:w-3 lg:h-3 ${turnTimeLeft <= 5 ? 'text-red-400 animate-spin' : isUsingTimeBank ? 'text-purple-300 animate-spin' : 'text-amber-400 animate-spin'}`} />
              <span>{Math.ceil(turnTimeLeft)}s</span>
            </div>
          )}
        </div>

        {/* Real-time turn progress bar */}
        {currentTurnPlayer && (
          <div className="poker-action-turn-progress w-full h-2 bg-slate-950 rounded-full overflow-hidden border border-slate-800 mt-2">
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
          <div className="poker-action-time-card-row flex items-center justify-between mt-1.5 lg:mt-2 pt-1.5 lg:pt-2 border-t border-slate-800/80">
            <div className="flex items-center gap-1.5 text-[11px] lg:text-xs text-slate-300 font-bold">
              <span>时间卡:</span>
              <span className="text-amber-400 font-black">{selfSeat?.time_bank_cards ?? 3} 张</span>
            </div>
            {!isUsingTimeBank && (selfSeat?.time_bank_cards ?? 0) > 0 && onUseTimeCard ? (
              <button
                onClick={onUseTimeCard}
                className="px-2 py-0.5 lg:px-2.5 lg:py-1 bg-gradient-to-r from-purple-700 to-indigo-700 hover:from-purple-600 hover:to-indigo-600 text-purple-100 rounded-lg text-[11px] lg:text-xs font-black border border-purple-400/50 shadow-md transition active:scale-95 cursor-pointer flex items-center gap-1"
                title="使用 1 张时间卡"
              >
                <Clock className="w-2.5 h-2.5 lg:w-3 lg:h-3 text-purple-300 animate-spin" />
                <span>+30 秒</span>
              </button>
            ) : isUsingTimeBank ? (
              <span className="text-[10px] lg:text-[11px] font-black text-purple-300 animate-pulse">
                时间卡生效
              </span>
            ) : (
              null
            )}
          </div>
        )}

      </div>

      {/* 2. Rebuy Alert Card (Only when player has 0 chips) */}
      {selfSeat && selfSeat.chips === 0 && (
        <div className="poker-action-rebuy bg-gradient-to-r from-red-950/90 via-amber-950/90 to-red-950/90 border border-amber-500/80 lg:border-2 rounded-xl lg:rounded-2xl p-2 lg:p-3 flex items-center justify-between shadow-glow-gold">
          <div className="flex flex-col gap-0.5">
            <span className="text-[11px] lg:text-xs font-black text-amber-300 flex items-center gap-1">
              <AlertCircle className="w-3 h-3 lg:w-3.5 lg:h-3.5 text-amber-400" />
              筹码为 0
            </span>
          </div>
          {onRebuy && (
            <button
              onClick={onRebuy}
              className="px-2.5 py-1 lg:px-3.5 lg:py-1.5 bg-gradient-to-r from-amber-400 to-amber-500 hover:from-amber-300 hover:to-amber-400 text-slate-950 text-[11px] lg:text-xs font-black rounded-lg lg:rounded-xl shadow-lg transition active:scale-95 cursor-pointer flex items-center gap-1"
            >
              <RefreshCw className="w-3 h-3 lg:w-3.5 lg:h-3.5" />
              补码 (${buyinChips})
            </button>
          )}
        </div>
      )}

      {/* 3. My Hand & Chips Overview Card */}
      {selfSeat && (
        <div className="poker-action-self-overview bg-slate-900/90 border border-slate-800 rounded-xl lg:rounded-2xl p-2 lg:p-3 flex items-center justify-between shadow-lg">
          <div className="flex flex-col gap-1">
            <div className="flex items-center gap-1.5">
              <span className="text-xs lg:text-sm font-black text-slate-100">{selfSeat.name}</span>
            </div>
            <div className="flex items-baseline gap-1">
              <span className="text-[11px] lg:text-xs text-slate-400 font-bold">筹码:</span>
              <span className={`text-sm lg:text-lg font-black ${selfSeat.chips === 0 ? 'text-red-400' : 'text-amber-400'}`}>
                ${selfSeat.chips}
              </span>
            </div>
            <div className="flex items-center gap-1.5 mt-0.5">
              <span className="text-[9px] lg:text-[10px] text-slate-400 font-bold">时间卡:</span>
              <span className="text-[10px] lg:text-[11px] text-amber-300 font-black bg-slate-950 px-1.5 lg:px-2 py-0.2 rounded-full border border-amber-500/30 flex items-center gap-1">
                <span>{selfSeat.time_bank_cards ?? 3} / 5</span>
              </span>
            </div>
          </div>

          {/* My Hole Cards Preview */}
          <div className="flex -space-x-2 lg:-space-x-3">
            {orderedHoleCards.length === 2 ? (
              orderedHoleCards.map((c, i) => (
                <CardView key={i} card={c} size="md" className="shadow-xl" />
              ))
            ) : (
              <div className="text-xs text-slate-500 font-medium italic">暂无手牌</div>
            )}
          </div>
        </div>
      )}

      {/* 4. Main Action Buttons Grid */}
      <div className="poker-action-controls bg-slate-900/90 border border-slate-800 rounded-xl lg:rounded-2xl p-2 lg:p-3 flex flex-col gap-2 lg:gap-2.5 shadow-xl">
        <div className="text-[11px] lg:text-xs font-extrabold text-slate-400 uppercase tracking-wider flex items-center gap-1">
          <Zap className="w-3 h-3 lg:w-3.5 lg:h-3.5 text-amber-400" />
          操作
        </div>

        <div className="grid grid-cols-2 gap-1.5 lg:gap-2">
          {/* Fold Button */}
          <button
            onClick={() => onAction('FOLD')}
            disabled={disabled || !isMyTurn || !legalActions?.can_fold}
            className="poker-action-button flex flex-col items-center justify-center py-2 lg:py-3 px-1 lg:px-2 bg-gradient-to-b from-red-800 to-red-950 hover:from-red-700 hover:to-red-900 disabled:opacity-35 disabled:cursor-not-allowed text-white font-extrabold rounded-lg lg:rounded-xl border border-red-500/40 lg:border-2 shadow-lg active:scale-95 transition cursor-pointer"
          >
            <span className="text-sm lg:text-base font-black tracking-wide">弃牌</span>
            <span className="text-[10px] lg:text-[11px] text-red-300/80 font-medium">Fold [F]</span>
          </button>

          {/* Check or Call Button */}
          {legalActions?.can_check ? (
            <button
              onClick={() => onAction('CHECK')}
              disabled={disabled || !isMyTurn}
              className="poker-action-button flex flex-col items-center justify-center py-2 lg:py-3 px-1 lg:px-2 bg-gradient-to-b from-emerald-600 to-emerald-950 hover:from-emerald-500 hover:to-emerald-900 disabled:opacity-35 disabled:cursor-not-allowed text-white font-extrabold rounded-lg lg:rounded-xl border border-emerald-400/50 lg:border-2 shadow-lg active:scale-95 transition cursor-pointer"
            >
              <span className="text-sm lg:text-base font-black tracking-wide">过牌</span>
              <span className="text-[10px] lg:text-[11px] text-emerald-300/80 font-medium">Check [Space]</span>
            </button>
          ) : (
            <button
              onClick={() => onAction('CALL', legalActions?.call_amount || 0)}
              disabled={disabled || !isMyTurn || !legalActions?.can_call}
              className="poker-action-button flex flex-col items-center justify-center py-2 lg:py-3 px-1 lg:px-2 bg-gradient-to-b from-emerald-600 to-emerald-950 hover:from-emerald-500 hover:to-emerald-900 disabled:opacity-35 disabled:cursor-not-allowed text-white font-extrabold rounded-lg lg:rounded-xl border border-emerald-400/50 lg:border-2 shadow-lg active:scale-95 transition cursor-pointer"
            >
              <span className="text-sm lg:text-base font-black tracking-wide">
                跟注 ${legalActions?.call_amount || 0}
              </span>
              <span className="text-[10px] lg:text-[11px] text-emerald-300/80 font-medium">Call [Space]</span>
            </button>
          )}

          {/* Bet or Raise Button */}
          <button
            onClick={handleRaiseSubmit}
            disabled={disabled || !isMyTurn || (!legalActions?.can_bet && !legalActions?.can_raise)}
            className="poker-action-button flex flex-col items-center justify-center py-2 lg:py-3 px-1 lg:px-2 bg-gradient-to-b from-amber-500 to-amber-900 hover:from-amber-400 hover:to-amber-800 disabled:opacity-35 disabled:cursor-not-allowed text-white font-black rounded-lg lg:rounded-xl border border-amber-300/70 lg:border-2 shadow-lg active:scale-95 transition cursor-pointer shadow-glow-gold"
          >
            <span className="text-sm lg:text-base font-black tracking-wide text-amber-200">
              {legalActions?.can_bet ? `下注 $${currentAmount}` : `加注至 $${currentAmount}`}
            </span>
            <span className="text-[10px] lg:text-[11px] text-amber-300/80 font-medium">
              {legalActions?.can_bet ? 'Bet [R]' : 'Raise [R]'}
            </span>
          </button>

          {/* All In Button */}
          <button
            onClick={() => onAction('ALL_IN', legalActions?.all_in_amount || 0)}
            disabled={disabled || !isMyTurn || !legalActions?.can_all_in}
            className="poker-action-button flex flex-col items-center justify-center py-2 lg:py-3 px-1 lg:px-2 bg-gradient-to-b from-purple-800 to-red-950 hover:from-purple-700 hover:to-red-900 disabled:opacity-35 disabled:cursor-not-allowed text-amber-300 font-black rounded-lg lg:rounded-xl border border-purple-400/50 lg:border-2 shadow-lg active:scale-95 transition cursor-pointer"
          >
            <span className="text-sm lg:text-base font-black tracking-wide flex items-center gap-1">
              <Flame className="w-3 h-3 lg:w-4 lg:h-4 text-amber-400 fill-amber-400" />
              全下 ${legalActions?.all_in_amount || 0}
            </span>
            <span className="text-[10px] lg:text-[11px] text-purple-300/80 font-medium">All-In [A]</span>
          </button>
        </div>
      </div>

      {/* 4. Raise / Bet Sizing Console */}
      <div className="poker-action-sizing bg-slate-900/90 border border-slate-800 rounded-xl lg:rounded-2xl p-2 lg:p-3 flex flex-col gap-2 lg:gap-2.5 shadow-xl">
        <div className="flex items-center justify-between">
          <span className="text-[11px] lg:text-xs font-extrabold text-slate-400 uppercase tracking-wider">
            下注额
          </span>
          <div className="flex items-center gap-1 bg-slate-950 px-2 py-0.5 lg:px-2.5 rounded-lg border border-amber-500/40">
            <span className="text-amber-400 font-black text-xs lg:text-sm">$</span>
            <input
              type="number"
              min={sizingMin}
              max={sizingMax}
              step={blindUnit}
              value={currentAmount}
              disabled={!isMyTurn || (!legalActions?.can_bet && !legalActions?.can_raise)}
              onChange={(e) => setRaiseAmount(alignAmount(e.target.value))}
              className="w-14 lg:w-16 bg-transparent text-right font-black text-amber-300 text-xs lg:text-sm focus:outline-none"
            />
          </div>
        </div>

        {/* Preset Ratio Buttons (Pot fractions: 1/3, 1/2, 2/3, Pot, 1.5 Pot, 2 Pot, 3 Pot, All-in) */}
        <div className="grid grid-cols-4 gap-1 lg:gap-1.5">
          {potPresets.map((preset, idx) => {
            const amount = preset.isMax ? maxVal : calcPresetAmount(preset.ratio);
            const isSelected = isMyTurn && currentAmount === amount && (legalActions?.can_bet || legalActions?.can_raise);
            return (
              <button
                key={idx}
                onClick={() => (preset.isMax ? setRaiseAmount(maxVal) : applyPresetRatio(preset.ratio))}
                disabled={!isMyTurn || (!legalActions?.can_bet && !legalActions?.can_raise)}
                className={`flex flex-col items-center justify-center py-1 px-0.5 lg:py-1.5 lg:px-1 rounded-lg lg:rounded-xl transition active:scale-95 cursor-pointer border ${
                  isSelected
                    ? 'bg-amber-950/70 border-amber-400 shadow-[0_0_10px_rgba(251,191,36,0.25)]'
                    : preset.isMax
                    ? 'bg-gradient-to-b from-red-950/80 to-slate-900 border-red-500/40 hover:from-red-900/80 hover:to-slate-800'
                    : 'bg-slate-800/90 hover:bg-slate-700/90 border-slate-700/80'
                } disabled:opacity-40 disabled:cursor-not-allowed`}
              >
                <span
                    className={`text-[10px] lg:text-[11px] font-bold tracking-tight ${
                    preset.isMax ? 'text-red-300' : isSelected ? 'text-amber-200' : 'text-slate-300'
                  }`}
                >
                  {preset.label}
                </span>
                <span
                    className={`text-[11px] lg:text-xs font-black ${
                    preset.isMax ? 'text-amber-400' : isSelected ? 'text-amber-300' : 'text-amber-400/90'
                  }`}
                >
                  ${amount}
                </span>
              </button>
            );
          })}
        </div>

        {/* BB Multipliers */}
        <div className="grid grid-cols-4 gap-1 lg:gap-1.5">
          {bbPresets.map((preset, idx) => {
            const amount = calcBBAmount(preset.mult);
            const isSelected = isMyTurn && currentAmount === amount && (legalActions?.can_bet || legalActions?.can_raise);
            return (
              <button
                key={idx}
                onClick={() => applyBBMultiplier(preset.mult)}
                disabled={!isMyTurn || (!legalActions?.can_bet && !legalActions?.can_raise)}
                className={`flex flex-col items-center justify-center py-0.5 px-0.5 lg:py-1 lg:px-1 rounded-md lg:rounded-lg transition active:scale-95 cursor-pointer border ${
                  isSelected
                    ? 'bg-amber-950/60 border-amber-400/80 shadow-[0_0_8px_rgba(251,191,36,0.2)]'
                    : 'bg-slate-800/80 hover:bg-slate-700/80 border-slate-700/70'
                } disabled:opacity-40 disabled:cursor-not-allowed`}
              >
                <span className={`text-[9px] lg:text-[10px] font-bold ${isSelected ? 'text-amber-200' : 'text-slate-300'}`}>
                  {preset.label}
                </span>
                <span className={`text-[10px] lg:text-[11px] font-black ${isSelected ? 'text-amber-300' : 'text-slate-400'}`}>
                  ${amount}
                </span>
              </button>
            );
          })}
        </div>

        {/* Slider & Stepper Controls */}
        <div className="flex items-center gap-1.5 lg:gap-2 mt-1">
          <button
            onClick={() => adjustBB(-1)}
            disabled={!isMyTurn || (!legalActions?.can_bet && !legalActions?.can_raise)}
            className="px-1.5 py-0.5 lg:px-2 lg:py-1 bg-slate-800 hover:bg-slate-700 disabled:opacity-40 text-slate-200 rounded-md lg:rounded-lg border border-slate-700 text-[10px] lg:text-xs font-bold active:scale-95 shadow"
            title="-1 BB"
          >
            -1BB
          </button>

          <input
            type="range"
            min={sizingMin}
            max={sizingMax}
            step={blindUnit}
            value={currentAmount}
            disabled={!isMyTurn || (!legalActions?.can_bet && !legalActions?.can_raise)}
            onChange={(e) => setRaiseAmount(alignAmount(e.target.value))}
            className="w-full h-2 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-amber-400 disabled:opacity-40 lg:h-2.5"
          />

          <button
            onClick={() => adjustBB(1)}
            disabled={!isMyTurn || (!legalActions?.can_bet && !legalActions?.can_raise)}
            className="px-1.5 py-0.5 lg:px-2 lg:py-1 bg-slate-800 hover:bg-slate-700 disabled:opacity-40 text-slate-200 rounded-md lg:rounded-lg border border-slate-700 text-[10px] lg:text-xs font-bold active:scale-95 shadow"
            title="+1 BB"
          >
            +1BB
          </button>
        </div>
      </div>

        {/* 行动记录 */}
      {actionHistory && actionHistory.length > 0 && (
        <div className="poker-action-history flex-1 bg-slate-900/90 border border-slate-800 rounded-xl lg:rounded-2xl p-2 lg:p-3 flex flex-col gap-2 shadow-xl min-h-0 lg:min-h-[140px] max-h-[120px] lg:max-h-[220px] overflow-hidden">
          <div className="text-[11px] lg:text-xs font-extrabold text-slate-400 uppercase tracking-wider flex items-center gap-1.5 flex-shrink-0">
            <History className="w-3 h-3 lg:w-3.5 lg:h-3.5 text-sky-400" />
            行动记录
          </div>

          <div className="flex-1 overflow-y-auto pr-1 flex flex-col gap-1.5 text-xs">
            {actionHistory.map((item, idx) => (
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
                  className={`font-black whitespace-nowrap text-xs md:text-sm ${
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
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
