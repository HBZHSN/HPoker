import React, { useEffect, useState } from 'react';

export default function AdminJevSettings({ token }) {
  const [fee, setFee] = useState('0.01');
  const [key, setKey] = useState('');
  const [hasKey, setHasKey] = useState(false);
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    fetch('/api/admin/config/jev', { headers: { Authorization: 'Bearer ' + token } })
      .then((response) => response.json())
      .then((data) => { setFee(data.fee); setHasKey(data.has_key); })
      .catch(() => setMessage('无法读取 Jev 配置'));
  }, [token]);

  const save = async (event) => {
    event.preventDefault();
    setBusy(true);
    setMessage('');
    try {
      const response = await fetch('/api/admin/config/jev', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + token },
        body: JSON.stringify({ fee, ...(key ? { api_key: key } : {}) }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || '保存失败');
      setFee(data.fee);
      setHasKey(data.has_key);
      setKey('');
      setMessage('已保存');
    } catch (error) {
      setMessage(error.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={save} className="rounded-2xl border border-purple-500/30 bg-slate-900/90 p-4 space-y-3">
      <h3 className="text-xs font-black text-purple-300">Jev 配置</h3>
      <label className="block text-xs text-slate-300">API key {hasKey && <span className="text-emerald-400">（已配置，留空保持不变）</span>}
        <input type="password" autoComplete="off" value={key} onChange={(event) => setKey(event.target.value)} placeholder="输入新的 API key" className="mt-1 w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100" />
      </label>
      <label className="block text-xs text-slate-300">每次调用扣除 H币
        <input type="number" min="0" max="1000000" step="0.01" required value={fee} onChange={(event) => setFee(event.target.value)} className="mt-1 w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100" />
      </label>
      <div className="flex items-center gap-3">
        <button type="submit" disabled={busy} className="rounded-xl bg-purple-600 px-4 py-2 text-xs font-bold text-white disabled:opacity-50">保存 Jev 配置</button>
        {message && <span role="status" className="text-xs text-slate-300">{message}</span>}
      </div>
    </form>
  );
}
