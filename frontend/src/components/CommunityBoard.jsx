import React from 'react';
import CardView from './CardView';

const BOARD_SIZE = 5;

function BoardRow({
  label,
  cards,
  size,
  compact,
  normalCardCount = 0,
  marksPostHandReveal = false,
  canReveal,
  isRevealing,
  onReveal,
  accentClass,
}) {
  const slots = Array.from({ length: BOARD_SIZE }, (_, index) => cards[index] || null);

  return (
    <div className="poker-board-row flex min-w-max items-center gap-1.5 md:gap-2">
      {label && (
        <span className={`text-[10px] md:text-[11px] font-black px-2 py-0.5 rounded border flex-shrink-0 ${accentClass}`}>
          {label}
        </span>
      )}
      <div className="poker-board-cards flex flex-shrink-0 items-center gap-1.5 md:gap-2">
        {slots.map((card, index) => {
          const isHidden = !card;
          const isPostHandRevealed = Boolean(
            card && marksPostHandReveal && index >= normalCardCount
          );
          const isClickable = isHidden && canReveal && !isRevealing;

          return (
            <button
              key={index}
              type="button"
              onClick={isClickable ? onReveal : undefined}
              disabled={!isClickable}
              aria-label={
                isHidden
                  ? '点击翻开公共牌'
                  : isPostHandRevealed
                  ? `公共牌第 ${index + 1} 张（牌局结束后揭示）`
                  : `公共牌第 ${index + 1} 张`
              }
              className={`relative flex-shrink-0 rounded-lg p-0 border-0 bg-transparent focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-300 focus-visible:ring-offset-1 focus-visible:ring-offset-slate-950 ${
                isClickable
                  ? 'cursor-pointer transition-transform hover:-translate-y-1 hover:scale-[1.03] active:scale-95'
                  : 'cursor-default'
              }`}
            >
              <CardView
                card={card}
                isBack={isHidden}
                isPartiallyRevealed={isPostHandRevealed}
                size={size}
                className={`shadow-lg ${
                  isHidden && isClickable
                    ? 'ring-1 ring-amber-400/40'
                    : isPostHandRevealed
                    ? 'ring-1 ring-amber-300/70'
                    : ''
                }`}
                style={card ? undefined : { animationDelay: `${index * 70}ms` }}
              />
            </button>
          );
        })}
      </div>
    </div>
  );
}

export default function CommunityBoard({
  boardCards = [],
  boardCards2 = [],
  boardCardsFull = [],
  boardCards2Full = [],
  allInInitialBoardCount = 0,
  ritEnabled = false,
  street = 'IDLE',
  boardCardsRevealed = false,
  onReveal,
  isRevealing = false,
  size = 'lg',
  compact = false,
}) {
  const isHandEnd = street === 'HAND_END';
  const hasSecondBoard =
    ritEnabled ||
    street === 'RIT_DECISION' ||
    boardCards2.length > 0 ||
    boardCards2Full.length > 0;
  const sharedCount = Math.max(0, Math.min(BOARD_SIZE, allInInitialBoardCount || 0));

  const firstBoard = boardCardsRevealed && boardCardsFull.length > 0 ? boardCardsFull : boardCards;
  const sharedCards = boardCards.slice(0, sharedCount);
  const secondBoardInProgress =
    boardCards2.length >= sharedCount
      ? boardCards2
      : [...sharedCards, ...boardCards2.slice(sharedCount)];
  const secondBoard =
    boardCardsRevealed && boardCards2Full.length > 0 ? boardCards2Full : secondBoardInProgress;
  const firstBoardUsesFinalCards = boardCardsRevealed && boardCardsFull.length > 0;
  const secondBoardUsesFinalCards = boardCardsRevealed && boardCards2Full.length > 0;

  const hasHiddenCards =
    firstBoard.length < BOARD_SIZE ||
    (hasSecondBoard && secondBoard.length < BOARD_SIZE);
  const canReveal = isHandEnd && !boardCardsRevealed && hasHiddenCards && typeof onReveal === 'function';
  const rootClassName = compact
    ? 'pointer-events-auto flex flex-col items-center gap-1.5 bg-black/55 p-1.5 rounded-xl border border-slate-800/90 shadow-xl'
    : 'pointer-events-auto flex flex-col items-center gap-2 bg-black/60 p-3 rounded-2xl border border-amber-500/25 backdrop-blur-md shadow-2xl overflow-x-auto';

  return (
    <div className={`poker-community-board ${rootClassName}`}>
      {hasSecondBoard ? (
        <div className="flex flex-col gap-1.5">
          <BoardRow
            label="第 1 次"
            cards={firstBoard}
            size={compact ? 'xs' : 'md'}
            compact={compact}
            normalCardCount={boardCards.length}
            marksPostHandReveal={firstBoardUsesFinalCards}
            canReveal={canReveal}
            isRevealing={isRevealing}
            onReveal={onReveal}
            accentClass="text-purple-300 bg-purple-950/90 border-purple-500/30"
          />
          <BoardRow
            label={sharedCount === 0 ? '第 2 次' : sharedCount === 3 ? '第 2 次 (转/河)' : '第 2 次 (河)'}
            cards={secondBoard}
            size={compact ? 'xs' : 'md'}
            compact={compact}
            normalCardCount={secondBoardInProgress.length}
            marksPostHandReveal={secondBoardUsesFinalCards}
            canReveal={canReveal}
            isRevealing={isRevealing}
            onReveal={onReveal}
            accentClass="text-indigo-300 bg-indigo-950/90 border-indigo-500/30"
          />
        </div>
      ) : (
        <BoardRow
          cards={firstBoard}
          size={size}
          compact={compact}
          normalCardCount={boardCards.length}
          marksPostHandReveal={firstBoardUsesFinalCards}
          canReveal={canReveal}
          isRevealing={isRevealing}
          onReveal={onReveal}
          accentClass=""
        />
      )}
    </div>
  );
}
