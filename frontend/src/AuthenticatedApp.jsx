import React, { useState, useEffect, useRef, useCallback } from 'react';
import Lobby from './components/Lobby';
import PokerTable from './components/PokerTable';
import ProfileModal from './components/ProfileModal';
import AdminUserModal from './components/AdminUserModal';
import BalanceCenterModal from './components/BalanceCenterModal';
import PWAInstallModal from './components/PWAInstallModal';
import MobilePWAGate from './components/MobilePWAGate';
import { soundEngine } from './sound/SoundEngine';
import { ActionSounds } from './sound/ActionSounds';
import { usePWA } from './utils/usePWA';

const lastRoomStorageKey = (userId) => `active_room_${userId}`;
const legacyLastRoomStorageKey = (userId) => `hpoker_active_room_${userId}`;

export default function AuthenticatedApp({
  currentUser,
  token,
  onLogout,
  onUpdateUser,
}) {
  // Dynamically set page title when authenticated
  useEffect(() => {
    document.title = 'HPoker 德州扑克在线现金局';
    return () => {
      document.title = '系统登录';
    };
  }, []);

  const [rooms, setRooms] = useState([]);
  const [lobbyUsers, setLobbyUsers] = useState([]);
  const [activeRoomId, setActiveRoomId] = useState(() => {
    if (!currentUser?.user_id) return null;
    try {
      return (
        localStorage.getItem(lastRoomStorageKey(currentUser.user_id)) ||
        localStorage.getItem(legacyLastRoomStorageKey(currentUser.user_id))
      );
    } catch {
      return null;
    }
  });
  const [spectateMode, setSpectateMode] = useState(() => {
    if (!currentUser?.user_id) return false;
    try {
      return (
        localStorage.getItem(`spectate_${currentUser.user_id}`) === 'true' ||
        localStorage.getItem(`hpoker_spectate_${currentUser.user_id}`) === 'true'
      );
    } catch {
      return false;
    }
  });
  const [roomData, setRoomData] = useState(null);
  const [connectionStatus, setConnectionStatus] = useState(activeRoomId ? 'connecting' : 'idle');
  const [socialHistory, setSocialHistory] = useState([]);
  const [seatSocialBubbles, setSeatSocialBubbles] = useState({});
  const [spectatorSocialBubbles, setSpectatorSocialBubbles] = useState([]);

  // Modals
  const [profileOpen, setProfileOpen] = useState(false);
  const [adminOpen, setAdminOpen] = useState(false);
  const [balanceOpen, setBalanceOpen] = useState(false);
  const [userBalance, setUserBalance] = useState(null);

  // User explicitly continued past the PWA gate (remembered on this device).
  const [pwaGateDismissed, setPwaGateDismissed] = useState(() => {
    if (typeof window === 'undefined') return false;
    return (
      localStorage.getItem('portal_pwa_dismissed') === 'true' ||
      localStorage.getItem('hpoker_pwa_dismissed') === 'true'
    );
  });

  const pwa = usePWA();

  const wsRef = useRef(null);
  const actionSoundsRef = useRef(null);
  if (!actionSoundsRef.current) actionSoundsRef.current = new ActionSounds(soundEngine);
  const socialBubbleTimersRef = useRef(new Map());

  useEffect(() => {
    setSocialHistory([]);
    setSeatSocialBubbles({});
    setSpectatorSocialBubbles([]);
    for (const timer of socialBubbleTimersRef.current.values()) {
      window.clearTimeout(timer);
    }
    socialBubbleTimersRef.current.clear();
  }, [activeRoomId]);

  // Fetch initial active rooms and online users
  const fetchLobbyData = useCallback(async () => {
    try {
      const [roomsRes, usersRes, balanceRes] = await Promise.all([
        fetch('/api/rooms', {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        }),
        fetch('/api/lobby/users', {
          headers: { Authorization: `Bearer ${token}` },
        }),
        token
          ? fetch('/api/balance/my', {
              headers: { Authorization: `Bearer ${token}` },
            })
          : Promise.resolve(null),
      ]);
      if (roomsRes.ok) {
        const roomsJson = await roomsRes.json();
        setRooms(roomsJson);
      }
      if (usersRes.ok) {
        const usersJson = await usersRes.json();
        setLobbyUsers(usersJson);
      }
      if (balanceRes && balanceRes.ok) {
        const balanceJson = await balanceRes.json();
        setUserBalance(balanceJson.available_cash);
      }
    } catch (e) {
      console.error('Failed to load lobby data:', e);
    }
  }, [token]);

  useEffect(() => {
    fetchLobbyData();
    const interval = setInterval(fetchLobbyData, 5000);
    return () => clearInterval(interval);
  }, [fetchLobbyData]);

  // A remembered room takes priority over the lobby after login or refresh.
  useEffect(() => {
    if (!currentUser?.user_id) return;
    const savedRoomId =
      localStorage.getItem(lastRoomStorageKey(currentUser.user_id)) ||
      localStorage.getItem(legacyLastRoomStorageKey(currentUser.user_id));
    const savedSpectate =
      localStorage.getItem(`spectate_${currentUser.user_id}`) === 'true' ||
      localStorage.getItem(`hpoker_spectate_${currentUser.user_id}`) === 'true';
    if (savedRoomId) {
      setSpectateMode(savedSpectate);
      setActiveRoomId(savedRoomId);
      setConnectionStatus('connecting');
    }
  }, [currentUser?.user_id, token]);

  const rememberAndEnterRoom = useCallback((roomId, options = {}) => {
    const isSpectate = Boolean(options.spectate);
    if (currentUser?.user_id) {
      localStorage.setItem(lastRoomStorageKey(currentUser.user_id), roomId);
      if (isSpectate) {
        localStorage.setItem(`spectate_${currentUser.user_id}`, 'true');
      } else {
        localStorage.removeItem(`spectate_${currentUser.user_id}`);
        localStorage.removeItem(`hpoker_spectate_${currentUser.user_id}`);
      }
    }
    setRoomData(null);
    setSpectateMode(isSpectate);
    setActiveRoomId(roomId);
    setConnectionStatus('connecting');
  }, [currentUser?.user_id]);

  const handleStandUpToSpectate = useCallback(() => {
    if (
      activeRoomId &&
      wsRef.current &&
      wsRef.current.readyState === WebSocket.OPEN
    ) {
      wsRef.current.send(JSON.stringify({ event: 'STAND_UP', payload: {} }));
      setSpectateMode(true);
      if (currentUser?.user_id) {
        localStorage.setItem(`spectate_${currentUser.user_id}`, 'true');
      }
    }
  }, [activeRoomId, currentUser?.user_id]);

  const handleLeaveRoom = useCallback((options = {}) => {
    const notifyServer = options.notifyServer !== false;
    if (
      notifyServer &&
      activeRoomId &&
      wsRef.current &&
      wsRef.current.readyState === WebSocket.OPEN
    ) {
      wsRef.current.send(JSON.stringify({ event: 'STAND_UP', payload: {} }));
    }
    if (currentUser?.user_id) {
      localStorage.removeItem(lastRoomStorageKey(currentUser.user_id));
      localStorage.removeItem(legacyLastRoomStorageKey(currentUser.user_id));
      localStorage.removeItem(`spectate_${currentUser.user_id}`);
      localStorage.removeItem(`hpoker_spectate_${currentUser.user_id}`);
    }
    setSpectateMode(false);
    setActiveRoomId(null);
    setRoomData(null);
    setConnectionStatus('idle');
    fetchLobbyData();
  }, [activeRoomId, currentUser?.user_id, fetchLobbyData]);

  // Keep reconnecting after mobile background suspension.
  useEffect(() => {
    if (!currentUser?.user_id) {
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
      return;
    }

    let disposed = false;
    let terminalClose = false;
    let reconnectTimer = null;
    let heartbeatTimer = null;
    let retryCount = 0;

    const clearSocketTimers = () => {
      if (reconnectTimer) window.clearTimeout(reconnectTimer);
      if (heartbeatTimer) window.clearInterval(heartbeatTimer);
      reconnectTimer = null;
      heartbeatTimer = null;
    };

    const showSeatSocialBubble = (activity) => {
      setSeatSocialBubbles((bubbles) => ({
        ...bubbles,
        [activity.player_id]: activity,
      }));
      const previousTimer = socialBubbleTimersRef.current.get(activity.player_id);
      if (previousTimer) window.clearTimeout(previousTimer);
      const timer = window.setTimeout(() => {
        setSeatSocialBubbles((bubbles) => {
          if (bubbles[activity.player_id]?.activity_id !== activity.activity_id) {
            return bubbles;
          }
          const next = { ...bubbles };
          delete next[activity.player_id];
          return next;
        });
        socialBubbleTimersRef.current.delete(activity.player_id);
      }, 5000);
      socialBubbleTimersRef.current.set(activity.player_id, timer);
    };

    const showSpectatorSocialBubble = (activity) => {
      setSpectatorSocialBubbles((prev) => [...prev, activity].slice(-5));
      window.setTimeout(() => {
        setSpectatorSocialBubbles((prev) =>
          prev.filter((item) => item.activity_id !== activity.activity_id)
        );
      }, 4500);
    };

    const appendSocialActivity = (activity) => {
      setSocialHistory((history) => [...history, activity].slice(-80));
      if (activity.is_spectator) {
        showSpectatorSocialBubble(activity);
      } else {
        showSeatSocialBubble(activity);
      }
    };

    const connect = () => {
      if (disposed || terminalClose) return;
      setConnectionStatus(retryCount > 0 ? 'retrying' : 'connecting');
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const tokenParam = token ? `?token=${encodeURIComponent(token)}` : '';
      const spectateParam = spectateMode ? (tokenParam ? '&spectate=true' : '?spectate=true') : '';
      const wsUrl = activeRoomId
        ? `${protocol}//${window.location.host}/ws/${activeRoomId}/${currentUser.user_id}${tokenParam}${spectateParam}`
        : `${protocol}//${window.location.host}/ws/lobby/${currentUser.user_id}${tokenParam}`;
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;
      actionSoundsRef.current.reset();

      ws.onopen = () => {
        if (disposed) return;
        retryCount = 0;
        setConnectionStatus('connected');
        heartbeatTimer = window.setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ event: 'PING', payload: {} }));
          }
        }, 15000);
      };

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.event === 'ROOM_STATE') {
            if (activeRoomId) {
              localStorage.setItem(lastRoomStorageKey(currentUser.user_id), activeRoomId);
              const tableSeats = msg.payload?.table?.seats || [];
              const isSeated = tableSeats.some((s) => s && s.player_id === currentUser.user_id);
              if (isSeated) {
                setSpectateMode(false);
                if (currentUser?.user_id) {
                  localStorage.removeItem(`spectate_${currentUser.user_id}`);
                  localStorage.removeItem(`hpoker_spectate_${currentUser.user_id}`);
                }
              }
              setRoomData(msg.payload);
              setConnectionStatus('connected');
            }
          } else if (msg.event === 'ONLINE_USERS_UPDATE') {
            const onlineIds = new Set(msg.payload?.online_user_ids || []);
            const locations = msg.payload?.user_locations || {};
            setLobbyUsers((prev) => {
              if (!prev || prev.length === 0) return prev;
              return prev.map((u) => ({
                ...u,
                is_online: onlineIds.has(u.user_id),
                current_room_id: locations[u.user_id] === 'lobby' ? null : (locations[u.user_id] || null),
              }));
            });
            fetchLobbyData();
          } else if (msg.event === 'SOUND_EFFECT') {
            actionSoundsRef.current.receive(msg.payload);
          } else if (msg.event === 'CHAT_MESSAGE') {
            appendSocialActivity({
              ...msg.payload,
              activity_id: msg.payload.message_id,
              type: 'chat',
              timestamp: msg.timestamp,
            });
          } else if (msg.event === 'EMOJI_REACTION') {
            appendSocialActivity({
              ...msg.payload,
              activity_id: msg.payload.reaction_id,
              type: 'emoji',
              timestamp: msg.timestamp,
            });
          } else if (msg.event === 'PLAYER_KICKED') {
            if (activeRoomId) {
              terminalClose = true;
              alert(msg.payload?.message || '你已被房主移出房间');
              handleLeaveRoom({ notifyServer: false });
            }
          } else if (msg.event === 'ROOM_DELETED') {
            if (activeRoomId) {
              terminalClose = true;
              alert(msg.payload?.message || '房间已被房主解散');
              handleLeaveRoom({ notifyServer: false });
            } else {
              fetchLobbyData();
            }
          } else if (msg.event === 'ERROR_MESSAGE') {
            if (msg.payload?.message && msg.payload.message !== 'Room not found') {
              alert(msg.payload.message);
            }
            if (msg.payload?.message === 'Room not found' && activeRoomId) {
              terminalClose = true;
              handleLeaveRoom({ notifyServer: false });
            }
          }
        } catch (err) {
          console.error('Error parsing WS message:', err);
        }
      };

      ws.onclose = () => {
        if (heartbeatTimer) window.clearInterval(heartbeatTimer);
        heartbeatTimer = null;
        if (wsRef.current === ws) wsRef.current = null;
        if (disposed || terminalClose) return;
        retryCount += 1;
        setConnectionStatus('retrying');
        const delay = Math.min(1000 * 2 ** (retryCount - 1), 10000);
        reconnectTimer = window.setTimeout(connect, delay);
      };

      ws.onerror = () => ws.close();
    };

    let wasHidden = document.visibilityState === 'hidden';
    const reconnectWhenVisible = () => {
      if (document.visibilityState === 'hidden') {
        wasHidden = true;
        return;
      }
      if (!wasHidden) return;
      wasHidden = false;
      const socket = wsRef.current;
      if (reconnectTimer) window.clearTimeout(reconnectTimer);
      reconnectTimer = null;
      if (heartbeatTimer) window.clearInterval(heartbeatTimer);
      heartbeatTimer = null;
      if (socket) {
        socket.onclose = null;
        socket.close();
        if (wsRef.current === socket) wsRef.current = null;
      }
      connect();
    };

    connect();
    document.addEventListener('visibilitychange', reconnectWhenVisible);
    return () => {
      disposed = true;
      document.removeEventListener('visibilitychange', reconnectWhenVisible);
      clearSocketTimers();
      if (wsRef.current) wsRef.current.close();
      wsRef.current = null;
    };
  }, [activeRoomId, currentUser?.user_id, spectateMode, token, handleLeaveRoom]);

  const sendWsEvent = (event, payload = {}) => {
    actionSoundsRef.current.send(wsRef.current, event, payload, currentUser?.user_id);
  };

  const handleCreateRoom = async (config) => {
    try {
      const res = await fetch('/api/rooms', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(config),
      });
      const data = await res.json();
      if (!res.ok) {
        alert(data.detail || '创建房间失败');
        return false;
      }
      rememberAndEnterRoom(data.room_id);
      return true;
    } catch (e) {
      console.error('Failed to create room:', e);
      alert('创建房间失败，请稍后重试');
      return false;
    }
  };

  const handleDeleteRoom = async (roomId) => {
    try {
      const res = await fetch(`/api/rooms/${roomId}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        if (activeRoomId === roomId) {
          handleLeaveRoom({ notifyServer: false });
        } else {
          fetchLobbyData();
        }
      } else {
        const data = await res.json();
        alert(data.detail || '删除房间失败');
      }
    } catch (e) {
      console.error('Failed to delete room:', e);
      alert('网络错误，删除房间失败');
    }
  };

  const handleJoinRoom = (roomId, options = {}) => {
    rememberAndEnterRoom(roomId, options);
  };

  // Mobile device mandatory PWA enforcement for authenticated users
  const isQueryBypass = typeof window !== 'undefined' && window.location.search.includes('bypass_pwa=1');
  const isUserBypassed = pwaGateDismissed || isQueryBypass;
  const canBypassGate = isUserBypassed && !pwa.isInAppBrowser;
  const requiresMobilePWAGate = Boolean(pwa.isMobileDevice && !pwa.isStandalone && !canBypassGate);

  const handlePwaContinue = () => {
    try {
      localStorage.setItem('portal_pwa_dismissed', 'true');
      localStorage.setItem('hpoker_pwa_dismissed', 'true');
    } catch (err) {
      console.warn('[PWA] Failed to persist dismissal:', err);
    }
    setPwaGateDismissed(true);
  };

  if (requiresMobilePWAGate) {
    return (
      <>
        <MobilePWAGate
          isIOS={pwa.isIOS}
          isInAppBrowser={pwa.isInAppBrowser}
          hasNativePrompt={pwa.hasNativePrompt}
          onInstallNative={pwa.promptInstall}
          onOpenInstallModal={pwa.openInstallModal}
          onContinue={pwa.isInAppBrowser ? null : handlePwaContinue}
        />
        <PWAInstallModal
          isOpen={pwa.isModalOpen}
          onClose={pwa.closeInstallModal}
          onInstallNative={pwa.promptInstall}
          hasNativePrompt={pwa.hasNativePrompt}
          guideType={pwa.guideType}
          onToggleFullscreen={pwa.toggleFullscreen}
          isFullscreen={pwa.isFullscreen}
        />
      </>
    );
  }

  return (
    <div
      className={`w-full h-full bg-[#080b11] text-slate-100 flex flex-col font-sans ${
        activeRoomId && roomData ? 'overflow-hidden' : 'overflow-y-auto overscroll-contain'
      }`}
    >
      {activeRoomId && roomData ? (
        <PokerTable
          token={token}
          room={roomData}
          currentUser={currentUser}
          socialHistory={socialHistory}
          seatSocialBubbles={seatSocialBubbles}
          spectatorSocialBubbles={spectatorSocialBubbles}
          onSendWsEvent={sendWsEvent}
          onLeaveRoom={handleLeaveRoom}
          onStandUpToSpectate={handleStandUpToSpectate}
          onToggleFullscreen={pwa.toggleFullscreen}
          isFullscreen={pwa.isFullscreen}
          onOpenBalance={() => setBalanceOpen(true)}
        />
      ) : activeRoomId ? (
        <div className="w-full h-full min-h-screen bg-[#080b11] flex flex-col items-center justify-center gap-4 text-center p-6">
          <div className="w-10 h-10 rounded-full border-4 border-slate-700 border-t-amber-400 animate-spin" />
          <div>
            <div className="text-sm font-black text-amber-300">
              {connectionStatus === 'retrying' ? '正在重新连接牌桌' : '正在恢复上次牌桌'}
            </div>
          </div>
          <button
            onClick={handleLeaveRoom}
            className="px-4 py-2 rounded-xl bg-slate-900 border border-slate-700 text-xs font-bold text-slate-300"
          >
            返回大厅
          </button>
        </div>
      ) : (
        <Lobby
          currentUser={currentUser}
          token={token}
          userBalance={userBalance}
          onUpdateUser={onUpdateUser}
          onOpenProfile={() => setProfileOpen(true)}
          onOpenAdmin={() => setAdminOpen(true)}
          onOpenBalance={() => setBalanceOpen(true)}
          onLogout={onLogout}
          rooms={rooms}
          users={lobbyUsers}
          onRefreshLobby={fetchLobbyData}
          onCreateRoom={handleCreateRoom}
          onDeleteRoom={handleDeleteRoom}
          onJoinRoom={handleJoinRoom}
          onInstallApp={pwa.promptInstall}
          onToggleFullscreen={pwa.toggleFullscreen}
          isFullscreen={pwa.isFullscreen}
          isStandalone={pwa.isStandalone}
          isInstallable={pwa.isInstallable}
          pwaAcknowledged={pwaGateDismissed}
        />
      )}

      {/* User Profile Modal */}
      {profileOpen && (
        <ProfileModal
          isOpen={profileOpen}
          user={currentUser}
          token={token}
          onUpdateUser={onUpdateUser}
          onClose={() => setProfileOpen(false)}
        />
      )}

      {/* Admin User & Account Management Modal */}
      {adminOpen && currentUser?.is_admin && (
        <AdminUserModal
          isOpen={adminOpen}
          adminUser={currentUser}
          token={token}
          onClose={() => setAdminOpen(false)}
        />
      )}

      {/* Balance & Ledger Management Modal */}
      {balanceOpen && (
        <BalanceCenterModal
          isOpen={balanceOpen}
          currentUser={currentUser}
          token={token}
          onClose={() => {
            setBalanceOpen(false);
            fetchLobbyData();
          }}
        />
      )}

      {/* PWA Installation Guidance Modal */}
      <PWAInstallModal
        isOpen={pwa.isModalOpen}
        onClose={pwa.closeInstallModal}
        onInstallNative={pwa.promptInstall}
        hasNativePrompt={pwa.hasNativePrompt}
        guideType={pwa.guideType}
        onToggleFullscreen={pwa.toggleFullscreen}
        isFullscreen={pwa.isFullscreen}
      />
    </div>
  );
}
