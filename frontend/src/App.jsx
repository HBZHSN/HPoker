import React, { useState, useEffect, useRef, useCallback } from 'react';
import Lobby from './components/Lobby';
import PokerTable from './components/PokerTable';
import { soundEngine } from './sound/SoundEngine';

export default function App() {
  const [users, setUsers] = useState([]);
  const [currentUser, setCurrentUser] = useState(null);
  const [rooms, setRooms] = useState([]);
  const [activeRoomId, setActiveRoomId] = useState(null);
  const [roomData, setRoomData] = useState(null);

  const wsRef = useRef(null);

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
      if (!currentUser && usersJson.length > 0) {
        setCurrentUser(usersJson[0]);
      }
      setRooms(roomsJson);
    } catch (e) {
      console.error("Failed to load lobby data:", e);
    }
  }, [currentUser]);

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
          onSelectUser={setCurrentUser}
          rooms={rooms}
          onCreateRoom={handleCreateRoom}
          onJoinRoom={handleJoinRoom}
        />
      )}
    </div>
  );
}
