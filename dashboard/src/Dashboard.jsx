import React, { useState, useEffect } from 'react';
import { agentsAPI, alertsAPI } from './api';
import MetricsChart from './MetricsChart';
import WebSocketNotifications from './WebSocketNotifications';
import ThemeToggle from './ThemeToggle';

function Dashboard({ token, user, onLogout }) {
  const [agents, setAgents] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [selectedAgent, setSelectedAgent] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 30000); // Refresh every 30 seconds
    return () => clearInterval(interval);
  }, [token]);

  const fetchData = async () => {
    try {
      const [agentsRes, alertsRes] = await Promise.all([
        agentsAPI.list(token),
        alertsAPI.list(token)
      ]);
      setAgents(agentsRes.data.data || []);
      setAlerts(alertsRes.data.data || []);
      setError('');
    } catch (err) {
      setError('Erreur lors de la récupération des données');
    } finally {
      setLoading(false);
    }
  };

  const fetchAgentDetails = async (agentId) => {
    try {
      const response = await agentsAPI.get(agentId, token);
      setSelectedAgent(response.data);
    } catch (err) {
      setError('Erreur lors de la récupération des détails de l\'agent');
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'active': return 'green';
      case 'revoked': return 'red';
      case 'deleted': return 'gray';
      default: return 'black';
    }
  };

  const getSeverityColor = (severity) => {
    switch (severity) {
      case 'critical': return 'red';
      case 'warning': return 'orange';
      case 'info': return 'blue';
      default: return 'black';
    }
  };

  const formatUptime = (seconds) => {
    if (!seconds) return 'N/A';
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    return `${days}j ${hours}h ${minutes}m`;
  };

  const handleNotification = (notification) => {
    // Rafraîchir les données lors de la réception d'une notification
    if (notification.type === 'alert_created' || notification.type === 'alert_updated') {
      fetchData();
    }
  };

  if (loading) {
    return <div style={{ textAlign: 'center', marginTop: '50px' }}>Chargement...</div>;
  }

  return (
    <div style={{ padding: '20px', maxWidth: '1400px', margin: '0 auto' }}>
      <WebSocketNotifications token={token} onNotification={handleNotification} />
      
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '30px', flexWrap: 'wrap', gap: '10px' }}>
        <h1 style={{ fontSize: window.innerWidth < 768 ? '24px' : '32px', margin: 0 }}>CBC Supervision Platform</h1>
        <div style={{ display: 'flex', flexDirection: window.innerWidth < 768 ? 'column' : 'row', alignItems: 'center', gap: '10px' }}>
          <span style={{ fontSize: window.innerWidth < 768 ? '12px' : '14px' }}>Connecté en tant que: <strong>{user.username}</strong> ({user.role})</span>
          <ThemeToggle />
          <button onClick={onLogout} style={{ padding: '8px 16px', backgroundColor: '#dc3545', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer' }}>
            Déconnexion
          </button>
        </div>
      </div>

      {error && <div style={{ color: 'red', marginBottom: '20px' }}>{error}</div>}

      <div style={{ marginBottom: '30px' }}>
        <h2>Alertes ({alerts.length})</h2>
        {alerts.length === 0 ? (
          <p style={{ color: 'green' }}>Aucune alerte active</p>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', border: '1px solid #ddd', minWidth: '800px' }}>
              <thead>
                <tr style={{ backgroundColor: '#f5f5f5' }}>
                  <th style={{ padding: '10px', textAlign: 'left', border: '1px solid #ddd' }}>Sévérité</th>
                  <th style={{ padding: '10px', textAlign: 'left', border: '1px solid #ddd' }}>Type</th>
                  <th style={{ padding: '10px', textAlign: 'left', border: '1px solid #ddd' }}>Message</th>
                  <th style={{ padding: '10px', textAlign: 'left', border: '1px solid #ddd' }}>Agent ID</th>
                  <th style={{ padding: '10px', textAlign: 'left', border: '1px solid #ddd' }}>Début</th>
                  <th style={{ padding: '10px', textAlign: 'left', border: '1px solid #ddd' }}>Statut</th>
                </tr>
              </thead>
              <tbody>
                {alerts.map((alert) => (
                  <tr key={alert.id}>
                    <td style={{ padding: '10px', border: '1px solid #ddd', color: getSeverityColor(alert.severity), fontWeight: 'bold' }}>
                      {alert.severity.toUpperCase()}
                    </td>
                    <td style={{ padding: '10px', border: '1px solid #ddd' }}>{alert.type}</td>
                    <td style={{ padding: '10px', border: '1px solid #ddd' }}>{alert.message}</td>
                    <td style={{ padding: '10px', border: '1px solid #ddd', fontFamily: 'monospace' }}>{alert.agent_id.substring(0, 8)}...</td>
                    <td style={{ padding: '10px', border: '1px solid #ddd' }}>{new Date(alert.started_at).toLocaleString()}</td>
                    <td style={{ padding: '10px', border: '1px solid #ddd', color: alert.status === 'open' ? 'red' : 'green' }}>
                      {alert.status.toUpperCase()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div>
        <h2>Agents ({agents.length})</h2>
        {agents.length === 0 ? (
          <p>Aucun agent enregistré</p>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', border: '1px solid #ddd', minWidth: '800px' }}>
              <thead>
                <tr style={{ backgroundColor: '#f5f5f5' }}>
                  <th style={{ padding: '10px', textAlign: 'left', border: '1px solid #ddd' }}>Hostname</th>
                  <th style={{ padding: '10px', textAlign: 'left', border: '1px solid #ddd' }}>OS</th>
                  <th style={{ padding: '10px', textAlign: 'left', border: '1px solid #ddd' }}>Statut</th>
                  <th style={{ padding: '10px', textAlign: 'left', border: '1px solid #ddd' }}>Dernière communication</th>
                  <th style={{ padding: '10px', textAlign: 'left', border: '1px solid #ddd' }}>Enrôlé le</th>
                  <th style={{ padding: '10px', textAlign: 'left', border: '1px solid #ddd' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {agents.map((agent) => (
                  <tr key={agent.id}>
                    <td style={{ padding: '10px', border: '1px solid #ddd', fontWeight: 'bold' }}>{agent.hostname}</td>
                    <td style={{ padding: '10px', border: '1px solid #ddd' }}>{agent.os}</td>
                    <td style={{ padding: '10px', border: '1px solid #ddd', color: getStatusColor(agent.status), fontWeight: 'bold' }}>
                      {agent.status.toUpperCase()}
                    </td>
                    <td style={{ padding: '10px', border: '1px solid #ddd' }}>
                      {agent.last_communication ? new Date(agent.last_communication).toLocaleString() : 'Jamais'}
                    </td>
                    <td style={{ padding: '10px', border: '1px solid #ddd' }}>
                      {new Date(agent.enrolled_at).toLocaleString()}
                    </td>
                    <td style={{ padding: '10px', border: '1px solid #ddd' }}>
                      <button 
                        onClick={() => fetchAgentDetails(agent.id)}
                        style={{ padding: '5px 10px', backgroundColor: '#007bff', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer' }}
                      >
                        Voir détails
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {selectedAgent && (
        <div style={{ marginTop: '30px', padding: '20px', border: '1px solid #ddd', borderRadius: '8px', backgroundColor: '#f9f9f9' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px', flexWrap: 'wrap', gap: '10px' }}>
            <h3 style={{ fontSize: window.innerWidth < 768 ? '18px' : '24px', margin: 0 }}>Détails de l'agent: {selectedAgent.hostname}</h3>
            <button 
              onClick={() => setSelectedAgent(null)}
              style={{ padding: '5px 10px', backgroundColor: '#6c757d', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer' }}
            >
              Fermer
            </button>
          </div>

          {selectedAgent.last_heartbeat ? (
            <div>
              <div style={{ display: 'grid', gridTemplateColumns: window.innerWidth < 768 ? '1fr' : 'repeat(auto-fit, minmax(250px, 1fr))', gap: '20px', marginBottom: '30px' }}>
                <div style={{ padding: '15px', backgroundColor: 'white', border: '1px solid #ddd', borderRadius: '4px' }}>
                  <h4 style={{ margin: '0 0 10px 0', color: '#007bff' }}>CPU</h4>
                  <p><strong>Utilisation:</strong> {selectedAgent.last_heartbeat.cpu_percent}%</p>
                  <p><strong>Cœurs:</strong> {selectedAgent.last_heartbeat.cpu_cores}</p>
                  <p><strong>Architecture:</strong> {selectedAgent.last_heartbeat.cpu_architecture}</p>
                </div>

                <div style={{ padding: '15px', backgroundColor: 'white', border: '1px solid #ddd', borderRadius: '4px' }}>
                  <h4 style={{ margin: '0 0 10px 0', color: '#28a745' }}>RAM</h4>
                  <p><strong>Utilisation:</strong> {selectedAgent.last_heartbeat.ram_percent}%</p>
                  <p><strong>Total:</strong> {selectedAgent.last_heartbeat.ram_total_gb} GB</p>
                  <p><strong>Utilisée:</strong> {selectedAgent.last_heartbeat.ram_used_gb} GB</p>
                  <p><strong>Libre:</strong> {selectedAgent.last_heartbeat.ram_free_gb} GB</p>
                </div>

                <div style={{ padding: '15px', backgroundColor: 'white', border: '1px solid #ddd', borderRadius: '4px' }}>
                  <h4 style={{ margin: '0 0 10px 0', color: '#dc3545' }}>Disque</h4>
                  <p><strong>Utilisation:</strong> {selectedAgent.last_heartbeat.disk_percent}%</p>
                  <p><strong>Total:</strong> {selectedAgent.last_heartbeat.disk_total_gb} GB</p>
                  <p><strong>Utilisé:</strong> {selectedAgent.last_heartbeat.disk_used_gb} GB</p>
                  <p><strong>Libre:</strong> {selectedAgent.last_heartbeat.disk_free_gb} GB</p>
                </div>

                <div style={{ padding: '15px', backgroundColor: 'white', border: '1px solid #ddd', borderRadius: '4px' }}>
                  <h4 style={{ margin: '0 0 10px 0', color: '#6c757d' }}>Système</h4>
                  <p><strong>Uptime:</strong> {formatUptime(selectedAgent.last_heartbeat.uptime_seconds)}</p>
                  <p><strong>Latence:</strong> {selectedAgent.last_heartbeat.latency_ms} ms</p>
                  <p><strong>Température:</strong> {selectedAgent.last_heartbeat.temperature_celsius ? `${selectedAgent.last_heartbeat.temperature_celsius}°C` : 'N/A'}</p>
                </div>

                <div style={{ padding: '15px', backgroundColor: 'white', border: '1px solid #ddd', borderRadius: '4px' }}>
                  <h4 style={{ margin: '0 0 10px 0', color: '#17a2b8' }}>Informations</h4>
                  <p><strong>OS:</strong> {selectedAgent.os} {selectedAgent.os_version}</p>
                  <p><strong>Version agent:</strong> {selectedAgent.agent_version}</p>
                  <p><strong>IP:</strong> {selectedAgent.ip_address}</p>
                  <p><strong>Machine ID:</strong> {selectedAgent.machine_id.substring(0, 8)}...</p>
                </div>

                <div style={{ padding: '15px', backgroundColor: 'white', border: '1px solid #ddd', borderRadius: '4px' }}>
                  <h4 style={{ margin: '0 0 10px 0', color: '#ffc107' }}>Timestamp</h4>
                  <p><strong>Dernier heartbeat:</strong></p>
                  <p>{new Date(selectedAgent.last_heartbeat.timestamp).toLocaleString()}</p>
                </div>
              </div>
              
              <div style={{ marginTop: '30px' }}>
                <MetricsChart agentId={selectedAgent.id} token={token} />
              </div>
            </div>
          ) : (
            <p>Aucun heartbeat disponible pour cet agent</p>
          )}
        </div>
      )}
    </div>
  );
}

export default Dashboard;
