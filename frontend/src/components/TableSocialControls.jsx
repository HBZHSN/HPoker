import React, { useEffect, useRef, useState } from 'react';
import { MessageCircle, Send, SmilePlus, X } from 'lucide-react';

export const TABLE_EMOJIS = [
  '😀', '😂', '😍', '😎', '🤔', '😢',
  '😡', '👍', '👏', '🔥', '🎉', '🃏',
];

export default function TableSocialControls({
  messages = [],
  currentUserId,
  canReact = false,
  onSendChat,
  onSendEmoji,
}) {
  const [chatOpen, setChatOpen] = useState(false);
  const [emojiOpen, setEmojiOpen] = useState(false);
  const [draft, setDraft] = useState('');
  const [hasUnread, setHasUnread] = useState(false);
  const lastMessageIdRef = useRef(null);
  const messageListRef = useRef(null);

  const latestMessageId = messages.at(-1)?.message_id || null;

  useEffect(() => {
    if (
      latestMessageId &&
      lastMessageIdRef.current &&
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
  }, [chatOpen, messages.length]);

  const submitChat = (event) => {
    event.preventDefault();
    const message = draft.trim();
    if (!message) return;
    onSendChat(message);
    setDraft('');
  };

  const chooseEmoji = (emoji) => {
    if (!canReact) return;
    onSendEmoji(emoji);
    setEmojiOpen(false);
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
              title="关闭聊天"
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
            {messages.length === 0 ? (
              <div className="m-auto text-xs text-slate-600">还没有聊天消息</div>
            ) : messages.map((message) => {
              const isSelf = message.player_id === currentUserId;
              return (
                <div
                  key={message.message_id}
                  className={`flex items-end gap-2 ${isSelf ? 'flex-row-reverse' : ''}`}
                >
                  <span className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full border border-slate-700 bg-slate-900 text-base">
                    {message.avatar || '👤'}
                  </span>
                  <div className={`min-w-0 max-w-[78%] ${isSelf ? 'text-right' : ''}`}>
                    <div className="mb-0.5 truncate px-1 text-[10px] font-bold text-slate-500">
                      {message.name}
                    </div>
                    <div className={`break-words rounded-2xl px-3 py-2 text-left text-xs leading-relaxed shadow ${
                      isSelf
                        ? 'rounded-br-sm bg-amber-500 text-slate-950'
                        : 'rounded-bl-sm border border-slate-700 bg-slate-800 text-slate-100'
                    }`}>
                      {message.message}
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
              placeholder="输入消息…"
              className="min-w-0 flex-1 rounded-xl border border-slate-700 bg-slate-900 px-3 py-2 text-xs text-white outline-none transition placeholder:text-slate-600 focus:border-amber-500"
              aria-label="聊天内容"
            />
            <button
              type="submit"
              disabled={!draft.trim()}
              className="flex h-9 w-9 items-center justify-center rounded-xl bg-amber-500 text-slate-950 transition hover:bg-amber-400 disabled:cursor-not-allowed disabled:opacity-40"
              title="发送"
              aria-label="发送聊天消息"
            >
              <Send className="h-4 w-4" />
            </button>
          </form>
        </section>
      )}

      {emojiOpen && (
        <div
          className="absolute bottom-14 left-0 grid w-52 grid-cols-4 gap-1.5 rounded-2xl border border-amber-500/35 bg-slate-950/95 p-2.5 shadow-2xl backdrop-blur-xl"
          aria-label="选择表情"
        >
          {TABLE_EMOJIS.map((emoji) => (
            <button
              type="button"
              key={emoji}
              onClick={() => chooseEmoji(emoji)}
              className="flex aspect-square items-center justify-center rounded-xl bg-slate-900 text-2xl transition hover:bg-amber-950 hover:scale-110 active:scale-95"
              aria-label={`发送表情 ${emoji}`}
            >
              {emoji}
            </button>
          ))}
        </div>
      )}

      <button
        type="button"
        disabled={!canReact}
        onClick={() => {
          setEmojiOpen((open) => !open);
          setChatOpen(false);
        }}
        className="flex h-11 w-11 items-center justify-center rounded-full border border-amber-500/50 bg-slate-950/95 text-amber-300 shadow-xl backdrop-blur-md transition hover:border-amber-400 hover:bg-amber-950 active:scale-95 disabled:cursor-not-allowed disabled:opacity-40"
        title={canReact ? '发表情' : '入座后可发表情'}
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
        title="聊天"
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
