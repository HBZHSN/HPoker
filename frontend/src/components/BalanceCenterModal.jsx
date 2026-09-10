import React, { useState, useEffect, useCallback, useRef } from 'react';
import { X, RotateCcw, Info } from 'lucide-react';
import { HandHistoryPanel } from './PersonalHistory';
import { formatHCoins, normalizeHCoinsMessage } from '../utils/hCurrency';

const labels = {
  wallet_deposit: '管理员发放H币',
  wallet_withdraw: '管理员回收H币',
  wallet_buyin: '买入扣除H币',
  wallet_cashout: '离桌返还H币',
  wallet_mode_change: '模式切换',
};

export default function BalanceCenterModal({ isOpen, currentUser, token, onClose }) {
  const [tab, setTab] = useState('my');
  const [balance, setBalance] = useState(null);
  const [users, setUsers] = useState([]);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [busy, setBusy] = useState(false);
  const [target, setTarget] = useState('');
  const [amount, setAmount] = useState('');
  const [kind, setKind] = useState('deposit');
  const pending = useRef(null);
  const submitting = useRef(false);

  const request = useCallback(async (url, options = {}) => {
    const res = await fetch(url, { ...options, headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` } });
    const data = await res.json();
    if (!res.ok) throw new Error(normalizeHCoinsMessage(data.detail, '请求失败'));
    return data;
  }, [token]);

  const refresh = useCallback(async () => {
    try {
      const [mine, overview] = await Promise.all([
        request('/api/balance/my'),
        currentUser?.is_admin ? request('/api/balance/overview') : Promise.resolve(null),
      ]);
      setBalance(mine);
      if (overview) setUsers(overview.user_balances.filter(u => !u.is_test));
      setError('');
    } catch (e) { setError(e.message); }
  }, [request, currentUser?.is_admin]);

  useEffect(() => {
    if (!isOpen) return;
    refresh();
    const timer = setInterval(refresh, 3000);
    const onKey = e => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => { clearInterval(timer); window.removeEventListener('keydown', onKey); };
  }, [isOpen, refresh, onClose]);

  const submit = async e => {
    e.preventDefault();
    if (submitting.current) return;
    submitting.current = true;
    setBusy(true); setError(''); setSuccess('');
    const payload = { user_id: target, amount, kind };
    const signature = JSON.stringify(payload);
    if (pending.current?.signature !== signature) pending.current = { signature, id: crypto.randomUUID() };
    try {
      await request('/api/balance/wallet-change', { method: 'POST', body: JSON.stringify({ ...payload, request_id: pending.current.id }) });
      pending.current = null;
      setAmount('');
      await refresh();
      setSuccess(kind === 'deposit' ? 'H币增加成功' : 'H币扣除成功');
    } catch (e) { setError(e.message); }
    finally { submitting.current = false; setBusy(false); }
  };

  if (!isOpen) return null;
  const field = 'rounded-xl border border-slate-700 bg-slate-900 p-3 text-white min-w-0';

  return (
    <div className="fixed inset-0 z-[100] bg-black/80 flex items-center justify-center p-3">
      <div role="dialog" aria-modal="true" aria-label="H币中心" className="w-full max-w-4xl max-h-[92dvh] overflow-y-auto rounded-3xl border border-amber-500/40 bg-slate-950 p-5 text-slate-200 space-y-5">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-black">H币中心</h2>
          <div className="flex gap-3">
            <button aria-label="刷新" onClick={refresh}><RotateCcw size={18} /></button>
            <button aria-label="关闭" onClick={onClose}><X /></button>
          </div>
        </div>

        <nav className="flex gap-3">
          {[
            ['my', '我的'],
            ['hands', '牌局'],
            ...(currentUser?.is_admin ? [['admin', 'H币管理']] : []),
          ].map(([id, name]) => (
            <button
              key={id}
              onClick={() => setTab(id)}
              className={`rounded-xl px-4 py-2 text-sm font-bold transition ${
                tab === id ? 'bg-amber-500 text-slate-950 shadow-glow-gold' : 'bg-slate-800 text-slate-300 hover:bg-slate-700'
              }`}
            >
              {name}
            </button>
          ))}
        </nav>

        {error && <p role="alert" className="text-sm font-bold text-red-400 bg-red-950/40 border border-red-500/30 rounded-xl p-3">{error}</p>}
        {success && <p role="status" className="text-sm font-bold text-emerald-400 bg-emerald-950/40 border border-emerald-500/30 rounded-xl p-3">{success}</p>}

        {tab === 'my' && (
          <>
            <div className="grid grid-cols-2 gap-3">
              <div className="bg-slate-900 border border-slate-800 p-4 rounded-2xl">
                <p className="text-xs font-bold text-slate-400">可用H币</p>
                <p className="text-2xl text-amber-300 font-black mt-1">
                  {balance ? formatHCoins(balance.available_cash) : '—'}
                </p>
              </div>
              <div className="bg-slate-900 border border-slate-800 p-4 rounded-2xl">
                <p className="text-xs font-bold text-slate-400">生涯总盈亏</p>
                <p className={`text-2xl font-black mt-1 ${
                  Number(balance?.lifetime_net_cash || 0) > 0
                    ? 'text-emerald-400'
                    : Number(balance?.lifetime_net_cash || 0) < 0
                      ? 'text-rose-400'
                      : 'text-slate-200'
                }`}>
                  {balance ? formatHCoins(balance.lifetime_net_cash, { showPlus: true }) : '—'}
                </p>
              </div>
            </div>

            <div className="rounded-2xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm font-bold text-amber-300 flex items-center gap-2">
              <Info className="w-4 h-4 flex-shrink-0" />
              <span>H币不足时无法买入或补码</span>
            </div>

            <h3 className="font-bold text-sm text-slate-300">H币流水</h3>
            <div className="space-y-2 max-h-72 overflow-y-auto">
              {balance?.records?.length ? (
                balance.records.map(rec => {
                  const net = Number(rec.my_record?.net_cash || 0);
                  return (
                    <div key={rec.entry_id} className="flex justify-between items-center gap-3 rounded-xl bg-slate-900 border border-slate-800/80 p-3 text-sm">
                      <div>
                        <p className="font-bold text-slate-200">{labels[rec.entry_kind] || '历史记录'}{rec.room_name && ` · ${rec.room_name}`}</p>
                        <p className="text-xs text-slate-500 mt-0.5">{new Date(rec.created_at * 1000).toLocaleString()}</p>
                      </div>
                      <span className={`whitespace-nowrap font-black ${net > 0 ? 'text-emerald-400' : net < 0 ? 'text-rose-400' : 'text-slate-400'}`}>
                        {formatHCoins(net, { showPlus: true })}
                      </span>
                    </div>
                  );
                })
              ) : (
                <p className="text-xs text-slate-500 py-4 text-center">暂无记录</p>
              )}
            </div>
          </>
        )}

        {tab === 'hands' && <HandHistoryPanel token={token} userId={currentUser?.user_id} />}

        {tab === 'admin' && currentUser?.is_admin && (
          <>
            <form onSubmit={submit} className="grid gap-3 sm:grid-cols-2">
              <select
                aria-label="用户"
                required
                value={target}
                disabled={busy}
                onChange={e => setTarget(e.target.value)}
                className={field}
              >
                <option value="">选择用户</option>
                {users.map(u => (
                  <option key={u.user_id} value={u.user_id}>
                    {u.nickname} · {u.user_id} · {formatHCoins(u.available_cash)}
                  </option>
                ))}
              </select>
              <select
                aria-label="操作"
                value={kind}
                disabled={busy}
                onChange={e => setKind(e.target.value)}
                className={field}
              >
                <option value="deposit">增加H币</option>
                <option value="withdraw">扣除H币</option>
              </select>
              <input
                aria-label="H币数量"
                required
                type="number"
                min="0.01"
                max="100000000"
                step="0.01"
                placeholder="H币数量"
                value={amount}
                disabled={busy}
                onChange={e => setAmount(e.target.value)}
                className={field}
              />
              <button
                disabled={busy}
                className="rounded-xl bg-amber-500 hover:bg-amber-400 text-slate-950 p-3 font-black shadow-glow-gold transition disabled:opacity-50 cursor-pointer"
              >
                {busy ? '处理中…' : kind === 'deposit' ? '确认增加H币' : '确认扣除H币'}
              </button>
            </form>

            <div className="space-y-1.5 max-h-60 overflow-y-auto">
              <p className="text-xs font-bold text-slate-400 mb-1">用户H币列表（点击快捷选中）</p>
              {users.map(u => (
                <div
                  key={u.user_id}
                  onClick={() => setTarget(u.user_id)}
                  className={`flex justify-between items-center py-2 px-3 rounded-xl border transition cursor-pointer ${
                    target === u.user_id ? 'bg-amber-500/10 border-amber-500/40 text-amber-200' : 'bg-slate-900 border-slate-800/80 hover:bg-slate-800 text-slate-300'
                  }`}
                >
                  <span className="font-bold">{u.avatar} {u.nickname} <span className="text-xs text-slate-500 font-normal">({u.username || u.user_id})</span></span>
                  <span className="font-black text-amber-300">{formatHCoins(u.available_cash)}</span>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
