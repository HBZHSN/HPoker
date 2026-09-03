import React, { useState } from 'react';
import { Award, CheckCircle2, DollarSign, X, AlertCircle } from 'lucide-react';

export default function EndRoomConfirmModal({
  isOpen,
  hasTestAccount = false,
  onConfirm,
  onClose,
}) {
  const [settlementType, setSettlementType] = useState('balance');

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="relative w-full max-w-md bg-gradient-to-b from-slate-900 via-slate-950 to-black border border-amber-500/40 rounded-3xl p-6 shadow-2xl flex flex-col gap-5 animate-scale-up">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl bg-amber-500/20 border border-amber-500/40 flex items-center justify-center text-amber-400">
              <Award className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-black text-white">结束房间与结算方式</h3>
              <p className="text-[11px] text-slate-400">请选择本局的账目处理方式</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 transition"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Options */}
        <div className="flex flex-col gap-3">
          {/* Option 1: Record to Balance */}
          <div
            onClick={() => setSettlementType('balance')}
            className={`p-4 rounded-2xl border transition cursor-pointer flex items-start gap-3 select-none ${
              settlementType === 'balance'
                ? 'bg-amber-950/40 border-amber-500 shadow-glow-gold'
                : 'bg-slate-900/60 border-slate-800 hover:border-slate-700'
            }`}
          >
            <div className={`mt-0.5 w-5 h-5 rounded-full border flex items-center justify-center flex-shrink-0 ${
              settlementType === 'balance'
                ? 'border-amber-400 bg-amber-400 text-slate-950'
                : 'border-slate-600'
            }`}>
              {settlementType === 'balance' && <CheckCircle2 className="w-4 h-4" />}
            </div>
            <div className="flex flex-col gap-1">
              <div className="flex items-center gap-2">
                <span className="text-sm font-black text-white">计入余额（记账模式）</span>
                <span className="text-[10px] bg-amber-500/20 text-amber-300 px-1.5 py-0.2 rounded font-bold border border-amber-500/30">
                  推荐
                </span>
              </div>
              <p className="text-xs text-slate-400 leading-relaxed">
                将本局各玩家的输赢记入系统账户。后续可在首页【账务中心】由管理员统一一次性结算对账，无需当场逐笔转账。
              </p>
            </div>
          </div>

          {/* Option 2: Immediate Transfer */}
          <div
            onClick={() => setSettlementType('immediate')}
            className={`p-4 rounded-2xl border transition cursor-pointer flex items-start gap-3 select-none ${
              settlementType === 'immediate'
                ? 'bg-emerald-950/40 border-emerald-500 shadow-glow-emerald'
                : 'bg-slate-900/60 border-slate-800 hover:border-slate-700'
            }`}
          >
            <div className={`mt-0.5 w-5 h-5 rounded-full border flex items-center justify-center flex-shrink-0 ${
              settlementType === 'immediate'
                ? 'border-emerald-400 bg-emerald-400 text-slate-950'
                : 'border-slate-600'
            }`}>
              {settlementType === 'immediate' && <CheckCircle2 className="w-4 h-4" />}
            </div>
            <div className="flex flex-col gap-1">
              <span className="text-sm font-black text-white">实时转账（现结模式）</span>
              <p className="text-xs text-slate-400 leading-relaxed">
                当场生成点对点最简转账清单，各玩家私下微信/支付宝结清，不计入系统待结余额。
              </p>
            </div>
          </div>
        </div>

        {/* Test Account Notice */}
        {hasTestAccount && (
          <div className="flex items-start gap-2 p-3 bg-purple-950/30 border border-purple-500/40 rounded-xl text-purple-200 text-xs">
            <AlertCircle className="w-4 h-4 text-purple-400 flex-shrink-0 mt-0.5" />
            <div className="text-[11px] leading-relaxed">
              <span className="font-bold text-purple-300">测试隔离保护：</span>
              当前牌桌包含测试账号或机器人，系统已自动隔离测试数据，绝不会污染真实用户的系统待结余额。
            </div>
          </div>
        )}

        {/* Actions */}
        <div className="flex items-center gap-3 pt-2">
          <button
            type="button"
            onClick={onClose}
            className="flex-1 py-2.5 bg-slate-800 hover:bg-slate-700 text-slate-300 font-bold text-xs rounded-xl border border-slate-700 transition"
          >
            取消
          </button>
          <button
            type="button"
            onClick={() => onConfirm(settlementType)}
            className="flex-1 py-2.5 bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-400 hover:to-amber-500 text-slate-950 font-black text-xs rounded-xl shadow-glow-gold transition active:scale-95"
          >
            确认结算
          </button>
        </div>
      </div>
    </div>
  );
}
