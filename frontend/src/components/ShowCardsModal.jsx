import React from 'react';
import CardView from './CardView';
import { sortCardsWithIndex } from '../utils/cards';
import { Eye, EyeOff } from 'lucide-react';

export default function ShowCardsModal({
  holeCards = [],
  onShowCard,
  onClose,
}) {
  if (!holeCards || holeCards.length < 2) return null;

  const orderedHoleCards = sortCardsWithIndex(holeCards);
  const leftCard = orderedHoleCards[0];
  const rightCard = orderedHoleCards[1];

  return (
    <div className="fixed bottom-24 left-1/2 -translate-x-1/2 z-40 bg-slate-900/95 border-2 border-amber-500/60 rounded-2xl p-4 shadow-2xl backdrop-blur-md flex flex-col items-center gap-3">
      <div className="text-sm font-bold text-amber-300 flex items-center gap-1.5">
        <Eye className="w-4 h-4 text-amber-400" />
        亮牌
      </div>

      <div className="flex gap-4 items-center">
        {/* Card 1 */}
        <div className="flex flex-col items-center gap-2">
          <CardView card={leftCard.card} size="md" />
          <button
            onClick={() => onShowCard(leftCard.index, false)}
            className="px-3 py-1 bg-slate-800 hover:bg-slate-700 text-xs font-bold text-amber-400 rounded-lg border border-slate-600 shadow transition active:scale-95"
          >
            亮左牌
          </button>
        </div>

        {/* Card 2 */}
        <div className="flex flex-col items-center gap-2">
          <CardView card={rightCard.card} size="md" />
          <button
            onClick={() => onShowCard(rightCard.index, false)}
            className="px-3 py-1 bg-slate-800 hover:bg-slate-700 text-xs font-bold text-amber-400 rounded-lg border border-slate-600 shadow transition active:scale-95"
          >
            亮右牌
          </button>
        </div>
      </div>

      <div className="flex gap-3 mt-1 w-full justify-center">
        <button
          onClick={() => onShowCard(null, true)}
          className="px-4 py-1.5 bg-amber-500 hover:bg-amber-400 text-slate-950 text-xs font-black rounded-lg shadow-md transition active:scale-95"
        >
          全部亮出
        </button>
        <button
          onClick={onClose}
          className="px-4 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-bold rounded-lg border border-slate-600 shadow transition active:scale-95 flex items-center gap-1"
        >
          <EyeOff className="w-3.5 h-3.5" />
          不亮牌
        </button>
      </div>
    </div>
  );
}
