import React from 'react';
import CardView from './CardView';
import { Eye, EyeOff } from 'lucide-react';

export default function ShowCardsModal({
  holeCards = [],
  onShowCard,
  onClose,
}) {
  if (!holeCards || holeCards.length < 2) return null;

  return (
    <div className="fixed bottom-28 left-1/2 -translate-x-1/2 z-40 bg-slate-900/95 border border-amber-500/50 rounded-2xl p-3 shadow-2xl backdrop-blur-md flex flex-col items-center gap-2 animate-bounce">
      <div className="text-xs font-bold text-amber-300 flex items-center gap-1">
        <Eye className="w-3.5 h-3.5" />
        局末亮牌展示选择
      </div>

      <div className="flex gap-3 items-center">
        {/* Card 1 */}
        <div className="flex flex-col items-center gap-1">
          <CardView card={holeCards[0]} size="md" />
          <button
            onClick={() => onShowCard(0, false)}
            className="px-2 py-0.5 bg-slate-800 hover:bg-slate-700 text-[11px] font-semibold text-amber-400 rounded border border-slate-700 transition"
          >
            亮左牌
          </button>
        </div>

        {/* Card 2 */}
        <div className="flex flex-col items-center gap-1">
          <CardView card={holeCards[1]} size="md" />
          <button
            onClick={() => onShowCard(1, false)}
            className="px-2 py-0.5 bg-slate-800 hover:bg-slate-700 text-[11px] font-semibold text-amber-400 rounded border border-slate-700 transition"
          >
            亮右牌
          </button>
        </div>
      </div>

      <div className="flex gap-2 mt-1">
        <button
          onClick={() => onShowCard(null, true)}
          className="px-3 py-1 bg-amber-500 hover:bg-amber-400 text-slate-950 text-xs font-bold rounded-lg transition"
        >
          全部亮出
        </button>
        <button
          onClick={onClose}
          className="px-3 py-1 bg-slate-800 hover:bg-slate-700 text-slate-400 text-xs font-medium rounded-lg transition flex items-center gap-1"
        >
          <EyeOff className="w-3 h-3" />
          藏牌 (Muck)
        </button>
      </div>
    </div>
  );
}
