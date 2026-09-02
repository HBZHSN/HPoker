import React from 'react';

// Suit Color and Symbol mapping
// Hearts and Diamonds MUST be red; Spades and Clubs are dark black
const SUIT_META = {
  s: { symbol: '♠', name: 'spade', color: 'text-slate-950', border: 'border-slate-300' },
  h: { symbol: '♥', name: 'heart', color: 'text-red-600', border: 'border-red-200' },
  c: { symbol: '♣', name: 'club', color: 'text-slate-950', border: 'border-slate-300' },
  d: { symbol: '♦', name: 'diamond', color: 'text-red-600', border: 'border-red-200' },
};

export default function CardView({
  card,
  isBack = false,
  size = 'md', // 'xs', 'sm', 'md', 'lg', 'xl'
  isHighlighted = false,
  className = '',
  style,
}) {
  const sizeClasses = {
    xs: 'w-8 h-12 rounded',
    sm: 'w-10 h-14 md:w-12 md:h-17 rounded-md',
    md: 'w-13 h-19 md:w-16 md:h-23 rounded-lg',
    lg: 'w-16 h-24 md:w-20 md:h-28 rounded-xl',
    xl: 'w-20 h-30 md:w-24 md:h-36 rounded-xl',
  }[size] || 'w-13 h-19 md:w-16 md:h-23 rounded-lg';

  const fontSizes = {
    xs: { rank: 'text-sm font-black', suit: 'text-xs' },
    sm: { rank: 'text-lg md:text-xl font-black', suit: 'text-base md:text-lg' },
    md: { rank: 'text-2xl md:text-3xl font-black', suit: 'text-xl md:text-2xl' },
    lg: { rank: 'text-3xl md:text-4xl font-black', suit: 'text-2xl md:text-3xl' },
    xl: { rank: 'text-4xl md:text-5xl font-black', suit: 'text-3xl md:text-4xl' },
  }[size] || { rank: 'text-2xl md:text-3xl font-black', suit: 'text-xl md:text-2xl' };

  if (isBack || !card) {
    return (
      <div
        style={style}
        className={`relative flex flex-col items-center justify-center border-2 border-amber-600/50 bg-gradient-to-br from-red-950 via-red-900 to-slate-950 shadow-lg select-none ${sizeClasses} ${className}`}
      >
        <div className="w-full h-full p-1 flex items-center justify-center">
          <div className="w-full h-full border border-amber-500/40 rounded flex items-center justify-center bg-[radial-gradient(#d97706_1.5px,transparent_1.5px)] [background-size:6px_6px]">
            <span className="text-amber-400 font-black text-xs md:text-sm tracking-tighter select-none opacity-90 drop-shadow">
              H
            </span>
          </div>
        </div>
      </div>
    );
  }

  const meta = SUIT_META[card.suit] || SUIT_META.s;

  return (
    <div
      style={style}
      className={`relative flex flex-col items-center justify-center p-1 bg-white border-2 select-none shadow-md transition-all duration-200 animate-card-flip ${sizeClasses} ${
        isHighlighted
          ? 'ring-2 ring-amber-400 -translate-y-1.5 shadow-glow-gold border-amber-400'
          : 'border-slate-300'
      } ${className}`}
    >
      <div className="flex flex-col items-center justify-center leading-none text-center">
        <span className={`${fontSizes.rank} tracking-tighter leading-none ${meta.color}`}>
          {card.rank_symbol}
        </span>
        <span className={`${fontSizes.suit} leading-none mt-1 ${meta.color} drop-shadow-sm`}>
          {meta.symbol}
        </span>
      </div>
    </div>
  );
}
