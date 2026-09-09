import React, { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { X, ArrowLeft, ChevronRight, History } from 'lucide-react';
import StatisticsPanel from './StatisticsPanel';
import { getNextNetSortOrder, getNetSortQueryParams, getNetSortTooltip } from '../utils/handSort';

const button = 'rounded-xl border border-slate-700 px-3 py-2 text-xs text-slate-200 hover:bg-slate-800 focus-visible:ring-2 focus-visible:ring-amber-400 disabled:opacity-40';
const signed = value => `${value > 0 ? '+' : ''}${Number(value || 0).toLocaleString('zh-CN')}`;
const tone = value => value > 0 ? 'text-emerald-400' : value < 0 ? 'text-rose-400' : 'text-slate-300';
const date = value => new Date(value * 1000).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });

function useHistoryData(url, token) {
  const [state, setState] = useState({});
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setState({ url });
    fetch(url, { signal: controller.signal, headers: { Authorization: `Bearer ${token}` } })
      .then(async response => {
        if (!response.ok) throw new Error('历史记录加载失败，请重试');
        return response.json();
      })
      .then(data => { if (!controller.signal.aborted) setState({ url, data }); })
      .catch(error => { if (!controller.signal.aborted) setState({ url, error: error.message }); });
    return () => controller.abort();
  }, [url, token, retry]);
  return { ...(state.url === url ? state : {}), reload: () => setRetry(n => n + 1) };
}

function LoadState({ error, reload }) {
  return error ? <div role="alert" className="py-8 text-center text-sm text-rose-300">{error}<button className={`${button} block mx-auto mt-3`} onClick={reload}>重试</button></div>
    : <p role="status" className="py-12 text-center text-sm text-slate-400">正在加载历史记录…</p>;
}

function Pager({ page, total, size, setPage }) {
  return <nav aria-label="历史记录分页" className="flex items-center justify-between gap-2 pt-3 text-xs text-slate-400">
    <span>共 {total} 条 · 第 {page + 1} / {Math.max(1, Math.ceil(total / size))} 页</span>
    <div className="flex gap-2"><button className={button} disabled={!page} onClick={() => setPage(page - 1)}>上一页</button><button className={button} disabled={(page + 1) * size >= total} onClick={() => setPage(page + 1)}>下一页</button></div>
  </nav>;
}

function Cards({ cards = [] }) {
  const suits = { s: '♠', h: '♥', c: '♣', d: '♦', spades: '♠', hearts: '♥', clubs: '♣', diamonds: '♦' };
  return <div className="flex gap-1 min-h-9 items-center">{cards.length ? cards.map((card, index) => {
    const suit = card.suit_symbol || suits[card.suit] || '';
    const rank = card.rank_symbol || ({ 11: 'J', 12: 'Q', 13: 'K', 14: 'A' }[card.rank]) || card.rank;
    return <span key={index} className={`inline-flex items-center justify-center gap-0.5 rounded-md bg-slate-100 border border-white/70 shadow-sm h-9 min-w-8 px-1 text-sm font-black ${['♥', '♦'].includes(suit) ? 'text-red-600' : 'text-slate-950'}`}>{rank}{suit}</span>;
  }) : <span className="text-xs text-slate-500">未发出</span>}</div>;
}

function Summary({ items }) {
  return <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">{items.map(([label, value, color]) => <div key={label} className="rounded-2xl border border-slate-800 bg-gradient-to-br from-slate-900 to-slate-950 p-3"><p className="text-[11px] text-slate-400">{label}</p><p className={`mt-1 text-xl font-black tabular-nums ${color || 'text-amber-200'}`}>{value}</p></div>)}</div>;
}

export function HandHistoryPanel({ token, userId, roomId }) {
  const [page, setPage] = useState(0);
  const [sort, setSort] = useState('none');
  const params = new URLSearchParams({ limit: '20', offset: String(page * 20), ...getNetSortQueryParams(sort) });
  if (roomId) params.set('room_id', roomId);
  const { data, error, reload } = useHistoryData(`/api/hands/my?${params}`, token);
  const actions = { FOLD: '弃牌', CHECK: '过牌', CALL: '跟注', BET: '下注至', RAISE: '加注至', ALL_IN: '全下至', POST_SB: '小盲', POST_BB: '大盲' };
  const streets = { PREFLOP: '翻牌前', FLOP: '翻牌', TURN: '转牌', RIVER: '河牌', SHOWDOWN: '摊牌' };
  return <div className="space-y-4">
    <div className="flex items-center justify-between"><h3 className="text-sm font-bold text-slate-100">逐手记录</h3><button className={button} title={getNetSortTooltip(sort)} onClick={() => { setSort(getNextNetSortOrder(sort)); setPage(0); }}>净结果 {sort === 'none' ? '↕' : sort === 'asc' ? '↑' : '↓'}</button></div>
    {!data ? <LoadState error={error} reload={reload} /> : <>
      <Summary items={[
        ['累计手数', data.total], ['净筹码', signed(data.summary.net_chips), tone(data.summary.net_chips)],
        ['最大赢牌', signed(data.summary.biggest_win?.net_chips), 'text-emerald-400'], ['最大输牌', signed(data.summary.biggest_loss?.net_chips), 'text-rose-400'],
      ]} />
      {!data.hands.length && <p className="py-12 text-center text-slate-400 text-sm">暂无已完成的牌局记录</p>}
      <div className="space-y-3">{data.hands.map(hand => <article key={hand.hand_id} className="rounded-2xl border border-slate-800 bg-slate-900/40 overflow-hidden">
        <div className="p-4 flex justify-between gap-3 border-b border-slate-800/70">
          <div className="min-w-0"><h4 className="font-bold text-sm text-slate-100 break-words">{hand.room_name} <span className="text-amber-300">#{hand.hand_number}</span></h4><p className="mt-1 text-[11px] text-slate-500">{date(hand.ended_at)} · {hand.money_mode === 'play' ? '娱乐局' : '现金局'} · {hand.small_blind}/{hand.big_blind}</p></div>
          <div className={`text-right shrink-0 ${tone(hand.net_chips)}`}><p className="text-xl font-black tabular-nums">{signed(hand.net_chips)}</p><p className="text-[10px]">{hand.money_mode === 'real' ? `${signed(hand.net_cash)} 元` : '筹码'}</p></div>
        </div>
        <div className="p-4 grid gap-4 sm:grid-cols-[1fr_1.5fr_1fr]">
          <div><p className="text-[10px] text-slate-500 mb-2">我的手牌</p><Cards cards={hand.hole_cards} /><p className="text-xs text-amber-200 mt-2">{hand.hand_description || '—'}</p></div>
          <div><p className="text-[10px] text-slate-500 mb-2">公共牌{hand.board_2?.length ? ' · 牌面 1' : ''}</p><Cards cards={hand.board} />{!!hand.board_2?.length && <div className="mt-2"><p className="text-[10px] text-slate-500 mb-1">牌面 2</p><Cards cards={hand.board_2} /></div>}</div>
          <dl className="text-xs space-y-2 text-slate-400">{[['底池', hand.total_pot], ['投入 / 收回', `${hand.contributed_chips} / ${hand.payout_chips}`], ['筹码变化', `${hand.starting_chips} → ${hand.ending_chips}`]].map(([k, v]) => <div key={k} className="flex justify-between gap-2"><dt>{k}</dt><dd className="text-slate-200 tabular-nums">{v}</dd></div>)}</dl>
        </div>
        <details className="border-t border-slate-800/70 text-xs"><summary className="cursor-pointer px-4 py-3 text-slate-400 hover:text-amber-200">行动过程 · {hand.actions?.length || 0} 次</summary><ol className="px-4 pb-4 space-y-2">{(hand.actions || []).map((action, index) => <li key={index} className={`flex gap-3 rounded-lg px-3 py-2 ${action.player_id === userId ? 'bg-amber-950/30 text-amber-200' : 'bg-slate-950/70 text-slate-400'}`}><span className="w-12 shrink-0 text-slate-500">{streets[action.street] || action.street}</span><span className="flex-1 break-words">{action.player_id === userId ? '我' : action.player_name || '玩家'}</span><span className="shrink-0">{actions[action.action] || action.action}{action.amount > 0 ? ` ${action.amount}` : ''}</span></li>)}</ol></details>
      </article>)}</div>
      <Pager page={page} total={data.total} size={20} setPage={setPage} />
    </>}
  </div>;
}

function Stats({ token, roomId }) {
  const { data, error, reload } = useHistoryData(`/api/statistics/my${roomId ? `?room_id=${encodeURIComponent(roomId)}` : ''}`, token);
  return data ? <StatisticsPanel data={data} /> : <LoadState error={error} reload={reload} />;
}

function Overview({ token, userId }) {
  const { data, error, reload } = useHistoryData(`/api/users/${encodeURIComponent(userId)}/overview`, token);
  return <div className="space-y-4">
    {!data ? <LoadState error={error} reload={reload} /> : <Summary items={[
      ['累计手数', data.total], ['净筹码', signed(data.summary.net_chips), tone(data.summary.net_chips)],
      ['现金局净额（元）', signed(data.summary.net_cash), tone(data.summary.net_cash)],
      ['最大赢牌', signed(data.summary.biggest_win?.net_chips), 'text-emerald-400'],
    ]} />}
    {data && <StatisticsPanel data={data.statistics} />}
  </div>;
}

function TableHistory({ token, onSelect }) {
  const [page, setPage] = useState(0);
  const { data, error, reload } = useHistoryData(`/api/tables/my?limit=12&offset=${page * 12}`, token);
  if (!data) return <LoadState error={error} reload={reload} />;
  return <div className="space-y-3"><p className="text-xs text-slate-400">共 {data.total} 张牌桌 · 按最近参与时间排列</p>
    {!data.total && <p className="py-12 text-center text-slate-400">暂无历史牌桌</p>}
    <div className="grid gap-3 sm:grid-cols-2">{data.tables.map(table => <button key={table.room_id} onClick={() => onSelect(table)} className="text-left p-4 rounded-2xl border border-slate-800 bg-gradient-to-br from-slate-900 to-slate-950 hover:border-amber-500/50 focus-visible:ring-2 focus-visible:ring-amber-400 transition">
      <div className="flex justify-between items-center gap-2"><h3 className="font-bold text-slate-100 truncate">{table.room_name}</h3><ChevronRight size={16} className="text-amber-300 shrink-0" /></div>
      <p className="text-[10px] text-slate-500 mt-1">{date(table.last_hand_at)} · 最近参与</p>
      <div className="flex items-end justify-between gap-2 mt-5"><div><p className="text-[10px] text-slate-500">净筹码</p><p className={`text-2xl font-black tabular-nums ${tone(table.net_chips)}`}>{signed(table.net_chips)}</p></div><span className="text-xs text-slate-400">{table.hands} 手 · 赢 {table.winning_hands} 手</span></div>
      <p className="text-[11px] text-slate-500 mt-3">最近配置 {table.small_blind}/{table.big_blind} · {table.money_mode === 'play' ? '娱乐局' : '现金局'} <span className="float-right text-amber-200">查看数据与牌运</span></p>
    </button>)}</div><Pager page={page} total={data.total} size={12} setPage={setPage} /></div>;
}

export default function PersonalHistory({ currentUser, profileUser = currentUser, token, onClose }) {
  const isSelf = profileUser.user_id === currentUser.user_id;
  const [tab, setTab] = useState('overview');
  const [table, setTable] = useState(null);
  const dialog = useRef(null);
  useEffect(() => {
    const previous = document.activeElement;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    dialog.current?.querySelector('button')?.focus();
    const keydown = event => {
      if (event.key === 'Escape') { event.preventDefault(); onClose(); }
      if (event.key === 'Tab') {
        const nodes = [...dialog.current.querySelectorAll('button:not(:disabled), summary')].filter(node => node.getClientRects().length);
        const first = nodes[0], last = nodes[nodes.length - 1];
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
        if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
      }
    };
    window.addEventListener('keydown', keydown);
    return () => { window.removeEventListener('keydown', keydown); document.body.style.overflow = overflow; previous?.focus(); };
  }, [onClose]);
  return createPortal(<div className="fixed inset-0 z-[140] bg-black/80 backdrop-blur-md flex items-center justify-center p-2 sm:p-6" onClick={onClose}>
    <section ref={dialog} role="dialog" aria-modal="true" aria-labelledby="personal-history-title" onClick={event => event.stopPropagation()} className="w-full max-w-5xl max-h-[92dvh] flex flex-col rounded-3xl border border-amber-500/30 bg-slate-950 text-slate-100 shadow-2xl overflow-hidden">
      <header className="flex items-center gap-3 p-4 sm:p-6 border-b border-slate-800 bg-gradient-to-r from-amber-950/30 to-slate-950"><span className="text-3xl p-2 bg-slate-900 rounded-2xl">{profileUser.avatar || '👤'}</span><div className="flex-1 min-w-0"><h2 id="personal-history-title" className="font-black text-lg truncate">{profileUser.nickname || profileUser.username} · 个人档案</h2><p className="text-xs text-slate-400 mt-1">历史战绩与牌运统计</p></div><button onClick={onClose} className={button} aria-label="关闭个人历史"><X size={20} /></button></header>
      <div className="flex gap-2 px-4 sm:px-6 py-3 border-b border-slate-800">{(isSelf ? [['overview', '历史总览'], ['tables', '历次牌桌'], ['hands', '逐手记录']] : [['overview', '历史总览']]).map(([value, label]) => <button key={value} aria-pressed={tab === value} onClick={() => { setTab(value); setTable(null); }} className={`px-4 py-2 rounded-xl text-xs font-bold ${tab === value ? 'bg-amber-400 text-slate-950' : 'bg-slate-900 text-slate-400 hover:text-white'}`}>{label}</button>)}</div>
      <div className="overflow-y-auto overscroll-contain p-4 sm:p-6 space-y-5">
        {(!isSelf || tab === 'overview') && <><div className="flex items-center gap-2 text-amber-200"><History size={18} /><h3 className="font-bold">{isSelf ? '我的累计表现' : '累计表现'}</h3></div><Overview token={token} userId={profileUser.user_id} /><p className="text-xs text-slate-500">统计包含已记录的现金局与娱乐局，离桌后更新，仅计已完成手牌。</p></>}
        {isSelf && tab === 'tables' && (!table ? <TableHistory token={token} onSelect={setTable} /> : <>
          <button className={`${button} inline-flex items-center gap-1`} onClick={() => setTable(null)}><ArrowLeft size={14} />全部牌桌</button>
          <div><h3 className="text-xl font-black break-words">{table.room_name}</h3><p className="text-xs text-slate-500 mt-1">记录范围 {date(table.first_hand_at)} — {date(table.last_hand_at)}</p></div>
          <Summary items={[
            ['净筹码', signed(table.net_chips), tone(table.net_chips)], ['现金局净额（元）', signed(table.net_cash), tone(table.net_cash)],
            ['累计投入', table.contributed_chips], ['累计收回', table.payout_chips],
          ]} />
          <Stats token={token} roomId={table.room_id} />
          <HandHistoryPanel key={table.room_id} token={token} userId={currentUser.user_id} roomId={table.room_id} />
        </>)}
        {isSelf && tab === 'hands' && <HandHistoryPanel token={token} userId={currentUser.user_id} />}
      </div>
    </section>
  </div>, document.body);
}
