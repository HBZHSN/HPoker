import React, { useState } from 'react';
import { PlusCircle, Users, DollarSign, Clock, ShieldCheck, Play, ArrowRight } from 'lucide-react';

export default function Lobby({
  users,
  currentUser,
  onSelectUser,
  rooms,
  onCreateRoom,
  onJoinRoom,
}) {
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [roomName, setRoomName] = useState('GGPoker 高端现金桌');
  const [buyinChips, setBuyinChips] = useState(1000);
  const [cashValue, setCashValue] = useState(100);
  const [smallBlind, setSmallBlind] = useState(5);
  const [bigBlind, setBigBlind] = useState(10);
  const [actionTimeout, setActionTimeout] = useState(15);
  const [maxSeats, setMaxSeats] = useState(6);

  const handleSubmitCreate = (e) => {
    e.preventDefault();
    onCreateRoom({
      host_player_id: currentUser?.user_id || 'u_admin',
      room_name: roomName,
      buyin_chips: Number(buyinChips),
      cash_value: Number(cashValue),
      small_blind: Number(smallBlind),
      big_blind: Number(bigBlind),
      action_timeout: Number(actionTimeout),
      max_seats: Number(maxSeats),
    });
    setCreateModalOpen(false);
  };

  return (
    <div className="w-full max-w-5xl mx-auto p-4 md:p-8 flex flex-col gap-8">
      {/* Top Banner & User Switcher */}
      <header className="flex flex-col md:flex-row items-center justify-between gap-4 bg-slate-900/80 border border-amber-500/30 p-5 rounded-3xl backdrop-blur-md shadow-2xl">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-amber-500 to-amber-700 flex items-center justify-center text-slate-950 font-black text-xl shadow-glow-gold">
            GG
          </div>
          <div>
            <h1 className="text-xl md:text-2xl font-black text-white tracking-wider flex items-center gap-2">
              GGPOKER 在线德州现金局
            </h1>
            <p className="text-xs text-slate-400">
              真实边池计算 · 现金局重买记录 · 终局极简转账图结算
            </p>
          </div>
        </div>

        {/* User Identity Selector */}
        <div className="flex items-center gap-2 bg-slate-950 px-3 py-2 rounded-2xl border border-slate-800">
          <span className="text-xs text-slate-400">当前身份:</span>
          <select
            value={currentUser?.user_id || ''}
            onChange={(e) => {
              const u = users.find((item) => item.user_id === e.target.value);
              if (u) onSelectUser(u);
            }}
            className="bg-slate-900 text-amber-400 font-bold text-xs rounded-xl px-2 py-1 border border-slate-700 outline-none cursor-pointer"
          >
            {users.map((u) => (
              <option key={u.user_id} value={u.user_id}>
                {u.avatar} {u.nickname} {u.is_admin ? '(Admin)' : ''}
              </option>
            ))}
          </select>
        </div>
      </header>

      {/* Main Room List Section */}
      <section className="flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Users className="w-5 h-5 text-amber-400" />
            <h2 className="text-lg font-bold text-white tracking-wide">进行中的牌桌</h2>
            <span className="text-xs bg-slate-800 text-slate-400 px-2 py-0.5 rounded-full font-medium">
              {rooms.length} 桌
            </span>
          </div>

          <button
            onClick={() => setCreateModalOpen(true)}
            className="flex items-center gap-1.5 px-4 py-2.5 bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-400 hover:to-amber-500 text-slate-950 text-xs font-black rounded-xl shadow-glow-gold transition active:scale-95"
          >
            <PlusCircle className="w-4 h-4" />
            创建现金局房间
          </button>
        </div>

        {/* Rooms Grid */}
        {rooms.length === 0 ? (
          <div className="flex flex-col items-center justify-center p-12 bg-slate-900/40 rounded-3xl border border-slate-800/80 text-center gap-3">
            <div className="w-12 h-12 rounded-full bg-slate-800 flex items-center justify-center text-slate-500 text-2xl">
              ♠️
            </div>
            <p className="text-sm text-slate-400 font-medium">暂无活跃房间，快来创建第一张现金桌吧！</p>
            <button
              onClick={() => setCreateModalOpen(true)}
              className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-amber-400 text-xs font-bold rounded-xl border border-slate-700 transition"
            >
              立即创建
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {rooms.map((r) => (
              <div
                key={r.room_id}
                className="flex flex-col justify-between p-5 bg-gradient-to-b from-slate-900/90 to-slate-950 border border-slate-800 hover:border-amber-500/50 rounded-2xl shadow-xl transition-all duration-200 group"
              >
                <div className="flex flex-col gap-3">
                  <div className="flex items-start justify-between">
                    <div>
                      <h3 className="font-extrabold text-white text-base group-hover:text-amber-400 transition">
                        {r.room_name}
                      </h3>
                      <span className="text-[11px] text-slate-400 font-mono">
                        ID: {r.room_id}
                      </span>
                    </div>
                    <span className="text-xs bg-amber-950 text-amber-300 font-bold px-2 py-0.5 rounded-full border border-amber-500/30">
                      ${r.small_blind}/${r.big_blind}
                    </span>
                  </div>

                  <div className="grid grid-cols-2 gap-2 text-xs text-slate-300">
                    <div className="flex items-center gap-1.5 bg-slate-800/50 p-2 rounded-xl border border-slate-800">
                      <DollarSign className="w-3.5 h-3.5 text-amber-400" />
                      <span>买入: ${r.buyin_chips} = ¥{r.cash_value}</span>
                    </div>
                    <div className="flex items-center gap-1.5 bg-slate-800/50 p-2 rounded-xl border border-slate-800">
                      <Users className="w-3.5 h-3.5 text-sky-400" />
                      <span>在座: {r.seated_count}/{r.max_seats}</span>
                    </div>
                  </div>
                </div>

                <button
                  onClick={() => onJoinRoom(r.room_id)}
                  className="mt-4 w-full py-2.5 bg-slate-800 hover:bg-amber-500 hover:text-slate-950 text-white font-bold text-xs rounded-xl border border-slate-700 hover:border-amber-400 transition flex items-center justify-center gap-1.5 shadow"
                >
                  进入牌桌
                  <ArrowRight className="w-3.5 h-3.5" />
                </button>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Create Room Modal */}
      {createModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-md flex items-center justify-center p-4">
          <div className="w-full max-w-md bg-slate-900 border border-amber-500/40 rounded-3xl p-6 shadow-2xl flex flex-col gap-4">
            <h3 className="text-lg font-black text-white">创建现金局房间</h3>

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
                  <label className="text-slate-400 font-semibold block mb-1">买入筹码数</label>
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
                  <label className="text-slate-400 font-semibold block mb-1">对应现金 (¥)</label>
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
                  <label className="text-slate-400 font-semibold block mb-1">小盲 (SB)</label>
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
                  <label className="text-slate-400 font-semibold block mb-1">大盲 (BB)</label>
                  <input
                    type="number"
                    value={bigBlind}
                    onChange={(e) => setBigBlind(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-white outline-none focus:border-amber-400"
                    min="2"
                    required
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-slate-400 font-semibold block mb-1">思考超时 (秒)</label>
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
                  <label className="text-slate-400 font-semibold block mb-1">座位上限</label>
                  <select
                    value={maxSeats}
                    onChange={(e) => setMaxSeats(Number(e.target.value))}
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-white outline-none focus:border-amber-400"
                  >
                    <option value={6}>6 人桌 (短牌/标准)</option>
                    <option value={9}>9 人桌 (满员桌)</option>
                  </select>
                </div>
              </div>

              <div className="flex gap-2 mt-3">
                <button
                  type="submit"
                  className="flex-1 py-2.5 bg-amber-500 hover:bg-amber-400 text-slate-950 font-black rounded-xl transition"
                >
                  确认创建
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
