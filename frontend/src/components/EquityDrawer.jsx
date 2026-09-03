import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { createPortal } from 'react-dom';
import {
  TrendingUp,
  TrendingDown,
  Minus,
  ChevronDown,
  ChevronUp,
  Dices,
  Sparkles,
  Loader2,
  BarChart3,
  Target,
  DollarSign,
  AlertCircle,
  CheckCircle2,
} from 'lucide-react';
import { preflopChenScore } from '../utils/equityCalculator';
import { evaluateHand } from '../utils/pokerEvaluator';

const STAGE_NAMES = {
  PREFLOP: '翻牌前',
  FLOP: '翻牌圈',
  TURN: '转牌圈',
  RIVER: '河牌圈',
  SHOWDOWN: '摊牌',
  HAND_END: '牌局结束',
  IDLE: '等待开局',
};

function sortedCategoryEntries(dist) {
  if (!dist) return [];
  return Object.entries(dist)
    .map(([cat, val]) => ({ cat: Number(cat), ...val }))
    .sort((a, b) => b.cat - a.cat);
}

function winRateColor(pct) {
  if (pct >= 0.6) return 'text-emerald-400';
  if (pct >= 0.4) return 'text-amber-300';
  if (pct >= 0.2) return 'text-orange-400';
  return 'text-red-400';
}

function currentHandDescription(holeCards, boardCards) {
  const all = [...(holeCards || []), ...(boardCards || [])];
  if (all.length >= 5) {
    try {
      const ev = evaluateHand(all);
      return ev.description;
    } catch {
      return null;
    }
  }
  return null;
}

export default function EquityDrawer({
  holeCards = [],
  boardCards = [],
  street = 'IDLE',
  numOpponents = 1,
  potSize = 0,
  toCall = 0,
}) {
  const [isOpen, setIsOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState(null);
  const [result, setResult] = useState(null);

  const holeKey = useMemo(
    () => (holeCards || []).map((c) => c?.notation || '').join('|'),
    [holeCards?.[0]?.notation, holeCards?.[1]?.notation]
  );
  const boardKey = useMemo(
    () => (boardCards || []).map((c) => c?.notation || '').join('|'),
    [boardCards?.map((c) => c?.notation).join(',')]
  );
  const oppCount = useMemo(() => numOpponents | 0, [numOpponents]);

  const shouldCompute = useMemo(() => {
    if (['IDLE', 'HAND_END'].includes(street)) return false;
    if (!holeCards || holeCards.length < 2) return false;
    return true;
  }, [holeKey, street]);

  const chenScore = useMemo(() => {
    if (holeCards?.length === 2 && (!boardCards || boardCards.length === 0)) {
      return preflopChenScore(holeCards[0], holeCards[1]);
    }
    return null;
  }, [holeKey, boardKey]);

  const handDesc = useMemo(() => currentHandDescription(holeCards, boardCards), [holeKey, boardKey]);

  const runCalculation = useCallback(async () => {
    if (!shouldCompute) {
      setResult(null);
      setErrorMsg(null);
      return;
    }
    setLoading(true);
    setErrorMsg(null);
    setResult(null);

    try {
      const body = {
        hero_cards: holeCards.slice(0, 2).map((c) => ({ notation: c.notation })),
        board_cards: (boardCards || []).map((c) => ({ notation: c.notation })),
        num_opponents: Math.max(1, oppCount),
      };
      // Only send pot info when meaningful — avoid sending 0
      if (potSize > 0) body.pot_size = potSize;
      if (toCall > 0) body.to_call = toCall;

      const res = await fetch('/api/equity', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }
      const data = await res.json();
      setResult(data);
    } catch (err) {
      console.error('Equity API error:', err);
      setErrorMsg(err.message || '计算失败');
    } finally {
      setLoading(false);
    }
  }, [shouldCompute, holeKey, boardKey, oppCount, holeCards, boardCards, potSize, toCall]);

  useEffect(() => {
    if (isOpen) runCalculation();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen, holeKey, boardKey, street, oppCount]);

  // ---------- UI Components ----------
  const WinBar = ({ win, tie }) => (
    <div className="w-full h-2.5 bg-slate-800 rounded-full overflow-hidden flex">
      <div className="h-full bg-gradient-to-r from-emerald-500 to-emerald-400 transition-all duration-500"
        style={{ width: `${Math.round((win || 0) * 100)}%` }} />
      <div className="h-full bg-amber-500/80 transition-all duration-500"
        style={{ width: `${Math.round((tie || 0) * 100)}%` }} />
      <div className="h-full bg-red-500/70 transition-all duration-500"
        style={{ width: `${Math.max(0, Math.round((1 - (win || 0) - (tie || 0)) * 100))}%` }} />
    </div>
  );

  const CategoryBar = ({ name, pct }) => {
    const pctClamp = Math.max(0, Math.min(1, pct));
    const tierClass = pctClamp >= 0.05
      ? 'from-emerald-500 to-teal-400'
      : pctClamp >= 0.01
        ? 'from-amber-500 to-amber-400'
        : 'from-slate-600 to-slate-500';
    return (
      <div className="flex items-center gap-2 text-xs">
        <span className="w-20 text-slate-300 font-bold flex-shrink-0">{name}</span>
        <div className="flex-1 h-2 bg-slate-800 rounded-full overflow-hidden">
          <div className={`h-full bg-gradient-to-r ${tierClass} transition-all duration-700`}
            style={{ width: `${Math.round(pctClamp * 100)}%` }} />
        </div>
        <span className="w-12 text-right font-mono text-amber-300">
          {(pctClamp * 100).toFixed(1)}%
        </span>
      </div>
    );
  };

  const ToggleButton = () => (
    <button
      onClick={() => setIsOpen((o) => !o)}
      disabled={!shouldCompute}
      className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-bold border transition active:scale-95 cursor-pointer shadow
        ${shouldCompute
          ? 'bg-gradient-to-r from-purple-900/80 to-indigo-900/80 hover:from-purple-800 hover:to-indigo-800 text-purple-200 border-purple-500/50'
          : 'bg-slate-900/50 text-slate-600 border-slate-700 cursor-not-allowed'}`}
      title={shouldCompute ? '查看胜率分析' : '发牌后可用'}
    >
      <BarChart3 className="w-3.5 h-3.5" />
      胜率
      {chenScore !== null && (
        <span className="px-1.5 py-0.5 bg-amber-500/90 text-slate-950 rounded text-[10px] font-black">
          {chenScore}
        </span>
      )}
      {isOpen ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
    </button>
  );

  // ---------- Render ----------
  const equity = result?.equity;
  const drawProbs = result?.drawProbabilities;
  const outs = result?.outs;
  const potOdds = result?.potOdds;

  return (
    <>
      <div data-equity-trigger><ToggleButton /></div>

      {createPortal(
        isOpen && shouldCompute && (
          <div
            className="fixed top-0 left-0 h-full w-[360px] max-w-[85vw] z-[9999] animate-slide-in-left bg-gradient-to-b from-slate-900 via-slate-950 to-slate-900 border-r border-purple-500/50 shadow-2xl shadow-purple-500/30 overflow-y-auto"
          >
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-3 bg-gradient-to-r from-purple-900/60 to-indigo-900/60 border-b border-purple-500/30 sticky top-0 z-10">
              <div className="flex items-center gap-2">
                <Dices className="w-4 h-4 text-amber-400" />
                <span className="text-sm font-black text-purple-100 tracking-wide">
                  胜率分析
                </span>
              </div>
              <button
                onClick={() => setIsOpen(false)}
                className="text-purple-200 hover:text-white text-lg leading-none cursor-pointer px-2 py-1 rounded-lg hover:bg-purple-500/20"
                title="关闭"
              >
                ✕
              </button>
            </div>

            <div className="px-4 py-3 space-y-3">
              {/* Status line */}
              <div className="flex items-center justify-between text-xs">
                <span className="text-slate-400">
                  阶段: <span className="text-amber-300 font-black">{STAGE_NAMES[street] || street}</span>
                  {numOpponents > 0 && <span className="ml-2 text-slate-500">vs {numOpponents} 名对手</span>}
                </span>
                {handDesc && (
                  <span className="text-purple-300 font-bold flex items-center gap-1">
                    <Sparkles className="w-3 h-3" />{handDesc}
                  </span>
                )}
              </div>

              {/* Chen Score (preflop only) */}
              {chenScore !== null && (
                <div className="bg-slate-800/60 border border-slate-700 rounded-xl px-4 py-2 flex items-center justify-between">
                  <div className="flex items-center gap-2 text-xs text-slate-300">
                    <Sparkles className="w-3.5 h-3.5 text-amber-400" />
                    <span>翻前 Chen 强度</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="w-28 h-1.5 bg-slate-800 rounded-full overflow-hidden">
                      <div className="h-full bg-gradient-to-r from-amber-500 to-amber-300 transition-all duration-500"
                        style={{ width: `${chenScore}%` }} />
                    </div>
                    <span className="font-black text-amber-300 text-sm w-8 text-right">{chenScore}</span>
                  </div>
                </div>
              )}

              {/* Loading */}
              {loading && (
                <div className="flex flex-col items-center justify-center py-10 gap-2 text-slate-400">
                  <Loader2 className="w-6 h-6 animate-spin text-purple-400" />
                  <span className="text-xs">后端蒙特卡洛模拟中...</span>
                </div>
              )}

              {/* Error */}
              {!loading && errorMsg && (
                <div className="bg-red-950/60 border border-red-500/40 rounded-xl px-4 py-3 text-red-300 text-xs text-center">
                  计算失败: {errorMsg}
                </div>
              )}

              {/* Equity (win/tie/lose) */}
              {!loading && equity && (
                <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 text-xs text-slate-400 font-bold">
                      <BarChart3 className="w-3.5 h-3.5" /> 当前胜率 vs 随机对手
                    </div>
                    <span className="text-[10px] text-slate-500">
                      {equity.strategy === 'exact' ? '精确' : 'MC'}
                    </span>
                  </div>
                  <div className="grid grid-cols-3 gap-2 text-center">
                    <div className="flex flex-col items-center gap-1 bg-emerald-950/40 rounded-lg py-2 border border-emerald-500/30">
                      <TrendingUp className="w-4 h-4 text-emerald-400" />
                      <span className={`text-xl font-black ${winRateColor(equity.winRate)}`}>
                        {(equity.winRate * 100).toFixed(1)}%
                      </span>
                      <span className="text-[10px] text-slate-400">赢</span>
                    </div>
                    <div className="flex flex-col items-center gap-1 bg-amber-950/40 rounded-lg py-2 border border-amber-500/30">
                      <Minus className="w-4 h-4 text-amber-400" />
                      <span className="text-xl font-black text-amber-300">
                        {(equity.tieRate * 100).toFixed(1)}%
                      </span>
                      <span className="text-[10px] text-slate-400">平</span>
                    </div>
                    <div className="flex flex-col items-center gap-1 bg-red-950/40 rounded-lg py-2 border border-red-500/30">
                      <TrendingDown className="w-4 h-4 text-red-400" />
                      <span className="text-xl font-black text-red-400">
                        {(equity.loseRate * 100).toFixed(1)}%
                      </span>
                      <span className="text-[10px] text-slate-400">输</span>
                    </div>
                  </div>
                  <WinBar win={equity.winRate} tie={equity.tieRate} />
                </div>
              )}

              {/* Outs Analysis */}
              {!loading && outs && outs.categories.length > 0 && (
                <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 text-xs text-slate-400 font-bold">
                      <Target className="w-3.5 h-3.5 text-cyan-400" /> 听牌分析 (Outs)
                    </div>
                    <span className="text-amber-300 font-black text-sm">
                      {outs.total_outs} outs
                    </span>
                  </div>

                  <div className="space-y-1.5">
                    {outs.categories.map((c, i) => (
                      <div key={i} className="bg-slate-900/60 rounded-lg px-3 py-2 flex items-center justify-between text-xs">
                        <div>
                          <div className="text-slate-300 font-bold">{c.name}</div>
                          <div className="text-[10px] text-slate-500">{c.desc}</div>
                        </div>
                        <span className="text-amber-300 font-black text-sm">{c.outs} outs</span>
                      </div>
                    ))}
                  </div>

                  <div className="text-[11px] text-slate-400 bg-slate-900/50 rounded-lg px-3 py-2 border border-slate-700/50">
                    <span className="text-slate-500">补牌概率 — 转牌:</span>{' '}
                    <span className="text-cyan-300 font-bold">
                      {(outs.turn_hit_pct * 100).toFixed(1)}%
                    </span>
                    <span className="text-slate-600 mx-2">·</span>
                    <span className="text-slate-500">转+河:</span>{' '}
                    <span className="text-cyan-300 font-bold">
                      {(outs.river_hit_pct * 100).toFixed(1)}%
                    </span>
                  </div>
                </div>
              )}

              {/* Pot Odds + Decision */}
              {!loading && potOdds && (
                <div className={`rounded-xl p-4 space-y-3 border
                  ${potOdds.decision === 'call'
                    ? 'bg-emerald-950/40 border-emerald-500/50'
                    : 'bg-red-950/40 border-red-500/50'}`}>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 text-xs font-bold
                      ${potOdds.decision === 'call' ? 'text-emerald-300' : 'text-red-300'}">
                      <DollarSign className="w-3.5 h-3.5" /> 底池赔率 & 决策建议
                    </div>
                    <div className={`flex items-center gap-1 font-black text-sm
                      ${potOdds.decision === 'call' ? 'text-emerald-300' : 'text-red-300'}`}>
                      {potOdds.decision === 'call'
                        ? <CheckCircle2 className="w-4 h-4" />
                        : <AlertCircle className="w-4 h-4" />}
                      {potOdds.decision === 'call' ? '建议 CALL' : '建议 FOLD'}
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <div className="bg-slate-900/60 rounded-lg px-3 py-2">
                      <div className="text-slate-500 text-[10px]">底池</div>
                      <div className="text-amber-300 font-black">{potOdds.pot_size}</div>
                    </div>
                    <div className="bg-slate-900/60 rounded-lg px-3 py-2">
                      <div className="text-slate-500 text-[10px]">需跟注</div>
                      <div className="text-amber-300 font-black">{potOdds.to_call}</div>
                    </div>
                  </div>

                  <div className="flex items-center justify-between text-[11px]">
                    <span className="text-slate-400">底池赔率</span>
                    <span className="text-slate-200 font-mono">
                      {potOdds.to_call} : {potOdds.pot_size} = {(potOdds.pot_odds_pct * 100).toFixed(1)}%
                    </span>
                  </div>

                  <div className="flex items-center justify-between text-[11px]">
                    <span className="text-slate-400">需要的最低胜率</span>
                    <span className="text-slate-200 font-mono">
                      ≥ {(potOdds.need_rate * 100).toFixed(1)}%
                    </span>
                  </div>

                  <div className={`text-[11px] pt-2 border-t border-slate-700/50 text-center
                    ${potOdds.decision === 'call' ? 'text-emerald-300' : 'text-red-300'}`}>
                    {potOdds.reason}
                  </div>
                </div>
              )}

              {/* Draw outcome distribution (river-end) */}
              {!loading && drawProbs && (
                <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-4 space-y-2">
                  <div className="flex items-center gap-2 text-xs text-slate-400 font-bold">
                    <Sparkles className="w-3.5 h-3.5 text-purple-400" /> 河牌终局成牌概率
                  </div>
                  <div className="space-y-1.5 pt-1">
                    {sortedCategoryEntries(drawProbs)
                      .filter((e) => e.pct >= 0.005)
                      .map((e) => (
                        <CategoryBar key={e.cat} name={e.name} pct={e.pct} />
                      ))}
                    {sortedCategoryEntries(drawProbs).length === 0 && (
                      <div className="text-[11px] text-slate-500">暂无数据</div>
                    )}
                  </div>
                </div>
              )}

              <div className="text-center pt-1 pb-6">
                <button
                  onClick={runCalculation}
                  className="text-[11px] text-purple-300 hover:text-purple-200 underline cursor-pointer"
                >
                  ↻ 重新计算
                </button>
              </div>
            </div>
          </div>
        ),
        document.body
      )}
    </>
  );
}
