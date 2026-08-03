import React, { useState, useEffect } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer
} from 'recharts';

const MetricsChart = ({ agentId, token }) => {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchMetrics = async () => {
      try {
        const response = await fetch(
          `https://localhost:8443/api/agents/${agentId}/heartbeats?limit=100`,
          {
            headers: {
              'Authorization': `Bearer ${token}`,
              'Content-Type': 'application/json'
            }
          }
        );
        
        if (!response.ok) {
          throw new Error('Failed to fetch metrics');
        }
        
        const heartbeats = await response.json();
        
        // Transformer les données pour le graphique
        const chartData = heartbeats.map(hb => ({
          timestamp: new Date(hb.timestamp).toLocaleTimeString(),
          cpu: hb.cpu_percent,
          ram: hb.ram_percent,
          disk: hb.disk_percent
        })).reverse(); // Inverser pour avoir l'ordre chronologique
        
        setData(chartData);
        setLoading(false);
      } catch (err) {
        setError(err.message);
        setLoading(false);
      }
    };

    fetchMetrics();
  }, [agentId, token]);

  if (loading) return <div>Chargement des métriques...</div>;
  if (error) return <div>Erreur: {error}</div>;
  if (data.length === 0) return <div>Aucune donnée disponible</div>;

  return (
    <div className="metrics-chart">
      <h3>Évolution des métriques</h3>
      <ResponsiveContainer width="100%" height={400}>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="timestamp" />
          <YAxis domain={[0, 100]} />
          <Tooltip />
          <Legend />
          <Line
            type="monotone"
            dataKey="cpu"
            stroke="#8884d8"
            name="CPU (%)"
            strokeWidth={2}
          />
          <Line
            type="monotone"
            dataKey="ram"
            stroke="#82ca9d"
            name="RAM (%)"
            strokeWidth={2}
          />
          <Line
            type="monotone"
            dataKey="disk"
            stroke="#ffc658"
            name="Disque (%)"
            strokeWidth={2}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
};

export default MetricsChart;
