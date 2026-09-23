import React, { useEffect, useRef, useState } from 'react';
import { BarChart3, ChevronDown, ChevronUp, Loader2 } from 'lucide-react';
import { formatChipAmount, formatHCoins } from '../utils/hCurrency';
import CardView from './CardView';

export function EquityTrigger({ isOpen = false, onToggle }) {
  return (
    <button onClick={onToggle} className={'flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-bold border transition active:scale-95 cursor-pointer shadow ' + (isOpen ? 'bg-gradient-to-r from-purple-700 to-indigo-700 text-white border-purple-300' : 'bg-gradient-to-r from-purple-950/80 to-indigo-950/80 text-purple-200 border-purple-500/50')}>
      <BarChart3 className="w-3.5 h-3.5 text-amber-400" />
      <span>Jev 建议</span>
      {isOpen ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
    </button>
  );
}

const ACTIONS = [
  ['fold', '弃牌 FOLD'],
  ['call', '跟注 CALL'],
  ['raise', '加注 RAISE'],
];

const STREETS = { PREFLOP: '翻牌前', FLOP: '翻牌圈', TURN: '转牌圈', RIVER: '河牌圈' };
const ACTION_NAMES = {
  POST_SB: '下小盲', POST_BB: '下大盲', CHECK: '过牌', CALL: '跟注',
  BET: '下注到', RAISE: '加注到', ALL_IN: '全下到', FOLD: '弃牌',
};
const CHOICES = { fold: '弃牌', call: '过牌／跟注', raise: '下注／加注' };
const STATS = [
  ['vpip', '主动入池率', '%'], ['pfr', '翻前加注率', '%'], ['three_bet', '翻前再加注率', '%'],
  ['win_rate', '历史盈利手率', '%'], ['collect_rate', '收池率', '%'],
  ['showdown_rate', '摊牌率', '%'], ['luck', '综合牌运', ' / 100'],
];
const chips = (value) => value == null ? '暂无' : `${formatChipAmount(value)} 筹码`;
const seatName = (seat) => seat == null ? '未知座位' : `${seat + 1} 号位`;

function RequestCards({ cards = [] }) {
  return cards.length ? <div className="flex flex-wrap gap-1.5">{cards.map((notation, index) =>
    <CardView key={`${notation}-${index}`} size="xs" card={{ rank_symbol: notation.slice(0, -1), suit: notation.slice(-1) }} />
  )}</div> : <span className="text-xs text-slate-500">尚未发牌</span>;
}

function JevRequestDetails({ request }) {
  const { state = {}, questions = {} } = request;
  const legal = state.legal_actions || {};
  const question = questions.action || {};
  const history = state.action_history || state.recent_actions || [];
  const instructions = question.instructions?.replaceAll('public_stats', '对手公开统计').replaceAll('win_rate', '历史盈利手率').replaceAll('null', '无数据');
  const available = [
    legal.can_fold && '弃牌', legal.can_check && '过牌',
    legal.can_call && `跟注 ${chips(legal.call_amount)}`,
    legal.can_bet && `下注 ${chips(legal.min_bet)} 至 ${chips(legal.max_bet)}`,
    legal.can_raise && `加注到 ${chips(legal.min_raise_to)} 至 ${chips(legal.max_raise_to)}`,
    legal.can_all_in && `全下 ${chips(legal.all_in_amount)}`,
  ].filter(Boolean);

  return <div id="jev-request-details" className="space-y-4 rounded-2xl border border-purple-500/30 bg-slate-950/80 p-3 text-xs text-slate-200 select-text">
    <div className="flex items-center justify-between gap-2 border-b border-slate-800 pb-2">
      <h3 className="font-black text-purple-200">发送给 Jev 的牌局信息</h3>
      <span className="text-[10px] text-slate-500">{request.model}</span>
    </div>
    <section className="space-y-2">
      <h4 className="font-bold text-amber-300">牌面</h4>
      <div className="rounded-xl bg-slate-900 p-2 space-y-2"><span className="text-slate-400">我的手牌</span><RequestCards cards={state.hero_cards} /></div>
      <div className="rounded-xl bg-slate-900 p-2 space-y-2"><span className="text-slate-400">公共牌</span><RequestCards cards={state.board_cards} /></div>
    </section>
    <section className="space-y-2">
      <h4 className="font-bold text-amber-300">牌局状态</h4>
      <div className="grid grid-cols-2 gap-1.5">
        {[
          ['游戏', state.game === "Texas Hold'em" ? '德州扑克' : state.game],
          ['阶段', STREETS[state.street] || state.street],
          ['我的座位', seatName(state.hero_seat)], ['庄家座位', seatName(state.dealer_seat)],
          ['我的筹码', chips(state.hero_stack)], ['底池', chips(state.pot)],
          ['小盲 / 大盲', `${chips(state.small_blind)} / ${chips(state.big_blind)}`],
        ].map(([label, value]) => <div key={label} className="rounded-lg bg-slate-900 p-2">
          <div className="text-[10px] text-slate-500">{label}</div><div className="mt-0.5 font-semibold text-slate-100">{value || '暂无'}</div>
        </div>)}
      </div>
    </section>
    <section className="space-y-2">
      <h4 className="font-bold text-amber-300">当前可执行操作</h4>
      <div className="flex flex-wrap gap-1.5">{available.length ? available.map((action) =>
        <span key={action} className="rounded-lg border border-purple-500/30 bg-purple-950/50 px-2 py-1.5">{action}</span>
      ) : <span className="text-slate-500">暂无</span>}</div>
    </section>
    <section className="space-y-2">
      <h4 className="font-bold text-amber-300">对手公开信息</h4>
      {(state.opponents || []).length ? state.opponents.map((opponent, index) => {
        const stats = opponent.public_stats || {};
        return <div key={`${opponent.seat}-${index}`} className="space-y-2 rounded-xl border border-slate-800 bg-slate-900 p-2">
          <div className="flex flex-wrap items-center justify-between gap-1"><strong>{seatName(opponent.seat)}</strong><span className="text-slate-400">{opponent.folded ? '已弃牌' : opponent.all_in ? '已全下' : '在局中'}</span></div>
          <p className="text-slate-400">剩余 {chips(opponent.chips)} · 本轮已下注 {chips(opponent.current_bet)}</p>
          <div className="grid grid-cols-2 gap-1.5">{STATS.map(([key, label, suffix]) =>
            <div key={key} className="rounded-lg bg-slate-950 p-2"><span className="block text-[10px] text-slate-500">{label}</span><strong>{stats[key] == null ? '暂无' : `${stats[key]}${suffix}`}</strong></div>
          )}</div>
          <p className="text-[10px] text-slate-500">已完成 {stats.hands ?? '暂无'} 手 · 再加注机会 {stats.three_bet_opportunities ?? '暂无'} 次 · 牌运样本 {stats.luck_samples ?? '暂无'} 手{stats.updating ? ' · 统计更新中' : ''}</p>
        </div>;
      }) : <p className="text-slate-500">暂无对手</p>}
    </section>
    <section className="space-y-2">
      <h4 className="font-bold text-amber-300">本手全部行动</h4>
      {history.length ? <div className="space-y-1">{history.map((action, index) =>
        <div key={index} className="flex justify-between gap-2 rounded-lg bg-slate-900 px-2 py-1.5">
          <span className="text-slate-400">{STREETS[action.street] || action.street} · {seatName(action.seat)}</span>
          <span className="text-right">{ACTION_NAMES[action.action] || action.action}{action.amount ? ` ${chips(action.amount)}` : ''}</span>
        </div>
      )}</div> : <p className="text-slate-500">暂无行动记录</p>}
    </section>
    <section className="space-y-2 border-t border-slate-800 pt-3">
      <h4 className="font-bold text-amber-300">给 Jev 的分析要求</h4>
      <p className="leading-relaxed text-slate-300">{instructions}</p>
      <div className="space-y-1">{Object.entries(question.criteria || {}).map(([action, description]) =>
        <p key={action} className="rounded-lg bg-slate-900 px-2 py-1.5"><strong className="text-purple-200">{CHOICES[action] || action}</strong>：{description}</p>
      )}</div>
    </section>
  </div>;
}

export default function EquityDrawer({ isOpen, onClose, roomId, token, decisionKey, isMyTurn, toCall }) {
  const [result, setResult] = useState(null);
  const [usesPerCoin, setUsesPerCoin] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [requestOpen, setRequestOpen] = useState(false);
  const loadedDecisionKey = useRef(null);

  useEffect(() => {
    loadedDecisionKey.current = null;
    setResult(null);
    setError('');
    setRequestOpen(false);
  }, [roomId, token]);

  useEffect(() => {
    if (!isOpen) return;
    fetch('/api/config/jev', { headers: { Authorization: 'Bearer ' + token } })
      .then((response) => response.json())
      .then((data) => setUsesPerCoin(data.uses_per_coin))
      .catch(() => setUsesPerCoin(null));
  }, [isOpen, token]);

  useEffect(() => {
    if (!isOpen || !isMyTurn || !decisionKey) {
      setLoading(false);
      return;
    }
    if (loadedDecisionKey.current === decisionKey) return;
    const controller = new AbortController();
    setRequestOpen(false);
    setResult(null);
    setLoading(true);
    setError('');
    fetch('/api/rooms/' + encodeURIComponent(roomId) + '/jev-decision', {
      method: 'POST',
      headers: { Authorization: 'Bearer ' + token },
      signal: controller.signal,
    })
      .then(async (response) => {
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || '获取建议失败');
        return data;
      })
      .then((data) => {
        if (!controller.signal.aborted) {
          loadedDecisionKey.current = decisionKey;
          setResult(data);
        }
      })
      .catch((cause) => { if (cause.name !== 'AbortError') setError(cause.message); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [isOpen, isMyTurn, decisionKey, roomId, token]);

  if (!isOpen) return null;
  const wasCheck = result?.request?.state?.legal_actions?.can_check ?? (toCall === 0);

  return (
    <>
      <button className="fixed inset-0 bg-black/60 z-40 lg:hidden" onClick={onClose} aria-label="关闭 Jev 建议" />
      <aside className="poker-table-equity fixed inset-y-0 left-0 w-[320px] max-w-[85vw] z-50 lg:static lg:inset-auto lg:h-full lg:w-72 xl:w-80 2xl:w-[350px] lg:z-20 lg:flex-shrink-0 bg-gradient-to-b from-slate-900 via-slate-950 to-slate-900 border-r border-purple-500/40 shadow-2xl overflow-y-auto flex flex-col select-none">
        <div className="flex items-center justify-between px-4 py-3 bg-purple-900/60 border-b border-purple-500/30">
          <span className="flex items-center gap-2 text-sm font-black text-purple-100"><BarChart3 size={16} /> Jev 行动建议</span>
          <button onClick={onClose} className="text-purple-200 hover:text-white px-2" aria-label="收起建议">✕</button>
        </div>
        <div className="p-4 space-y-4 text-sm">
          {usesPerCoin !== null && <p className="text-xs text-amber-300">{usesPerCoin ? `1 H币 / ${usesPerCoin} 次` : '免费'}{result && ` · 本次扣费 ${formatHCoins(result.fee)}`}</p>}
          {!isMyTurn && !result && <p className="text-slate-400 py-8 text-center">轮到你行动时显示建议</p>}
          {isMyTurn && loading && <div role="status" className="flex justify-center py-8 text-purple-300"><Loader2 className="animate-spin" /></div>}
          {isMyTurn && !loading && error && <p role="alert" className="text-red-300 bg-red-950/50 rounded-xl p-3">{error}</p>}
          {!loading && result && (
            <>
              {!isMyTurn && <p className="text-xs text-slate-400">上次行动建议</p>}
              <p className="font-bold text-amber-300">推荐：{result.recommendation === 'call' && wasCheck ? '过牌 CHECK' : ACTIONS.find(([key]) => key === result.recommendation)?.[1]}</p>
              {ACTIONS.map(([key, label]) => (
                <div key={key} className={'rounded-xl border p-3 ' + (result.recommendation === key ? 'border-amber-400 bg-amber-500/10' : 'border-slate-700 bg-slate-800/50')}>
                  <div className="flex justify-between font-bold"><span>{key === 'call' && wasCheck ? '过牌 CHECK' : label}</span><span>{(result.probabilities[key] * 100).toFixed(1)}%</span></div>
                  <div className="mt-2 h-1.5 rounded-full bg-slate-700"><div className="h-full rounded-full bg-amber-400" style={{ width: (result.probabilities[key] * 100) + '%' }} /></div>
                </div>
              ))}
              <p className="text-xs text-slate-500">行动概率由 Jev 模型给出。</p>
              {result.request && (
                <div className="space-y-2">
                  <input type="button" value={requestOpen ? '收起发给 Jev 的牌局信息' : '查看发给 Jev 的牌局信息'}
                    onClick={() => setRequestOpen(!requestOpen)} aria-expanded={requestOpen} aria-controls="jev-request-details"
                    className="w-full cursor-pointer rounded-xl border border-purple-500/40 bg-slate-800 px-3 py-2 text-left text-xs font-semibold text-purple-100 hover:bg-slate-700" />
                  {requestOpen && <JevRequestDetails request={result.request} />}
                </div>
              )}
            </>
          )}
        </div>
      </aside>
    </>
  );
}
