import React, { useState } from 'react';
import { Lock, User, KeyRound, AlertCircle, ArrowRight, CheckSquare, Square } from 'lucide-react';

export default function LoginModal({ onLoginSuccess }) {
  const [username, setUsername] = useState(() => localStorage.getItem('hpoker_remembered_username') || localStorage.getItem('ggpoker_remembered_username') || '');
  const [password, setPassword] = useState('');
  const [rememberLogin, setRememberLogin] = useState(true);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const executeLogin = async (loginUser, loginPass) => {
    if (!loginUser.trim() || !loginPass.trim()) {
      setError('请输入用户名和密码');
      return;
    }
    setError('');
    setLoading(true);

    try {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: loginUser.trim(), password: loginPass.trim() }),
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || '登录失败，请检查账号密码');
      }

      const data = await res.json();
      if (rememberLogin) {
        localStorage.setItem('hpoker_remembered_username', loginUser.trim());
      } else {
        localStorage.removeItem('hpoker_remembered_username');
        localStorage.removeItem('ggpoker_remembered_username');
      }
      onLoginSuccess(data.user, data.token, rememberLogin);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = (e) => {
    e?.preventDefault();
    executeLogin(username, password);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/90 backdrop-blur-md p-4 animate-fade-in">
      <div className="relative w-full max-w-md bg-gradient-to-b from-slate-900 via-slate-950 to-black border-2 border-amber-500/50 rounded-3xl p-6 md:p-8 shadow-2xl overflow-hidden flex flex-col gap-5">
        {/* Glow backdrop decor */}
        <div className="absolute -top-20 -left-20 w-48 h-48 bg-amber-500/15 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute -bottom-20 -right-20 w-48 h-48 bg-emerald-500/15 rounded-full blur-3xl pointer-events-none" />

        {/* Title */}
        <div className="flex flex-col items-center text-center gap-1.5 z-10">
          <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-amber-400 to-amber-600 flex items-center justify-center shadow-glow-gold">
            <Lock className="w-6 h-6 text-slate-950" />
          </div>
          <h2 className="text-xl md:text-2xl font-black text-amber-400 tracking-wide mt-2">
            HPoker 账号登录
          </h2>
        </div>

        {/* Error notice */}
        {error && (
          <div className="flex items-center gap-2 p-3 bg-red-950/80 border border-red-500/60 rounded-xl text-red-300 text-xs font-bold animate-shake z-10">
            <AlertCircle className="w-4 h-4 text-red-400 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} className="flex flex-col gap-3.5 z-10">
          <div className="flex flex-col gap-1">
            <label className="text-xs font-bold text-slate-300 flex items-center gap-1">
              <User className="w-3.5 h-3.5 text-amber-400" />
              用户名
            </label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full bg-slate-950 px-3.5 py-2.5 rounded-xl border border-slate-700 text-slate-100 font-bold text-sm focus:border-amber-400 focus:outline-none transition shadow-inner"
            />
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-xs font-bold text-slate-300 flex items-center gap-1">
              <KeyRound className="w-3.5 h-3.5 text-amber-400" />
              密码
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full bg-slate-950 px-3.5 py-2.5 rounded-xl border border-slate-700 text-slate-100 font-bold text-sm focus:border-amber-400 focus:outline-none transition shadow-inner"
            />
          </div>

          <div className="flex items-center justify-between py-0.5">
            <label
              onClick={() => setRememberLogin(!rememberLogin)}
              className="flex items-center gap-2 text-xs font-medium text-slate-300 cursor-pointer select-none"
            >
              {rememberLogin ? (
                <CheckSquare className="w-4 h-4 text-amber-400" />
              ) : (
                <Square className="w-4 h-4 text-slate-500" />
              )}
              <span>记住登录状态</span>
            </label>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-3 bg-gradient-to-r from-amber-500 via-amber-600 to-amber-500 hover:from-amber-400 hover:to-amber-500 text-slate-950 font-black text-base rounded-xl shadow-glow-gold transition active:scale-95 cursor-pointer flex items-center justify-center gap-2 mt-1"
          >
            <span>{loading ? '登录中...' : '登录'}</span>
            <ArrowRight className="w-4 h-4" />
          </button>
        </form>
      </div>
    </div>
  );
}
