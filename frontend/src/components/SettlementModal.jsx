import React, { useState } from 'react';
import { Award, ArrowRight, Copy, Check, X, TrendingUp, TrendingDown, DollarSign } from 'lucide-react';

export default function SettlementModal({
  report,
  onClose,
}) {
  const [copied, setCopied] = useState(false);

  if (!report) return null;

  const copySettlementText = () => {
    let text = `【${report.room_name} - 结算清单】\n`;
    text += `买入: ${report.buyin_chips}筹码 = ¥${report.cash_value}\n\n`;
    text += `--- 玩家战绩 ---\n`;
    report.player_records.forEach((r, idx) => {
      const sign = r.net_cash >= 0 ? '+' : '';
      text += `${idx + 1}. ${r.player_name}: 买入x${r.rebuy_count} (${r.total_buyin_chips}筹码) -> 余额${r.final_chips}筹码 | 净输赢: ${sign}¥${r.net_cash.toFixed(2)}\n`;
    });

    text += `\n--- 转账 ---\n`;
    if (report.transactions.length === 0) {
      text += `无需转账。\n`;
    } else {
      report.transactions.forEach((t, idx) => {
        text += `${idx + 1}. ${t.from_player_name} -> ${t.to_player_name}: ¥${t.amount_cash.toFixed(2)} (${t.amount_chips} 筹码)\n`;
      });
    }

    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2500);
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-md flex items-center justify-center p-4 overflow-y-auto">
      <div className="relative w-full max-w-2xl bg-gradient-to-b from-slate-900 via-slate-900 to-black border border-amber-500/40 rounded-3xl p-6 shadow-2xl flex flex-col gap-5 max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-800 pb-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-2xl bg-amber-500/20 border border-amber-500/40 flex items-center justify-center text-amber-400">
              <Award className="w-6 h-6" />
            </div>
            <div>
              <h2 className="text-xl font-black text-white tracking-wide">战局结束 · 现金结算清单</h2>
              <p className="text-xs text-slate-400">
                {report.room_name} · 买入: ${report.buyin_chips} = ¥{report.cash_value}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 text-slate-400 hover:text-white rounded-xl hover:bg-slate-800 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Player Leaderboard */}
        <div className="flex flex-col gap-2">
          <h3 className="text-xs font-bold text-amber-400 uppercase tracking-wider">玩家战绩</h3>
          <div className="overflow-hidden rounded-xl border border-slate-800 bg-slate-950/60">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-900/80 text-slate-400 font-semibold border-b border-slate-800">
                <tr>
                  <th className="p-2.5">玩家</th>
                  <th className="p-2.5 text-center">买入次数</th>
                  <th className="p-2.5 text-right">总买入筹码</th>
                  <th className="p-2.5 text-right">剩余筹码</th>
                  <th className="p-2.5 text-right">净输赢 (¥)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 font-medium">
                {report.player_records.map((r, i) => {
                  const isProfit = r.net_cash >= 0;
                  return (
                    <tr key={r.player_id} className="hover:bg-slate-900/40 transition">
                      <td className="p-2.5 font-bold text-white flex items-center gap-1.5">
                        <span className="text-[10px] w-4 text-slate-500">{i + 1}</span>
                        <span
                          className="w-7 h-7 rounded-full bg-slate-900 border border-slate-700 flex items-center justify-center text-base leading-none flex-shrink-0"
                          aria-label={`${r.player_name}的头像`}
                        >
                          {r.avatar || '👤'}
                        </span>
                        <span className="truncate">{r.player_name}</span>
                      </td>
                      <td className="p-2.5 text-center text-slate-300">
                        x{r.rebuy_count}
                      </td>
                      <td className="p-2.5 text-right text-slate-400">
                        {r.total_buyin_chips}
                      </td>
                      <td className="p-2.5 text-right text-amber-300 font-bold">
                        {r.final_chips}
                      </td>
                      <td className={`p-2.5 text-right font-black ${isProfit ? 'text-emerald-400' : 'text-red-400'}`}>
                        <div className="flex items-center justify-end gap-1">
                          {isProfit ? <TrendingUp className="w-3.5 h-3.5" /> : <TrendingDown className="w-3.5 h-3.5" />}
                          {isProfit ? '+' : ''}¥{r.net_cash.toFixed(2)}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

        {/* Minimal Transfer Transactions Graph */}
        <div className="flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-bold text-amber-400 uppercase tracking-wider">
              现金转账明细
            </h3>
            <span className="text-[11px] text-slate-400">
              共 {report.transactions.length} 笔支付
            </span>
          </div>

          {report.transactions.length === 0 ? (
            <div className="p-4 rounded-xl border border-slate-800 bg-slate-950/40 text-center text-slate-400 text-xs">
              无需转账
            </div>
          ) : (
            <div className="flex flex-col gap-2">
              {report.transactions.map((t, idx) => (
                <div
                  key={idx}
                  className="flex items-center justify-between p-3 rounded-xl border border-slate-800 bg-gradient-to-r from-red-950/30 via-slate-900 to-emerald-950/30 shadow-inner"
                >
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-red-400 bg-red-950/80 px-2 py-1 rounded-lg text-xs border border-red-900/60">
                      {t.from_player_name}
                    </span>
                    <span className="text-slate-400 text-xs">应付给</span>
                    <ArrowRight className="w-4 h-4 text-amber-400" />
                    <span className="font-bold text-emerald-400 bg-emerald-950/80 px-2 py-1 rounded-lg text-xs border border-emerald-900/60">
                      {t.to_player_name}
                    </span>
                  </div>

                  <div className="flex flex-col items-end">
                    <div className="text-sm font-black text-amber-400">
                      ¥{t.amount_cash.toFixed(2)}
                    </div>
                    <div className="text-[10px] text-slate-400 font-medium">
                      ({t.amount_chips} 筹码)
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Bottom Actions */}
        <div className="flex gap-3 pt-2">
          <button
            onClick={copySettlementText}
            className="flex-1 py-3 bg-amber-500 hover:bg-amber-400 text-slate-950 font-black rounded-xl shadow-lg transition flex items-center justify-center gap-1.5"
          >
            {copied ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
            {copied ? "已复制" : "复制结算清单"}
          </button>
          <button
            onClick={onClose}
            className="px-6 py-3 bg-slate-800 hover:bg-slate-700 text-slate-200 font-bold rounded-xl border border-slate-700 transition"
          >
            返回大厅
          </button>
        </div>
      </div>
    </div>
  );
}
