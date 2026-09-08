import React, { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { X } from 'lucide-react';

const luckDimensions = [
  ['starting', '起手牌运', '35%'],
  ['board', '公共牌运', '25%'],
  ['matchup', '对位牌运', '20%'],
  ['all_in', '全下兑现', '20%'],
];

const metrics = [
  ['vpip', 'VPIP', '翻牌前主动投入筹码的手数 / 已完成手数'],
  ['pfr', 'PFR', '翻牌前加注的手数 / 已完成手数'],
  ['three_bet', '3Bet', '翻牌前首次再加注的手数 / 有再加注机会的手数'],
  ['win_rate', '胜率', '净赢筹码的手数 / 已完成手数'],
  ['collect_rate', '收池率', '获得奖池（含平分）的手数 / 已完成手数；不含单纯退回下注'],
  ['showdown_rate', '摊牌率', '参与摊牌的手数 / 已完成手数'],
];

export default function PlayerStatsModal({ player, roomId, currentUserId, token, handNumber, street, onClose }) {
  const [scope, setScope] = useState('table');
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [retry, setRetry] = useState(0);
  const dialog = useRef(null);
  const isSelf = player.player_id === currentUserId;

  useEffect(() => {
    const previous = document.activeElement;
    dialog.current?.querySelector('button')?.focus();
    const onKey = (event) => {
      // Capture before table shortcuts: inspecting stats must never place a bet.
      event.stopImmediatePropagation();
      if (event.key === 'Escape') { event.preventDefault(); onClose(); }
      if (event.key === 'Tab') {
        const buttons = [...dialog.current.querySelectorAll('button, summary')];
        const first = buttons[0], last = buttons[buttons.length - 1];
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
      }
    };
    window.addEventListener('keydown', onKey, true);
    return () => { window.removeEventListener('keydown', onKey, true); previous?.focus(); };
  }, [onClose]);

  useEffect(() => {
    const controller = new AbortController();
    setData(null); setError('');
    const url = scope === 'history' && isSelf
      ? '/api/statistics/my'
      : `/api/rooms/${encodeURIComponent(roomId)}/players/${encodeURIComponent(player.player_id)}/statistics`;
    fetch(url, { signal: controller.signal, headers: token ? { Authorization: `Bearer ${token}` } : {} })
      .then(async response => {
        if (!response.ok) throw new Error('统计加载失败，请重试');
        return response.json();
      })
      .then(setData)
      .catch(err => { if (err.name !== 'AbortError') setError(err.message); });
    return () => controller.abort();
  }, [roomId, player.player_id, scope, isSelf, token, handNumber, street, retry]);

  return createPortal(
    <div className="fixed inset-0 z-[150] bg-black/75 backdrop-blur-sm flex items-center justify-center p-4" onClick={onClose}>
      <section ref={dialog} role="dialog" aria-modal="true" aria-labelledby="player-stats-title" onClick={event => event.stopPropagation()}
        className="w-full max-w-sm max-h-[85dvh] overflow-y-auto rounded-2xl border border-amber-500/30 bg-slate-950 p-5 text-slate-100 shadow-2xl">
        <header className="flex items-center gap-3 mb-4">
          <span className="text-3xl" aria-hidden="true">{player.avatar || '👤'}</span>
          <div className="min-w-0 flex-1"><h2 id="player-stats-title" className="font-bold truncate">{player.name}</h2><p className="text-xs text-slate-400">{scope === 'history' ? '个人历史累计' : '本桌公开数据'}</p></div>
          <button type="button" onClick={onClose} aria-label="关闭统计" className="p-2 rounded-lg hover:bg-slate-800"><X size={20} /></button>
        </header>
        {isSelf && <div className="grid grid-cols-2 gap-1 rounded-xl bg-slate-900 p-1 mb-4">
          {[['table', '本桌'], ['history', '历史累计']].map(([value, label]) => <button type="button" key={value} aria-pressed={scope === value} onClick={() => setScope(value)} className={`rounded-lg py-2 text-sm font-bold ${scope === value ? 'bg-amber-400 text-slate-950' : 'text-slate-400'}`}>{label}</button>)}
        </div>}
        {error ? <div role="alert" className="text-center py-8 text-sm text-slate-400">{error}<button type="button" className="block mx-auto mt-3 text-amber-300 p-2" onClick={() => setRetry(n => n + 1)}>重试</button></div>
          : !data ? <p role="status" className="text-center py-12 text-slate-400">加载中…</p>
          : <>
            <p className="text-xs text-slate-400 mb-3">已完成 {data.hands} 手{data.hands < 30 ? ' · 样本较少' : ''}</p>
            <div className="grid grid-cols-3 gap-2">
              {metrics.map(([key, label, help]) => <div key={key} title={help} className="rounded-xl border border-slate-800 bg-slate-900/60 px-2 py-3 text-center">
                <p className="text-xs text-slate-400 mb-1">{label}</p><p className="font-bold text-lg tabular-nums">{data[key] == null ? '—' : `${data[key]}%`}</p>
              </div>)}
            </div>
            <div className="mt-3 rounded-xl border border-amber-500/25 bg-amber-950/15 p-3">
              <div className="flex justify-between items-baseline"><span className="text-sm text-amber-200">综合牌运</span><span className="text-xl font-bold text-amber-300">{data.luck}<span className="text-xs text-slate-500"> / 100</span></span></div>
              <div className="relative h-1.5 rounded-full bg-slate-800 my-2"><div className="h-full rounded-full bg-gradient-to-r from-slate-500 to-amber-400" style={{ width: `${data.luck}%` }} /><span className="absolute left-1/2 top-0 h-full w-px bg-white/60" /></div>
              <p className="text-xs text-slate-400">{data.luck_samples ? `${data.luck_samples} 手起手样本 · 50 为中性` : '暂无有效样本 · 暂记中性 50'}</p>
              <div className="mt-3 grid grid-cols-2 gap-2">
                {luckDimensions.map(([key, label, weight]) => {
                  const dimension = data.luck_dimensions?.[key];
                  return <div key={key} className="rounded-lg bg-slate-950/50 p-2">
                    <div className="flex justify-between gap-2 text-xs"><span className="text-slate-300">{label}</span><span className="text-slate-500">{weight}</span></div>
                    <div className="mt-1 flex items-baseline justify-between gap-2"><span className="font-bold tabular-nums text-amber-200">{dimension?.score ?? 50}</span><span className="text-[10px] text-slate-400">{dimension?.samples ? `${dimension.samples} 手` : '暂无样本'}</span></div>
                  </div>;
                })}
              </div>
            </div>
            <details className="mt-4 text-xs text-slate-400 leading-relaxed">
              <summary className="cursor-pointer py-1">统计口径</summary>
              <div className="mt-2 space-y-2">
                {metrics.map(([key, label, help]) => <p key={key}>{label}：{help}。</p>)}
                <p>3Bet 机会 {data.three_bet_opportunities} 手。无分母时显示 —，当前未结束的手牌不计入。</p>
                <p>综合牌运按起手 35%、公共牌 25%、对位 20%、全下 20% 加权。各维度 50 为中性、范围 0–100；缺少样本时记 50，小样本向中性收缩。</p>
                <p>起手牌运：按全部 1,326 种组合加权的起手强度百分位；包含弃牌和未亮底牌。本桌公开展示完整分数及四维统计，每手结束后更新。</p>
                <p>公共牌运：仍在参与时，实际公共牌下对随机对手的牌力减去起手预期；弃牌后的发牌不计入。</p>
                <p>对位牌运：完整公开摊牌时，实际比牌份额减去面对同人数随机对手的预期份额，反映大牌相撞等对位结果。</p>
                <p>全下兑现：主池、边池分别比较下注与资格锁定时的理论份额和最终份额；按底池 BB 数的平方根加权，上限 4。退款、河牌后投入不计，双牌面取平均，平局平分；不计奇数筹码和辅助折让。</p>
                <p>各维度使用 50 + 50 × 加权差值总和 ÷（样本权重总和 + 10）。起手百分位先映射到 −1 至 1，其余用实际与预期份额之差。期望值采用固定模拟估算，全下转牌时精确枚举。</p>
                <p>牌运描述已记录样本，仍受参与和摊牌选择影响，不代表技术、净盈利或下一手胜率。历史按原始统计量累计，记录缺失的维度不补造样本。</p>
              </div>
            </details>
          </>}
      </section>
    </div>, document.body,
  );
}
