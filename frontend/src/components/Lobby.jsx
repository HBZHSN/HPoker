import React, { useState, useMemo } from 'react';
import { PlusCircle, Users, DollarSign, Clock, ShieldCheck, Play, ArrowRight, Trash2, Wallet, Eye } from 'lucide-react';
import { filterVisibleLobbyUsers } from '../utils/lobbyUsers';

export default function Lobby({
  currentUser,
  token,
  onUpdateUser,
  onOpenProfile,
  onOpenAdmin,
  onOpenBalance,
  onLogout,
  rooms = [],
  users = [],
  onCreateRoom,
  onDeleteRoom,
  onJoinRoom,
}) {
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [roomName, setRoomName] = useState('新现金桌');
  const [buyinChips, setBuyinChips] = useState(1000);
  const [cashValue, setCashValue] = useState(100);
  const [smallBlind, setSmallBlind] = useState(10);
  const [actionTimeout, setActionTimeout] = useState(15);
  const [maxSeats, setMaxSeats] = useState(6);
  const [assistantWinPct, setAssistantWinPct] = useState(70);
  const [userFilter, setUserFilter] = useState('all'); // 'all' or 'online'

  const visibleUsers = useMemo(() => filterVisibleLobbyUsers(users), [users]);

  const onlineCount = useMemo(() => {
    return visibleUsers.filter((u) => u.is_online).length;
  }, [visibleUsers]);

  const sortedUsers = useMemo(() => {
    const list = [...visibleUsers];
    list.sort((a, b) => {
      const aSelf = a.user_id === currentUser?.user_id;
      const bSelf = b.user_id === currentUser?.user_id;
      if (a.is_online !== b.is_online) {
        return a.is_online ? -1 : 1;
      }
      if (aSelf !== bSelf) {
        return aSelf ? -1 : 1;
      }
      const nameA = a.nickname || a.username || '';
      const nameB = b.nickname || b.username || '';
      return nameA.localeCompare(nameB, 'zh-Hans-CN');
    });
    return list;
  }, [visibleUsers, currentUser?.user_id]);

  const displayedUsers = useMemo(() => {
    if (userFilter === 'online') {
      return sortedUsers.filter((u) => u.is_online);
    }
    return sortedUsers;
  }, [sortedUsers, userFilter]);

  const handleSubmitCreate = (e) => {
    e.preventDefault();
    onCreateRoom({
      host_player_id: currentUser?.user_id || 'u_admin',
      room_name: roomName,
      buyin_chips: Number(buyinChips),
      cash_value: Number(cashValue),
      small_blind: Number(smallBlind),
      action_timeout: Number(actionTimeout),
      max_seats: Number(maxSeats),
      assistant_win_ratio: Number(assistantWinPct) / 100,
    });
    setCreateModalOpen(false);
  };

  return (
    <div className="w-full max-w-7xl mx-auto p-4 md:p-6 lg:p-8 flex flex-col gap-6">
      {/* Top Banner & User Switcher / Auth Control */}
      <header className="flex flex-col md:flex-row items-center justify-between gap-4 bg-slate-900/80 border border-amber-500/30 p-5 rounded-3xl backdrop-blur-md shadow-2xl">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-amber-500 to-amber-700 flex items-center justify-center text-slate-950 font-black text-xl shadow-glow-gold">
            H
          </div>
          <div>
            <h1 className="text-xl md:text-2xl font-black text-white tracking-wider flex items-center gap-2">
              HPoker
            </h1>
          </div>
        </div>

        {/* User Profile & Management Controls */}
        <div className="flex items-center gap-2.5 bg-slate-950 px-3.5 py-2 rounded-2xl border border-slate-800">
          <div className="text-2xl select-none">{currentUser?.avatar || '👤'}</div>
          <div className="flex flex-col">
            <div className="flex items-center gap-1.5">
              <span className="text-xs md:text-sm font-black text-slate-100">{currentUser?.nickname}</span>
              {currentUser?.is_admin && (
                <span className="text-[10px] bg-amber-950 text-amber-300 px-1.5 py-0.2 rounded border border-amber-500/40 font-bold">
                  👑 管理员
                </span>
              )}
              {currentUser?.is_test && (
                <span className="text-[10px] bg-purple-950 text-purple-300 px-1.5 py-0.2 rounded border border-purple-500/40 font-bold">
                  🧪 测试账号
                </span>
              )}
            </div>
          </div>

          <div className="flex items-center gap-1.5 ml-2">
            {/* Balance Button */}
            <button
              onClick={onOpenBalance}
              className="px-2.5 py-1.5 bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-400 hover:to-amber-500 text-slate-950 text-xs font-black rounded-xl shadow-glow-gold transition active:scale-95 cursor-pointer flex items-center gap-1"
            >
              <Wallet className="w-3.5 h-3.5" />
              余额
            </button>

            {/* Edit Profile Button */}
            <button
              onClick={onOpenProfile}
              className="px-2.5 py-1.5 bg-slate-800 hover:bg-slate-700 text-sky-300 text-xs font-bold rounded-xl border border-slate-700 transition active:scale-95 cursor-pointer"
            >
              个人设置
            </button>

            {/* Admin Management Button */}
            {currentUser?.is_admin && (
              <button
                onClick={onOpenAdmin}
                className="px-2.5 py-1.5 bg-amber-950 hover:bg-amber-900 text-amber-300 text-xs font-bold rounded-xl border border-amber-500/40 transition active:scale-95 cursor-pointer flex items-center gap-1 shadow"
              >
                <ShieldCheck className="w-3.5 h-3.5" />
                账号管理
              </button>
            )}

            {/* Logout Button */}
            <button
              onClick={onLogout}
              className="px-2.5 py-1.5 bg-red-950/80 hover:bg-red-900 text-red-300 text-xs font-bold rounded-xl border border-red-500/40 transition active:scale-95 cursor-pointer"
            >
              退出
            </button>
          </div>
        </div>
      </header>

      {/* Main Dual-Column Content: Left = 牌桌列表 (一行一个), Right = 在线用户 */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left Column: 牌桌列表 (一行一个) */}
        <section className="lg:col-span-8 flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Users className="w-5 h-5 text-amber-400" />
              <h2 className="text-lg font-bold text-white tracking-wide">牌桌列表</h2>
              <span className="text-xs bg-slate-800 text-slate-400 px-2 py-0.5 rounded-full font-medium">
                {rooms.length} 桌
              </span>
            </div>

            <button
              onClick={() => setCreateModalOpen(true)}
              className="flex items-center gap-1.5 px-4 py-2.5 bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-400 hover:to-amber-500 text-slate-950 text-xs font-black rounded-xl shadow-glow-gold transition active:scale-95 cursor-pointer"
            >
              <PlusCircle className="w-4 h-4" />
              创建房间
            </button>
          </div>

          {/* Rooms List (一行一个) */}
          {rooms.length === 0 ? (
            <div className="flex flex-col items-center justify-center p-12 bg-slate-900/40 rounded-3xl border border-slate-800/80 text-center gap-3">
              <div className="w-12 h-12 rounded-full bg-slate-800 flex items-center justify-center text-slate-500 text-2xl">
                ♠️
              </div>
              <p className="text-sm text-slate-400 font-medium">暂无牌桌</p>
              <button
                onClick={() => setCreateModalOpen(true)}
                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-amber-400 text-xs font-bold rounded-xl border border-slate-700 transition cursor-pointer"
              >
                创建房间
              </button>
            </div>
          ) : (
            <div className="flex flex-col gap-3.5">
              {rooms.map((r) => {
                const canDelete = currentUser?.user_id === r.host_player_id || currentUser?.is_admin;
                return (
                  <div
                    key={r.room_id}
                    className="p-4 md:p-5 bg-gradient-to-r from-slate-900/90 via-slate-900/80 to-slate-950 border border-slate-800 hover:border-amber-500/50 rounded-2xl shadow-xl transition-all duration-200 group flex flex-col sm:flex-row sm:items-center justify-between gap-4"
                  >
                    <div className="flex items-center gap-3.5 min-w-0 flex-1">
                      {/* Table Icon */}
                      <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-amber-500/20 to-amber-950/40 border border-amber-500/30 flex items-center justify-center text-xl shrink-0 group-hover:scale-105 transition">
                        ♠️
                      </div>

                      {/* Details */}
                      <div className="flex flex-col gap-1 min-w-0 flex-1">
                        <div className="flex items-center gap-2 flex-wrap">
                          <h3 className="font-extrabold text-white text-base group-hover:text-amber-400 transition truncate">
                            {r.room_name}
                          </h3>
                          {r.host_player_id === currentUser?.user_id && (
                            <span className="text-[10px] bg-amber-950 text-amber-300 font-bold px-1.5 py-0.5 rounded border border-amber-500/30 shrink-0">
                              👑 房主
                            </span>
                          )}
                          <span className="text-xs bg-amber-950/80 text-amber-300 font-bold px-2 py-0.5 rounded-full border border-amber-500/30 shrink-0">
                            ${r.small_blind}/${r.big_blind}
                          </span>
                        </div>

                        <div className="flex items-center gap-2.5 text-xs text-slate-300 flex-wrap">
                          <span className="text-[11px] text-slate-500 font-mono">ID: {r.room_id}</span>
                          <span className="text-slate-600">·</span>
                          <span className="flex items-center gap-1 text-slate-300">
                            <DollarSign className="w-3.5 h-3.5 text-amber-400" />
                            买入: ${r.buyin_chips} = ¥{r.cash_value}
                          </span>
                          <span className="text-slate-600">·</span>
                          <span className="flex items-center gap-1 text-sky-300">
                            <Users className="w-3.5 h-3.5 text-sky-400" />
                            在座: {r.seated_count}/{r.max_seats}
                          </span>
                          {r.spectator_count > 0 && (
                            <>
                              <span className="text-slate-600">·</span>
                              <span className="flex items-center gap-1 text-amber-300 font-medium">
                                <Eye className="w-3.5 h-3.5 text-amber-400" />
                                观战: {r.spectator_count}
                              </span>
                            </>
                          )}
                          <span className="text-slate-600">·</span>
                          <span className="flex items-center gap-1 text-slate-400">
                            <Clock className="w-3.5 h-3.5 text-slate-400" />
                            限时: {r.action_timeout}s
                          </span>
                          {r.assistant_win_ratio !== undefined && (
                            <>
                              <span className="text-slate-600">·</span>
                              <span className="flex items-center gap-1 text-purple-300 font-medium">
                                辅助折算: {Math.round(r.assistant_win_ratio * 100)}%
                              </span>
                            </>
                          )}
                        </div>
                      </div>
                    </div>

                    {/* Actions */}
                    <div className="flex items-center gap-2 sm:self-center shrink-0">
                      {r.seated_count >= r.max_seats ? (
                        <button
                          onClick={() => onJoinRoom(r.room_id, { spectate: true })}
                          className="px-3.5 py-2.5 bg-indigo-950/80 hover:bg-indigo-900 text-indigo-200 hover:text-white font-bold text-xs rounded-xl border border-indigo-500/40 transition flex items-center justify-center gap-1.5 shadow cursor-pointer whitespace-nowrap"
                          title="牌桌已满，作为观众进入观战"
                        >
                          <Eye className="w-3.5 h-3.5 text-indigo-400" />
                          满员观战
                        </button>
                      ) : (
                        <>
                          <button
                            onClick={() => onJoinRoom(r.room_id, { spectate: false })}
                            className="px-3.5 py-2.5 bg-slate-800 hover:bg-amber-500 hover:text-slate-950 text-white font-bold text-xs rounded-xl border border-slate-700 hover:border-amber-400 transition flex items-center justify-center gap-1.5 shadow cursor-pointer whitespace-nowrap"
                          >
                            进入牌桌
                            <ArrowRight className="w-3.5 h-3.5" />
                          </button>
                          <button
                            onClick={() => onJoinRoom(r.room_id, { spectate: true })}
                            className="px-2.5 py-2.5 bg-slate-900 hover:bg-slate-800 text-slate-300 hover:text-amber-300 font-bold text-xs rounded-xl border border-slate-700/80 hover:border-amber-500/40 transition flex items-center justify-center gap-1 shadow cursor-pointer whitespace-nowrap"
                            title="不入座，作为观众进入观战"
                          >
                            <Eye className="w-3.5 h-3.5 text-amber-400/80" />
                            观战
                          </button>
                        </>
                      )}
                      {canDelete && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            if (window.confirm(`确定要解散并删除房间 "${r.room_name}" 吗？`)) {
                              onDeleteRoom?.(r.room_id);
                            }
                          }}
                          className="p-2.5 bg-red-950/70 hover:bg-red-900 text-red-300 hover:text-white rounded-xl border border-red-500/40 transition active:scale-95 cursor-pointer shadow flex items-center justify-center"
                          title="解散/删除此房间"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </section>

        {/* Right Column: 在线用户 */}
        <aside className="lg:col-span-4 flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="relative flex items-center justify-center">
                <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse ring-4 ring-emerald-400/20" />
              </div>
              <h2 className="text-lg font-bold text-white tracking-wide">在线用户</h2>
              <span className="text-xs bg-emerald-950/80 text-emerald-300 border border-emerald-500/30 px-2 py-0.5 rounded-full font-bold">
                {onlineCount} 在线
              </span>
            </div>

            {/* Filter Tabs: 全部 / 仅在线 */}
            <div className="flex items-center bg-slate-950 p-1 rounded-xl border border-slate-800 text-[11px]">
              <button
                onClick={() => setUserFilter('online')}
                className={`px-2.5 py-1 rounded-lg font-bold transition cursor-pointer ${
                  userFilter === 'online'
                    ? 'bg-amber-500 text-slate-950 shadow'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                在线
              </button>
              <button
                onClick={() => setUserFilter('all')}
                className={`px-2.5 py-1 rounded-lg font-bold transition cursor-pointer ${
                  userFilter === 'all'
                    ? 'bg-amber-500 text-slate-950 shadow'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                全部
              </button>
            </div>
          </div>

          {/* Users List Container */}
          <div className="bg-slate-900/80 border border-slate-800 rounded-3xl p-3 md:p-4 shadow-xl backdrop-blur-md flex flex-col gap-2.5 max-h-[640px] overflow-y-auto">
            {displayedUsers.length === 0 ? (
              <div className="py-12 flex flex-col items-center justify-center text-center gap-2 text-slate-500 text-xs">
                <div className="text-2xl">👥</div>
                <div>暂无{userFilter === 'online' ? '在线' : ''}用户</div>
              </div>
            ) : (
              displayedUsers.map((u) => {
                const isSelf = u.user_id === currentUser?.user_id;
                return (
                  <div
                    key={u.user_id}
                    className={`flex items-center justify-between p-3 rounded-2xl border transition-all ${
                      u.is_online
                        ? 'bg-slate-950/70 border-slate-800 hover:border-emerald-500/40'
                        : 'bg-slate-950/30 border-slate-900/60 opacity-60'
                    }`}
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      <div className="relative select-none text-2xl shrink-0">
                        {u.avatar || '👤'}
                        <span
                          className={`absolute -bottom-0.5 -right-0.5 w-3 h-3 rounded-full border-2 border-slate-950 ${
                            u.is_online
                              ? 'bg-emerald-400 shadow-sm shadow-emerald-400/80 ring-1 ring-emerald-300 animate-pulse'
                              : 'bg-slate-600'
                          }`}
                        />
                      </div>

                      <div className="flex flex-col min-w-0">
                        <div className="flex items-center gap-1.5 flex-wrap">
                          <span className={`text-xs font-bold truncate ${isSelf ? 'text-amber-300' : 'text-slate-200'}`}>
                            {u.nickname || u.username}
                          </span>
                          {isSelf && (
                            <span className="text-[9px] bg-sky-950 text-sky-300 px-1 py-0.2 rounded border border-sky-500/30 font-bold shrink-0">
                              我
                            </span>
                          )}
                          {u.is_admin && (
                            <span className="text-[9px] bg-amber-950 text-amber-300 px-1 py-0.2 rounded border border-amber-500/30 font-bold shrink-0">
                              👑 管理员
                            </span>
                          )}
                          {u.is_test && (
                            <span className="text-[9px] bg-purple-950 text-purple-300 px-1 py-0.2 rounded border border-purple-500/30 font-bold shrink-0">
                              🧪 测试
                            </span>
                          )}
                        </div>

                        <div className="text-[10px] truncate mt-0.5">
                          {u.is_online ? (
                            u.current_room_name ? (
                              <span className="text-amber-400 font-medium">
                                牌桌中 · {u.current_room_name}
                              </span>
                            ) : (
                              <span className="text-emerald-400 font-medium">
                                大厅
                              </span>
                            )
                          ) : (
                            <span className="text-slate-500">离线</span>
                          )}
                        </div>
                      </div>
                    </div>

                    <div className="shrink-0 ml-2">
                      {u.is_online ? (
                        <span className="text-[10px] bg-emerald-950/80 text-emerald-300 font-bold px-2 py-0.5 rounded-full border border-emerald-500/40 flex items-center gap-1">
                          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                          在线
                        </span>
                      ) : (
                        <span className="text-[10px] bg-slate-900 text-slate-500 font-medium px-2 py-0.5 rounded-full border border-slate-800">
                          离线
                        </span>
                      )}
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </aside>
      </div>

      {/* Create Room Modal */}
      {createModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-md flex items-center justify-center p-4">
          <div className="w-full max-w-md bg-slate-900 border border-amber-500/40 rounded-3xl p-6 shadow-2xl flex flex-col gap-4">
            <h3 className="text-lg font-black text-white">创建房间</h3>

            <form onSubmit={handleSubmitCreate} className="flex flex-col gap-3 text-xs">
              <div>
                <label className="text-slate-400 font-semibold block mb-1">房间名称</label>
                <input
                  type="text"
                  value={roomName}
                  onChange={(e) => setRoomName(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-white outline-none focus:border-amber-400"
                  required
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-slate-400 font-semibold block mb-1">买入筹码</label>
                  <input
                    type="number"
                    value={buyinChips}
                    onChange={(e) => setBuyinChips(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-white outline-none focus:border-amber-400"
                    min="10"
                    required
                  />
                </div>
                <div>
                  <label className="text-slate-400 font-semibold block mb-1">现金 (¥)</label>
                  <input
                    type="number"
                    value={cashValue}
                    onChange={(e) => setCashValue(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-white outline-none focus:border-amber-400"
                    min="1"
                    required
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-slate-400 font-semibold block mb-1">小盲 SB</label>
                  <input
                    type="number"
                    value={smallBlind}
                    onChange={(e) => setSmallBlind(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-white outline-none focus:border-amber-400"
                    min="1"
                    required
                  />
                </div>
                <div>
                  <label className="text-slate-400 font-semibold block mb-1">大盲 BB</label>
                  <div className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-amber-300 font-black">
                    {Number(smallBlind) > 0 ? Number(smallBlind) * 2 : '—'}
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-slate-400 font-semibold block mb-1">行动限时 (秒)</label>
                  <input
                    type="number"
                    value={actionTimeout}
                    onChange={(e) => setActionTimeout(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-white outline-none focus:border-amber-400"
                    min="5"
                    max="60"
                    required
                  />
                </div>
                <div>
                  <label className="text-slate-400 font-semibold block mb-1">人数</label>
                  <select
                    value={maxSeats}
                    onChange={(e) => setMaxSeats(Number(e.target.value))}
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-white outline-none focus:border-amber-400"
                  >
                    {Array.from({ length: 8 }, (_, index) => index + 2).map((seatCount) => (
                      <option key={seatCount} value={seatCount}>{seatCount} 人桌</option>
                    ))}
                  </select>
                </div>
              </div>

              <div>
                <label className="text-slate-400 font-semibold block mb-1">
                  辅助折算 (%)
                </label>
                <div className="flex items-center gap-3">
                  <input
                    type="range"
                    min="10"
                    max="100"
                    step="5"
                    value={assistantWinPct}
                    onChange={(e) => setAssistantWinPct(Number(e.target.value))}
                    className="flex-1 accent-amber-500 cursor-pointer"
                  />
                  <div className="w-16 bg-slate-950 border border-slate-800 rounded-xl px-2 py-1.5 text-center font-bold text-amber-400 text-xs">
                    {assistantWinPct}%
                  </div>
                </div>
              </div>

              <div className="flex gap-2 mt-3">
                <button
                  type="submit"
                  className="flex-1 py-2.5 bg-amber-500 hover:bg-amber-400 text-slate-950 font-black rounded-xl transition"
                >
                  创建
                </button>
                <button
                  type="button"
                  onClick={() => setCreateModalOpen(false)}
                  className="px-4 py-2.5 bg-slate-800 hover:bg-slate-700 text-slate-300 font-bold rounded-xl transition"
                >
                  取消
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
