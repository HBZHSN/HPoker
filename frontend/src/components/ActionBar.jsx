import React, { useState, useEffect, useRef } from 'react';
import CardView from './CardView';
import { sortCardsLowToHigh } from '../utils/cards';
import {
  Flame,
  Clock,
  Zap,
  History,
  RefreshCw,
  AlertCircle,
  Eye,
  UserPlus,
  Minus,
  Plus,
} from 'lucide-react';
import {
  PRE_ACTIONS,
  isEligibleForPreAction,
  getEffectiveHighestBet,
  calculatePreActionBounds,
  shouldCancelPreAction,
  determineAutoAction,
} from '../utils/preActionRules';
import {
  BET_SLIDER_STEPS,
  amountToNonlinearProgress,
  nonlinearProgressToAmount,
} from '../utils/betSizing';

export default function ActionBar({
  legalActions,
  totalPot = 0,
  smallBlind = 10,
  buyinChips = 1000,
  onAction,
  disabled = false,
  selfSeat = null,
  onRebuy,
  canRebuy = false,
  onQuickSitDown,
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
  currentRoundHighestBet = 0,
  handNumber = 0,
}) {
  const blindUnit = Math.max(1, Number(smallBlind) || 1);
  const bigBlind = blindUnit * 2;
  const selfChips = Number(selfSeat?.chips) || 0;
  const selfRoundBet = Number(selfSeat?.current_round_bet) || 0;
  const effectiveHighestBet = getEffectiveHighestBet(currentRoundHighestBet, seats);
  const preCallCost = Math.max(0, effectiveHighestBet - selfRoundBet);
  const preCallDisplayAmt = Math.min(preCallCost, selfChips);

  const hasCards = Boolean(selfSeat?.has_cards || (selfSeat?.hole_cards && selfSeat.hole_cards.length > 0));
  const effectiveIsMyTurn = Boolean(isMyTurn && hasCards);

  const canPreAction = isEligibleForPreAction({
    disabled,
    isMyTurn: effectiveIsMyTurn,
    selfSeat,
    street,
  });

  const preActionBounds = calculatePreActionBounds({
    effectiveHighestBet,
    selfChips,
    selfRoundBet,
    bigBlind,
  });

  const minVal = effectiveIsMyTurn
    ? (legalActions?.can_bet ? legalActions.min_bet : (legalActions?.min_raise_to || 0))
    : (canPreAction ? preActionBounds.minVal : 0);

  const maxVal = effectiveIsMyTurn
    ? (legalActions?.can_bet ? legalActions.max_bet : (legalActions?.max_raise_to || 0))
    : (canPreAction ? preActionBounds.maxVal : 0);

  const alignedMinVal = minVal > 0 ? Math.ceil(minVal / blindUnit) * blindUnit : 0;
  const alignedMaxVal = maxVal > 0 ? Math.floor(maxVal / blindUnit) * blindUnit : 0;
  const hasAlignedRange = alignedMinVal <= alignedMaxVal;
  const sizingMin = hasAlignedRange ? alignedMinVal : minVal;
  const sizingMax = hasAlignedRange ? alignedMaxVal : maxVal;

  const alignAmount = (value) => {
    const numericValue = Number(value);
    if (!Number.isFinite(numericValue)) return sizingMin || 0;
    if (maxVal > 0 && numericValue >= maxVal) return maxVal;
    if (minVal > 0 && numericValue <= minVal) return minVal;
    if (!hasAlignedRange) {
      return Math.max(minVal, Math.min(maxVal, numericValue));
    }
    const snapped = Math.round(numericValue / blindUnit) * blindUnit;
    if (sizingMax > 0 && snapped >= sizingMax) return maxVal;
    return Math.max(alignedMinVal, Math.min(alignedMaxVal, snapped));
  };

  const [raiseAmount, setRaiseAmount] = useState(minVal || 0);
  const effectiveTimeout = (isUsingTimeBank || (currentTurnPlayer && isUsingTimeBank))
    ? (currentTurnDuration || 30)
    : (currentTurnDuration || actionTimeout || 15);
  const [turnTimeLeft, setTurnTimeLeft] = useState(effectiveTimeout);

  // Pre-action selection state
  const [preAction, setPreAction] = useState(null); // 'CHECK_FOLD' | 'CHECK_CALL' | 'RAISE' | null
  const [preActionData, setPreActionData] = useState(null); // { street, highestBet, targetAmount }

  const preActionRef = useRef(preAction);
  preActionRef.current = preAction;
  const preActionDataRef = useRef(preActionData);
  preActionDataRef.current = preActionData;
  const canPreActionRef = useRef(canPreAction);
  canPreActionRef.current = canPreAction;

  // Sync raiseAmount whenever minVal or maxVal changes
  useEffect(() => {
    if (minVal > 0) {
      setRaiseAmount((prev) => {
        const next = !prev || prev < minVal || prev > maxVal ? minVal : prev;
        return alignAmount(next);
      });
    }
  }, [minVal, maxVal, legalActions?.can_bet, legalActions?.can_raise, effectiveIsMyTurn, canPreAction]);

  // Reset pre-action when street changes
  const prevStreetRef = useRef(street);
  useEffect(() => {
    if (prevStreetRef.current !== street) {
      prevStreetRef.current = street;
      setPreAction(null);
      setPreActionData(null);
    }
  }, [street]);

  // Reset pre-action when hand changes
  const prevHandRef = useRef(handNumber);
  useEffect(() => {
    if (prevHandRef.current !== handNumber) {
      prevHandRef.current = handNumber;
      setPreAction(null);
      setPreActionData(null);
    }
  }, [handNumber]);

  // Reset pre-action if player folds, all-in, or leaves seat
  useEffect(() => {
    if (!selfSeat || selfSeat.is_folded || selfSeat.is_all_in || selfSeat.is_sitting_out) {
      setPreAction(null);
      setPreActionData(null);
    }
  }, [selfSeat?.is_folded, selfSeat?.is_all_in, selfSeat?.is_sitting_out, selfSeat?.player_id]);

  // Cancel pre-action if someone raises higher before my turn (CHECK_CALL & RAISE)
  useEffect(() => {
    if (!preAction || !preActionData || effectiveIsMyTurn) return;

    const shouldCancel = shouldCancelPreAction({
      preAction,
      preActionData,
      currentStreet: street,
      effectiveHighestBet,
    });

    if (shouldCancel) {
      setPreAction(null);
      setPreActionData(null);
    }
  }, [effectiveHighestBet, street, preAction, preActionData, effectiveIsMyTurn]);

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
  const sliderValue = amountToNonlinearProgress(currentAmount, sizingMin, sizingMax);
  const isAllIn = Boolean(
    ((effectiveIsMyTurn && (legalActions?.can_bet || legalActions?.can_raise)) || (canPreAction && maxVal > 0)) &&
    maxVal > 0 &&
    (currentAmount >= maxVal || (sizingMax > 0 && currentAmount >= sizingMax))
  );
  const orderedHoleCards = sortCardsLowToHigh(selfSeat?.hole_cards || []);

  const currentAmountRef = useRef(currentAmount);
  currentAmountRef.current = currentAmount;
  const legalActionsRef = useRef(legalActions);
  legalActionsRef.current = legalActions;

  // Toggle pre-action
  const togglePreAction = (actionType) => {
    if (!canPreAction) return;
    if (preAction === actionType) {
      setPreAction(null);
      setPreActionData(null);
    } else {
      setPreAction(actionType);
      setPreActionData({
        street,
        highestBet: effectiveHighestBet,
        targetAmount: currentAmountRef.current,
      });
    }
  };
  const togglePreActionRef = useRef(togglePreAction);
  togglePreActionRef.current = togglePreAction;

  // Update target amount when slider / presets change while RAISE pre-action is armed
  useEffect(() => {
    if (preAction === PRE_ACTIONS.RAISE) {
      setPreActionData((prev) => (prev ? { ...prev, targetAmount: currentAmount } : prev));
    }
  }, [currentAmount, preAction]);

  // Execute pre-action when it becomes my turn
  useEffect(() => {
    if (!effectiveIsMyTurn || !preActionRef.current || !legalActions) return;

    const actionToRun = preActionRef.current;
    const dataToRun = preActionDataRef.current;

    setPreAction(null);
    setPreActionData(null);

    const resolved = determineAutoAction({
      preAction: actionToRun,
      preActionData: dataToRun,
      legalActions,
      effectiveHighestBet,
      selfChips,
    });

    if (resolved) {
      const timer = setTimeout(() => {
        onAction(resolved.action, resolved.amount);
      }, 120);
      return () => clearTimeout(timer);
    }
  }, [effectiveIsMyTurn, legalActions]);

  // Keyboard shortcuts (PC)
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (disabled) return;
      if (['input', 'textarea'].includes(e.target.tagName.toLowerCase())) return;

      if (effectiveIsMyTurn && legalActionsRef.current) {
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
          if (currentAmountRef.current >= maxVal && legal.can_all_in) {
            onAction('ALL_IN', legal.all_in_amount || maxVal);
          } else {
            const act = legal.can_bet ? 'BET' : 'RAISE';
            onAction(act, currentAmountRef.current);
          }
        } else if (e.code === 'KeyA' && (legal.can_all_in || legal.can_bet || legal.can_raise)) {
          if (legal.can_all_in) {
            onAction('ALL_IN', legal.all_in_amount || maxVal);
          }
        }
      } else if (canPreActionRef.current) {
        if (e.code === 'KeyF') {
          e.preventDefault();
          togglePreActionRef.current(PRE_ACTIONS.CHECK_FOLD);
        } else if (e.code === 'Space') {
          e.preventDefault();
          togglePreActionRef.current(PRE_ACTIONS.CHECK_CALL);
        } else if (e.code === 'KeyR') {
          e.preventDefault();
          togglePreActionRef.current(PRE_ACTIONS.RAISE);
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [disabled, onAction, effectiveIsMyTurn, maxVal]);

  // Preset Bet Sizing helpers
  const calcPresetAmount = (ratio) => {
    const isRaise = effectiveIsMyTurn ? legalActions?.can_raise : (effectiveHighestBet > 0);
    if (isRaise) {
      const callCost = effectiveIsMyTurn ? (legalActions?.call_amount || 0) : preCallCost;
      const effectivePot = totalPot + callCost;
      const raiseAdd = Math.round((effectivePot * ratio) / blindUnit) * blindUnit;
      const target = (selfSeat?.current_bet || selfRoundBet || 0) + callCost + raiseAdd;
      return alignAmount(Math.max(minVal, target));
    }
    const target = Math.round((totalPot * ratio) / blindUnit) * blindUnit;
    return alignAmount(target);
  };

  const calcBBAmount = (mult) => {
    return Math.round((mult * bigBlind) / blindUnit) * blindUnit;
  };

  const adjustBB = (multiplier) => {
    const next = alignAmount(currentAmount + multiplier * bigBlind);
    setRaiseAmount(next);
    if (preAction === PRE_ACTIONS.RAISE) {
      setPreActionData((prev) => (prev ? { ...prev, targetAmount: next } : prev));
    }
  };

  const executeBetOrRaise = (targetAmount) => {
    if (disabled || !effectiveIsMyTurn || !legalActions) return;
    if (!legalActions.can_bet && !legalActions.can_raise && !legalActions.can_all_in) return;

    const amount = alignAmount(targetAmount);
    setRaiseAmount(amount);

    const isTargetAllIn = Boolean(
      maxVal > 0 &&
      (amount >= maxVal || (sizingMax > 0 && amount >= sizingMax))
    );

    if (isTargetAllIn && legalActions.can_all_in) {
      onAction('ALL_IN', legalActions.all_in_amount || maxVal);
      return;
    }

    const act = legalActions.can_bet ? 'BET' : 'RAISE';
    onAction(act, amount);
  };

  const executeAllIn = () => {
    if (disabled || !effectiveIsMyTurn || !legalActions) return;
    if (legalActions.can_all_in) {
      setRaiseAmount(maxVal);
      onAction('ALL_IN', legalActions.all_in_amount || maxVal);
    } else if (legalActions.can_bet || legalActions.can_raise) {
      executeBetOrRaise(maxVal);
    }
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

  const quickPresets = [
    { label: '1/3 底池', type: 'pot', ratio: 1 / 3 },
    { label: '1/2 底池', type: 'pot', ratio: 1 / 2 },
    { label: '2/3 底池', type: 'pot', ratio: 2 / 3 },
    { label: '底池', type: 'pot', ratio: 1.0 },
    { label: '1.5 底池', type: 'pot', ratio: 1.5 },
    { label: '2 底池', type: 'pot', ratio: 2.0 },
    { label: '3 BB', type: 'bb', mult: 3 },
    { label: '4 BB', type: 'bb', mult: 4 },
    { label: '5 BB', type: 'bb', mult: 5 },
    { label: '全下', type: 'allin', isMax: true },
  ];

  const handlePresetClick = (amount, isMax) => {
    if (effectiveIsMyTurn) {
      if (isMax) {
        executeAllIn();
      } else {
        executeBetOrRaise(amount);
      }
    } else if (canPreAction) {
      const target = isMax ? maxVal : amount;
      setRaiseAmount(target);
      if (preAction === PRE_ACTIONS.RAISE) {
        setPreActionData((prev) => (prev ? { ...prev, targetAmount: target } : prev));
      }
    }
  };

  const handleRaiseSubmit = () => {
    if (!legalActions) return;
    if (isAllIn && legalActions.can_all_in) {
      onAction('ALL_IN', legalActions.all_in_amount || maxVal);
      return;
    }
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
        return '弃牌';
      case 'CHECK':
        return '过牌';
      case 'CALL':
        return `跟注 $${amt}`;
      case 'BET':
        return `下注 $${amt}`;
      case 'RAISE':
        return `加注至 $${amt}`;
      case 'ALL_IN':
        return `全下 $${amt}`;
      case 'POST_SB':
        return `小盲 $${amt}`;
      case 'POST_BB':
        return `大盲 $${amt}`;
      default:
        return act;
    }
  };

  return (
    <div className="poker-action-bar flex flex-col gap-2 lg:gap-3 w-full h-full text-slate-100 select-none">
      {/* 1. Turn Status & Countdown Banner (Fixed Height on PC to eliminate Layout Shift) */}
      <div
        className={`poker-action-turn-status ${effectiveIsMyTurn ? 'poker-action-turn-status-self' : ''} p-2.5 lg:p-3 rounded-xl lg:rounded-2xl border transition-colors duration-200 flex flex-col justify-between flex-shrink-0 lg:h-[110px] ${
          effectiveIsMyTurn && isUsingTimeBank
            ? 'bg-gradient-to-r from-purple-950/90 via-slate-900 to-indigo-950 border-purple-400 shadow-glow-cyan'
            : effectiveIsMyTurn
            ? 'bg-gradient-to-r from-amber-950/80 to-slate-900 border-amber-400 shadow-glow-gold'
            : currentTurnPlayer
            ? 'bg-slate-900/90 border-slate-700/80'
            : 'bg-slate-900/60 border-slate-800'
        }`}
      >
        {/* Row 1: Status & Countdown Badge (fixed h-7) */}
        <div className="flex items-center justify-between h-7">
          <div className="flex items-center gap-1.5 lg:gap-2 min-w-0">
            {effectiveIsMyTurn ? (
              <span className="flex h-2.5 w-2.5 lg:h-3 lg:w-3 relative flex-shrink-0">
                <span className={`animate-ping absolute inline-flex h-full w-full rounded-full ${isUsingTimeBank ? 'bg-purple-400' : 'bg-amber-400'} opacity-75`}></span>
                <span className={`relative inline-flex rounded-full h-2.5 w-2.5 lg:h-3 lg:w-3 ${isUsingTimeBank ? 'bg-purple-500' : 'bg-amber-500'}`}></span>
              </span>
            ) : (
              <Clock className="w-3.5 h-3.5 lg:w-4 lg:h-4 text-slate-400 flex-shrink-0" />
            )}
            <span className="text-xs lg:text-sm font-black tracking-wide truncate">
              {effectiveIsMyTurn && isUsingTimeBank
                ? '时间卡生效中'
                : effectiveIsMyTurn
                ? '轮到你行动'
                : selfSeat && !hasCards && !['IDLE', 'HAND_END'].includes(street)
                ? (currentTurnPlayer ? `等下局 · 等待 ${currentTurnPlayer.name}` : '等待下一局')
                : currentTurnPlayer
                ? `等待 ${currentTurnPlayer.name}`
                : street === 'HAND_END'
                ? '本局结束'
                : '等待开局'}
            </span>
          </div>

          <div className={`flex items-center justify-center gap-1 px-2.5 py-0.5 rounded-full border text-[11px] lg:text-xs font-black min-w-[58px] h-6 flex-shrink-0 transition-all ${
            currentTurnPlayer
              ? turnTimeLeft <= 5
                ? 'bg-red-950/90 border-red-500 text-red-200 shadow-glow-red animate-bounce'
                : isUsingTimeBank
                ? 'bg-purple-950 border-purple-400/70 text-purple-200 shadow-glow-cyan'
                : 'bg-slate-950/80 border-amber-500/40 text-amber-300'
              : 'bg-slate-950/40 border-slate-800/80 text-slate-500'
          }`}>
            <Clock className={`w-3 h-3 ${
              currentTurnPlayer
                ? turnTimeLeft <= 5
                  ? 'text-red-400 animate-spin'
                  : isUsingTimeBank
                  ? 'text-purple-300 animate-spin'
                  : 'text-amber-400 animate-spin'
                : 'text-slate-600'
            }`} />
            <span>{currentTurnPlayer ? `${Math.ceil(turnTimeLeft)}s` : '—'}</span>
          </div>
        </div>

        {/* Row 2: Real-time turn progress bar (always fixed height) */}
        <div className="poker-action-turn-progress w-full h-2 bg-slate-950 rounded-full overflow-hidden border border-slate-800 mt-2 flex-shrink-0">
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
            style={{ width: currentTurnPlayer ? `${Math.min(100, (turnTimeLeft / effectiveTimeout) * 100)}%` : '0%' }}
          />
        </div>

        {/* Row 3: Time Card Row (always fixed height on PC to prevent shift) */}
        <div className="poker-action-time-card-row flex items-center justify-between mt-2 pt-2 border-t border-slate-800/80 h-7 flex-shrink-0">
          <div className="flex items-center gap-1.5 text-[11px] lg:text-xs text-slate-300 font-bold">
            <span>时间卡:</span>
            <span className="text-amber-400 font-black">{selfSeat?.time_bank_cards ?? 3} 张</span>
          </div>
          {effectiveIsMyTurn && !isUsingTimeBank && (selfSeat?.time_bank_cards ?? 0) > 0 && onUseTimeCard ? (
            <button
              type="button"
              onClick={onUseTimeCard}
              className="px-2.5 py-1 bg-gradient-to-r from-purple-700 to-indigo-700 hover:from-purple-600 hover:to-indigo-600 text-purple-100 rounded-lg text-[11px] lg:text-xs font-black border border-purple-400/50 shadow-md transition active:scale-95 cursor-pointer flex items-center gap-1 h-6"
            >
              <Clock className="w-2.5 h-2.5 lg:w-3 lg:h-3 text-purple-300 animate-spin" />
              <span>+30 秒</span>
            </button>
          ) : effectiveIsMyTurn && isUsingTimeBank ? (
            <span className="px-2.5 py-1 bg-purple-950/80 border border-purple-500/40 rounded-lg text-[10px] lg:text-[11px] font-black text-purple-300 animate-pulse flex items-center gap-1 h-6">
              <Clock className="w-2.5 h-2.5 lg:w-3 lg:h-3 text-purple-400 animate-spin" />
              <span>+30 秒</span>
            </span>
          ) : (
            <span className="px-2.5 py-1 bg-slate-950/40 border border-slate-800/60 rounded-lg text-[10px] lg:text-[11px] font-semibold text-slate-500 flex items-center gap-1 h-6 select-none">
              <Clock className="w-2.5 h-2.5 lg:w-3 lg:h-3 text-slate-600" />
              <span>+30 秒</span>
            </span>
          )}
        </div>
      </div>

      {!selfSeat ? (
        <div className="poker-action-spectator-panel bg-slate-900/90 border border-indigo-500/40 rounded-xl lg:rounded-2xl p-3 flex flex-col gap-3 shadow-xl">
          <div className="flex items-center gap-2 text-indigo-300">
            <Eye className="w-4 h-4 text-indigo-400" />
            <span className="text-xs lg:text-sm font-black tracking-wide">观战模式</span>
          </div>

          <p className="text-[11px] lg:text-xs text-slate-400 leading-relaxed">
            您当前正在实时观战。手牌对观战者绝对保密，只展示公共牌与公开亮牌。可随时在左下角与全桌正常聊天与发表情。
          </p>

          <div className="p-2.5 rounded-xl bg-slate-950/80 border border-slate-800 flex flex-col gap-1.5 text-xs">
            <div className="flex items-center justify-between text-slate-300">
              <span className="text-[11px] text-slate-500">在座人数</span>
              <span className="font-bold text-amber-300">
                {seats.filter(Boolean).length} / {seats.length} 人
              </span>
            </div>
            <div className="flex items-center justify-between text-slate-300">
              <span className="text-[11px] text-slate-500">当前底池</span>
              <span className="font-black text-amber-400">${totalPot}</span>
            </div>
            {currentRoundHighestBet > 0 && (
              <div className="flex items-center justify-between text-slate-300">
                <span className="text-[11px] text-slate-500">本轮最高注</span>
                <span className="font-bold text-sky-400">${currentRoundHighestBet}</span>
              </div>
            )}
          </div>

          {seats.some((s) => !s) ? (
            <div className="flex flex-col gap-1.5 mt-1">
              <span className="text-[11px] text-emerald-400 font-bold flex items-center gap-1">
                ✓ 牌桌尚有空座，可入座对局
              </span>
              {onQuickSitDown && (
                <button
                  type="button"
                  onClick={onQuickSitDown}
                  className="w-full py-2.5 px-3 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white font-black text-xs lg:text-sm rounded-xl shadow-glow-cyan transition active:scale-95 cursor-pointer flex items-center justify-center gap-1.5"
                >
                  <UserPlus className="w-4 h-4" />
                  入座参与对局
                </button>
              )}
            </div>
          ) : (
            <div className="p-2.5 rounded-xl bg-slate-950/60 border border-slate-800/80 text-center text-[11px] font-bold text-slate-400">
              牌桌当前已满员，尽享精彩对局
            </div>
          )}
        </div>
      ) : (
        <>
          {/* 2. Rebuy Alert Card (Only when player has 0 chips) */}
          {canRebuy && (
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
        <div className="poker-action-self-overview bg-slate-900/90 border border-slate-800 rounded-xl lg:rounded-2xl p-2 lg:p-3 flex items-center justify-between shadow-lg lg:h-[94px] flex-shrink-0">
          <div className="flex flex-col gap-1 min-w-0">
            <div className="flex items-center gap-1.5">
              <span className="text-xs lg:text-sm font-black text-slate-100 truncate">{selfSeat.name}</span>
              {selfSeat.rebuy_count > 1 && (
                <span className="text-[10px] bg-amber-950/80 text-amber-300 border border-amber-500/40 px-1.5 py-0.2 rounded-full font-bold flex-shrink-0">
                  买入 x{selfSeat.rebuy_count}
                </span>
              )}
            </div>
            <div className="flex items-baseline gap-1">
              <span className="text-[11px] lg:text-xs text-slate-400 font-bold">筹码</span>
              <span className={`text-sm lg:text-lg font-black ${selfSeat.chips === 0 ? 'text-red-400' : 'text-amber-400'}`}>
                ${selfSeat.chips}
              </span>
            </div>
            <div className="flex items-center gap-1.5 mt-0.5">
              <span className="text-[9px] lg:text-[10px] text-slate-400 font-bold">时间卡:</span>
              <span className="text-[10px] lg:text-[11px] text-amber-300 font-black bg-slate-950 px-1.5 lg:px-2 py-0.2 rounded-full border border-amber-500/30 flex items-center gap-1">
                <span>{selfSeat.time_bank_cards ?? 3} / 5</span>
                <span className="text-[9px] text-slate-400 font-normal">({(selfSeat.hands_played ?? 0) % 15}/15手)</span>
              </span>
            </div>
          </div>

          {/* My Hole Cards Preview */}
          <div className="flex items-center justify-end -space-x-2 lg:-space-x-3 h-[58px] lg:h-[68px] min-w-[70px] lg:min-w-[84px] flex-shrink-0">
            {orderedHoleCards.length === 2 ? (
              orderedHoleCards.map((c, i) => (
                <CardView key={i} card={c} size="sm" className="shadow-xl" />
              ))
            ) : (
              <div className="h-[52px] lg:h-[68px] w-[70px] lg:w-[84px] border border-dashed border-slate-700/80 rounded-lg flex items-center justify-center text-[11px] text-slate-500 font-bold bg-slate-950/40">
                暂无手牌
              </div>
            )}
          </div>
        </div>
      )}

      {/* 4. Mobile Action Console (lg:hidden): Action Buttons, Sizing Slider, and 10 Quick Presets */}
      <div className="poker-action-controls poker-action-controls-mobile lg:hidden bg-slate-900/90 border border-slate-800 rounded-xl p-2 sm:p-2.5 flex flex-col gap-2 shadow-xl">
        {/* Pre-action indicator / clear button */}
        {canPreAction && preAction && (
          <div className="flex items-center justify-between pb-1 border-b border-slate-800/80">
            <span className="text-[11px] text-amber-300 font-bold flex items-center gap-1">
              <Zap className="w-3 h-3 text-amber-400" />
              预选：{
                preAction === PRE_ACTIONS.CHECK_FOLD
                  ? '过牌/弃牌'
                  : preAction === PRE_ACTIONS.CHECK_CALL
                  ? `过牌/跟注${preCallCost > 0 ? ` $${preCallDisplayAmt}` : ''}`
                  : `加注至 $${currentAmount}`
              }
            </span>
            <button
              type="button"
              onClick={() => {
                setPreAction(null);
                setPreActionData(null);
              }}
              className="text-[10px] text-amber-400 hover:text-amber-300 font-bold cursor-pointer transition"
            >
              取消 ✕
            </button>
          </div>
        )}

        {selfSeat && !hasCards && !['IDLE', 'HAND_END'].includes(street) && (
          <div className="flex items-center justify-center gap-1.5 py-1 px-2 bg-slate-950/85 border border-amber-500/30 rounded-lg text-xs text-amber-300 font-bold">
            <Clock className="w-3.5 h-3.5 text-amber-400" />
            <span>本局未参与，等待下一局开始</span>
          </div>
        )}

        {/* Primary Action Buttons (1 row, 3 columns) */}
        <div className="poker-primary-actions grid grid-cols-3 gap-1.5 sm:gap-2">
          {/* Fold / Check-Fold Button */}
          {effectiveIsMyTurn ? (
            <button
              type="button"
              onClick={() => onAction('FOLD')}
              disabled={disabled || !legalActions?.can_fold}
              className="poker-action-button flex flex-col items-center justify-center py-2 sm:py-2.5 px-1 bg-gradient-to-b from-red-700 to-red-950 hover:from-red-600 hover:to-red-900 disabled:opacity-35 disabled:cursor-not-allowed text-white font-extrabold rounded-xl border border-red-500/50 shadow-lg active:scale-95 transition cursor-pointer"
            >
              <span className="text-sm sm:text-base font-black tracking-wide">弃牌</span>
              <span className="text-[10px] sm:text-[11px] text-red-300/80 font-medium">[F]</span>
            </button>
          ) : canPreAction ? (
            <button
              type="button"
              onClick={() => togglePreAction(PRE_ACTIONS.CHECK_FOLD)}
              disabled={disabled}
              className={`poker-action-button flex flex-col items-center justify-center py-2 sm:py-2.5 px-1 font-extrabold rounded-xl border transition active:scale-95 cursor-pointer shadow-lg ${
                preAction === PRE_ACTIONS.CHECK_FOLD
                  ? 'bg-gradient-to-b from-red-700 via-amber-950 to-red-950 border-amber-400 ring-2 ring-amber-400/80 text-amber-200 shadow-glow-gold'
                  : 'bg-gradient-to-b from-slate-800 to-slate-900 hover:from-slate-700 hover:to-slate-800 border-slate-700/80 text-slate-300 hover:text-white'
              }`}
            >
              <div className="flex items-center gap-1">
                <span className={`w-3 h-3 rounded-full flex items-center justify-center text-[9px] font-black ${
                  preAction === PRE_ACTIONS.CHECK_FOLD ? 'bg-amber-400 text-slate-950' : 'border border-slate-500 text-transparent'
                }`}>
                  ✓
                </span>
                <span className="text-xs sm:text-sm font-black tracking-wide">过牌/弃牌</span>
              </div>
              <span className={`text-[10px] font-medium ${
                preAction === PRE_ACTIONS.CHECK_FOLD ? 'text-amber-300' : 'text-slate-400'
              }`}>
                [F]
              </span>
            </button>
          ) : (
            <button
              type="button"
              disabled={true}
              className="poker-action-button flex flex-col items-center justify-center py-2 sm:py-2.5 px-1 bg-gradient-to-b from-red-800 to-red-950 opacity-35 cursor-not-allowed text-white font-extrabold rounded-xl border border-red-500/40 shadow-lg"
            >
              <span className="text-sm sm:text-base font-black tracking-wide">弃牌</span>
              <span className="text-[10px] sm:text-[11px] text-red-300/80 font-medium">[F]</span>
            </button>
          )}

          {/* Check / Call / Check-Call Button */}
          {effectiveIsMyTurn ? (
            legalActions?.can_check ? (
              <button
                type="button"
                onClick={() => onAction('CHECK')}
                disabled={disabled}
                className="poker-action-button flex flex-col items-center justify-center py-2 sm:py-2.5 px-1 bg-gradient-to-b from-emerald-600 to-emerald-950 hover:from-emerald-500 hover:to-emerald-900 disabled:opacity-35 disabled:cursor-not-allowed text-white font-extrabold rounded-xl border border-emerald-400/50 shadow-lg active:scale-95 transition cursor-pointer"
              >
                <span className="text-sm sm:text-base font-black tracking-wide">过牌</span>
                <span className="text-[10px] sm:text-[11px] text-emerald-300/80 font-medium">[Space]</span>
              </button>
            ) : (
              <button
                type="button"
                onClick={() => onAction('CALL', legalActions?.call_amount || 0)}
                disabled={disabled || !legalActions?.can_call}
                className="poker-action-button flex flex-col items-center justify-center py-2 sm:py-2.5 px-1 bg-gradient-to-b from-emerald-600 to-emerald-950 hover:from-emerald-500 hover:to-emerald-900 disabled:opacity-35 disabled:cursor-not-allowed text-white font-extrabold rounded-xl border border-emerald-400/50 shadow-lg active:scale-95 transition cursor-pointer"
              >
                <span className="text-sm sm:text-base font-black tracking-wide truncate max-w-full">
                  跟注 ${legalActions?.call_amount || 0}
                </span>
                <span className="text-[10px] sm:text-[11px] text-emerald-300/80 font-medium">[Space]</span>
              </button>
            )
          ) : canPreAction ? (
            <button
              type="button"
              onClick={() => togglePreAction(PRE_ACTIONS.CHECK_CALL)}
              disabled={disabled}
              className={`poker-action-button flex flex-col items-center justify-center py-2 sm:py-2.5 px-1 font-extrabold rounded-xl border transition active:scale-95 cursor-pointer shadow-lg ${
                preAction === PRE_ACTIONS.CHECK_CALL
                  ? 'bg-gradient-to-b from-emerald-600 to-emerald-950 border-emerald-400 ring-2 ring-emerald-400/80 text-white shadow-[0_0_15px_rgba(52,211,153,0.5)]'
                  : 'bg-gradient-to-b from-slate-800 to-slate-900 hover:from-slate-700 hover:to-slate-800 border-slate-700/80 text-slate-300 hover:text-white'
              }`}
            >
              <div className="flex items-center gap-1 truncate max-w-full">
                <span className={`w-3 h-3 rounded-full flex items-center justify-center text-[9px] font-black ${
                  preAction === PRE_ACTIONS.CHECK_CALL ? 'bg-emerald-400 text-slate-950' : 'border border-slate-500 text-transparent'
                }`}>
                  ✓
                </span>
                <span className="text-xs sm:text-sm font-black tracking-wide truncate">
                  过/跟{preCallCost > 0 ? ` $${preCallDisplayAmt}` : ''}
                </span>
              </div>
              <span className={`text-[10px] font-medium ${
                preAction === PRE_ACTIONS.CHECK_CALL ? 'text-emerald-200' : 'text-slate-400'
              }`}>
                [Space]
              </span>
            </button>
          ) : (
            <button
              type="button"
              disabled={true}
              className="poker-action-button flex flex-col items-center justify-center py-2 sm:py-2.5 px-1 bg-gradient-to-b from-emerald-600 to-emerald-950 opacity-35 cursor-not-allowed text-white font-extrabold rounded-xl border border-emerald-400/50 shadow-lg"
            >
              <span className="text-sm sm:text-base font-black tracking-wide">过牌</span>
              <span className="text-[10px] sm:text-[11px] text-emerald-300/80 font-medium">[Space]</span>
            </button>
          )}

          {/* Raise / Bet / Pre-Raise / All-In Button */}
          {effectiveIsMyTurn ? (
            <button
              type="button"
              onClick={handleRaiseSubmit}
              disabled={disabled || (!legalActions?.can_bet && !legalActions?.can_raise && !(isAllIn && legalActions?.can_all_in))}
              className={`poker-action-button flex flex-col items-center justify-center py-2 sm:py-2.5 px-1 font-black rounded-xl border transition active:scale-95 cursor-pointer disabled:opacity-35 disabled:cursor-not-allowed shadow-lg ${
                isAllIn
                  ? 'bg-gradient-to-b from-purple-800 via-red-950 to-amber-950 hover:from-purple-700 hover:to-red-900 border-purple-400/80 shadow-[0_0_15px_rgba(168,85,247,0.4)] text-amber-300'
                  : 'bg-gradient-to-b from-amber-500 to-amber-900 hover:from-amber-400 hover:to-amber-800 border-amber-300/70 shadow-glow-gold text-white'
              }`}
            >
              {isAllIn ? (
                <>
                  <span className="text-sm sm:text-base font-black tracking-wide text-amber-200 whitespace-nowrap flex items-center gap-1 truncate max-w-full">
                    <Flame className="w-3.5 h-3.5 text-amber-400 fill-amber-400" />
                    全下 ${legalActions?.all_in_amount || currentAmount}
                  </span>
                  <span className="text-[10px] text-purple-300/90 font-medium">[R]</span>
                </>
              ) : (
                <>
                  <span className="text-sm sm:text-base font-black tracking-wide text-amber-200 whitespace-nowrap truncate max-w-full">
                    {legalActions?.can_bet ? `下注 $${currentAmount}` : `加注至 $${currentAmount}`}
                  </span>
                  <span className="text-[10px] text-amber-300/80 font-medium">[R]</span>
                </>
              )}
            </button>
          ) : canPreAction ? (
            <button
              type="button"
              onClick={() => togglePreAction(PRE_ACTIONS.RAISE)}
              disabled={disabled || maxVal <= 0}
              className={`poker-action-button flex flex-col items-center justify-center py-2 sm:py-2.5 px-1 font-black rounded-xl border transition active:scale-95 cursor-pointer disabled:opacity-35 disabled:cursor-not-allowed shadow-lg ${
                preAction === PRE_ACTIONS.RAISE
                  ? isAllIn
                    ? 'bg-gradient-to-b from-purple-800 via-red-950 to-amber-950 border-purple-400 ring-2 ring-purple-400/80 shadow-[0_0_15px_rgba(168,85,247,0.5)] text-amber-200'
                    : 'bg-gradient-to-b from-amber-600 to-amber-950 border-amber-300 ring-2 ring-amber-400/80 shadow-glow-gold text-white'
                  : 'bg-gradient-to-b from-slate-850 to-slate-950 hover:from-slate-800 hover:to-slate-900 border-slate-700/80 text-slate-300 hover:text-white'
              }`}
            >
              <div className="flex items-center gap-1 truncate max-w-full">
                <span className={`w-3 h-3 rounded-full flex items-center justify-center text-[9px] font-black ${
                  preAction === PRE_ACTIONS.RAISE ? 'bg-amber-400 text-slate-950' : 'border border-slate-500 text-transparent'
                }`}>
                  ✓
                </span>
                <span className="text-xs sm:text-sm font-black tracking-wide whitespace-nowrap truncate">
                  {isAllIn
                    ? `全下 $${maxVal}`
                    : (effectiveHighestBet === 0 ? `下注 $${currentAmount}` : `加注至 $${currentAmount}`)}
                </span>
              </div>
              <span className={`text-[10px] font-medium ${
                preAction === PRE_ACTIONS.RAISE ? 'text-amber-300' : 'text-slate-400'
              }`}>
                [R]
              </span>
            </button>
          ) : (
            <button
              type="button"
              disabled={true}
              className="poker-action-button flex flex-col items-center justify-center py-2 sm:py-2.5 px-1 font-black rounded-xl border shadow-lg opacity-35 cursor-not-allowed bg-gradient-to-b from-amber-500 to-amber-900 text-white"
            >
              <span className="text-sm sm:text-base font-black tracking-wide">加注</span>
              <span className="text-[10px] text-amber-300/80 font-medium">[R]</span>
            </button>
          )}
        </div>

        {/* Sizing Slider Row: [-] [===Slider===] [+] [$Amount Card] */}
        <div className="poker-sizing-row flex items-center gap-1.5 sm:gap-2 bg-slate-950/80 border border-slate-800/80 rounded-xl px-2 py-1.5 shadow-inner">
          <button
            type="button"
            onClick={() => adjustBB(-1)}
            disabled={(!effectiveIsMyTurn && !canPreAction) || (effectiveIsMyTurn && !legalActions?.can_bet && !legalActions?.can_raise) || maxVal <= 0}
            className="flex items-center justify-center w-8 h-8 rounded-lg bg-slate-800 hover:bg-slate-700 active:scale-95 disabled:opacity-30 disabled:cursor-not-allowed border border-slate-700 text-slate-200 font-bold transition flex-shrink-0 cursor-pointer shadow"
            aria-label="减少1个大盲"
          >
            <Minus className="w-4 h-4" />
          </button>

          <div className="flex-1 flex flex-col justify-center min-w-0 px-1">
            <input
              type="range"
              min={0}
              max={BET_SLIDER_STEPS}
              step={1}
              value={sliderValue}
              disabled={disabled || (!effectiveIsMyTurn && !canPreAction) || (effectiveIsMyTurn && !legalActions?.can_bet && !legalActions?.can_raise) || maxVal <= 0}
              onChange={(e) => {
                const progress = Number(e.target.value);
                const rawAmount = nonlinearProgressToAmount(progress, sizingMin, sizingMax);
                const next = progress >= BET_SLIDER_STEPS ? maxVal : alignAmount(rawAmount);
                setRaiseAmount(next);
                if (preAction === PRE_ACTIONS.RAISE) {
                  setPreActionData((prev) => (prev ? { ...prev, targetAmount: next } : prev));
                }
              }}
              className={`poker-horizontal-raise-slider w-full h-2 rounded-lg appearance-none cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed bg-slate-800 ${
                isAllIn ? 'accent-purple-400' : 'accent-amber-400'
              }`}
              aria-label="下注滑块"
            />
          </div>

          <button
            type="button"
            onClick={() => adjustBB(1)}
            disabled={(!effectiveIsMyTurn && !canPreAction) || (effectiveIsMyTurn && !legalActions?.can_bet && !legalActions?.can_raise) || maxVal <= 0}
            className="flex items-center justify-center w-8 h-8 rounded-lg bg-slate-800 hover:bg-slate-700 active:scale-95 disabled:opacity-30 disabled:cursor-not-allowed border border-slate-700 text-slate-200 font-bold transition flex-shrink-0 cursor-pointer shadow"
            aria-label="增加1个大盲"
          >
            <Plus className="w-4 h-4" />
          </button>

          {/* Amount Badge: display only current bet amount */}
          <div className="flex items-center justify-center bg-slate-900/95 px-2.5 py-1 sm:py-1.5 rounded-xl border border-amber-500/50 min-w-[68px] sm:min-w-[80px] flex-shrink-0 shadow-inner">
            <div className="flex items-center text-amber-400 font-black text-sm sm:text-base leading-tight">
              <span className="mr-0.5">$</span>
              <input
                type="number"
                min={sizingMin}
                max={sizingMax}
                step={blindUnit}
                value={currentAmount}
                disabled={(!effectiveIsMyTurn && !canPreAction) || (effectiveIsMyTurn && !legalActions?.can_bet && !legalActions?.can_raise) || maxVal <= 0}
                onChange={(e) => {
                  const next = alignAmount(e.target.value);
                  setRaiseAmount(next);
                  if (preAction === PRE_ACTIONS.RAISE) {
                    setPreActionData((prev) => (prev ? { ...prev, targetAmount: next } : prev));
                  }
                }}
                className="w-12 sm:w-14 bg-transparent text-center font-black text-amber-300 text-sm sm:text-base focus:outline-none p-0"
              />
            </div>
          </div>
        </div>

        {/* 10 Quick Bet Presets (2×5 Grid) */}
        <div className="poker-presets-grid grid grid-cols-5 gap-1 sm:gap-1.5">
          {quickPresets.map((preset, idx) => {
            let amount = 0;
            if (preset.isMax) {
              amount = maxVal;
            } else if (preset.type === 'pot') {
              amount = calcPresetAmount(preset.ratio);
            } else if (preset.type === 'bb') {
              amount = alignAmount(calcBBAmount(preset.mult));
            }

            const isTooSmall = !preset.isMax && amount < sizingMin;
            const isSelected = (effectiveIsMyTurn || canPreAction) && currentAmount === amount && (
              effectiveIsMyTurn ? (legalActions?.can_bet || legalActions?.can_raise || (preset.isMax && legalActions?.can_all_in)) : maxVal > 0
            );
            const isPresetDisabled = effectiveIsMyTurn
              ? (!legalActions?.can_bet && !legalActions?.can_raise && !(preset.isMax && legalActions?.can_all_in)) || isTooSmall
              : (!canPreAction || maxVal <= 0 || isTooSmall);

            return (
              <button
                key={idx}
                type="button"
                onClick={() => handlePresetClick(amount, preset.isMax)}
                disabled={isPresetDisabled}
                className={`poker-preset-btn flex flex-col items-center justify-center py-1 sm:py-1.5 px-0.5 rounded-lg border transition active:scale-95 cursor-pointer leading-tight ${
                  isSelected
                    ? 'bg-amber-950/80 border-amber-400 text-amber-300 shadow-[0_0_10px_rgba(251,191,36,0.3)] ring-1 ring-amber-400/70'
                    : preset.isMax
                    ? 'bg-gradient-to-b from-red-950/70 to-slate-900 border-red-500/40 text-red-300 hover:from-red-900/80'
                    : 'bg-slate-900 hover:bg-slate-800 border-slate-800 text-slate-300 hover:border-slate-700'
                } disabled:opacity-30 disabled:cursor-not-allowed`}
              >
                <span className={`text-[9px] sm:text-[10px] font-bold truncate max-w-full ${
                  preset.isMax ? 'text-red-300' : isSelected ? 'text-amber-200' : 'text-slate-300'
                }`}>
                  {preset.label}
                </span>
                <span className={`text-[10px] sm:text-[11px] font-black ${
                  preset.isMax ? 'text-amber-400' : isSelected ? 'text-amber-300' : 'text-amber-400/90'
                }`}>
                  ${amount}
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {/* 4. Desktop Action Console (hidden lg:flex): Classic Spacious 2x2 Action Buttons + Slider & Dedicated Sizing Console */}
      <div className="hidden lg:flex flex-col gap-2 lg:gap-2.5 w-full">
        {/* Desktop Main Action Buttons Grid (2x2) */}
        <div className="poker-action-controls bg-slate-900/90 border border-slate-800 rounded-xl lg:rounded-2xl p-2 lg:p-3 flex flex-col gap-2 lg:gap-2.5 shadow-xl flex-shrink-0">
          <div className="flex items-center justify-between h-7 flex-shrink-0">
            <div className="text-[11px] lg:text-xs font-extrabold text-slate-400 uppercase tracking-wider flex items-center gap-1">
              <Zap className="w-3 h-3 lg:w-3.5 lg:h-3.5 text-amber-400" />
              <span>
                {selfSeat && !hasCards && !['IDLE', 'HAND_END'].includes(street)
                  ? '等待下局'
                  : canPreAction
                  ? '预选'
                  : '操作'}
              </span>
            </div>
            {canPreAction && preAction ? (
              <button
                type="button"
                onClick={() => {
                  setPreAction(null);
                  setPreActionData(null);
                }}
                className="text-[10px] lg:text-[11px] text-amber-300 hover:text-amber-200 bg-amber-950/80 hover:bg-amber-900/90 border border-amber-500/50 px-2 py-0.5 rounded-full flex items-center gap-1 font-bold cursor-pointer transition shadow h-6"
              >
                <span>预选：{
                  preAction === PRE_ACTIONS.CHECK_FOLD
                    ? '过牌/弃牌'
                    : preAction === PRE_ACTIONS.CHECK_CALL
                    ? `过牌/跟注${preCallCost > 0 ? ` $${preCallDisplayAmt}` : ''}`
                    : `加注至 $${currentAmount}`
                }</span>
                <span className="text-amber-400 font-extrabold">✕</span>
              </button>
            ) : selfSeat && !hasCards && !['IDLE', 'HAND_END'].includes(street) ? (
              <span className="text-[10px] lg:text-[11px] text-amber-400/90 font-bold bg-amber-950/40 border border-amber-500/20 px-2 py-0.5 rounded-full">
                等待下一局开始
              </span>
            ) : null}
          </div>

          <div className="grid grid-cols-2 gap-1.5 lg:gap-2">
            {/* Col 1, Row 1: Fold / Check-Fold Button */}
            {effectiveIsMyTurn ? (
              <button
                type="button"
                onClick={() => onAction('FOLD')}
                disabled={disabled || !legalActions?.can_fold}
                className="poker-action-button flex flex-col items-center justify-center py-2 lg:py-3 px-1 lg:px-2 bg-gradient-to-b from-red-800 to-red-950 hover:from-red-700 hover:to-red-900 disabled:opacity-35 disabled:cursor-not-allowed text-white font-extrabold rounded-lg lg:rounded-xl border border-red-500/40 lg:border-2 shadow-lg active:scale-95 transition cursor-pointer h-[58px] lg:h-[64px] min-h-[58px] lg:min-h-[64px]"
              >
                <span className="text-sm lg:text-base font-black tracking-wide">弃牌</span>
                <span className="text-[10px] lg:text-[11px] text-red-300/80 font-medium">[F]</span>
              </button>
            ) : canPreAction ? (
              <button
                type="button"
                onClick={() => togglePreAction(PRE_ACTIONS.CHECK_FOLD)}
                disabled={disabled}
                className={`poker-action-button flex flex-col items-center justify-center py-2 lg:py-3 px-1 lg:px-2 font-extrabold rounded-lg lg:rounded-xl transition active:scale-95 cursor-pointer border lg:border-2 shadow-lg h-[58px] lg:h-[64px] min-h-[58px] lg:min-h-[64px] ${
                  preAction === PRE_ACTIONS.CHECK_FOLD
                    ? 'bg-gradient-to-b from-red-700 via-amber-950 to-red-950 border-amber-400 ring-2 ring-amber-400/80 text-amber-200 shadow-glow-gold'
                    : 'bg-gradient-to-b from-slate-800 to-slate-900 hover:from-slate-700 hover:to-slate-800 border-slate-700/80 text-slate-300 hover:text-white'
                }`}
              >
                <div className="flex items-center gap-1">
                  <span className={`w-3.5 h-3.5 rounded-full flex items-center justify-center text-[10px] font-black ${
                    preAction === PRE_ACTIONS.CHECK_FOLD ? 'bg-amber-400 text-slate-950' : 'border border-slate-500 text-transparent'
                  }`}>
                    ✓
                  </span>
                  <span className="text-sm lg:text-base font-black tracking-wide">
                    过牌 / 弃牌
                  </span>
                </div>
                <span className={`text-[10px] lg:text-[11px] font-medium ${
                  preAction === PRE_ACTIONS.CHECK_FOLD ? 'text-amber-300' : 'text-slate-400'
                }`}>
                  [F]
                </span>
              </button>
            ) : (
              <button
                type="button"
                disabled={true}
                className="poker-action-button flex flex-col items-center justify-center py-2 lg:py-3 px-1 lg:px-2 bg-gradient-to-b from-red-800 to-red-950 opacity-35 cursor-not-allowed text-white font-extrabold rounded-lg lg:rounded-xl border border-red-500/40 lg:border-2 shadow-lg h-[58px] lg:h-[64px] min-h-[58px] lg:min-h-[64px]"
              >
                <span className="text-sm lg:text-base font-black tracking-wide">弃牌</span>
                <span className="text-[10px] lg:text-[11px] text-red-300/80 font-medium">[F]</span>
              </button>
            )}

            {/* Col 2, Row 1: Check / Call / Check-Call Button */}
            {effectiveIsMyTurn ? (
              legalActions?.can_check ? (
                <button
                  type="button"
                  onClick={() => onAction('CHECK')}
                  disabled={disabled}
                  className="poker-action-button flex flex-col items-center justify-center py-2 lg:py-3 px-1 lg:px-2 bg-gradient-to-b from-emerald-600 to-emerald-950 hover:from-emerald-500 hover:to-emerald-900 disabled:opacity-35 disabled:cursor-not-allowed text-white font-extrabold rounded-lg lg:rounded-xl border border-emerald-400/50 lg:border-2 shadow-lg active:scale-95 transition cursor-pointer h-[58px] lg:h-[64px] min-h-[58px] lg:min-h-[64px]"
                >
                  <span className="text-sm lg:text-base font-black tracking-wide">过牌</span>
                  <span className="text-[10px] lg:text-[11px] text-emerald-300/80 font-medium">[Space]</span>
                </button>
              ) : (
                <button
                  type="button"
                  onClick={() => onAction('CALL', legalActions?.call_amount || 0)}
                  disabled={disabled || !legalActions?.can_call}
                  className="poker-action-button flex flex-col items-center justify-center py-2 lg:py-3 px-1 lg:px-2 bg-gradient-to-b from-emerald-600 to-emerald-950 hover:from-emerald-500 hover:to-emerald-900 disabled:opacity-35 disabled:cursor-not-allowed text-white font-extrabold rounded-lg lg:rounded-xl border border-emerald-400/50 lg:border-2 shadow-lg active:scale-95 transition cursor-pointer h-[58px] lg:h-[64px] min-h-[58px] lg:min-h-[64px]"
                >
                  <span className="text-sm lg:text-base font-black tracking-wide">
                    跟注 ${legalActions?.call_amount || 0}
                  </span>
                  <span className="text-[10px] lg:text-[11px] text-emerald-300/80 font-medium">[Space]</span>
                </button>
              )
            ) : canPreAction ? (
              <button
                type="button"
                onClick={() => togglePreAction(PRE_ACTIONS.CHECK_CALL)}
                disabled={disabled}
                className={`poker-action-button flex flex-col items-center justify-center py-2 lg:py-3 px-1 lg:px-2 font-extrabold rounded-lg lg:rounded-xl transition active:scale-95 cursor-pointer border lg:border-2 shadow-lg h-[58px] lg:h-[64px] min-h-[58px] lg:min-h-[64px] ${
                  preAction === PRE_ACTIONS.CHECK_CALL
                    ? 'bg-gradient-to-b from-emerald-600 to-emerald-950 border-emerald-400 ring-2 ring-emerald-400/80 text-white shadow-[0_0_15px_rgba(52,211,153,0.5)]'
                    : 'bg-gradient-to-b from-slate-800 to-slate-900 hover:from-slate-700 hover:to-slate-800 border-slate-700/80 text-slate-300 hover:text-white'
                }`}
              >
                <div className="flex items-center gap-1">
                  <span className={`w-3.5 h-3.5 rounded-full flex items-center justify-center text-[10px] font-black ${
                    preAction === PRE_ACTIONS.CHECK_CALL ? 'bg-emerald-400 text-slate-950' : 'border border-slate-500 text-transparent'
                  }`}>
                    ✓
                  </span>
                  <span className="text-sm lg:text-base font-black tracking-wide">
                    过牌 / 跟注{preCallCost > 0 ? ` $${preCallDisplayAmt}` : ''}
                  </span>
                </div>
                <span className={`text-[10px] lg:text-[11px] font-medium ${
                  preAction === PRE_ACTIONS.CHECK_CALL ? 'text-emerald-200' : 'text-slate-400'
                }`}>
                  [Space]
                </span>
              </button>
            ) : (
              <button
                type="button"
                disabled={true}
                className="poker-action-button flex flex-col items-center justify-center py-2 lg:py-3 px-1 lg:px-2 bg-gradient-to-b from-emerald-600 to-emerald-950 opacity-35 cursor-not-allowed text-white font-extrabold rounded-lg lg:rounded-xl border border-emerald-400/50 lg:border-2 shadow-lg h-[58px] lg:h-[64px] min-h-[58px] lg:min-h-[64px]"
              >
                <span className="text-sm lg:text-base font-black tracking-wide">过牌</span>
                <span className="text-[10px] lg:text-[11px] text-emerald-300/80 font-medium">[Space]</span>
              </button>
            )}

            {/* Col 1, Row 2: Horizontal Sizing Slider */}
            <div
              className={`poker-action-slider-container flex flex-col justify-between py-1.5 lg:py-2 px-2 lg:px-2.5 rounded-lg lg:rounded-xl border shadow-lg transition-all h-[58px] lg:h-[64px] min-h-[58px] lg:min-h-[64px] ${
                (effectiveIsMyTurn && (legalActions?.can_bet || legalActions?.can_raise)) || (canPreAction && maxVal > 0)
                  ? isAllIn
                    ? 'bg-gradient-to-b from-slate-900 via-purple-950/40 to-slate-950 border-purple-500/60 shadow-[0_0_12px_rgba(168,85,247,0.25)]'
                    : 'bg-slate-950/90 border-amber-500/40'
                  : 'bg-slate-950/50 border-slate-800 opacity-40'
              }`}
            >
              <div className="flex items-center justify-between text-[11px] lg:text-xs">
                <span className="text-slate-400 font-bold">
                  {effectiveIsMyTurn
                    ? (legalActions?.can_bet ? '下注' : '加注')
                    : (effectiveHighestBet === 0 ? '预设下注' : '预设加注')}
                </span>
                <span className={`font-black ${isAllIn ? 'text-purple-300 animate-pulse' : 'text-amber-300'}`}>
                  ${currentAmount}
                </span>
              </div>
              <input
                type="range"
                min={0}
                max={BET_SLIDER_STEPS}
                step={1}
                value={sliderValue}
                disabled={disabled || (!effectiveIsMyTurn && !canPreAction) || (effectiveIsMyTurn && !legalActions?.can_bet && !legalActions?.can_raise) || maxVal <= 0}
                onChange={(e) => {
                  const progress = Number(e.target.value);
                  const rawAmount = nonlinearProgressToAmount(
                    progress,
                    sizingMin,
                    sizingMax,
                  );
                  const next = progress >= BET_SLIDER_STEPS
                    ? maxVal
                    : alignAmount(rawAmount);
                  setRaiseAmount(next);
                  if (preAction === PRE_ACTIONS.RAISE) {
                    setPreActionData((prev) => (prev ? { ...prev, targetAmount: next } : prev));
                  }
                }}
                className={`poker-horizontal-raise-slider w-full h-2 lg:h-2.5 my-1 rounded-lg appearance-none cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed bg-slate-800 ${
                  isAllIn ? 'accent-purple-400' : 'accent-amber-400'
                }`}
                aria-label="下注额"
                aria-valuetext={`下注 ${currentAmount} 筹码`}
              />
              <div className="flex items-center justify-between text-[9px] lg:text-[10px] text-slate-500 font-semibold px-0.5">
                <span>${sizingMin}</span>
                <span className={isAllIn ? 'text-purple-400 font-bold' : ''}>
                  {isAllIn ? '全下' : `$${sizingMax}`}
                </span>
              </div>
            </div>

            {/* Col 2, Row 2: Raise Button (dynamically turns to All-In when dragged to end) */}
            {effectiveIsMyTurn ? (
              <button
                type="button"
                onClick={handleRaiseSubmit}
                disabled={disabled || (!legalActions?.can_bet && !legalActions?.can_raise && !(isAllIn && legalActions?.can_all_in))}
                className={`poker-action-button flex flex-col items-center justify-center py-2 lg:py-3 px-1 lg:px-2 font-black rounded-lg lg:rounded-xl border lg:border-2 shadow-lg active:scale-95 transition cursor-pointer disabled:opacity-35 disabled:cursor-not-allowed h-[58px] lg:h-[64px] min-h-[58px] lg:min-h-[64px] ${
                  isAllIn
                    ? 'bg-gradient-to-b from-purple-800 via-red-950 to-amber-950 hover:from-purple-700 hover:to-red-900 border-purple-400/80 shadow-[0_0_15px_rgba(168,85,247,0.4)] text-amber-300'
                    : 'bg-gradient-to-b from-amber-500 to-amber-900 hover:from-amber-400 hover:to-amber-800 border-amber-300/70 shadow-glow-gold text-white'
                }`}
              >
                {isAllIn ? (
                  <>
                    <span className="text-sm lg:text-base font-black tracking-wide text-amber-200 whitespace-nowrap flex items-center gap-1">
                      <Flame className="w-3.5 h-3.5 lg:w-4 lg:h-4 text-amber-400 fill-amber-400" />
                      全下 ${legalActions?.all_in_amount || currentAmount}
                    </span>
                    <span className="text-[10px] lg:text-[11px] text-purple-300/90 font-medium">
                      [R]
                    </span>
                  </>
                ) : (
                  <>
                    <span className="text-sm lg:text-base font-black tracking-wide text-amber-200 whitespace-nowrap">
                      {legalActions?.can_bet ? `下注 $${currentAmount}` : `加注至 $${currentAmount}`}
                    </span>
                    <span className="text-[10px] lg:text-[11px] text-amber-300/80 font-medium">
                      [R]
                    </span>
                  </>
                )}
              </button>
            ) : canPreAction ? (
              <button
                type="button"
                onClick={() => togglePreAction(PRE_ACTIONS.RAISE)}
                disabled={disabled || maxVal <= 0}
                className={`poker-action-button flex flex-col items-center justify-center py-2 lg:py-3 px-1 lg:px-2 font-black rounded-lg lg:rounded-xl border lg:border-2 shadow-lg active:scale-95 transition cursor-pointer disabled:opacity-35 disabled:cursor-not-allowed h-[58px] lg:h-[64px] min-h-[58px] lg:min-h-[64px] ${
                  preAction === PRE_ACTIONS.RAISE
                    ? isAllIn
                      ? 'bg-gradient-to-b from-purple-800 via-red-950 to-amber-950 border-purple-400 ring-2 ring-purple-400/80 shadow-[0_0_15px_rgba(168,85,247,0.5)] text-amber-200'
                      : 'bg-gradient-to-b from-amber-600 to-amber-950 border-amber-300 ring-2 ring-amber-400/80 shadow-glow-gold text-white'
                    : 'bg-gradient-to-b from-slate-850 to-slate-950 hover:from-slate-800 hover:to-slate-900 border-slate-700/80 text-slate-300 hover:text-white'
                }`}
              >
                <div className="flex items-center gap-1">
                  <span className={`w-3.5 h-3.5 rounded-full flex items-center justify-center text-[10px] font-black ${
                    preAction === PRE_ACTIONS.RAISE ? 'bg-amber-400 text-slate-950' : 'border border-slate-500 text-transparent'
                  }`}>
                    ✓
                  </span>
                  <span className="text-sm lg:text-base font-black tracking-wide whitespace-nowrap">
                    {isAllIn
                      ? `全下 $${maxVal}`
                      : (effectiveHighestBet === 0 ? `下注 $${currentAmount}` : `加注至 $${currentAmount}`)}
                  </span>
                </div>
                <span className={`text-[10px] lg:text-[11px] font-medium ${
                  preAction === PRE_ACTIONS.RAISE ? 'text-amber-300' : 'text-slate-400'
                }`}>
                  [R]
                </span>
              </button>
            ) : (
              <button
                type="button"
                disabled={true}
                className="poker-action-button flex flex-col items-center justify-center py-2 lg:py-3 px-1 lg:px-2 font-black rounded-lg lg:rounded-xl border lg:border-2 shadow-lg opacity-35 cursor-not-allowed h-[58px] lg:h-[64px] min-h-[58px] lg:min-h-[64px] bg-gradient-to-b from-amber-500 to-amber-900 text-white"
              >
                <span className="text-sm lg:text-base font-black tracking-wide">加注</span>
                <span className="text-[10px] lg:text-[11px] text-amber-300/80 font-medium">[R]</span>
              </button>
            )}
          </div>
        </div>

        {/* Desktop Raise / Bet Sizing Console */}
        <div className="poker-action-sizing bg-slate-900/90 border border-slate-800 rounded-xl lg:rounded-2xl p-2.5 lg:p-3 flex flex-col gap-2 lg:gap-2.5 shadow-xl flex-shrink-0">
          <div className="flex items-center justify-between h-7 flex-shrink-0">
            <span className="text-[11px] lg:text-xs font-extrabold text-slate-400 uppercase tracking-wider">
              {canPreAction && !effectiveIsMyTurn ? '预设额度' : '下注额'}
            </span>
            <div className="flex items-center gap-1.5">
              <button
                type="button"
                onClick={() => adjustBB(-1)}
                disabled={(!effectiveIsMyTurn && !canPreAction) || (effectiveIsMyTurn && !legalActions?.can_bet && !legalActions?.can_raise) || maxVal <= 0}
                className="px-1.5 py-0.5 lg:px-2 lg:py-1 bg-slate-800 hover:bg-slate-700 disabled:opacity-40 text-slate-200 rounded-md lg:rounded-lg border border-slate-700 text-[10px] lg:text-xs font-bold active:scale-95 shadow cursor-pointer transition"
              >
                -1BB
              </button>
              <div className="flex items-center gap-1 bg-slate-950 px-2 py-0.5 lg:px-2.5 rounded-lg border border-amber-500/40">
                <span className="text-amber-400 font-black text-xs lg:text-sm">$</span>
                <input
                  type="number"
                  min={sizingMin}
                  max={sizingMax}
                  step={blindUnit}
                  value={currentAmount}
                  disabled={(!effectiveIsMyTurn && !canPreAction) || (effectiveIsMyTurn && !legalActions?.can_bet && !legalActions?.can_raise) || maxVal <= 0}
                  onChange={(e) => {
                    const next = alignAmount(e.target.value);
                    setRaiseAmount(next);
                    if (preAction === PRE_ACTIONS.RAISE) {
                      setPreActionData((prev) => (prev ? { ...prev, targetAmount: next } : prev));
                    }
                  }}
                  className="w-14 lg:w-16 bg-transparent text-right font-black text-amber-300 text-xs lg:text-sm focus:outline-none"
                />
              </div>
              <button
                type="button"
                onClick={() => adjustBB(1)}
                disabled={(!effectiveIsMyTurn && !canPreAction) || (effectiveIsMyTurn && !legalActions?.can_bet && !legalActions?.can_raise) || maxVal <= 0}
                className="px-1.5 py-0.5 lg:px-2 lg:py-1 bg-slate-800 hover:bg-slate-700 disabled:opacity-40 text-slate-200 rounded-md lg:rounded-lg border border-slate-700 text-[10px] lg:text-xs font-bold active:scale-95 shadow cursor-pointer transition"
              >
                +1BB
              </button>
            </div>
          </div>

          {/* Preset Ratio Buttons (Pot fractions: 1/3, 1/2, 2/3, Pot, 1.5 Pot, 2 Pot, 3 Pot, All-in) */}
          <div className="grid grid-cols-4 gap-1 lg:gap-1.5">
            {potPresets.map((preset, idx) => {
              const amount = preset.isMax ? maxVal : calcPresetAmount(preset.ratio);
              const isTooSmall = !preset.isMax && amount < sizingMin;
              const isSelected = (effectiveIsMyTurn || canPreAction) && currentAmount === amount && (
                effectiveIsMyTurn ? (legalActions?.can_bet || legalActions?.can_raise || (preset.isMax && legalActions?.can_all_in)) : maxVal > 0
              );
              const isPresetDisabled = effectiveIsMyTurn
                ? (!legalActions?.can_bet && !legalActions?.can_raise && !(preset.isMax && legalActions?.can_all_in)) || isTooSmall
                : (!canPreAction || maxVal <= 0 || isTooSmall);

              return (
                <button
                  key={idx}
                  type="button"
                  onClick={() => handlePresetClick(amount, preset.isMax)}
                  disabled={isPresetDisabled}
                  className={`flex flex-col items-center justify-center py-1 px-0.5 lg:py-1.5 lg:px-1 rounded-lg lg:rounded-xl transition active:scale-95 cursor-pointer border h-[42px] lg:h-[46px] flex-shrink-0 ${
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
              const rawAmount = calcBBAmount(preset.mult);
              const amount = alignAmount(rawAmount);
              const isTooSmall = rawAmount < sizingMin;
              const isSelected = (effectiveIsMyTurn || canPreAction) && currentAmount === amount && (
                effectiveIsMyTurn ? (legalActions?.can_bet || legalActions?.can_raise) : maxVal > 0
              );
              const isBbDisabled = effectiveIsMyTurn
                ? (!legalActions?.can_bet && !legalActions?.can_raise) || isTooSmall
                : (!canPreAction || maxVal <= 0 || isTooSmall);

              return (
                <button
                  key={idx}
                  type="button"
                  onClick={() => handlePresetClick(amount, false)}
                  disabled={isBbDisabled}
                  className={`flex flex-col items-center justify-center py-0.5 px-0.5 lg:py-1 lg:px-1 rounded-md lg:rounded-lg transition active:scale-95 cursor-pointer border h-[34px] lg:h-[38px] flex-shrink-0 ${
                    isSelected
                      ? 'bg-amber-950/60 border-amber-400/80 shadow-[0_0_8px_rgba(251,191,36,0.2)]'
                      : 'bg-slate-800/80 hover:bg-slate-700/80 border-slate-700/70'
                  } disabled:opacity-40 disabled:cursor-not-allowed`}
                >
                  <span className={`text-[9px] lg:text-[10px] font-bold ${isSelected ? 'text-amber-200' : 'text-slate-300'}`}>
                    {preset.label}
                  </span>
                  <span className={`text-[10px] lg:text-[11px] font-black ${isSelected ? 'text-amber-300' : 'text-slate-400'}`}>
                    ${rawAmount}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      </div>
      </>
      )}

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
