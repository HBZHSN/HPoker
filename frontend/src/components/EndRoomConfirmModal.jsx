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
            <div className="w-8 h-8 rounded-xl bg-amber-500/20 border border-amber-500/40 flex items-center justify-center text-amber-400">
              <Award className="w-4 h-4" />
            </div>
            <h3 className="text-base font-black text-white">结算</h3>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 transition"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Options */}
        <div className="flex flex-col gap-2.5">
          {/* Option 1: Record to Balance */}
          <div
            onClick={() => setSettlementType('balance')}
            className={`p-3.5 rounded-2xl border transition cursor-pointer flex items-center justify-between select-none ${
              settlementType === 'balance'
                ? 'bg-amber-950/40 border-amber-500 shadow-glow-gold'
                : 'bg-slate-900/60 border-slate-800 hover:border-slate-700'
            }`}
          >
            <div className="flex items-center gap-2.5">
              <div className={`w-5 h-5 rounded-full border flex items-center justify-center flex-shrink-0 ${
                settlementType === 'balance'
                  ? 'border-amber-400 bg-amber-400 text-slate-950'
                  : 'border-slate-600'
              }`}>
                {settlementType === 'balance' && <CheckCircle2 className="w-4 h-4" />}
              </div>
              <span className="text-sm font-black text-white">计入余额</span>
            </div>
          </div>

          {/* Option 2: Immediate Transfer */}
          <div
            onClick={() => setSettlementType('immediate')}
            className={`p-3.5 rounded-2xl border transition cursor-pointer flex items-center justify-between select-none ${
              settlementType === 'immediate'
                ? 'bg-emerald-950/40 border-emerald-500 shadow-glow-emerald'
                : 'bg-slate-900/60 border-slate-800 hover:border-slate-700'
            }`}
          >
            <div className="flex items-center gap-2.5">
              <div className={`w-5 h-5 rounded-full border flex items-center justify-center flex-shrink-0 ${
                settlementType === 'immediate'
                  ? 'border-emerald-400 bg-emerald-400 text-slate-950'
                  : 'border-slate-600'
              }`}>
                {settlementType === 'immediate' && <CheckCircle2 className="w-4 h-4" />}
              </div>
              <span className="text-sm font-black text-white">实时转账</span>
            </div>
          </div>
        </div>

        {/* Test Account Notice */}
        {hasTestAccount && (
          <div className="flex items-center gap-2 px-3 py-2 bg-purple-950/30 border border-purple-500/40 rounded-xl text-purple-300 text-xs">
            <AlertCircle className="w-3.5 h-3.5 flex-shrink-0" />
            <span>包含测试账号</span>
          </div>
        )}

        {/* Actions */}
        <div className="flex items-center gap-3 pt-1">
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
            确认
          </button>
        </div>
      </div>
    </div>
  );
}
