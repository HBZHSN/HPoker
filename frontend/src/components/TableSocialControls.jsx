import React, { useEffect, useMemo, useRef, useState } from 'react';
import { ChevronLeft, ChevronRight, MessageCircle, Send, SmilePlus, X } from 'lucide-react';

export const TABLE_EMOJIS = [
  '😀', '😃', '😄', '😁', '😆', '😂', '🤣', '😊', '😇', '🙂',
  '🙃', '😉', '😍', '🥰', '😘', '😋', '😜', '🤪', '🤩', '🥳',
  '😎', '🤓', '🧐', '🤔', '🤫', '🤭', '🫡', '😴', '😢', '😭',
  '😤', '😡', '🤬', '😱', '😨', '🥶', '🥵', '🤢', '🤮', '🤡',
  '👻', '💀', '👽', '🤖', '💩', '👍', '👎', '👏', '🙌', '🫶',
  '🤝', '💪', '🙏', '👊', '✌️', '🤞', '👌', '🤟', '❤️', '🧡',
  '💛', '💚', '💙', '💜', '🖤', '💯', '🔥', '🎉', '🎊', '⭐',
  '✨', '💥', '🏆', '🃏', '♠️', '♥️', '♣️', '♦️',
  '😮', '😯', '😲', '😳', '🥺', '🥹', '😏', '😒', '🙄', '😬',
  '😶', '🫠', '🫣', '🤗', '🤠', '👋', '🤌', '🤏', '👈', '👉',
  '☝️', '👇', '👆', '✋', '🤚', '🖐️', '🖖', '🫰', '🤙', '💅',
  '❓', '❔', '⁉️', '‼️', '❗', '❕', '❌', '⭕', '✅', '⚠️',
  '🔔', '💤', '💢', '💦', '💨', '💫', '🌀', '👀', '🎰', '🎱',
  '🎴', '🪙', '💵', '💸', '💳', '📈', '📉', '🏅', '🥇', '🥈',
  '🥉', '🚀', '🧨', '🎁', '🎈', '🎵', '🎶', '📣', '🐭', '🐹',
  '🐰', '🐻', '🐨', '🐮', '🐷', '🐸', '🐵', '🐔', '🐧', '🐢',
  '🐠', '🐟', '🦉', '🐲', '🦓', '🍎', '🍌', '🍓', '🍒', '🍇',
  '🍩', '🍪', '🌭', '🍟', '🍻', '🥂', '🍷', '☕', '🍵', '🌶️',
  '?', '!', '!!', '???', '？', '！', '！？', 'GG', 'EZ', '+1',
  'XD', 'LOL', 'OwO', 'ಠ_ಠ', '(ง •̀_•́)ง',
];

const EMOJIS_PER_PAGE = 20;
const emojiUsageStorageKey = (userId) => `hpoker_emoji_usage_${userId || 'guest'}`;

const loadEmojiUsage = (userId) => {
  try {
    return JSON.parse(localStorage.getItem(emojiUsageStorageKey(userId)) || '{}');
  } catch {
    return {};
  }
};

const saveEmojiUsage = (userId, usage) => {
  try {
    localStorage.setItem(emojiUsageStorageKey(userId), JSON.stringify(usage));
  } catch {
    // The picker still works when storage is unavailable or full.
  }
};

export default function TableSocialControls({
  activities = [],
  currentUserId,
  canReact = false,
  onSendChat,
  onSendEmoji,
}) {
  const [chatOpen, setChatOpen] = useState(false);
  const [emojiOpen, setEmojiOpen] = useState(false);
  const [draft, setDraft] = useState('');
  const [hasUnread, setHasUnread] = useState(false);
  const [emojiPage, setEmojiPage] = useState(0);
  const [emojiUsage, setEmojiUsage] = useState(() => loadEmojiUsage(currentUserId));
  const lastMessageIdRef = useRef(null);
  const messageListRef = useRef(null);

  const latestMessageId = activities.at(-1)?.activity_id || null;
  const sortedEmojis = useMemo(() => TABLE_EMOJIS
    .map((emoji, defaultIndex) => ({
      emoji,
      defaultIndex,
      uses: Number(emojiUsage[emoji]) || 0,
    }))
    .sort((left, right) => right.uses - left.uses || left.defaultIndex - right.defaultIndex)
    .map((item) => item.emoji), [emojiUsage]);
  const emojiPageCount = Math.ceil(sortedEmojis.length / EMOJIS_PER_PAGE);
  const visibleEmojis = sortedEmojis.slice(
    emojiPage * EMOJIS_PER_PAGE,
    (emojiPage + 1) * EMOJIS_PER_PAGE,
  );

  useEffect(() => {
    setEmojiUsage(loadEmojiUsage(currentUserId));
    setEmojiPage(0);
  }, [currentUserId]);

  useEffect(() => {
    if (
      latestMessageId &&
      latestMessageId !== lastMessageIdRef.current &&
      !chatOpen
    ) {
      setHasUnread(true);
    }
    lastMessageIdRef.current = latestMessageId;
  }, [latestMessageId, chatOpen]);

  useEffect(() => {
    if (!chatOpen) return;
    setHasUnread(false);
    const list = messageListRef.current;
    if (list) list.scrollTop = list.scrollHeight;
  }, [chatOpen, activities.length]);

  const submitChat = (event) => {
    event.preventDefault();
    const message = draft.trim();
    if (!message) return;
    onSendChat(message);
    setDraft('');
  };

  const chooseEmoji = (emoji) => {
    if (!canReact) return;
    setEmojiUsage((usage) => {
      const next = { ...usage, [emoji]: (Number(usage[emoji]) || 0) + 1 };
      saveEmojiUsage(currentUserId, next);
      return next;
    });
    onSendEmoji(emoji);
    setEmojiOpen(false);
    setEmojiPage(0);
  };

  return (
    <div className="poker-social-controls absolute bottom-4 left-4 z-50 flex items-end gap-2">
      {chatOpen && (
        <section
          className="poker-chat-window absolute bottom-14 left-0 w-[min(340px,calc(100vw-32px))] overflow-hidden rounded-2xl border border-amber-500/35 bg-slate-950/95 shadow-2xl backdrop-blur-xl"
          aria-label="牌桌聊天"
        >
          <header className="flex items-center justify-between border-b border-slate-800 px-3 py-2.5">
            <div className="flex items-center gap-2 text-sm font-black text-amber-300">
              <MessageCircle className="h-4 w-4" />
              牌桌聊天
            </div>
            <button
              type="button"
              onClick={() => setChatOpen(false)}
              className="rounded-lg p-1 text-slate-400 transition hover:bg-slate-800 hover:text-white"
              aria-label="关闭聊天"
            >
              <X className="h-4 w-4" />
            </button>
          </header>

          <div
            ref={messageListRef}
            className="poker-chat-messages flex h-64 flex-col gap-2 overflow-y-auto px-3 py-3"
            aria-live="polite"
          >
            {activities.length === 0 ? (
              <div className="m-auto text-xs text-slate-600">暂无消息</div>
            ) : activities.map((activity) => {
              const isSelf = activity.player_id === currentUserId;
              const isEmoji = activity.type === 'emoji';
              return (
                <div
                  key={activity.activity_id}
                  className={`flex items-end gap-2 ${isSelf ? 'flex-row-reverse' : ''}`}
                >
                  <span className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full border border-slate-700 bg-slate-900 text-base">
                    {activity.avatar || '👤'}
                  </span>
                  <div className={`min-w-0 max-w-[78%] ${isSelf ? 'text-right' : ''}`}>
                    <div className="mb-0.5 truncate px-1 text-[10px] font-bold text-slate-500">
                      {activity.name}
                    </div>
                    <div className={`break-words rounded-2xl px-3 py-2 text-left text-xs leading-relaxed shadow ${
                      isSelf
                        ? 'rounded-br-sm bg-amber-500 text-slate-950'
                        : 'rounded-bl-sm border border-slate-700 bg-slate-800 text-slate-100'
                    }`}>
                      {isEmoji ? (
                        <span className="text-2xl leading-none">{activity.emoji}</span>
                      ) : activity.message}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          <form onSubmit={submitChat} className="flex gap-2 border-t border-slate-800 p-2.5">
            <input
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              maxLength={120}
              autoFocus
              placeholder="消息"
              className="min-w-0 flex-1 rounded-xl border border-slate-700 bg-slate-900 px-3 py-2 text-xs text-white outline-none transition placeholder:text-slate-600 focus:border-amber-500"
              aria-label="聊天内容"
            />
            <button
              type="submit"
              disabled={!draft.trim()}
              className="flex h-9 w-9 items-center justify-center rounded-xl bg-amber-500 text-slate-950 transition hover:bg-amber-400 disabled:cursor-not-allowed disabled:opacity-40"
              aria-label="发送聊天消息"
            >
              <Send className="h-4 w-4" />
            </button>
          </form>
        </section>
      )}

      {emojiOpen && (
        <div
          className="absolute bottom-14 left-0 w-64 rounded-2xl border border-amber-500/35 bg-slate-950/95 p-2.5 shadow-2xl backdrop-blur-xl"
          aria-label="选择表情"
        >
          <div className="mb-2 flex items-center justify-end px-1 text-[10px] font-bold text-slate-500">
            <span>{emojiPage + 1} / {emojiPageCount}</span>
          </div>
          <div className="grid grid-cols-5 gap-1.5">
            {visibleEmojis.map((emoji) => (
              <button
                type="button"
                key={emoji}
                onClick={() => chooseEmoji(emoji)}
                className="flex aspect-square items-center justify-center rounded-xl bg-slate-900 text-2xl transition hover:bg-amber-950 hover:scale-110 active:scale-95"
                aria-label={`发送表情 ${emoji}，已使用 ${emojiUsage[emoji] || 0} 次`}
              >
                {emoji}
              </button>
            ))}
          </div>
          <div className="mt-2 flex items-center justify-between">
            <button
              type="button"
              onClick={() => setEmojiPage((page) => Math.max(0, page - 1))}
              disabled={emojiPage === 0}
              className="flex h-7 w-9 items-center justify-center rounded-lg border border-slate-700 bg-slate-900 text-slate-300 transition hover:border-amber-500 disabled:opacity-30"
              aria-label="上一页表情"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            <div className="flex gap-1" aria-hidden="true">
              {Array.from({ length: emojiPageCount }, (_, page) => (
                <span
                  key={page}
                  className={`h-1.5 rounded-full transition-all ${
                    page === emojiPage ? 'w-4 bg-amber-400' : 'w-1.5 bg-slate-700'
                  }`}
                />
              ))}
            </div>
            <button
              type="button"
              onClick={() => setEmojiPage((page) => Math.min(emojiPageCount - 1, page + 1))}
              disabled={emojiPage >= emojiPageCount - 1}
              className="flex h-7 w-9 items-center justify-center rounded-lg border border-slate-700 bg-slate-900 text-slate-300 transition hover:border-amber-500 disabled:opacity-30"
              aria-label="下一页表情"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}

      <button
        type="button"
        disabled={!canReact}
        onClick={() => {
          setEmojiOpen((open) => {
            if (!open) setEmojiPage(0);
            return !open;
          });
          setChatOpen(false);
        }}
        className="flex h-11 w-11 items-center justify-center rounded-full border border-amber-500/50 bg-slate-950/95 text-amber-300 shadow-xl backdrop-blur-md transition hover:border-amber-400 hover:bg-amber-950 active:scale-95 disabled:cursor-not-allowed disabled:opacity-40"
        aria-label="发表情"
      >
        <SmilePlus className="h-5 w-5" />
      </button>

      <button
        type="button"
        onClick={() => {
          setChatOpen((open) => !open);
          setEmojiOpen(false);
        }}
        className="relative flex h-11 w-11 items-center justify-center rounded-full border border-amber-500/50 bg-slate-950/95 text-amber-300 shadow-xl backdrop-blur-md transition hover:border-amber-400 hover:bg-amber-950 active:scale-95"
        aria-label="打开聊天"
      >
        <MessageCircle className="h-5 w-5" />
        {hasUnread && (
          <span className="absolute right-0 top-0 h-2.5 w-2.5 rounded-full border-2 border-slate-950 bg-red-500" />
        )}
      </button>
    </div>
  );
}
