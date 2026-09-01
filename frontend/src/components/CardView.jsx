import React from 'react';

// Suit Color and Symbol mapping (4-color GGPoker standard)
const SUIT_META = {
  s: { symbol: '♠', color: 'text-slate-900', bg: 'bg-slate-100', border: 'border-slate-300' },
  h: { symbol: '♥', color: 'text-red-600', bg: 'bg-red-50', border: 'border-red-200' },
  c: { symbol: '♣', color: 'text-emerald-700', bg: 'bg-emerald-50', border: 'border-emerald-200' },
  d: { symbol: '♦', color: 'text-blue-600', bg: 'bg-blue-50', border: 'border-blue-200' },
};

export default function CardView({
  card,
  isBack = false,
  size = 'md', // 'sm', 'md', 'lg'
  isHighlighted = false,
  className = '',
}) {
  const sizeClasses = {
    sm: 'w-7 h-10 text-xs rounded-sm',
    md: 'w-11 h-16 text-sm rounded-md',
    lg: 'w-14 h-20 text-base rounded-lg',
  }[size] || 'w-11 h-16 text-sm rounded-md';

  if (isBack || !card) {
    return (
      <div
        className={`relative flex flex-col items-center justify-center border border-amber-600/40 bg-gradient-to-br from-red-950 via-red-900 to-black shadow-md ${sizeClasses} ${className}`}
      >
        <div className="w-full h-full p-1 flex items-center justify-center">
          <div className="w-full h-full border border-amber-500/30 rounded flex items-center justify-center bg-[radial-gradient(#c2410c_1px,transparent_1px)] [background-size:6px_6px]">
            <span className="text-amber-400 font-bold text-xs select-none opacity-80">GG</span>
          </div>
        </div>
      </div>
    );
  }

  const meta = SUIT_META[card.suit] || SUIT_META.s;

  return (
    <div
      className={`relative flex flex-col justify-between p-1 bg-white border font-bold shadow-lg transition-all duration-200 animate-card-flip ${sizeClasses} ${
        isHighlighted ? 'ring-2 ring-amber-400 -translate-y-1 shadow-glow-gold' : 'border-slate-300'
      } ${className}`}
    >
      {/* Top-left rank & suit */}
      <div className="flex flex-col items-start leading-none">
        <span className={`font-black tracking-tighter ${meta.color}`}>
          {card.rank_symbol}
        </span>
        <span className={`text-[10px] -mt-0.5 ${meta.color}`}>
          {meta.symbol}
        </span>
      </div>

      {/* Center large suit watermark */}
      <div className="absolute inset-0 flex items-center justify-center opacity-15 pointer-events-none">
        <span className={`text-2xl ${meta.color}`}>{meta.symbol}</span>
      </div>

      {/* Bottom-right inverted rank */}
      <div className="flex flex-col items-end leading-none rotate-180">
        <span className={`font-black tracking-tighter ${meta.color}`}>
          {card.rank_symbol}
        </span>
      </div>
    </div>
  );
}
