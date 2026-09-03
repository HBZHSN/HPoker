import React, { useState, useEffect } from 'react';
import { Shield, UserPlus, KeyRound, Trash2, Edit3, X, CheckCircle2, AlertCircle, RefreshCw, RotateCcw } from 'lucide-react';

export default function AdminUserModal({ isOpen, adminUser, token, onClose }) {
  if (!isOpen || !adminUser || !adminUser.is_admin) return null;

  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(false);
  const [clearingData, setClearingData] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  // Add User Form State
  const [showAddForm, setShowAddForm] = useState(false);
  const [newUsername, setNewUsername] = useState('');
  const [newNickname, setNewNickname] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [newAvatar, setNewAvatar] = useState('👤');
  const [newIsAdmin, setNewIsAdmin] = useState(false);

  // Edit / Reset password state
  const [editingUserId, setEditingUserId] = useState(null);
  const [editNickname, setEditNickname] = useState('');
  const [editPassword, setEditPassword] = useState('');

  const fetchUsers = async () => {
    setLoading(true);
    try {
      const res = await fetch(`/api/admin/users?admin_id=${adminUser.user_id}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!res.ok) throw new Error('获取用户列表失败');
      const data = await res.json();
      setUsers(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchUsers();
  }, [adminUser.user_id]);

  const handleCreateUser = async (e) => {
    e?.preventDefault();
    if (!newUsername.trim()) {
      setError('用户名不能为空');
      return;
    }
    if (!newPassword.trim()) {
      setError('初始密码不能为空');
      return;
    }
    setError('');
    setSuccess('');

    try {
      const res = await fetch('/api/admin/users', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          admin_user_id: adminUser.user_id,
          username: newUsername.trim(),
          nickname: newNickname.trim() || newUsername.trim(),
          password: newPassword.trim(),
          avatar: newAvatar,
          is_admin: newIsAdmin,
        }),
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || '创建用户失败');

      setSuccess(`已创建账号 '${data.username}'`);
      setShowAddForm(false);
      setNewUsername('');
      setNewNickname('');
      setNewPassword('');
      fetchUsers();
    } catch (err) {
      setError(err.message);
    }
  };

  const handleUpdateUser = async (userId) => {
    setError('');
    setSuccess('');
    try {
      const res = await fetch(`/api/admin/users/${userId}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          admin_user_id: adminUser.user_id,
          nickname: editNickname.trim() || undefined,
          password: editPassword.trim() || undefined,
        }),
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || '更新失败');

      setSuccess(`已更新用户 '${data.username}'`);
      setEditingUserId(null);
      setEditPassword('');
      fetchUsers();
    } catch (err) {
      setError(err.message);
    }
  };

  const handleDeleteUser = async (userId, uname) => {
    if (!window.confirm(`确定要删除账号 '${uname}' 吗？`)) return;
    setError('');
    setSuccess('');
    try {
      const res = await fetch(`/api/admin/users/${userId}?admin_id=${adminUser.user_id}`, {
        method: 'DELETE',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || '删除失败');

      setSuccess(`账号 '${uname}' 已删除`);
      fetchUsers();
    } catch (err) {
      setError(err.message);
    }
  };

  const handleClearAllRecords = async () => {
    if (
      !window.confirm(
        '⚠️ 警告：确定要清空所有结算记录与账单数据吗？\n\n此操作将彻底清除所有未结账单、已结账单和历史结算批次，所有玩家余额归零重新起算，数据无法恢复！\n\n是否确认清空？'
      )
    ) {
      return;
    }
    setClearingData(true);
    setError('');
    setSuccess('');
    try {
      const res = await fetch(`/api/balance/all-records?admin_id=${adminUser.user_id}`, {
        method: 'DELETE',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || '清空失败');
      }
      const data = await res.json();
      setSuccess(data.message || '已成功清空所有结算与账单记录，重新开始计算！');
    } catch (err) {
      setError(err.message);
    } finally {
      setClearingData(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/85 backdrop-blur-md p-4 animate-fade-in">
      <div className="relative w-full max-w-3xl bg-gradient-to-b from-slate-900 via-slate-950 to-black border-2 border-amber-500/50 rounded-3xl p-6 shadow-2xl overflow-hidden flex flex-col gap-4 max-h-[90vh]">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-amber-400 to-amber-600 flex items-center justify-center text-slate-950 shadow-glow-gold">
              <Shield className="w-6 h-6" />
            </div>
            <div>
              <h3 className="text-lg font-black text-amber-400">账号管理</h3>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowAddForm(!showAddForm)}
              className="flex items-center gap-1 px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl text-xs font-black shadow transition active:scale-95 cursor-pointer"
            >
              <UserPlus className="w-3.5 h-3.5" />
              {showAddForm ? '收起添加' : '新建账号'}
            </button>
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white transition cursor-pointer"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
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

        {/* Add User Panel */}
        {showAddForm && (
          <form onSubmit={handleCreateUser} className="bg-slate-900/90 border border-amber-500/40 rounded-2xl p-4 flex flex-col gap-3 shadow-xl animate-fade-in">
            <div className="text-xs font-black text-amber-300 uppercase tracking-wide">新账号</div>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
              <input
                type="text"
                value={newUsername}
                onChange={(e) => setNewUsername(e.target.value)}
                placeholder="用户名"
                className="bg-slate-950 px-3 py-2 rounded-xl border border-slate-700 text-slate-100 font-bold text-xs focus:border-amber-400 focus:outline-none"
              />
              <input
                type="text"
                value={newNickname}
                onChange={(e) => setNewNickname(e.target.value)}
                placeholder="昵称"
                className="bg-slate-950 px-3 py-2 rounded-xl border border-slate-700 text-slate-100 font-bold text-xs focus:border-amber-400 focus:outline-none"
              />
              <input
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder="初始密码"
                className="bg-slate-950 px-3 py-2 rounded-xl border border-slate-700 text-slate-100 font-bold text-xs focus:border-amber-400 focus:outline-none"
              />
            </div>
            <div className="flex items-center justify-between">
              <label className="flex items-center gap-2 text-xs font-bold text-slate-300 cursor-pointer">
                <input
                  type="checkbox"
                  checked={newIsAdmin}
                  onChange={(e) => setNewIsAdmin(e.target.checked)}
                  className="rounded accent-amber-400"
                />
                管理员
              </label>

              <button
                type="submit"
                className="px-4 py-1.5 bg-gradient-to-r from-amber-500 to-amber-600 text-slate-950 rounded-xl text-xs font-black shadow transition active:scale-95 cursor-pointer"
              >
                创建
              </button>
            </div>
          </form>
        )}

        {/* User Table */}
        <div className="flex-1 overflow-y-auto pr-1">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-slate-800 text-slate-400 font-bold">
                <th className="py-2 px-3">头像</th>
                <th className="py-2 px-3">用户名</th>
                <th className="py-2 px-3">显示昵称</th>
                <th className="py-2 px-3">角色</th>
                <th className="py-2 px-3 text-right">操作</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => {
                const isEditing = editingUserId === u.user_id;

                return (
                  <tr key={u.user_id} className="border-b border-slate-800/60 hover:bg-slate-900/60 transition">
                    <td className="py-2.5 px-3 text-lg">{u.avatar}</td>
                    <td className="py-2.5 px-3 font-mono font-bold text-slate-200">{u.username}</td>
                    <td className="py-2.5 px-3 font-bold text-slate-300">
                      {isEditing ? (
                        <input
                          type="text"
                          value={editNickname}
                          onChange={(e) => setEditNickname(e.target.value)}
                          className="bg-slate-950 px-2 py-1 rounded border border-amber-400 text-xs w-28"
                        />
                      ) : (
                        u.nickname
                      )}
                    </td>
                    <td className="py-2.5 px-3">
                      {u.is_admin ? (
                        <span className="bg-amber-950 text-amber-300 px-2 py-0.5 rounded-full border border-amber-500/40 text-[10px] font-bold">
                          👑 管理员
                        </span>
                      ) : (
                        <span className="bg-slate-800 text-slate-400 px-2 py-0.5 rounded-full text-[10px] font-medium">
                          普通玩家
                        </span>
                      )}
                    </td>
                    <td className="py-2.5 px-3 text-right">
                      {isEditing ? (
                        <div className="flex items-center justify-end gap-1.5">
                          <input
                            type="password"
                            value={editPassword}
                            onChange={(e) => setEditPassword(e.target.value)}
                            placeholder="新密码"
                            className="bg-slate-950 px-2 py-1 rounded border border-amber-400 text-xs w-20"
                          />
                          <button
                            onClick={() => handleUpdateUser(u.user_id)}
                            className="px-2 py-1 bg-emerald-600 text-white rounded text-xs font-bold"
                          >
                            保存
                          </button>
                          <button
                            onClick={() => setEditingUserId(null)}
                            className="px-2 py-1 bg-slate-700 text-slate-300 rounded text-xs"
                          >
                            取消
                          </button>
                        </div>
                      ) : (
                        <div className="flex items-center justify-end gap-2">
                          <button
                            onClick={() => {
                              setEditingUserId(u.user_id);
                              setEditNickname(u.nickname);
                              setEditPassword('');
                            }}
                            className="p-1 text-sky-400 hover:text-sky-300 transition"
                            title="修改资料"
                          >
                            <Edit3 className="w-3.5 h-3.5" />
                          </button>
                          {!u.is_admin && (
                            <button
                              onClick={() => handleDeleteUser(u.user_id, u.username)}
                              className="p-1 text-red-400 hover:text-red-300 transition"
                              title="删除用户"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          )}
                        </div>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {/* Settlement Data Reset Panel */}
        <div className="p-3 bg-slate-900/90 border border-red-500/30 rounded-2xl flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
          <div className="flex flex-col gap-0.5">
            <div className="text-xs font-black text-red-300 flex items-center gap-1.5">
              <RotateCcw className="w-3.5 h-3.5 text-red-400" />
              战局结算与账单数据管理
            </div>
            <div className="text-[11px] text-slate-400">
              一键清除所有对局结算与账单记录，所有玩家余额归零重新起算
            </div>
          </div>
          <button
            onClick={handleClearAllRecords}
            disabled={clearingData}
            className="px-3.5 py-1.5 bg-red-600 hover:bg-red-500 text-white rounded-xl text-xs font-black shadow transition active:scale-95 flex items-center gap-1.5 cursor-pointer whitespace-nowrap"
          >
            <Trash2 className="w-3.5 h-3.5" />
            {clearingData ? '正在清空...' : '一键清空数据'}
          </button>
        </div>
      </div>
    </div>
  );
}
