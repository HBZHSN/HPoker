import React, { useState, useEffect, useRef, useCallback } from 'react';
import Lobby from './components/Lobby';
import PokerTable from './components/PokerTable';
import LoginModal from './components/LoginModal';
import ProfileModal from './components/ProfileModal';
import AdminUserModal from './components/AdminUserModal';
import { soundEngine } from './sound/SoundEngine';

export default function App() {
  const [token, setToken] = useState(() => localStorage.getItem('ggpoker_token') || '');
  const [currentUser, setCurrentUser] = useState(() => {
    const saved = localStorage.getItem('ggpoker_user');
    return saved ? JSON.parse(saved) : null;
  });

  const [users, setUsers] = useState([]);
  const [rooms, setRooms] = useState([]);
  const [activeRoomId, setActiveRoomId] = useState(null);
  const [roomData, setRoomData] = useState(null);

  // Modals
  const [profileOpen, setProfileOpen] = useState(false);
  const [adminOpen, setAdminOpen] = useState(false);

  const wsRef = useRef(null);

  // Verify stored token on startup
  useEffect(() => {
    if (token) {
      fetch(`/api/auth/me?token=${token}`)
        .then((res) => {
          if (!res.ok) throw new Error('Token expired');
          return res.json();
        })
        .then((data) => {
          setCurrentUser(data.user);
          localStorage.setItem('ggpoker_user', JSON.stringify(data.user));
        })
        .catch(() => {
          setToken('');
          setCurrentUser(null);
          localStorage.removeItem('ggpoker_token');
          localStorage.removeItem('ggpoker_user');
        });
    }
  }, [token]);

  const handleLoginSuccess = (user, authToken) => {
    setCurrentUser(user);
    setToken(authToken);
    localStorage.setItem('ggpoker_token', authToken);
    localStorage.setItem('ggpoker_user', JSON.stringify(user));
  };

  const handleLogout = () => {
    setToken('');
    setCurrentUser(null);
    setActiveRoomId(null);
    setRoomData(null);
    localStorage.removeItem('ggpoker_token');
    localStorage.removeItem('ggpoker_user');
  };

  const handleUpdateUser = (updatedUser) => {
    setCurrentUser(updatedUser);
    localStorage.setItem('ggpoker_user', JSON.stringify(updatedUser));
  };

  // Fetch initial users and active rooms
  const fetchLobbyData = useCallback(async () => {
    try {
      const [usersRes, roomsRes] = await Promise.all([
        fetch('/api/users'),
        fetch('/api/rooms'),
      ]);
      const usersJson = await usersRes.json();
      const roomsJson = await roomsRes.json();

      setUsers(usersJson);
      setRooms(roomsJson);
    } catch (e) {
      console.error("Failed to load lobby data:", e);
    }
  }, []);

  useEffect(() => {
    fetchLobbyData();
    const interval = setInterval(fetchLobbyData, 5000);
    return () => clearInterval(interval);
  }, [fetchLobbyData]);

  // Connect to WebSocket when entering a room
  useEffect(() => {
    if (!activeRoomId || !currentUser) {
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
      return;
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/${activeRoomId}/${currentUser.user_id}`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      console.log(`WebSocket connected to room ${activeRoomId}`);
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.event === 'ROOM_STATE') {
          setRoomData(msg.payload);
        } else if (msg.event === 'SOUND_EFFECT') {
          soundEngine.play(msg.payload.sound);
        }
      } catch (err) {
        console.error("Error parsing WS message:", err);
      }
    };

    ws.onclose = () => {
      console.log("WebSocket disconnected");
    };

    return () => {
      ws.close();
      wsRef.current = null;
    };
  }, [activeRoomId, currentUser]);

  const sendWsEvent = (event, payload = {}) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ event, payload }));
    }
  };

  const handleCreateRoom = async (config) => {
    try {
      const res = await fetch('/api/rooms', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config),
      });
      const data = await res.json();
      setActiveRoomId(data.room_id);
    } catch (e) {
      console.error("Failed to create room:", e);
    }
  };

  const handleJoinRoom = (roomId) => {
    setActiveRoomId(roomId);
  };

  const handleLeaveRoom = () => {
    setActiveRoomId(null);
    setRoomData(null);
    fetchLobbyData();
  };

  // If not authenticated, require login
  if (!token || !currentUser) {
    return (
      <div className="min-h-screen bg-gg-dark text-slate-100 flex flex-col font-sans">
        <LoginModal onLoginSuccess={handleLoginSuccess} />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gg-dark text-slate-100 flex flex-col font-sans">
      {activeRoomId && roomData ? (
        <PokerTable
          room={roomData}
          currentUser={currentUser}
          onSendWsEvent={sendWsEvent}
          onLeaveRoom={handleLeaveRoom}
        />
      ) : (
        <Lobby
          users={users}
          currentUser={currentUser}
          token={token}
          onUpdateUser={handleUpdateUser}
          onOpenProfile={() => setProfileOpen(true)}
          onOpenAdmin={() => setAdminOpen(true)}
          onLogout={handleLogout}
          rooms={rooms}
          onCreateRoom={handleCreateRoom}
          onJoinRoom={handleJoinRoom}
        />
      )}

      {/* User Profile Modal */}
      {profileOpen && (
        <ProfileModal
          isOpen={profileOpen}
          user={currentUser}
          token={token}
          onUpdateUser={handleUpdateUser}
          onClose={() => setProfileOpen(false)}
        />
      )}

      {/* Admin User & Account Management Modal */}
      {adminOpen && currentUser?.is_admin && (
        <AdminUserModal
          isOpen={adminOpen}
          adminUser={currentUser}
          onClose={() => setAdminOpen(false)}
        />
      )}
    </div>
  );
}

