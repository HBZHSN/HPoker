import React, { useState, useEffect, useMemo, useCallback, useRef } from 'react';
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
  Eye,
  EyeOff,
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

/** Header toggle button for equity analysis */
export function EquityTrigger({
  isOpen = false,
  onToggle,
}) {
  return (
    <button
      onClick={onToggle}
      className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-bold border transition active:scale-95 cursor-pointer shadow ${
        isOpen
          ? 'bg-gradient-to-r from-purple-700 to-indigo-700 text-white border-purple-300 shadow-glow-cyan'
          : 'bg-gradient-to-r from-purple-950/80 to-indigo-950/80 hover:from-purple-900 hover:to-indigo-900 text-purple-200 border-purple-500/50'
      }`}
      title={isOpen ? '收起胜率分析' : '展开胜率分析'}
    >
      <BarChart3 className="w-3.5 h-3.5 text-amber-400" />
      <span>胜率</span>
      {isOpen ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
    </button>
  );
}

/** Equity analysis side panel (renders in-flow to compress the table) */
export default function EquityDrawer({
  isOpen = false,
  onClose,
  holeCards = [],
  boardCards = [],
  street = 'IDLE',
  numOpponents = 1,
  potSize = 0,
  toCall = 0,
  isSeated = true,
  isFolded = false,
  handNumber = 0,
  onUseAssistant,
}) {
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState(null);
  const [result, setResult] = useState(null);
  const [isBlurred, setIsBlurred] = useState(false);

  const prevHandNumberRef = useRef(handNumber);
  const prevStreetRef = useRef(street);
  const prevIsOpenRef = useRef(isOpen);

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
    if (street === 'IDLE') return false;
    if (!holeCards || holeCards.length < 2) return false;
    return true;
  }, [holeKey, street]);

  // Handle hand transition & end blurring
  useEffect(() => {
    // When a hand ends, blur the analysis
    if (street === 'HAND_END' && prevStreetRef.current !== 'HAND_END') {
      setIsBlurred(true);
    }
    // When hand number changes (new hand starts), blur the analysis
    if (handNumber !== prevHandNumberRef.current && handNumber > 0) {
      setIsBlurred(true);
    }
    prevStreetRef.current = street;
    prevHandNumberRef.current = handNumber;
  }, [street, handNumber]);

  // When user opens the drawer:
  useEffect(() => {
    if (!prevIsOpenRef.current && isOpen) {
      if (street !== 'HAND_END' && street !== 'IDLE') {
        // Auto unblur and notify server
        setIsBlurred(false);
        onUseAssistant?.();
      } else if (street === 'HAND_END') {
        setIsBlurred(true);
      }
    }
    prevIsOpenRef.current = isOpen;
  }, [isOpen, street, onUseAssistant]);

  const handleReveal = useCallback(() => {
    setIsBlurred(false);
    onUseAssistant?.();
  }, [onUseAssistant]);

  const chenScore = useMemo(() => {
    if (holeCards?.length === 2 && (!boardCards || boardCards.length === 0)) {
      return preflopChenScore(holeCards[0], holeCards[1]);
    }
    return null;
  }, [holeKey, boardKey]);

  const handDesc = useMemo(() => currentHandDescription(holeCards, boardCards), [holeKey, boardKey]);

  const runCalculation = useCallback(async () => {
    if (!shouldCompute) {
      if (street === 'IDLE') {
        setResult(null);
      }
      setErrorMsg(null);
      return;
    }
    setLoading(true);
    setErrorMsg(null);

    try {
      const body = {
        hero_cards: holeCards.slice(0, 2).map((c) => ({ notation: c.notation })),
        board_cards: (boardCards || []).map((c) => ({ notation: c.notation })),
        num_opponents: Math.max(1, oppCount),
      };
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
  }, [shouldCompute, holeCards, boardCards, oppCount, potSize, toCall, street]);

  useEffect(() => {
    if (isOpen && shouldCompute) {
      runCalculation();
    }
  }, [isOpen, shouldCompute, holeKey, boardKey, street, oppCount, potSize, toCall, runCalculation]);

  if (!isOpen) return null;

  // ---------- UI Components ----------
  const WinBar = ({ win, tie }) => (
    <div className="w-full h-2.5 bg-slate-800 rounded-full overflow-hidden flex">
      <div
        className="h-full bg-gradient-to-r from-emerald-500 to-emerald-400 transition-all duration-500"
        style={{ width: `${Math.round((win || 0) * 100)}%` }}
      />
      <div
        className="h-full bg-amber-500/80 transition-all duration-500"
        style={{ width: `${Math.round((tie || 0) * 100)}%` }}
      />
      <div
        className="h-full bg-red-500/70 transition-all duration-500"
        style={{ width: `${Math.max(0, Math.round((1 - (win || 0) - (tie || 0)) * 100))}%` }}
      />
    </div>
  );

  const CategoryBar = ({ name, pct }) => {
    const pctClamp = Math.max(0, Math.min(1, pct));
    const tierClass =
      pctClamp >= 0.05
        ? 'from-emerald-500 to-teal-400'
        : pctClamp >= 0.01
        ? 'from-amber-500 to-amber-400'
        : 'from-slate-600 to-slate-500';
    return (
      <div className="flex items-center gap-2 text-xs">
        <span className="w-20 text-slate-300 font-bold flex-shrink-0">{name}</span>
        <div className="flex-1 h-2 bg-slate-800 rounded-full overflow-hidden">
          <div
            className={`h-full bg-gradient-to-r ${tierClass} transition-all duration-700`}
            style={{ width: `${Math.round(pctClamp * 100)}%` }}
          />
        </div>
        <span className="w-12 text-right font-mono text-amber-300">
          {(pctClamp * 100).toFixed(1)}%
        </span>
      </div>
    );
  };

  // ---------- Render ----------
  const equity = result?.equity;
  const drawProbs = result?.drawProbabilities;
  const outs = result?.outs;
  const potOdds = result?.potOdds;

  return (
    <>
      {/* Mobile backdrop for < lg */}
      <div
        className="fixed inset-0 bg-black/60 z-40 lg:hidden backdrop-blur-sm animate-fade-in"
        onClick={onClose}
      />

      {/* Main in-flow sidebar on desktop (compresses table), drawer overlay on mobile */}
      <aside className="poker-table-equity fixed inset-y-0 left-0 w-[320px] max-w-[85vw] z-50 lg:static lg:inset-auto lg:h-full lg:w-72 xl:w-80 2xl:w-[350px] lg:z-20 lg:flex-shrink-0 bg-gradient-to-b from-slate-900 via-slate-950 to-slate-900 border-r border-purple-500/40 shadow-2xl overflow-y-auto flex flex-col animate-slide-in-left lg:animate-none select-none">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 bg-gradient-to-r from-purple-900/60 to-indigo-900/60 border-b border-purple-500/30 sticky top-0 z-10 flex-shrink-0">
          <div className="flex items-center gap-2">
            <Dices className="w-4 h-4 text-amber-400" />
            <span className="text-sm font-black text-purple-100 tracking-wide">
              胜率分析
            </span>
          </div>
          {onClose && (
            <button
              onClick={onClose}
              className="text-purple-200 hover:text-white text-lg leading-none cursor-pointer px-2 py-1 rounded-lg hover:bg-purple-500/20 transition"
              title="收起胜率分析"
            >
              ✕
            </button>
          )}
        </div>

        <div className="px-4 py-3 space-y-3 flex-1 relative min-h-0">
          {!shouldCompute ? (
            <div className="flex flex-col items-center justify-center py-16 px-4 text-center space-y-3 text-slate-400">
              <div className="w-12 h-12 rounded-2xl bg-purple-950/50 border border-purple-500/30 flex items-center justify-center text-purple-300">
                <Dices className="w-6 h-6 animate-pulse text-amber-400" />
              </div>
              <div className="text-sm font-bold text-slate-300">
                {street === 'IDLE'
                  ? '等待开局发牌'
                  : !isSeated
                  ? '未入座'
                  : '等待发牌'}
              </div>
              <p className="text-xs text-slate-500 max-w-[220px] leading-relaxed">
                {street === 'IDLE'
                  ? '牌局尚未开始，开局发牌后将在此实时展示胜率与决策建议。'
                  : !isSeated
                  ? '入座参与对局后，此处将自动展示实时胜率与跟注建议。'
                  : '手牌发给玩家后，将实时计算胜率、Outs 及底池赔率。'}
              </p>
            </div>
          ) : (
            <div className="relative">
              {/* Blur Overlay & Reveal Button */}
              {isBlurred && (
                <div className="absolute inset-x-0 top-6 z-30 flex flex-col items-center justify-center p-5 bg-slate-900/95 border border-purple-500/50 rounded-2xl shadow-2xl backdrop-blur-md text-center animate-fade-in">
                  <div className="w-11 h-11 rounded-full bg-purple-950/80 border border-purple-400/60 flex items-center justify-center mb-2.5 shadow-glow-cyan">
                    <Eye className="w-5 h-5 text-amber-400" />
                  </div>
                  <h4 className="text-sm font-black text-slate-100 mb-1">
                    {street === 'HAND_END' ? '本局已结束（胜率已模糊）' : '胜率分析已模糊锁定'}
                  </h4>
                  <p className="text-xs text-slate-400 mb-3.5 leading-relaxed max-w-[220px]">
                    点击查看将向全桌玩家公开你正在使用辅助功能，并在头像上显示「辅助」标识。
                  </p>
                  <button
                    onClick={handleReveal}
                    className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-purple-600 via-indigo-600 to-purple-700 hover:from-purple-500 hover:to-indigo-500 text-white font-black text-xs rounded-xl shadow-glow-cyan border border-purple-300 transition active:scale-95 cursor-pointer"
                  >
                    <Eye className="w-3.5 h-3.5 text-amber-300" />
                    <span>{street === 'HAND_END' ? '点击查看结算胜率' : '点击查看胜率分析'}</span>
                  </button>
                </div>
              )}

              {/* Main Analysis Content */}
              <div className={`space-y-3 transition-all duration-300 ${isBlurred ? 'filter blur-md pointer-events-none select-none opacity-25' : ''}`}>
                {/* Status line */}
                <div className="flex items-center justify-between text-xs">
                  <span className="text-slate-400">
                    阶段: <span className="text-amber-300 font-black">{STAGE_NAMES[street] || street}</span>
                    {isFolded && <span className="ml-1 text-red-400 font-bold">(已弃牌)</span>}
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
          )}
        </div>
      </aside>
    </>
  );
}
