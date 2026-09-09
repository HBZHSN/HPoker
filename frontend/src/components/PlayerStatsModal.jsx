import React, { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { X } from 'lucide-react';

import StatisticsPanel from './StatisticsPanel';

export default function PlayerStatsModal({ player, roomId, currentUserId, token, handNumber, street, onClose }) {
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
    const url = `/api/rooms/${encodeURIComponent(roomId)}/players/${encodeURIComponent(player.player_id)}/statistics`;
    fetch(url, { signal: controller.signal, headers: token ? { Authorization: `Bearer ${token}` } : {} })
      .then(async response => {
        if (!response.ok) throw new Error('统计加载失败，请重试');
        return response.json();
      })
      .then(setData)
      .catch(err => { if (err.name !== 'AbortError') setError(err.message); });
    return () => controller.abort();
  }, [roomId, player.player_id, token, handNumber, street, retry]);

  return createPortal(
    <div className="fixed inset-0 z-[150] bg-black/75 backdrop-blur-sm flex items-center justify-center p-4" onClick={onClose}>
      <section ref={dialog} role="dialog" aria-modal="true" aria-labelledby="player-stats-title" onClick={event => event.stopPropagation()}
        className="w-full max-w-sm max-h-[85dvh] overflow-y-auto rounded-2xl border border-amber-500/30 bg-slate-950 p-5 text-slate-100 shadow-2xl">
        <header className="flex items-center gap-3 mb-4">
          <span className="text-3xl" aria-hidden="true">{player.avatar || '👤'}</span>
          <div className="min-w-0 flex-1"><h2 id="player-stats-title" className="font-bold truncate">{player.name}</h2><p className="text-xs text-slate-400">本局数据</p></div>
          <button type="button" onClick={onClose} aria-label="关闭统计" className="p-2 rounded-lg hover:bg-slate-800"><X size={20} /></button>
        </header>
        {error ? <div role="alert" className="text-center py-8 text-sm text-slate-400">{error}<button type="button" className="block mx-auto mt-3 text-amber-300 p-2" onClick={() => setRetry(n => n + 1)}>重试</button></div>
          : !data ? <p role="status" className="text-center py-12 text-slate-400">加载中…</p>
          : <>
            <StatisticsPanel data={data} showLuckDetails={isSelf} />
          </>}
      </section>
    </div>, document.body,
  );
}
