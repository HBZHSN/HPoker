import React, { useEffect, useState } from 'react';
import { BarChart3, ChevronDown, ChevronUp, Loader2 } from 'lucide-react';
import { formatHCoins } from '../utils/hCurrency';

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

export default function EquityDrawer({ isOpen, onClose, roomId, token, decisionKey, isMyTurn, toCall }) {
  const [result, setResult] = useState(null);
  const [fee, setFee] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!isOpen) return;
    fetch('/api/config/jev', { headers: { Authorization: 'Bearer ' + token } })
      .then((response) => response.json())
      .then((data) => setFee(data.fee))
      .catch(() => setFee(null));
  }, [isOpen, token]);

  useEffect(() => {
    if (!isOpen || !isMyTurn || !decisionKey) {
      setResult(null);
      setLoading(false);
      setError('');
      return;
    }
    const controller = new AbortController();
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
      .then(setResult)
      .catch((cause) => { if (cause.name !== 'AbortError') setError(cause.message); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [isOpen, isMyTurn, decisionKey, roomId, token]);

  if (!isOpen) return null;

  return (
    <>
      <button className="fixed inset-0 bg-black/60 z-40 lg:hidden" onClick={onClose} aria-label="关闭 Jev 建议" />
      <aside className="poker-table-equity fixed inset-y-0 left-0 w-[320px] max-w-[85vw] z-50 lg:static lg:inset-auto lg:h-full lg:w-72 xl:w-80 2xl:w-[350px] lg:z-20 lg:flex-shrink-0 bg-gradient-to-b from-slate-900 via-slate-950 to-slate-900 border-r border-purple-500/40 shadow-2xl overflow-y-auto flex flex-col select-none">
        <div className="flex items-center justify-between px-4 py-3 bg-purple-900/60 border-b border-purple-500/30">
          <span className="flex items-center gap-2 text-sm font-black text-purple-100"><BarChart3 size={16} /> Jev 行动建议</span>
          <button onClick={onClose} className="text-purple-200 hover:text-white px-2" aria-label="收起建议">✕</button>
        </div>
        <div className="p-4 space-y-4 text-sm">
          {fee !== null && <p className="text-xs text-amber-300">每次决策 {formatHCoins(result?.fee ?? fee)}</p>}
          {!isMyTurn && <p className="text-slate-400 py-8 text-center">轮到你行动时显示建议</p>}
          {isMyTurn && loading && <div role="status" className="flex justify-center py-8 text-purple-300"><Loader2 className="animate-spin" /></div>}
          {isMyTurn && !loading && error && <p role="alert" className="text-red-300 bg-red-950/50 rounded-xl p-3">{error}</p>}
          {isMyTurn && !loading && result && (
            <>
              <p className="font-bold text-amber-300">推荐：{result.recommendation === 'call' && toCall === 0 ? '过牌 CHECK' : ACTIONS.find(([key]) => key === result.recommendation)?.[1]}</p>
              {ACTIONS.map(([key, label]) => (
                <div key={key} className={'rounded-xl border p-3 ' + (result.recommendation === key ? 'border-amber-400 bg-amber-500/10' : 'border-slate-700 bg-slate-800/50')}>
                  <div className="flex justify-between font-bold"><span>{key === 'call' && toCall === 0 ? '过牌 CHECK' : label}</span><span>{(result.probabilities[key] * 100).toFixed(1)}%</span></div>
                  <div className="mt-2 h-1.5 rounded-full bg-slate-700"><div className="h-full rounded-full bg-amber-400" style={{ width: (result.probabilities[key] * 100) + '%' }} /></div>
                </div>
              ))}
              <p className="text-xs text-slate-500">行动概率由 Jev 模型给出。</p>
            </>
          )}
        </div>
      </aside>
    </>
  );
}
