import React, { useState, useEffect } from 'react';
import { ChevronUp, ChevronDown, Flame, DollarSign } from 'lucide-react';

export default function ActionBar({
  legalActions,
  totalPot = 0,
  bigBlind = 10,
  onAction,
  disabled = false,
}) {
  const [raiseAmount, setRaiseAmount] = useState(0);

  // Initialize or adjust default raise slider whenever legalActions changes
  useEffect(() => {
    if (legalActions?.can_bet) {
      setRaiseAmount(legalActions.min_bet);
    } else if (legalActions?.can_raise) {
      setRaiseAmount(legalActions.min_raise_to);
    }
  }, [legalActions?.min_bet, legalActions?.min_raise_to, legalActions?.can_bet, legalActions?.can_raise]);

  // Keyboard shortcuts (PC)
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (disabled || !legalActions) return;
      if (['input', 'textarea'].includes(e.target.tagName.toLowerCase())) return;

      if (e.code === 'KeyF' && legalActions.can_fold) {
        onAction('FOLD');
      } else if (e.code === 'Space') {
        e.preventDefault();
        if (legalActions.can_check) {
          onAction('CHECK');
        } else if (legalActions.can_call) {
          onAction('CALL', legalActions.call_amount);
        }
      } else if (e.code === 'KeyR' && (legalActions.can_bet || legalActions.can_raise)) {
        const act = legalActions.can_bet ? 'BET' : 'RAISE';
        onAction(act, raiseAmount);
      } else if (e.code === 'KeyA' && legalActions.can_all_in) {
        onAction('ALL_IN', legalActions.all_in_amount);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [disabled, legalActions, raiseAmount, onAction]);

  if (!legalActions) {
    return null;
  }

  const minVal = legalActions.can_bet ? legalActions.min_bet : legalActions.min_raise_to || 0;
  const maxVal = legalActions.can_bet ? legalActions.max_bet : legalActions.max_raise_to || 0;

  // Preset Bet Sizing helpers
  const applyPresetRatio = (ratio) => {
    let target = Math.round(totalPot * ratio);
    if (target < minVal) target = minVal;
    if (target > maxVal) target = maxVal;
    setRaiseAmount(target);
  };

  const adjustBB = (multiplier) => {
    let next = raiseAmount + multiplier * bigBlind;
    if (next < minVal) next = minVal;
    if (next > maxVal) next = maxVal;
    setRaiseAmount(next);
  };

  return (
    <div className="w-full max-w-2xl mx-auto bg-slate-900/90 border border-amber-500/30 rounded-2xl p-3 backdrop-blur-md shadow-2xl flex flex-col gap-2.5">
      {/* Top Row: Quick Bet Ratios & Precision Adjuster */}
      {(legalActions.can_bet || legalActions.can_raise) && (
        <div className="flex flex-col gap-2">
          {/* Quick Preset Buttons */}
          <div className="grid grid-cols-6 gap-1.5">
            <button
              onClick={() => setRaiseAmount(minVal)}
              className="px-2 py-1 bg-slate-800 hover:bg-slate-700 text-amber-300 rounded-lg text-xs font-bold border border-slate-700 transition"
            >
              Min
            </button>
            <button
              onClick={() => applyPresetRatio(1 / 3)}
              className="px-2 py-1 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg text-xs font-bold border border-slate-700 transition"
            >
              1/3 底池
            </button>
            <button
              onClick={() => applyPresetRatio(1 / 2)}
              className="px-2 py-1 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg text-xs font-bold border border-slate-700 transition"
            >
              1/2 底池
            </button>
            <button
              onClick={() => applyPresetRatio(2 / 3)}
              className="px-2 py-1 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg text-xs font-bold border border-slate-700 transition"
            >
              2/3 底池
            </button>
            <button
              onClick={() => applyPresetRatio(1.0)}
              className="px-2 py-1 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg text-xs font-bold border border-slate-700 transition"
            >
              底池 (Pot)
            </button>
            <button
              onClick={() => setRaiseAmount(maxVal)}
              className="px-2 py-1 bg-gradient-to-r from-red-900 to-amber-900 hover:from-red-800 hover:to-amber-800 text-amber-300 rounded-lg text-xs font-black border border-amber-500/40 transition flex items-center justify-center gap-0.5"
            >
              <Flame className="w-3 h-3 text-red-400" />
              All-In
            </button>
          </div>

          {/* Slider & Step Controls */}
          <div className="flex items-center gap-2 px-1">
            <button
              onClick={() => adjustBB(-1)}
              className="p-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg border border-slate-700"
              title="-1 BB"
            >
              <ChevronDown className="w-4 h-4" />
            </button>

            <input
              type="range"
              min={minVal}
              max={maxVal}
              step={bigBlind}
              value={raiseAmount}
              onChange={(e) => setRaiseAmount(Number(e.target.value))}
              className="w-full h-2 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-amber-400"
            />

            <button
              onClick={() => adjustBB(1)}
              className="p-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg border border-slate-700"
              title="+1 BB"
            >
              <ChevronUp className="w-4 h-4" />
            </button>

            <div className="min-w-[70px] text-right font-extrabold text-amber-400 text-sm">
              ${raiseAmount}
            </div>
          </div>
        </div>
      )}

      {/* Main Action Buttons Grid */}
      <div className="grid grid-cols-4 gap-2">
        {/* Fold Button */}
        <button
          onClick={() => onAction('FOLD')}
          disabled={disabled || !legalActions.can_fold}
          className="flex flex-col items-center justify-center py-3 bg-gradient-to-b from-red-800 to-red-950 hover:from-red-700 hover:to-red-900 disabled:opacity-40 text-white font-extrabold rounded-xl border border-red-500/40 shadow-lg active:scale-95 transition"
        >
          <span className="text-sm">弃牌</span>
          <span className="text-[10px] text-red-300/80 font-normal">Fold [F]</span>
        </button>

        {/* Check or Call Button */}
        {legalActions.can_check ? (
          <button
            onClick={() => onAction('CHECK')}
            disabled={disabled}
            className="flex flex-col items-center justify-center py-3 bg-gradient-to-b from-emerald-700 to-emerald-950 hover:from-emerald-600 hover:to-emerald-900 text-white font-extrabold rounded-xl border border-emerald-400/40 shadow-lg active:scale-95 transition"
          >
            <span className="text-sm">过牌</span>
            <span className="text-[10px] text-emerald-300/80 font-normal">Check [Space]</span>
          </button>
        ) : (
          <button
            onClick={() => onAction('CALL', legalActions.call_amount)}
            disabled={disabled || !legalActions.can_call}
            className="flex flex-col items-center justify-center py-3 bg-gradient-to-b from-emerald-700 to-emerald-950 hover:from-emerald-600 hover:to-emerald-900 disabled:opacity-40 text-white font-extrabold rounded-xl border border-emerald-400/40 shadow-lg active:scale-95 transition"
          >
            <span className="text-sm">跟注 ${legalActions.call_amount}</span>
            <span className="text-[10px] text-emerald-300/80 font-normal">Call [Space]</span>
          </button>
        )}

        {/* Bet or Raise Button */}
        <button
          onClick={() => {
            const act = legalActions.can_bet ? 'BET' : 'RAISE';
            onAction(act, raiseAmount);
          }}
          disabled={disabled || (!legalActions.can_bet && !legalActions.can_raise)}
          className="flex flex-col items-center justify-center py-3 bg-gradient-to-b from-amber-600 to-amber-900 hover:from-amber-500 hover:to-amber-800 disabled:opacity-40 text-slate-950 font-black rounded-xl border border-amber-300/60 shadow-lg active:scale-95 transition"
        >
          <span className="text-sm text-white">
            {legalActions.can_bet ? `下注 $${raiseAmount}` : `加注至 $${raiseAmount}`}
          </span>
          <span className="text-[10px] text-amber-200 font-normal">
            {legalActions.can_bet ? 'Bet [R]' : 'Raise [R]'}
          </span>
        </button>

        {/* All In Button */}
        <button
          onClick={() => onAction('ALL_IN', legalActions.all_in_amount)}
          disabled={disabled || !legalActions.can_all_in}
          className="flex flex-col items-center justify-center py-3 bg-gradient-to-b from-purple-800 to-red-950 hover:from-purple-700 hover:to-red-900 disabled:opacity-40 text-amber-300 font-black rounded-xl border border-purple-400/40 shadow-lg active:scale-95 transition"
        >
          <span className="text-sm flex items-center gap-0.5">
            <Flame className="w-3.5 h-3.5 text-amber-400 fill-amber-400" />
            全下 ${legalActions.all_in_amount}
          </span>
          <span className="text-[10px] text-purple-300/80 font-normal">All-In [A]</span>
        </button>
      </div>
    </div>
  );
}
