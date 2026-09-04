import React, { useState } from 'react';
import { User, KeyRound, CheckCircle2, AlertCircle, X } from 'lucide-react';

const AVATAR_OPTIONS = ['👑', '🦈', '🦁', '🐺', '🦅', '🦊', '🐯', '🐉', '🐼', '👤', '🤠', '🦄'];

export default function ProfileModal({ isOpen, user, token, onUpdateUser, onClose }) {
  if (!isOpen || !user) return null;

  const [nickname, setNickname] = useState(user.nickname || '');
  const [avatar, setAvatar] = useState(user.avatar || '👤');
  const [oldPassword, setOldPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSave = async (e) => {
    e?.preventDefault();
    setError('');
    setSuccess('');

    // If changing password, validate password fields
    if (newPassword.trim()) {
      if (!oldPassword.trim()) {
        setError('修改密码需输入原密码');
        return;
      }
      if (newPassword.trim().length < 3) {
        setError('新密码长度不能少于3位');
        return;
      }
      if (newPassword.trim() !== confirmPassword.trim()) {
        setError('两次输入的新密码不一致');
        return;
      }
    }

    setLoading(true);

    try {
      const res = await fetch('/api/auth/profile', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          user_id: user.user_id,
          nickname: nickname.trim() || undefined,
          avatar: avatar,
          old_password: oldPassword.trim() || undefined,
          new_password: newPassword.trim() || undefined,
        }),
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || '更新失败');
      }

      setSuccess('资料更新成功');
      onUpdateUser(data.user);
      setTimeout(() => {
        onClose();
      }, 1000);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/85 backdrop-blur-md p-4 animate-fade-in">
      <div className="relative w-full max-w-md bg-gradient-to-b from-slate-900 via-slate-950 to-black border-2 border-amber-500/50 rounded-3xl p-6 shadow-2xl overflow-hidden flex flex-col gap-4">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl bg-amber-500/20 border border-amber-500/40 flex items-center justify-center text-amber-400">
              <User className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-black text-amber-400">个人设置</h3>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white transition cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Notices */}
        {error && (
          <div className="flex items-center gap-2 p-2.5 bg-red-950/80 border border-red-500/60 rounded-xl text-red-300 text-xs font-bold">
            <AlertCircle className="w-4 h-4 text-red-400 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {success && (
          <div className="flex items-center gap-2 p-2.5 bg-emerald-950/80 border border-emerald-500/60 rounded-xl text-emerald-300 text-xs font-bold">
            <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
            <span>{success}</span>
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSave} className="flex flex-col gap-3">
          {/* Avatar selector */}
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-bold text-slate-300">头像</label>
            <div className="flex flex-wrap gap-1.5 bg-slate-950 p-2 rounded-xl border border-slate-800">
              {AVATAR_OPTIONS.map((av, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() => setAvatar(av)}
                  className={`w-8 h-8 rounded-lg text-lg flex items-center justify-center transition active:scale-90 cursor-pointer ${
                    avatar === av
                      ? 'bg-amber-500/30 border-2 border-amber-400 shadow'
                      : 'hover:bg-slate-800 border border-transparent'
                  }`}
                >
                  {av}
                </button>
              ))}
            </div>
          </div>

          {/* Read-only account username */}
          <div className="flex flex-col gap-1">
            <div className="flex items-center justify-between">
              <label className="text-xs font-bold text-slate-300">登录账号</label>
            </div>
            <input
              type="text"
              value={user.username}
              disabled
              className="w-full bg-slate-950/70 px-3 py-2 rounded-xl border border-slate-800 text-slate-400 font-mono text-xs cursor-not-allowed select-none"
            />
          </div>

          {/* Editable Nickname */}
          <div className="flex flex-col gap-1">
            <label className="text-xs font-bold text-slate-300">玩家昵称</label>
            <input
              type="text"
              value={nickname}
              onChange={(e) => setNickname(e.target.value)}
              className="w-full bg-slate-950 px-3 py-2 rounded-xl border border-slate-700 text-slate-100 font-bold text-sm focus:border-amber-400 focus:outline-none"
            />
          </div>

          {/* Password Change Section */}
          <div className="border-t border-slate-800/80 pt-3 flex flex-col gap-2.5">
            <div className="text-xs font-black text-amber-400/90 flex items-center justify-between">
              <span className="flex items-center gap-1.5">
                <KeyRound className="w-3.5 h-3.5" />
                修改密码
              </span>
            </div>

            <div className="flex flex-col gap-1">
              <label className="text-[11px] font-semibold text-slate-400">原密码</label>
              <input
                type="password"
                value={oldPassword}
                onChange={(e) => setOldPassword(e.target.value)}
                className="w-full bg-slate-950 px-3 py-1.5 rounded-xl border border-slate-700 text-slate-100 text-xs focus:border-amber-400 focus:outline-none"
              />
            </div>

            <div className="grid grid-cols-2 gap-2">
              <div className="flex flex-col gap-1">
                <label className="text-[11px] font-semibold text-slate-400">新密码</label>
                <input
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  className="w-full bg-slate-950 px-3 py-1.5 rounded-xl border border-slate-700 text-slate-100 text-xs focus:border-amber-400 focus:outline-none"
                />
              </div>

              <div className="flex flex-col gap-1">
                <label className="text-[11px] font-semibold text-slate-400">确认新密码</label>
                <input
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  className="w-full bg-slate-950 px-3 py-1.5 rounded-xl border border-slate-700 text-slate-100 text-xs focus:border-amber-400 focus:outline-none"
                />
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2 mt-2">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 py-2.5 bg-slate-800 hover:bg-slate-700 text-slate-300 font-bold text-sm rounded-xl border border-slate-700 transition cursor-pointer"
            >
              取消
            </button>
            <button
              type="submit"
              disabled={loading}
              className="flex-1 py-2.5 bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-400 hover:to-amber-500 text-slate-950 font-black text-sm rounded-xl shadow-glow-gold transition active:scale-95 cursor-pointer"
            >
              {loading ? '保存中...' : '保存修改'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
