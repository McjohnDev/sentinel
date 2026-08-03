import React, { useState, useEffect, useRef } from 'react';

const WebSocketNotifications = ({ token, onNotification }) => {
  const [connected, setConnected] = useState(false);
  const wsRef = useRef(null);

  useEffect(() => {
    if (!token) return;

    // Créer la connexion WebSocket
    const wsUrl = `wss://localhost:8443/ws/notifications?token=${token}`;
    wsRef.current = new WebSocket(wsUrl);

    wsRef.current.onopen = () => {
      console.log('WebSocket connecté');
      setConnected(true);
    };

    wsRef.current.onmessage = (event) => {
      const data = JSON.parse(event.data);
      console.log('Notification reçue:', data);
      
      if (onNotification) {
        onNotification(data);
      }
    };

    wsRef.current.onerror = (error) => {
      console.error('WebSocket error:', error);
      setConnected(false);
    };

    wsRef.current.onclose = () => {
      console.log('WebSocket déconnecté');
      setConnected(false);
    };

    // Envoyer un ping toutes les 30 secondes pour garder la connexion alive
    const pingInterval = setInterval(() => {
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.send('ping');
      }
    }, 30000);

    return () => {
      clearInterval(pingInterval);
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [token, onNotification]);

  return (
    <div style={{ 
      position: 'fixed', 
      top: '10px', 
      right: '10px', 
      padding: '10px', 
      backgroundColor: connected ? '#28a745' : '#dc3545', 
      color: 'white', 
      borderRadius: '4px',
      fontSize: '12px',
      zIndex: 1000
    }}>
      {connected ? '● Connecté' : '○ Déconnecté'}
    </div>
  );
};

export default WebSocketNotifications;
