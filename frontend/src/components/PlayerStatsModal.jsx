import React, { useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { X } from 'lucide-react';

import StatisticsPanel from './StatisticsPanel';

export default function PlayerStatsModal({ player, currentUserId, data, onClose }) {
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

  return createPortal(
    <div className="fixed inset-0 z-[150] bg-black/75 backdrop-blur-sm flex items-center justify-center p-4" onClick={onClose}>
      <section ref={dialog} role="dialog" aria-modal="true" aria-labelledby="player-stats-title" onClick={event => event.stopPropagation()}
        className="w-full max-w-sm max-h-[85dvh] overflow-y-auto rounded-2xl border border-amber-500/30 bg-slate-950 p-5 text-slate-100 shadow-2xl">
        <header className="flex items-center gap-3 mb-4">
          <span className="text-3xl" aria-hidden="true">{player.avatar || '👤'}</span>
          <div className="min-w-0 flex-1"><h2 id="player-stats-title" className="font-bold truncate">{player.name}</h2><p className="text-xs text-slate-400">本局数据{data?.updating ? ' · 更新中' : ''}</p></div>
          <button type="button" onClick={onClose} aria-label="关闭统计" className="p-2 rounded-lg hover:bg-slate-800"><X size={20} /></button>
        </header>
        {data ? <StatisticsPanel data={data} showLuckDetails={isSelf} />
          : <p role="status" className="text-center py-12 text-slate-400">统计暂不可用</p>}
      </section>
    </div>, document.body,
  );
}
