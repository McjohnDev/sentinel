/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState, useMemo, useEffect } from 'react';
import { useApp } from '../context/AppContext';
import { Badge } from '../components/common/Badge';
import { ProgressBar } from '../components/common/ProgressBar';
import { Modal } from '../components/common/Modal';
import { AcknowledgeModal } from '../components/common/AcknowledgeModal';
import { Alert } from '../types';
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  CartesianGrid,
} from 'recharts';
import {
  Server,
  WifiOff,
  Bell,
  AlertOctagon,
  ArrowUpRight,
  PlusCircle,
  Download,
  ExternalLink,
  CheckCircle2,
  Copy,
  Check,
  TrendingUp,
  PieChart as PieChartIcon,
  Signal,
  XCircle,
  AlertTriangle,
} from 'lucide-react';
import { BackendNotificationChannelStatus } from '../services/types/api.types';

export const DashboardView: React.FC = () => {
  const {
    agents,
    alerts,
    currentRole,
    setActiveView,
    navigateToAgentDetail,
    acknowledgeAlert,
    exportCSV,
    generateEnrollmentToken,
  } = useApp();

  const [tokenModalOpen, setTokenModalOpen] = useState(false);
  const [generatedToken, setGeneratedToken] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [pieMode, setPieMode] = useState<'os' | 'status' | 'alerts'>('os');
  const [ackModalOpen, setAckModalOpen] = useState(false);
  const [targetAlertToAck, setTargetAlertToAck] = useState<Alert | null>(null);
  const [notificationChannelStatus, setNotificationChannelStatus] = useState<BackendNotificationChannelStatus | null>(null);

  // Récupérer le statut du canal de notification (exigence R11)
  useEffect(() => {
    const fetchNotificationStatus = async () => {
      try {
        const response = await fetch('/api/system/notification-channel-status', {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
          },
        });
        if (response.ok) {
          const status = await response.json();
          setNotificationChannelStatus(status);
        }
      } catch (error) {
        console.error('Erreur lors de la récupération du statut du canal de notification:', error);
      }
    };

    fetchNotificationStatus();
    const interval = setInterval(fetchNotificationStatus, 60000); // Vérifier toutes les 60s
    return () => clearInterval(interval);
  }, []);

  const handleOpenAckModal = (alt: Alert) => {
    setTargetAlertToAck(alt);
    setAckModalOpen(true);
  };

  const handleConfirmAck = (alertId: string, comment: string, operatorName: string) => {
    acknowledgeAlert(alertId, comment, operatorName);
    setAckModalOpen(false);
    setTargetAlertToAck(null);
  };

  // Compute KPIs
  const totalAgents = agents.length;
  const onlineAgents = agents.filter((a) => a.status === 'online').length;
  const offlineAgents = agents.filter((a) => a.status === 'offline').length;
  const onlineRatio = totalAgents > 0 ? Math.round((onlineAgents / totalAgents) * 100) : 0;
  const offlineRatio = totalAgents > 0 ? Math.round((offlineAgents / totalAgents) * 100) : 0;

  const openAlerts = alerts.filter((a) => a.status === 'open');
  const criticalAlerts = openAlerts.filter((a) => a.severity === 'critical');
  const warningAlerts = openAlerts.filter((a) => a.severity === 'warning');
  const infoAlerts = openAlerts.filter((a) => a.severity === 'info');

  // Compute aggregated historical trend for Area Chart (average load across agents)
  const areaChartData = useMemo(() => {
    const timeLabels = ['00:00', '04:00', '08:00', '12:00', '16:00', '20:00', 'Maintenant'];
    if (agents.length === 0) return [];

    return timeLabels.map((time, index) => {
      let cpuSum = 0;
      let ramSum = 0;
      let diskSum = 0;

      agents.forEach((ag) => {
        const cpuHist = ag.metrics.cpuHistory || [ag.metrics.cpu];
        const ramHist = ag.metrics.ramHistory || [ag.metrics.ram];
        const diskHist = ag.metrics.diskHistory || [ag.metrics.disk];

        const cVal = cpuHist[index % cpuHist.length] ?? ag.metrics.cpu;
        const rVal = ramHist[index % ramHist.length] ?? ag.metrics.ram;
        const dVal = diskHist[index % diskHist.length] ?? ag.metrics.disk;

        cpuSum += cVal;
        ramSum += rVal;
        diskSum += dVal;
      });

      return {
        heure: time,
        CPU: Math.round(cpuSum / agents.length),
        RAM: Math.round(ramSum / agents.length),
        Disque: Math.round(diskSum / agents.length),
      };
    });
  }, [agents]);

  // Compute Pie Chart Data based on selected mode
  const pieChartData = useMemo(() => {
    if (pieMode === 'os') {
      const winCount = agents.filter((a) => a.os === 'windows').length;
      const linCount = agents.filter((a) => a.os === 'linux').length;
      const macCount = agents.filter((a) => a.os === 'macos').length;

      return [
        { name: 'Windows', value: winCount, color: '#0284C7' },
        { name: 'Linux', value: linCount, color: '#D0B335' },
        { name: 'macOS', value: macCount, color: '#64748B' },
      ].filter((item) => item.value > 0);
    } else if (pieMode === 'status') {
      const online = agents.filter((a) => a.status === 'online').length;
      const offline = agents.filter((a) => a.status === 'offline').length;
      const obsolete = agents.filter((a) => a.status === 'obsolete').length;
      const revoked = agents.filter((a) => a.status === 'revoked').length;

      return [
        { name: 'En ligne', value: online, color: '#10B981' },
        { name: 'Hors ligne', value: offline, color: '#EF4444' },
        { name: 'Obsolète', value: obsolete, color: '#F59E0B' },
        { name: 'Révoqué', value: revoked, color: '#94A3B8' },
      ].filter((item) => item.value > 0);
    } else {
      // Alerts by Severity
      return [
        { name: 'Critique', value: criticalAlerts.length, color: '#E11D48' },
        { name: 'Warning', value: warningAlerts.length, color: '#F59E0B' },
        { name: 'Information', value: infoAlerts.length, color: '#3B82F6' },
      ].filter((item) => item.value > 0);
    }
  }, [agents, pieMode, criticalAlerts.length, warningAlerts.length, infoAlerts.length]);

  const handleGenerateToken = () => {
    const newTokenObj = generateEnrollmentToken();
    setGeneratedToken(newTokenObj.token);
    setTokenModalOpen(true);
  };

  const handleCopyToken = () => {
    if (generatedToken) {
      navigator.clipboard.writeText(generatedToken);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="space-y-6">
      {/* Quick Action Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white p-5 rounded-2xl border border-slate-200/80 shadow-xs">
        <div className="flex-1">
          <h2 className="text-xl font-black text-slate-900 tracking-tight flex items-center gap-2">
            Vue d'ensemble du parc informatique
          </h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Supervision centralisée en temps réel — Commercial Bank Cameroun
          </p>
        </div>

        {/* Indicateur visuel du canal de notification (exigence R11) */}
        <div className="flex items-center gap-2">
          {notificationChannelStatus && (
            <div
              className={`flex items-center gap-2 px-3 py-2 rounded-xl border ${
                notificationChannelStatus.status === 'operational'
                  ? 'bg-emerald-50 border-emerald-200'
                  : notificationChannelStatus.status === 'degraded'
                  ? 'bg-amber-50 border-amber-200'
                  : notificationChannelStatus.status === 'error'
                  ? 'bg-rose-50 border-rose-200'
                  : 'bg-slate-50 border-slate-200'
              }`}
            >
              {notificationChannelStatus.status === 'operational' ? (
                <Signal className="w-4 h-4 text-emerald-600" />
              ) : notificationChannelStatus.status === 'degraded' ? (
                <AlertTriangle className="w-4 h-4 text-amber-600" />
              ) : notificationChannelStatus.status === 'error' ? (
                <XCircle className="w-4 h-4 text-rose-600" />
              ) : (
                <Signal className="w-4 h-4 text-slate-400" />
              )}
              <span
                className={`text-xs font-bold ${
                  notificationChannelStatus.status === 'operational'
                    ? 'text-emerald-800'
                    : notificationChannelStatus.status === 'degraded'
                    ? 'text-amber-800'
                    : notificationChannelStatus.status === 'error'
                    ? 'text-rose-800'
                    : 'text-slate-600'
                }`}
              >
                Canal de notification: {notificationChannelStatus.status === 'operational' ? 'Opérationnel' : notificationChannelStatus.status === 'degraded' ? 'Dégradé' : notificationChannelStatus.status === 'error' ? 'Erreur' : 'Inconnu'}
              </span>
            </div>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {currentRole === 'Admin' && (
            <button
              onClick={handleGenerateToken}
              className="inline-flex items-center gap-2 px-3.5 py-2 bg-[#D0B335] hover:bg-[#b89d2d] text-slate-950 text-xs font-bold rounded-xl shadow-xs transition-colors cursor-pointer"
            >
              <PlusCircle className="w-4 h-4" />
              Générer jeton d'enrôlement
            </button>
          )}

          <button
            onClick={() => setActiveView('alerts')}
            className="inline-flex items-center gap-2 px-3.5 py-2 bg-slate-100 hover:bg-slate-200 text-slate-800 text-xs font-semibold rounded-xl transition-colors border border-slate-200/60 cursor-pointer"
          >
            <Bell className="w-4 h-4 text-slate-600" />
            Voir les alertes
          </button>

          {currentRole !== 'ReadOnly' && (
            <button
              onClick={() => exportCSV('agents')}
              className="inline-flex items-center gap-2 px-3.5 py-2 bg-slate-900 hover:bg-slate-800 text-white text-xs font-semibold rounded-xl transition-colors shadow-xs cursor-pointer"
            >
              <Download className="w-4 h-4 text-slate-300" />
              Exporter CSV
            </button>
          )}
        </div>
      </div>

      {/* Row 1: 4 Top KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* KPI 1: Agents en ligne */}
        <div
          onClick={() => setActiveView('agents')}
          className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-xs hover:border-[#D0B335]/60 hover:shadow-md transition-all cursor-pointer relative overflow-hidden group"
        >
          <div className="flex justify-between items-start">
            <div>
              <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">
                Agents en ligne
              </span>
              <div className="text-3xl font-black text-slate-900 mt-2 flex items-baseline gap-2">
                {onlineAgents}
                <span className="text-xs font-semibold text-slate-400">/ {totalAgents}</span>
              </div>
            </div>
            <div className="w-10 h-10 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center border border-emerald-100 group-hover:scale-110 transition-transform">
              <Server className="w-5 h-5" />
            </div>
          </div>

          <div className="mt-4 flex items-center justify-between text-xs pt-3 border-t border-slate-100">
            <span
              className={`px-2 py-0.5 rounded-full font-bold text-[11px] ${
                onlineRatio >= 90
                  ? 'bg-emerald-100 text-emerald-800'
                  : onlineRatio >= 70
                  ? 'bg-amber-100 text-amber-800'
                  : 'bg-rose-100 text-rose-800'
              }`}
            >
              {onlineRatio}% en ligne
            </span>
            <span className="text-emerald-600 font-semibold flex items-center gap-0.5">
              <ArrowUpRight className="w-3.5 h-3.5" /> +2.4% vs hier
            </span>
          </div>
        </div>

        {/* KPI 2: Agents hors ligne */}
        <div
          onClick={() => setActiveView('agents')}
          className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-xs hover:border-rose-300 hover:shadow-md transition-all cursor-pointer relative overflow-hidden group"
        >
          <div className="flex justify-between items-start">
            <div>
              <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">
                Agents hors ligne
              </span>
              <div className="text-3xl font-black text-slate-900 mt-2 flex items-baseline gap-2">
                {offlineAgents}
                <span className="text-xs font-semibold text-slate-400">inactifs</span>
              </div>
            </div>
            <div className="w-10 h-10 rounded-xl bg-rose-50 text-rose-600 flex items-center justify-center border border-rose-100 group-hover:scale-110 transition-transform">
              <WifiOff className="w-5 h-5" />
            </div>
          </div>

          <div className="mt-4 flex items-center justify-between text-xs pt-3 border-t border-slate-100">
            <span
              className={`px-2 py-0.5 rounded-full font-bold text-[11px] ${
                offlineRatio > 10
                  ? 'bg-rose-100 text-rose-800'
                  : offlineRatio > 5
                  ? 'bg-amber-100 text-amber-800'
                  : 'bg-emerald-100 text-emerald-800'
              }`}
            >
              {offlineRatio}% hors ligne
            </span>
            <span className="text-slate-400 font-medium">Recherche d'heartbeat...</span>
          </div>
        </div>

        {/* KPI 3: Alertes actives */}
        <div
          onClick={() => setActiveView('alerts')}
          className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-xs hover:border-amber-300 hover:shadow-md transition-all cursor-pointer relative overflow-hidden group"
        >
          <div className="flex justify-between items-start">
            <div>
              <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">
                Alertes non acquittées
              </span>
              <div className="text-3xl font-black text-slate-900 mt-2">{openAlerts.length}</div>
            </div>
            <div className="w-10 h-10 rounded-xl bg-amber-50 text-amber-600 flex items-center justify-center border border-amber-100 group-hover:scale-110 transition-transform">
              <Bell className="w-5 h-5" />
            </div>
          </div>

          <div className="mt-4 flex items-center gap-2 text-xs pt-3 border-t border-slate-100">
            <span className="text-rose-600 font-bold">{criticalAlerts.length} Critique</span>
            <span className="text-slate-300">•</span>
            <span className="text-amber-600 font-bold">{warningAlerts.length} Warning</span>
            <span className="text-slate-300">•</span>
            <span className="text-blue-600 font-bold">{infoAlerts.length} Info</span>
          </div>
        </div>

        {/* KPI 4: Alertes critiques */}
        <div
          onClick={() => setActiveView('alerts')}
          className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-xs hover:border-rose-400 hover:shadow-md transition-all cursor-pointer relative overflow-hidden group"
        >
          <div className="flex justify-between items-start">
            <div>
              <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">
                Alertes critiques
              </span>
              <div className="text-3xl font-black text-rose-600 mt-2 flex items-center gap-2">
                {criticalAlerts.length}
                {criticalAlerts.length > 0 && (
                  <span className="w-2.5 h-2.5 rounded-full bg-rose-600 animate-ping"></span>
                )}
              </div>
            </div>
            <div className="w-10 h-10 rounded-xl bg-rose-600 text-white flex items-center justify-center shadow-md shadow-rose-600/20 group-hover:scale-110 transition-transform">
              <AlertOctagon className="w-5 h-5" />
            </div>
          </div>

          <div className="mt-4 flex items-center justify-between text-xs pt-3 border-t border-slate-100">
            <span className="text-rose-700 font-bold">
              {criticalAlerts.length > 0 ? 'Action immédiate requise' : 'Aucun incident critique'}
            </span>
            <ExternalLink className="w-3.5 h-3.5 text-slate-400" />
          </div>
        </div>
      </div>

      {/* Row 2: GRAPHICS (Line/Area Chart & Pie Chart side-by-side) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Chart 1: Évolution de la charge globale (Col-7 on Desktop) */}
        <div className="lg:col-span-7 bg-white p-5 rounded-2xl border border-slate-200/80 shadow-xs flex flex-col justify-between">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-base font-bold text-slate-900 tracking-tight flex items-center gap-2">
                <TrendingUp className="w-4 h-4 text-[#D0B335]" />
                Évolution de la charge système (24h)
              </h3>
              <p className="text-xs text-slate-500 mt-0.5">
                Consommation moyenne CPU, RAM et Disque sur l'ensemble du parc
              </p>
            </div>
            <div className="flex items-center gap-2 text-[11px] font-bold">
              <span className="flex items-center gap-1 text-[#8D771B]">
                <span className="w-2.5 h-2.5 rounded-full bg-[#D0B335]"></span> CPU
              </span>
              <span className="flex items-center gap-1 text-blue-600">
                <span className="w-2.5 h-2.5 rounded-full bg-blue-500"></span> RAM
              </span>
              <span className="flex items-center gap-1 text-purple-600">
                <span className="w-2.5 h-2.5 rounded-full bg-purple-500"></span> Disque
              </span>
            </div>
          </div>

          <div className="h-64 w-full pt-2">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={areaChartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <defs>
                  <linearGradient id="colorCpu" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#D0B335" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#D0B335" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="colorRam" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#3B82F6" stopOpacity={0.25} />
                    <stop offset="95%" stopColor="#3B82F6" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="colorDisk" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#8B5CF6" stopOpacity={0.2} />
                    <stop offset="95%" stopColor="#8B5CF6" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#E2E8F0" />
                <XAxis dataKey="heure" tick={{ fontSize: 11, fill: '#64748B' }} tickLine={false} axisLine={false} />
                <YAxis domain={[0, 100]} tick={{ fontSize: 11, fill: '#64748B' }} tickLine={false} axisLine={false} unit="%" />
                <Tooltip
                  contentStyle={{ backgroundColor: '#0F172A', borderRadius: '12px', color: '#fff', fontSize: '12px', border: 'none' }}
                  itemStyle={{ color: '#F8FAFC' }}
                  formatter={(val: number) => [`${val}%`, '']}
                />
                <Area type="monotone" dataKey="CPU" stroke="#D0B335" strokeWidth={2.5} fillOpacity={1} fill="url(#colorCpu)" />
                <Area type="monotone" dataKey="RAM" stroke="#3B82F6" strokeWidth={2} fillOpacity={1} fill="url(#colorRam)" />
                <Area type="monotone" dataKey="Disque" stroke="#8B5CF6" strokeWidth={2} fillOpacity={1} fill="url(#colorDisk)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Chart 2: Diagramme Circulaire (Col-5 on Desktop) */}
        <div className="lg:col-span-5 bg-white p-5 rounded-2xl border border-slate-200/80 shadow-xs flex flex-col justify-between">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-2">
            <div>
              <h3 className="text-base font-bold text-slate-900 tracking-tight flex items-center gap-2">
                <PieChartIcon className="w-4 h-4 text-[#D0B335]" />
                Répartition globale du parc
              </h3>
              <p className="text-xs text-slate-500 mt-0.5">Distribution par OS, statut ou gravité d'alerte</p>
            </div>

            <div className="flex items-center bg-slate-100 p-0.5 rounded-xl text-[11px] font-bold">
              <button
                onClick={() => setPieMode('os')}
                className={`px-2.5 py-1 rounded-lg transition-colors cursor-pointer ${
                  pieMode === 'os' ? 'bg-white text-slate-900 shadow-xs' : 'text-slate-500 hover:text-slate-900'
                }`}
              >
                Système OS
              </button>
              <button
                onClick={() => setPieMode('status')}
                className={`px-2.5 py-1 rounded-lg transition-colors cursor-pointer ${
                  pieMode === 'status' ? 'bg-white text-slate-900 shadow-xs' : 'text-slate-500 hover:text-slate-900'
                }`}
              >
                Statut
              </button>
              <button
                onClick={() => setPieMode('alerts')}
                className={`px-2.5 py-1 rounded-lg transition-colors cursor-pointer ${
                  pieMode === 'alerts' ? 'bg-white text-slate-900 shadow-xs' : 'text-slate-500 hover:text-slate-900'
                }`}
              >
                Alertes
              </button>
            </div>
          </div>

          <div className="h-64 w-full flex items-center justify-center relative">
            {pieChartData.length === 0 ? (
              <div className="text-xs text-slate-400 font-medium text-center">
                Aucune donnée à afficher pour cette catégorie.
              </div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={pieChartData}
                    cx="50%"
                    cy="50%"
                    innerRadius={55}
                    outerRadius={85}
                    paddingAngle={4}
                    dataKey="value"
                  >
                    {pieChartData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} stroke="none" />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{ backgroundColor: '#0F172A', borderRadius: '12px', color: '#fff', fontSize: '12px', border: 'none' }}
                    formatter={(val: number, name: string) => [`${val} (${Math.round((val / totalAgents) * 100) || 0}%)`, name]}
                  />
                  <Legend
                    verticalAlign="bottom"
                    height={36}
                    iconType="circle"
                    formatter={(value) => <span className="text-xs font-bold text-slate-700 mr-2">{value}</span>}
                  />
                </PieChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>
      </div>

      {/* Row 3: Agents List Widget (70%) + Recent Alerts Widget (30%) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Agents List Widget (Col-8 on Desktop) */}
        <div className="lg:col-span-8 bg-white rounded-2xl border border-slate-200/80 shadow-xs overflow-hidden">
          <div className="p-5 border-b border-slate-100 flex items-center justify-between">
            <div>
              <h3 className="text-base font-bold text-slate-900 tracking-tight flex items-center gap-2">
                <Server className="w-4 h-4 text-[#D0B335]" />
                Agents récents & Métriques en temps réel
              </h3>
              <p className="text-xs text-slate-500 mt-0.5">
                Aperçu rapide des 10 dernières machines enrôlées
              </p>
            </div>
            <button
              onClick={() => setActiveView('agents')}
              className="text-xs font-bold text-[#8D771B] hover:text-slate-900 transition-colors cursor-pointer"
            >
              Voir tous les agents ({agents.length}) →
            </button>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-slate-50/70 text-[11px] font-bold text-slate-500 uppercase tracking-wider border-b border-slate-100">
                  <th className="py-3 px-4">Agent / Hostname</th>
                  <th className="py-3 px-4">OS</th>
                  <th className="py-3 px-4">Statut</th>
                  <th className="py-3 px-4 min-w-[120px]">Charge CPU</th>
                  <th className="py-3 px-4 min-w-[120px]">Mémoire RAM</th>
                  <th className="py-3 px-4 text-center">Alertes</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-xs text-slate-700">
                {agents.slice(0, 10).map((ag) => (
                  <tr
                    key={ag.id}
                    onClick={() => navigateToAgentDetail(ag.id)}
                    className="hover:bg-slate-50/80 transition-colors cursor-pointer group"
                  >
                    <td className="py-3 px-4">
                      <div className="font-bold text-slate-900 group-hover:text-blue-600 transition-colors">
                        {ag.name}
                      </div>
                      <div className="text-[11px] text-slate-400 font-mono truncate max-w-[180px]">
                        {ag.hostname}
                      </div>
                    </td>
                    <td className="py-3 px-4">
                      <Badge type="os" value={ag.os} size="sm" />
                    </td>
                    <td className="py-3 px-4">
                      <Badge type="status" value={ag.status} size="sm" />
                    </td>
                    <td className="py-3 px-4">
                      <ProgressBar value={ag.metrics.cpu} type="cpu" size="sm" />
                    </td>
                    <td className="py-3 px-4">
                      <ProgressBar value={ag.metrics.ram} type="ram" size="sm" />
                    </td>
                    <td className="py-3 px-4 text-center">
                      {ag.activeAlertsCount > 0 ? (
                        <span className="inline-flex items-center justify-center w-5 h-5 rounded-full bg-rose-600 text-white font-bold text-[10px]">
                          {ag.activeAlertsCount}
                        </span>
                      ) : (
                        <span className="text-slate-400 text-xs">-</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Recent Alerts Widget (Col-4 on Desktop) */}
        <div className="lg:col-span-4 bg-white rounded-2xl border border-slate-200/80 shadow-xs flex flex-col overflow-hidden">
          <div className="p-5 border-b border-slate-100 flex items-center justify-between">
            <div>
              <h3 className="text-base font-bold text-slate-900 tracking-tight flex items-center gap-2">
                <Bell className="w-4 h-4 text-rose-500" />
                Dernières alertes
              </h3>
              <p className="text-xs text-slate-500 mt-0.5">Alertes système non résolues</p>
            </div>
            <button
              onClick={() => setActiveView('alerts')}
              className="text-xs font-bold text-[#8D771B] hover:text-slate-900 cursor-pointer"
            >
              Toutes →
            </button>
          </div>

          <div className="flex-1 overflow-y-auto divide-y divide-slate-100 p-2">
            {openAlerts.length === 0 ? (
              <div className="p-8 text-center text-xs text-slate-500">
                <CheckCircle2 className="w-10 h-10 text-emerald-500 mx-auto mb-2" />
                Toutes les alertes sont traitées.
              </div>
            ) : (
              openAlerts.slice(0, 5).map((alt) => (
                <div key={alt.id} className="p-3 hover:bg-slate-50 rounded-xl transition-colors">
                  <div className="flex items-center justify-between mb-1">
                    <Badge type="severity" value={alt.severity} size="sm" />
                    <span className="text-[10px] text-slate-400">{alt.timestamp}</span>
                  </div>
                  <p className="text-xs font-bold text-slate-900 mt-1">{alt.agentName}</p>
                  <p className="text-xs text-slate-600 line-clamp-2 mt-0.5 leading-relaxed">
                    {alt.message}
                  </p>
                  {currentRole !== 'ReadOnly' && (
                    <div className="mt-2 flex justify-end">
                      <button
                        onClick={() => handleOpenAckModal(alt)}
                        className="text-[11px] font-bold text-blue-600 hover:text-blue-800 cursor-pointer"
                      >
                        Acquitter
                      </button>
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* Acknowledge Modal */}
      <AcknowledgeModal
        isOpen={ackModalOpen}
        onClose={() => setAckModalOpen(false)}
        alert={targetAlertToAck}
        onConfirm={handleConfirmAck}
      />

      {/* Token Modal */}
      <Modal
        isOpen={tokenModalOpen}
        onClose={() => setTokenModalOpen(false)}
        title="Nouveau jeton d'enrôlement"
        footer={
          <button
            onClick={() => setTokenModalOpen(false)}
            className="px-4 py-2 bg-slate-900 text-white text-xs font-bold rounded-xl hover:bg-slate-800 cursor-pointer"
          >
            Fermer
          </button>
        }
      >
        <div className="space-y-4">
          <p className="text-xs text-slate-600 leading-relaxed">
            Utilisez ce jeton sécurisé à usage unique pour enrôler un nouvel agent (Windows, Linux, macOS) dans le parc CBC.
          </p>

          <div className="p-4 bg-slate-900 rounded-xl text-center border border-slate-800">
            <span className="text-xs text-slate-400 block mb-1">Jeton d'enrôlement (Valide 24h)</span>
            <div className="text-lg font-mono font-bold text-[#D0B335] tracking-wider my-1">
              {generatedToken}
            </div>
          </div>

          <button
            onClick={handleCopyToken}
            className="w-full py-2.5 bg-slate-100 hover:bg-slate-200 text-slate-900 text-xs font-bold rounded-xl border border-slate-300 flex items-center justify-center gap-2 transition-colors cursor-pointer"
          >
            {copied ? <Check className="w-4 h-4 text-emerald-600" /> : <Copy className="w-4 h-4" />}
            {copied ? 'Copié dans le presse-papier !' : 'Copier le jeton'}
          </button>
        </div>
      </Modal>
    </div>
  );
};
