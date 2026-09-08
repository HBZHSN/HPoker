import React, { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { X } from 'lucide-react';

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
              <div className="flex justify-between items-baseline"><span className="text-sm text-amber-200">河牌运气</span><span className="text-xl font-bold text-amber-300">{data.luck}<span className="text-xs text-slate-500"> / 100</span></span></div>
              <div className="relative h-1.5 rounded-full bg-slate-800 my-2"><div className="h-full rounded-full bg-gradient-to-r from-slate-500 to-amber-400" style={{ width: `${data.luck}%` }} /><span className="absolute left-1/2 top-0 h-full w-px bg-white/60" /></div>
              <p className="text-xs text-slate-400">{data.luck_samples ? `${data.luck_samples} 手有效摊牌 · 50 为中性` : '暂无有效摊牌样本 · 暂记中性 50'}</p>
            </div>
            <details className="mt-4 text-xs text-slate-400 leading-relaxed">
              <summary className="cursor-pointer py-1">统计口径</summary>
              <div className="mt-2 space-y-2">
                {metrics.map(([key, label, help]) => <p key={key}>{label}：{help}。</p>)}
                <p>3Bet 机会 {data.three_bet_opportunities} 手。无分母时显示 —，当前未结束的手牌不计入。</p>
                <p>运气仅衡量完整公开摊牌的河牌变化：实际比牌份额减去转牌时所有可能河牌的平均份额。50 + 50 × 差值总和 ÷（样本数 + 10），限制在 0–100；平局按人数平分，双牌面不计入。</p>
                <p>这是所选摊牌样本的河牌运气，非全下 EV、盈利能力或下一手胜率；不使用未公开底牌。历史累计包含留存的全部牌局。</p>
              </div>
            </details>
          </>}
      </section>
    </div>, document.body,
  );
}
