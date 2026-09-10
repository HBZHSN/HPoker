import React, { useEffect } from 'react';
import { createPortal } from 'react-dom';
import { Flame, Clock, X } from 'lucide-react';
import { formatHChipAmount } from '../utils/hCurrency';

export default function AllInConfirmModal({
  isOpen,
  amount = 0,
  turnTimeLeft = 0,
  onConfirm,
  onClose,
}) {
  // Listen for Escape key to cancel
  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e) => {
      if (e.code === 'Escape') {
        e.preventDefault();
        onClose?.();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const modalContent = (
    <div
      className="fixed inset-0 z-[120] flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-fade-in pointer-events-auto"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="allin-confirm-title"
    >
      <div
        className="relative w-full max-w-xs sm:max-w-sm bg-gradient-to-b from-slate-900 via-slate-950 to-black border border-purple-500/60 rounded-2xl p-5 shadow-[0_0_30px_rgba(168,85,247,0.35)] text-slate-100 flex flex-col items-center text-center gap-3 animate-scale-up"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Ambient Glows */}
        <div className="absolute -top-12 -left-12 w-28 h-28 bg-purple-600/15 rounded-full blur-2xl pointer-events-none" />
        <div className="absolute -bottom-12 -right-12 w-28 h-28 bg-amber-600/15 rounded-full blur-2xl pointer-events-none" />

        {/* Close Button */}
        <button
          type="button"
          onClick={onClose}
          className="absolute top-3 right-3 p-1.5 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800/80 transition cursor-pointer"
          aria-label="取消"
        >
          <X className="w-4 h-4" />
        </button>

        {/* Flaming Icon Badge */}
        <div className="w-12 h-12 rounded-full bg-gradient-to-br from-purple-900/90 via-red-950 to-amber-950 border border-purple-400/70 flex items-center justify-center shadow-[0_0_15px_rgba(168,85,247,0.5)] flex-shrink-0">
          <Flame className="w-6 h-6 text-amber-400 fill-amber-400 animate-pulse" />
        </div>

        {/* Title & Amount */}
        <div className="flex flex-col items-center">
          <h3 id="allin-confirm-title" className="text-base font-black text-white tracking-wide">
            确认全下
          </h3>
          <div className="text-2xl font-black text-amber-300 mt-1 tracking-tight">
            {formatHChipAmount(amount)}
          </div>
          <p className="text-xs text-slate-400 mt-0.5 font-medium">
            投入全部筹码
          </p>
        </div>

        {/* Turn Countdown (if thinking timer is running) */}
        {turnTimeLeft > 0 && (
          <div className="flex items-center gap-1 text-[11px] text-amber-400/90 font-mono font-bold bg-slate-900/90 px-2.5 py-1 rounded-full border border-slate-800">
            <Clock className="w-3.5 h-3.5 text-amber-400" />
            <span>剩余思考时间: {Math.ceil(turnTimeLeft)}s</span>
          </div>
        )}

        {/* Confirm and Cancel Buttons */}
        <div className="grid grid-cols-2 gap-2.5 w-full mt-1.5">
          <button
            type="button"
            onClick={onClose}
            className="py-2.5 px-3 rounded-xl bg-slate-800 hover:bg-slate-700 active:scale-95 border border-slate-700 text-slate-200 font-extrabold text-sm transition cursor-pointer shadow"
          >
            取消
          </button>
          <button
            type="button"
            onClick={onConfirm}
            className="py-2.5 px-3 rounded-xl bg-gradient-to-b from-purple-700 via-red-800 to-amber-800 hover:from-purple-600 hover:to-red-700 active:scale-95 border border-purple-400/80 text-amber-200 font-black text-sm transition cursor-pointer shadow-[0_0_15px_rgba(168,85,247,0.4)] flex items-center justify-center gap-1"
          >
            <Flame className="w-4 h-4 text-amber-400 fill-amber-400" />
            确认全下
          </button>
        </div>
      </div>
    </div>
  );

  if (typeof document !== 'undefined' && document.body) {
    return createPortal(modalContent, document.body);
  }

  return modalContent;
}
