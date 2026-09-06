import React, { useEffect } from 'react';
import CardView from './CardView';
import { sortCardsWithIndex } from '../utils/cards';
import { resolveHandEndHotkey } from '../utils/tableShortcuts';
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

  useEffect(() => {
    const handleKeyDown = (e) => {
      const action = resolveHandEndHotkey(e);
      if (!action) return;

      if (action.type === 'TOGGLE_CARD') {
        e.preventDefault();
        if (action.cardIndex === 0 && leftCard) {
          onShowCard(leftCard.index, false);
        } else if (action.cardIndex === 1 && rightCard) {
          onShowCard(rightCard.index, false);
        }
      } else if (action.type === 'SHOW_ALL') {
        e.preventDefault();
        onShowCard(null, true);
      } else if (action.type === 'HIDE_ALL' || action.type === 'CLOSE') {
        e.preventDefault();
        if (onClose) onClose();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [leftCard, rightCard, onShowCard, onClose]);

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
            title="亮左牌 (快捷键 1)"
            className="px-3 py-1 bg-slate-800 hover:bg-slate-700 text-xs font-bold text-amber-400 rounded-lg border border-slate-600 shadow transition active:scale-95 flex items-center gap-1 cursor-pointer"
          >
            <span>亮左牌</span>
            <span className="font-mono text-[9px] opacity-75">[1]</span>
          </button>
        </div>

        {/* Card 2 */}
        <div className="flex flex-col items-center gap-2">
          <CardView card={rightCard.card} size="md" />
          <button
            onClick={() => onShowCard(rightCard.index, false)}
            title="亮右牌 (快捷键 2)"
            className="px-3 py-1 bg-slate-800 hover:bg-slate-700 text-xs font-bold text-amber-400 rounded-lg border border-slate-600 shadow transition active:scale-95 flex items-center gap-1 cursor-pointer"
          >
            <span>亮右牌</span>
            <span className="font-mono text-[9px] opacity-75">[2]</span>
          </button>
        </div>
      </div>

      <div className="flex gap-3 mt-1 w-full justify-center">
        <button
          onClick={() => onShowCard(null, true)}
          title="全部亮出 (快捷键 A)"
          className="px-4 py-1.5 bg-amber-500 hover:bg-amber-400 text-slate-950 text-xs font-black rounded-lg shadow-md transition active:scale-95 flex items-center gap-1 cursor-pointer"
        >
          <span>全部亮出</span>
          <span className="font-mono text-[9px] opacity-75">[A]</span>
        </button>
        <button
          onClick={onClose}
          title="不亮牌 (快捷键 H / Esc)"
          className="px-4 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-bold rounded-lg border border-slate-600 shadow transition active:scale-95 flex items-center gap-1 cursor-pointer"
        >
          <EyeOff className="w-3.5 h-3.5" />
          <span>不亮牌</span>
          <span className="font-mono text-[9px] opacity-75">[H]</span>
        </button>
      </div>
    </div>
  );
}
