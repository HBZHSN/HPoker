import React, { useState, useEffect, useCallback } from 'react';
import {
  Wallet,
  TrendingUp,
  TrendingDown,
  ArrowRight,
  RotateCcw,
  CheckCircle2,
  AlertCircle,
  Copy,
  Check,
  X,
  History,
  ShieldCheck,
  Trash2,
  Calendar,
  Layers,
} from 'lucide-react';

export default function BalanceCenterModal({
  isOpen,
  currentUser,
  token,
  onClose,
}) {
  const [activeTab, setActiveTab] = useState('my'); // 'my' | 'hands' | 'history' | 'admin'
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [successMsg, setSuccessMsg] = useState('');
  const [copied, setCopied] = useState(false);

  // Data states
  const [myBalance, setMyBalance] = useState(null);
  const [overview, setOverview] = useState({ user_balances: [], preview: null });
  const [batches, setBatches] = useState([]);
  const [includeTest, setIncludeTest] = useState(false);
  const [settleConfirmOpen, setSettleConfirmOpen] = useState(false);
  const [selectedBatch, setSelectedBatch] = useState(null);
  const [handHistory, setHandHistory] = useState({ hands: [], total: 0, summary: {} });
  const [handOutcome, setHandOutcome] = useState('all');
  const [handSort, setHandSort] = useState('recent');

  const fetchMyBalance = useCallback(async () => {
    if (!currentUser?.user_id) return;
    try {
      const res = await fetch(`/api/balance/my?user_id=${currentUser.user_id}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (res.ok) {
        const data = await res.json();
        setMyBalance(data);
      }
    } catch (e) {
      console.error('Failed to fetch my balance', e);
    }
  }, [currentUser?.user_id, token]);

  const fetchOverview = useCallback(async () => {
    if (!currentUser?.is_admin) return;
    try {
      const res = await fetch(`/api/balance/overview?include_test=${includeTest}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (res.ok) {
        const data = await res.json();
        setOverview(data);
      }
    } catch (e) {
      console.error('Failed to fetch overview', e);
    }
  }, [currentUser?.is_admin, includeTest, token]);

  const fetchBatches = useCallback(async () => {
    try {
      const res = await fetch('/api/balance/batches', {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (res.ok) {
        const data = await res.json();
        setBatches(data);
      }
    } catch (e) {
      console.error('Failed to fetch batches', e);
    }
  }, [token]);

  const fetchHandHistory = useCallback(async () => {
    if (!currentUser?.user_id) return;
    const params = new URLSearchParams();
    if (handOutcome !== 'all') params.set('outcome', handOutcome);
    if (handSort === 'biggest-win') {
      params.set('sort_by', 'net_chips');
      params.set('order', 'desc');
    } else if (handSort === 'biggest-loss') {
      params.set('sort_by', 'net_chips');
      params.set('order', 'asc');
    }
    try {
      const res = await fetch(`/api/hands/my?${params.toString()}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (res.ok) {
        setHandHistory(await res.json());
      }
    } catch (e) {
      console.error('Failed to fetch hand history', e);
    }
  }, [currentUser?.user_id, handOutcome, handSort, token]);

  const refreshAll = useCallback(() => {
    setLoading(true);
    Promise.all([fetchMyBalance(), fetchOverview(), fetchBatches(), fetchHandHistory()])
      .finally(() => setLoading(false));
  }, [fetchMyBalance, fetchOverview, fetchBatches, fetchHandHistory]);

  useEffect(() => {
    if (isOpen) {
      refreshAll();
      setError('');
      setSuccessMsg('');
    }
  }, [isOpen, refreshAll]);

  if (!isOpen) return null;

  // Execute one-time batch settlement
  const handleExecuteBatchSettle = async () => {
    setError('');
    setSuccessMsg('');
    setLoading(true);
    try {
      const res = await fetch('/api/balance/settle-batch', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          operator_id: currentUser.user_id,
          include_test: includeTest,
        }),
      });
      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || '结算失败');
      }
      const newBatch = await res.json();
      setSuccessMsg(`已完成余额划转 #${newBatch.batch_id}`);
      setSettleConfirmOpen(false);
      setSelectedBatch(newBatch);
      refreshAll();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // Clear test records
  const handleClearTestRecords = async () => {
    if (!window.confirm('确认清理测试账号与机器人的对局记录？')) return;
    setLoading(true);
    try {
      const res = await fetch(`/api/balance/test-records?admin_id=${currentUser.user_id}`, {
        method: 'DELETE',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || '清空失败');
      }
      const data = await res.json();
      setSuccessMsg(data.message || '测试记录已清空');
      refreshAll();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // Clear all balance records and restart
  const handleClearAllRecords = async () => {
    if (
      !window.confirm(
        '确认清空所有结算与账单数据？\n\n此操作不可恢复。'
      )
    ) {
      return;
    }
    setLoading(true);
    setError('');
    setSuccessMsg('');
    try {
      const res = await fetch(`/api/balance/all-records?admin_id=${currentUser.user_id}`, {
        method: 'DELETE',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || '清空失败');
      }
      const data = await res.json();
      setSuccessMsg(data.message || '结算数据已清空');
      refreshAll();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const copyBatchText = (batch) => {
    if (!batch) return;
    const dateStr = new Date(batch.created_at * 1000).toLocaleString();
    let text = `【HPoker 余额划转批次 #${batch.batch_id}】\n`;
    text += `划转时间: ${dateStr}\n`;
    text += `操作员: ${batch.operator_name}\n`;
    text += `转账总额: ¥${batch.total_transferred_cash.toFixed(2)}\n\n`;

    text += `--- 各玩家结算汇总 ---\n`;
    (batch.user_summaries || []).forEach((u, idx) => {
      const sign = u.net_cash >= 0 ? '+' : '';
      text += `${idx + 1}. ${u.nickname}: 净额 ${sign}¥${u.net_cash.toFixed(2)} (${u.unsettled_games_count}笔流水)\n`;
    });

    text += `\n--- 最终转账执行清单 ---\n`;
    if (!batch.transactions || batch.transactions.length === 0) {
      text += `无需转账（收支已完全相抵或平局）。\n`;
    } else {
      batch.transactions.forEach((t, idx) => {
        text += `${idx + 1}. ${t.from_player_name} -> ${t.to_player_name}: ¥${t.amount_cash.toFixed(2)}\n`;
      });
    }

    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2500);
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/85 backdrop-blur-md flex items-center justify-center p-3 md:p-6 overflow-y-auto">
      <div className="relative w-full max-w-4xl bg-gradient-to-b from-slate-900 via-slate-950 to-black border border-amber-500/40 rounded-3xl p-5 md:p-7 shadow-2xl flex flex-col gap-5 max-h-[92vh] overflow-y-auto">
        {/* Top Header */}
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl bg-amber-500/20 border border-amber-500/40 flex items-center justify-center text-amber-400">
              <Wallet className="w-5 h-5" />
            </div>
            <h2 className="text-lg font-black text-white tracking-wide">余额</h2>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={refreshAll}
              disabled={loading}
              className="p-2 text-slate-400 hover:text-white rounded-xl hover:bg-slate-800 transition"
              title="刷新"
            >
              <RotateCcw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            </button>
            <button
              onClick={onClose}
              className="p-2 text-slate-400 hover:text-white rounded-xl hover:bg-slate-800 transition"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Navigation Tabs */}
        <div className="flex items-center gap-2 border-b border-slate-800 pb-2">
          <button
            onClick={() => setActiveTab('my')}
            className={`px-3.5 py-1.5 rounded-xl text-xs font-bold transition flex items-center gap-1.5 ${
              activeTab === 'my'
                ? 'bg-amber-500 text-slate-950 shadow-glow-gold'
                : 'bg-slate-900 text-slate-300 hover:bg-slate-800'
            }`}
          >
            <Wallet className="w-3.5 h-3.5" />
            我的
            {myBalance && myBalance.unsettled_games_count > 0 && (
              <span className={`text-[10px] px-1.5 py-0.2 rounded-full font-black ${
                activeTab === 'my' ? 'bg-slate-950 text-amber-300' : 'bg-amber-950 text-amber-300'
              }`}>
                {myBalance.unsettled_games_count}
              </span>
            )}
          </button>

          <button
            onClick={() => setActiveTab('hands')}
            className={`px-3.5 py-1.5 rounded-xl text-xs font-bold transition flex items-center gap-1.5 ${
              activeTab === 'hands'
                ? 'bg-amber-500 text-slate-950 shadow-glow-gold'
                : 'bg-slate-900 text-slate-300 hover:bg-slate-800'
            }`}
          >
            <Layers className="w-3.5 h-3.5" />
            牌局
            {handHistory.total > 0 && (
              <span className={`text-[10px] px-1.5 rounded-full font-black ${
                activeTab === 'hands' ? 'bg-slate-950 text-amber-300' : 'bg-slate-800 text-slate-400'
              }`}>
                {handHistory.total}
              </span>
            )}
          </button>

          <button
            onClick={() => setActiveTab('history')}
            className={`px-3.5 py-1.5 rounded-xl text-xs font-bold transition flex items-center gap-1.5 ${
              activeTab === 'history'
                ? 'bg-amber-500 text-slate-950 shadow-glow-gold'
                : 'bg-slate-900 text-slate-300 hover:bg-slate-800'
            }`}
          >
            <History className="w-3.5 h-3.5" />
            记录
            {batches.length > 0 && (
              <span className={`text-[10px] px-1.5 py-0.2 rounded-full font-black ${
                activeTab === 'history' ? 'bg-slate-950 text-amber-300' : 'bg-slate-800 text-slate-400'
              }`}>
                {batches.length}
              </span>
            )}
          </button>

          {currentUser?.is_admin && (
            <button
              onClick={() => setActiveTab('admin')}
              className={`px-3.5 py-1.5 rounded-xl text-xs font-bold transition flex items-center gap-1.5 ${
                activeTab === 'admin'
                  ? 'bg-amber-500 text-slate-950 shadow-glow-gold'
                  : 'bg-amber-950/40 text-amber-300 border border-amber-500/30 hover:bg-amber-900/50'
              }`}
            >
              <ShieldCheck className="w-3.5 h-3.5" />
              对账
              {overview?.preview?.entry_count > 0 && (
                <span className={`text-[10px] px-1.5 py-0.2 rounded-full font-black ${
                  activeTab === 'admin' ? 'bg-slate-950 text-amber-300' : 'bg-amber-500 text-slate-950'
                }`}>
                  {overview.preview.entry_count}
                </span>
              )}
            </button>
          )}
        </div>

        {/* Notices */}
        {error && (
          <div className="flex items-center gap-2 p-3 bg-red-950/80 border border-red-500/60 rounded-xl text-red-300 text-xs font-bold">
            <AlertCircle className="w-4 h-4 text-red-400 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}
        {successMsg && (
          <div className="flex items-center gap-2 p-3 bg-emerald-950/80 border border-emerald-500/60 rounded-xl text-emerald-300 text-xs font-bold">
            <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
            <span>{successMsg}</span>
          </div>
        )}

        {/* Tab 1: My Account View */}
        {activeTab === 'my' && (
          <div className="flex flex-col gap-4">
            {/* My Balance Summary Card */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <div className="p-3.5 rounded-2xl bg-gradient-to-br from-slate-900 to-slate-950 border border-slate-800 flex flex-col gap-0.5">
                <span className="text-[11px] text-slate-400 font-medium">待结金额</span>
                <div className={`text-2xl font-black flex items-center gap-1 ${
                  (myBalance?.pending_net_cash || 0) >= 0 ? 'text-emerald-400' : 'text-red-400'
                }`}>
                  {(myBalance?.pending_net_cash || 0) >= 0 ? (
                    <TrendingUp className="w-5 h-5" />
                  ) : (
                    <TrendingDown className="w-5 h-5" />
                  )}
                  {(myBalance?.pending_net_cash || 0) >= 0 ? '+' : ''}
                  ¥{(myBalance?.pending_net_cash || 0).toFixed(2)}
                </div>
              </div>

              <div className="p-3.5 rounded-2xl bg-slate-900/60 border border-slate-800 flex flex-col gap-0.5">
                <span className="text-[11px] text-slate-400 font-medium">待结筹码</span>
                <div className="text-2xl font-black text-amber-300">
                  {(myBalance?.pending_net_chips || 0) >= 0 ? '+' : ''}
                  {myBalance?.pending_net_chips || 0}
                </div>
              </div>

              <div className="p-3.5 rounded-2xl bg-slate-900/60 border border-slate-800 flex flex-col gap-0.5">
                <span className="text-[11px] text-slate-400 font-medium">余额流水</span>
                <div className="text-2xl font-black text-slate-200">
                  {myBalance?.unsettled_games_count || 0} 笔
                </div>
              </div>
            </div>

            {/* My Match Ledger History */}
            <div className="flex flex-col gap-2">
              <h3 className="text-xs font-bold text-amber-400 uppercase tracking-wider">
                账单
              </h3>
              {(!myBalance?.records || myBalance.records.length === 0) ? (
                <div className="p-6 rounded-2xl border border-slate-800 bg-slate-950/40 text-center text-slate-400 text-xs">
                  暂无记录
                </div>
              ) : (
                <div className="overflow-hidden rounded-2xl border border-slate-800 bg-slate-950/60">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-slate-900 text-slate-400 font-semibold border-b border-slate-800">
                      <tr>
                        <th className="p-3">房间 / 时间</th>
                        <th className="p-3 text-center">流水</th>
                        <th className="p-3 text-right">筹码变动</th>
                        <th className="p-3 text-right">余额变动</th>
                        <th className="p-3 text-center">状态</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/60">
                      {myBalance.records.map((rec) => {
                        const myRec = rec.my_record || {};
                        const isCredit = (myRec.net_cash || 0) > 0;
                        const dateStr = new Date(rec.created_at * 1000).toLocaleString();
                        const isSettled = rec.status === 'settled';
                        const entryLabels = {
                          buyin: '买入扣款',
                          cashout: '筹码兑回',
                          mode_change: '模式切换',
                          settlement: '对局结算',
                        };
                        return (
                          <tr key={rec.entry_id} className="hover:bg-slate-900/40 transition">
                            <td className="p-3">
                              <div className="font-bold text-slate-200 flex items-center gap-1.5">
                                {rec.room_name}
                                {rec.is_test_game && (
                                  <span className="text-[9px] bg-purple-950 text-purple-300 border border-purple-500/40 px-1 rounded">
                                    测试
                                  </span>
                                )}
                              </div>
                              <div className="text-[10px] text-slate-500 font-mono mt-0.5">{dateStr}</div>
                            </td>
                            <td className="p-3 text-center">
                              <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold border ${
                                isCredit
                                  ? 'bg-emerald-950/60 text-emerald-300 border-emerald-500/30'
                                  : 'bg-red-950/60 text-red-300 border-red-500/30'
                              }`}>
                                {entryLabels[rec.entry_kind] || '对局结算'}
                              </span>
                            </td>
                            <td className={`p-3 text-right font-bold ${isCredit ? 'text-emerald-400' : 'text-red-400'}`}>
                              {(myRec.net_chips || 0) > 0 ? '+' : ''}{myRec.net_chips || 0}
                            </td>
                            <td className={`p-3 text-right font-black ${isCredit ? 'text-emerald-400' : 'text-red-400'}`}>
                              {(myRec.net_cash || 0) > 0 ? '+' : ''}¥{(myRec.net_cash || 0).toFixed(2)}
                            </td>
                            <td className="p-3 text-center">
                              <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold ${
                                isSettled
                                  ? 'bg-slate-800 text-slate-400'
                                  : 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                              }`}>
                                {isSettled ? '已划转' : '待划转'}
                              </span>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Personal per-hand history. Hole cards belong only to this user. */}
        {activeTab === 'hands' && (
          <div className="flex flex-col gap-4">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
              <div className="grid grid-cols-2 gap-2 flex-1">
                <div className="rounded-2xl border border-emerald-500/30 bg-emerald-950/20 p-3">
                  <div className="text-[10px] text-emerald-300">最大赢牌</div>
                  <div className="text-lg font-black text-emerald-400">
                    +{handHistory.summary?.biggest_win?.net_chips || 0}
                  </div>
                </div>
                <div className="rounded-2xl border border-red-500/30 bg-red-950/20 p-3">
                  <div className="text-[10px] text-red-300">最大输牌</div>
                  <div className="text-lg font-black text-red-400">
                    {handHistory.summary?.biggest_loss?.net_chips || 0}
                  </div>
                </div>
              </div>
              <div className="flex gap-2">
                <select
                  value={handOutcome}
                  onChange={(event) => setHandOutcome(event.target.value)}
                  className="rounded-xl border border-slate-700 bg-slate-900 px-3 py-2 text-xs text-slate-200"
                >
                  <option value="all">全部结果</option>
                  <option value="win">只看赢牌</option>
                  <option value="loss">只看输牌</option>
                  <option value="even">只看持平</option>
                </select>
                <select
                  value={handSort}
                  onChange={(event) => setHandSort(event.target.value)}
                  className="rounded-xl border border-slate-700 bg-slate-900 px-3 py-2 text-xs text-slate-200"
                >
                  <option value="recent">最近牌局</option>
                  <option value="biggest-win">赢得最多</option>
                  <option value="biggest-loss">输得最多</option>
                </select>
              </div>
            </div>

            {handHistory.hands.length === 0 ? (
              <div className="p-8 rounded-2xl border border-slate-800 bg-slate-950/40 text-center text-slate-400 text-xs">
                暂无符合条件的牌局
              </div>
            ) : (
              <div className="overflow-hidden rounded-2xl border border-slate-800 bg-slate-950/60">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-900 text-slate-400 border-b border-slate-800">
                    <tr>
                      <th className="p-3">牌局</th>
                      <th className="p-3">我的手牌</th>
                      <th className="p-3">公共牌</th>
                      <th className="p-3 text-right">投入 / 收回</th>
                      <th className="p-3 text-right">净结果</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60">
                    {handHistory.hands.map((hand) => {
                      const positive = hand.net_chips >= 0;
                      const cardText = (card) => card.display || `${card.rank_symbol || card.rank}${card.suit_symbol || card.suit}`;
                      return (
                        <tr key={hand.hand_id} className="hover:bg-slate-900/40">
                          <td className="p-3">
                            <div className="font-bold text-slate-200">{hand.room_name} · #{hand.hand_number}</div>
                            <div className="mt-0.5 text-[10px] text-slate-500">
                              {new Date(hand.ended_at * 1000).toLocaleString()}
                              {hand.money_mode === 'play' && <span className="ml-1 text-purple-300">测试</span>}
                            </div>
                          </td>
                          <td className="p-3 font-black text-amber-300">
                            {(hand.hole_cards || []).map(cardText).join(' ') || '—'}
                            <div className="text-[10px] font-normal text-slate-500">{hand.hand_description}</div>
                          </td>
                          <td className="p-3 text-slate-300">
                            {(hand.board || []).map(cardText).join(' ') || '—'}
                          </td>
                          <td className="p-3 text-right text-slate-400">
                            {hand.contributed_chips} / {hand.payout_chips}
                          </td>
                          <td className={`p-3 text-right font-black ${positive ? 'text-emerald-400' : 'text-red-400'}`}>
                            {positive ? '+' : ''}{hand.net_chips}
                            {hand.money_mode === 'real' && (
                              <div className="text-[10px]">{positive ? '+' : ''}¥{Number(hand.net_cash || 0).toFixed(2)}</div>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* Settlement Batches History */}
        {activeTab === 'history' && (
          <div className="flex flex-col gap-4">
            <h3 className="text-xs font-bold text-amber-400 uppercase tracking-wider">
              结算记录
            </h3>

            {batches.length === 0 ? (
              <div className="p-8 rounded-2xl border border-slate-800 bg-slate-950/40 text-center text-slate-400 text-xs">
                暂无记录
              </div>
            ) : (
              <div className="flex flex-col gap-3">
                {batches.map((batch) => {
                  const dateStr = new Date(batch.created_at * 1000).toLocaleString();
                  const isExpanded = selectedBatch?.batch_id === batch.batch_id;
                  return (
                    <div
                      key={batch.batch_id}
                      className="border border-slate-800 bg-slate-950/60 rounded-2xl p-4 flex flex-col gap-3 transition hover:border-slate-700"
                    >
                      <div className="flex flex-col md:flex-row md:items-center justify-between gap-2">
                        <div className="flex items-center gap-2.5">
                          <span className="font-mono text-xs font-black text-amber-400 bg-amber-950/80 px-2 py-1 rounded-lg border border-amber-500/30">
                            #{batch.batch_id}
                          </span>
                          <div>
                            <div className="text-xs font-bold text-white flex items-center gap-2">
                              <span>{batch.operator_name}</span>
                              <span className="text-slate-500">·</span>
                              <span className="text-slate-400">{batch.entry_ids?.length || 0} 局</span>
                            </div>
                            <div className="text-[10px] text-slate-500 font-mono mt-0.5 flex items-center gap-1">
                              <Calendar className="w-3 h-3" />
                              {dateStr}
                            </div>
                          </div>
                        </div>

                        <div className="flex items-center gap-2">
                          <div className="text-right">
                            <div className="text-xs text-slate-400">转账总额</div>
                            <div className="text-sm font-black text-amber-400">
                              ¥{(batch.total_transferred_cash || 0).toFixed(2)}
                            </div>
                          </div>
                          <button
                            onClick={() => setSelectedBatch(isExpanded ? null : batch)}
                            className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-bold rounded-xl border border-slate-700 transition"
                          >
                            {isExpanded ? '收起' : '明细'}
                          </button>
                          <button
                            onClick={() => copyBatchText(batch)}
                            className="px-3 py-1.5 bg-amber-500 hover:bg-amber-400 text-slate-950 text-xs font-black rounded-xl shadow transition flex items-center gap-1"
                          >
                            {copied ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
                            {copied ? '已复制' : '复制'}
                          </button>
                        </div>
                      </div>

                      {/* Expanded Batch Detail */}
                      {isExpanded && (
                        <div className="border-t border-slate-800/80 pt-3 flex flex-col gap-3">
                          {/* User Summaries in this batch */}
                          <div className="flex flex-col gap-1.5">
                            <span className="text-[11px] font-bold text-slate-400">净额</span>
                            <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                              {(batch.user_summaries || []).map((u, i) => {
                                const isPos = u.net_cash >= 0;
                                return (
                                  <div
                                    key={i}
                                    className="p-2.5 rounded-xl bg-slate-900 border border-slate-800 flex items-center justify-between text-xs"
                                  >
                                    <span className="font-bold text-slate-200 truncate">{u.nickname}</span>
                                    <span className={`font-black ${isPos ? 'text-emerald-400' : 'text-red-400'}`}>
                                      {isPos ? '+' : ''}¥{u.net_cash.toFixed(2)}
                                    </span>
                                  </div>
                                );
                              })}
                            </div>
                          </div>

                          {/* Minimal Transfers in this batch */}
                          <div className="flex flex-col gap-1.5">
                            <span className="text-[11px] font-bold text-slate-400">转账</span>
                            {(!batch.transactions || batch.transactions.length === 0) ? (
                              <div className="p-2.5 rounded-xl bg-slate-900/50 text-center text-slate-400 text-xs">
                                无需转账
                              </div>
                            ) : (
                              <div className="flex flex-col gap-1.5">
                                {batch.transactions.map((t, idx) => (
                                  <div
                                    key={idx}
                                    className="flex items-center justify-between p-2.5 rounded-xl border border-slate-800 bg-slate-900/70 text-xs"
                                  >
                                    <div className="flex items-center gap-2">
                                      <span className="font-bold text-red-400 bg-red-950/80 px-2 py-0.5 rounded border border-red-900/60">
                                        {t.from_player_name}
                                      </span>
                                      <ArrowRight className="w-3.5 h-3.5 text-slate-500" />
                                      <span className="font-bold text-emerald-400 bg-emerald-950/80 px-2 py-0.5 rounded border border-emerald-900/60">
                                        {t.to_player_name}
                                      </span>
                                    </div>
                                    <span className="font-black text-amber-400 text-sm">
                                      ¥{t.amount_cash.toFixed(2)}
                                    </span>
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* Tab 3: Admin Consolidated Settlement & Audit */}
        {activeTab === 'admin' && currentUser?.is_admin && (
          <div className="flex flex-col gap-5">
            {/* Top Toolbar / Filter */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 p-3 rounded-2xl bg-slate-900/80 border border-slate-800">
              <label className="flex items-center gap-2 text-xs font-bold text-slate-300 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={includeTest}
                  onChange={(e) => setIncludeTest(e.target.checked)}
                  className="rounded border-slate-700 text-amber-500 focus:ring-amber-500"
                />
                <span>含测试</span>
              </label>

              <div className="flex items-center gap-2">
                <button
                  onClick={handleClearTestRecords}
                  disabled={loading}
                  className="px-3 py-1.5 bg-red-950/60 hover:bg-red-900 text-red-300 text-xs font-bold rounded-xl border border-red-500/40 transition flex items-center gap-1 cursor-pointer"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                  清理测试数据
                </button>
                <button
                  onClick={handleClearAllRecords}
                  disabled={loading}
                  className="px-3 py-1.5 bg-red-600 hover:bg-red-500 text-white text-xs font-black rounded-xl shadow-lg transition flex items-center gap-1 active:scale-95 cursor-pointer"
                >
                  <RotateCcw className="w-3.5 h-3.5" />
                  清空数据
                </button>
              </div>
            </div>

            {/* Overview Stats */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <div className="p-3.5 rounded-2xl bg-slate-900/70 border border-slate-800 flex flex-col gap-0.5">
                <span className="text-[11px] text-slate-400 font-medium">余额流水</span>
                <div className="text-2xl font-black text-amber-400">
                  {overview?.preview?.entry_count || 0} 笔
                </div>
              </div>

              <div className="p-3.5 rounded-2xl bg-slate-900/70 border border-slate-800 flex flex-col gap-0.5">
                <span className="text-[11px] text-slate-400 font-medium">活跃玩家</span>
                <div className="text-2xl font-black text-slate-200">
                  {overview?.user_balances?.length || 0} 人
                </div>
              </div>

              <div className="p-3.5 rounded-2xl bg-gradient-to-br from-amber-950/30 via-slate-900 to-slate-950 border border-amber-500/40 flex flex-col gap-0.5">
                <span className="text-[11px] text-amber-400 font-medium">划转总额</span>
                <div className="text-2xl font-black text-amber-400">
                  ¥{(overview?.preview?.total_transferred_cash || 0).toFixed(2)}
                </div>
              </div>
            </div>

            {/* User Balances Table */}
            <div className="flex flex-col gap-2">
              <h3 className="text-xs font-bold text-amber-400 uppercase tracking-wider">
                待结清单
              </h3>
              {(!overview?.user_balances || overview.user_balances.length === 0) ? (
                <div className="p-6 rounded-2xl border border-slate-800 bg-slate-950/40 text-center text-slate-400 text-xs">
                  暂无待结数据
                </div>
              ) : (
                <div className="overflow-hidden rounded-2xl border border-slate-800 bg-slate-950/60">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-slate-900 text-slate-400 font-semibold border-b border-slate-800">
                      <tr>
                        <th className="p-3">玩家</th>
                        <th className="p-3 text-center">余额流水</th>
                        <th className="p-3 text-right">待结筹码</th>
                        <th className="p-3 text-right">待结金额 (¥)</th>
                        <th className="p-3 text-center">状态</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/60">
                      {overview.user_balances.map((u) => {
                        const isProfit = u.net_cash >= 0;
                        return (
                          <tr key={u.user_id} className="hover:bg-slate-900/40 transition">
                            <td className="p-3 font-bold text-white flex items-center gap-2">
                              <span className="w-7 h-7 rounded-full bg-slate-900 border border-slate-700 flex items-center justify-center text-sm">
                                {u.avatar || '👤'}
                              </span>
                              <span>{u.nickname}</span>
                              {u.is_test && (
                                <span className="text-[9px] bg-purple-950 text-purple-300 border border-purple-500/40 px-1 rounded font-bold">
                                  测试
                                </span>
                              )}
                            </td>
                            <td className="p-3 text-center text-slate-300">
                              {u.unsettled_games_count} 笔
                            </td>
                            <td className="p-3 text-right text-amber-300 font-bold">
                              {u.net_chips > 0 ? '+' : ''}{u.net_chips}
                            </td>
                            <td className={`p-3 text-right font-black ${isProfit ? 'text-emerald-400' : 'text-red-400'}`}>
                              {isProfit ? '+' : ''}¥{u.net_cash.toFixed(2)}
                            </td>
                            <td className="p-3 text-center">
                              <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold ${
                                isProfit
                                  ? 'bg-emerald-950 text-emerald-300 border border-emerald-500/40'
                                  : 'bg-red-950 text-red-300 border border-red-500/40'
                              }`}>
                                {isProfit ? '应收' : '应付'}
                              </span>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            {/* Minimal Debt Transfer Preview */}
            <div className="flex flex-col gap-2">
              <h3 className="text-xs font-bold text-amber-400 uppercase tracking-wider">
                转账方案
              </h3>

              {(!overview?.preview?.transactions || overview.preview.transactions.length === 0) ? (
                <div className="p-4 rounded-xl border border-slate-800 bg-slate-950/40 text-center text-slate-400 text-xs">
                  无需转账
                </div>
              ) : (
                <div className="flex flex-col gap-2">
                  {overview.preview.transactions.map((t, idx) => (
                    <div
                      key={idx}
                      className="flex items-center justify-between p-3 rounded-xl border border-slate-800 bg-slate-900/60 shadow"
                    >
                      <div className="flex items-center gap-2 text-xs">
                        <span className="font-bold text-red-400 bg-red-950/80 px-2 py-1 rounded-lg border border-red-900/60">
                          {t.from_player_name}
                        </span>
                        <ArrowRight className="w-3.5 h-3.5 text-slate-500" />
                        <span className="font-bold text-emerald-400 bg-emerald-950/80 px-2 py-1 rounded-lg border border-emerald-900/60">
                          {t.to_player_name}
                        </span>
                      </div>
                      <span className="font-black text-amber-400 text-sm">
                        ¥{t.amount_cash.toFixed(2)}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {overview?.preview?.entry_count > 0 && overview?.preview?.is_balanced === false && (
              <div className="flex items-center gap-2 rounded-xl border border-amber-500/50 bg-amber-950/40 p-3 text-xs font-bold text-amber-300">
                <AlertCircle className="h-4 w-4 flex-shrink-0" />
                仍有¥{(overview?.preview?.unmatched_cash || 0).toFixed(2)} 对应筹码在桌，全部兑回余额后才能划转。
              </div>
            )}

            {/* Batch Settle Action Button */}
            <div className="pt-2 flex justify-end">
              <button
                disabled={loading || !overview?.preview?.entry_count || overview?.preview?.is_balanced === false}
                onClick={() => setSettleConfirmOpen(true)}
                className={`px-5 py-2.5 rounded-xl font-black text-xs flex items-center gap-2 shadow-lg transition active:scale-95 ${
                  overview?.preview?.entry_count && overview?.preview?.is_balanced !== false
                    ? 'bg-gradient-to-r from-amber-500 via-amber-400 to-amber-500 text-slate-950 shadow-glow-gold hover:brightness-105 cursor-pointer'
                    : 'bg-slate-800 text-slate-500 cursor-not-allowed border border-slate-700'
                }`}
              >
                <CheckCircle2 className="w-4 h-4" />
                划转结算 ({overview?.preview?.entry_count || 0} 笔)
              </button>
            </div>
          </div>
        )}

        {/* Batch Settlement Confirmation Modal */}
        {settleConfirmOpen && (
          <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
            <div className="relative w-full max-w-md bg-gradient-to-b from-slate-900 to-black border border-amber-500/50 rounded-3xl p-5 shadow-2xl flex flex-col gap-4">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-xl bg-amber-500/20 border border-amber-500/40 flex items-center justify-center text-amber-400">
                  <CheckCircle2 className="w-5 h-5" />
                </div>
                <h3 className="text-base font-black text-white">确认余额划转？</h3>
              </div>

              <div className="p-3.5 rounded-2xl bg-slate-950/80 border border-slate-800 text-xs flex flex-col gap-2">
                <div className="flex justify-between text-slate-300">
                  <span>余额流水:</span>
                  <span className="font-bold text-amber-400">{overview?.preview?.entry_count || 0} 笔</span>
                </div>
                <div className="flex justify-between text-slate-300">
                  <span>涉及玩家:</span>
                  <span className="font-bold text-white">{overview?.user_balances?.length || 0} 位</span>
                </div>
                <div className="flex justify-between text-slate-300">
                  <span>转账总额:</span>
                  <span className="font-black text-amber-400">¥{(overview?.preview?.total_transferred_cash || 0).toFixed(2)}</span>
                </div>
                <div className="flex justify-between text-slate-300">
                  <span>转账笔数:</span>
                  <span className="font-bold text-slate-200">{overview?.preview?.transactions?.length || 0} 笔</span>
                </div>
              </div>

              <div className="max-h-52 overflow-y-auto rounded-2xl border border-slate-800 bg-slate-950/80 p-3">
                <div className="mb-2 text-[11px] font-bold text-slate-400">本次付款关系</div>
                {(!overview?.preview?.transactions || overview.preview.transactions.length === 0) ? (
                  <div className="py-3 text-center text-xs text-slate-400">无需转账</div>
                ) : (
                  <div className="flex flex-col gap-2">
                    {overview.preview.transactions.map((transaction, index) => (
                      <div key={index} className="flex items-center justify-between gap-3 rounded-xl bg-slate-900 p-2.5 text-xs">
                        <div className="flex min-w-0 items-center gap-2">
                          <span className="truncate font-bold text-red-400">{transaction.from_player_name}</span>
                          <ArrowRight className="h-3.5 w-3.5 flex-shrink-0 text-slate-500" />
                          <span className="truncate font-bold text-emerald-400">{transaction.to_player_name}</span>
                        </div>
                        <span className="flex-shrink-0 font-black text-amber-400">¥{transaction.amount_cash.toFixed(2)}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div className="flex gap-2.5 pt-1">
                <button
                  onClick={() => setSettleConfirmOpen(false)}
                  className="flex-1 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 font-bold text-xs rounded-xl border border-slate-700 transition"
                >
                  取消
                </button>
                <button
                  disabled={loading}
                  onClick={handleExecuteBatchSettle}
                  className="flex-1 py-2 bg-amber-500 hover:bg-amber-400 text-slate-950 font-black text-xs rounded-xl shadow-glow-gold transition flex items-center justify-center gap-1.5"
                >
                  {loading ? '处理中...' : '确认划转'}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
