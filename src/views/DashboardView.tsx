/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState, useMemo, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../context/AppContext';
import { Badge } from '../components/common/Badge';
import { ProgressBar } from '../components/common/ProgressBar';
import { AcknowledgeModal } from '../components/common/AcknowledgeModal';
import { PageHeader } from '../components/layout/PageHeader';
import { EnrolmentSheet } from '../components/ui/EnrolmentSheet';
import { PulseStrip } from '../components/layout/PulseStrip';
import { Alert, AlertSeverity } from '../types';
import { useI18n } from '../i18n';
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
  Bell,
  Plus,
  Download,
  CheckCircle2,
  TrendingUp,
  PieChart as PieChartIcon,
  ArrowRight,
  ServerOff,
} from 'lucide-react';
import { BackendNotificationChannelStatus } from '../services/types/api.types';

function severityRank(severity: AlertSeverity): number {
  if (severity === 'critical') return 0;
  if (severity === 'major' || severity === 'warning') return 1;
  if (severity === 'minor') return 2;
  return 3;
}

function triageSeverityStyle(severity: AlertSeverity) {
  if (severity === 'critical') {
    return { short: 'CRIT', bg: 'bg-rose-50', fg: 'text-rose-700', bd: 'border-rose-200' };
  }
  if (severity === 'major' || severity === 'warning') {
    return { short: 'MAJ', bg: 'bg-amber-50', fg: 'text-amber-800', bd: 'border-amber-200' };
  }
  if (severity === 'minor') {
    return { short: 'MIN', bg: 'bg-orange-50', fg: 'text-orange-800', bd: 'border-orange-200' };
  }
  return { short: 'INFO', bg: 'bg-[var(--color-ln2)]', fg: 'text-[var(--color-tx2)]', bd: 'border-[var(--color-ln)]' };
}

export const DashboardView: React.FC = () => {
  const navigate = useNavigate();
  const { t } = useI18n();
  const {
    agents,
    alerts,
    currentRole,
    navigateToAgentDetail,
    acknowledgeAlert,
    exportCSV,
    generateEnrollmentToken,
  } = useApp();

  const [enrolOpen, setEnrolOpen] = useState(false);
  const [enrolToken, setEnrolToken] = useState<string | null>(null);
  const [enrolExpires, setEnrolExpires] = useState<string | undefined>();
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

  const openAlerts = alerts.filter((a) => a.status === 'open');
  const criticalAlerts = openAlerts.filter((a) => a.severity === 'critical');
  const warningAlerts = openAlerts.filter(
    (a) => a.severity === 'major' || a.severity === 'warning' || a.severity === 'minor'
  );
  const infoAlerts = openAlerts.filter((a) => a.severity === 'info');

  const triageAlerts = useMemo(
    () =>
      [...openAlerts]
        .sort((a, b) => severityRank(a.severity) - severityRank(b.severity))
        .slice(0, 8),
    [openAlerts]
  );

  const silentAgents = useMemo(() => agents.filter((a) => a.status === 'offline'), [agents]);

  const pulseItems = useMemo(
    () => [
      {
        id: 'fleet',
        label: 'Parc en ligne',
        value: `${onlineAgents}/${totalAgents}`,
        color: 'text-[var(--color-tx)]',
        sub: offlineAgents > 0 ? `${offlineAgents} hôte${offlineAgents > 1 ? 's' : ''} silencieux` : 'Tout le parc répond',
        onClick: () => navigate('/agents'),
      },
      {
        id: 'critical',
        label: 'Alertes critiques ouvertes',
        value: criticalAlerts.length,
        color: criticalAlerts.length > 0 ? 'text-rose-600' : 'text-emerald-600',
        sub: criticalAlerts[0] ? `dernière à ${criticalAlerts[0].timestamp}` : 'Aucune',
        onClick: () => navigate('/alerts'),
      },
      {
        id: 'offline',
        label: 'Hors ligne',
        value: offlineAgents,
        unit: 'hôtes',
        color: offlineAgents > 0 ? 'text-amber-700' : 'text-[var(--color-tx)]',
        sub: silentAgents.length === 1 ? silentAgents[0].name : undefined,
        onClick: () => navigate('/agents?status=offline'),
      },
      {
        id: 'mail',
        label: 'Canal Mail',
        value:
          notificationChannelStatus?.status === 'operational'
            ? 'OK'
            : notificationChannelStatus?.status === 'degraded'
              ? 'Dég.'
              : notificationChannelStatus?.status === 'error'
                ? 'Err.'
                : '—',
        color:
          notificationChannelStatus?.status === 'operational'
            ? 'text-emerald-600'
            : notificationChannelStatus?.status === 'error'
              ? 'text-rose-600'
              : 'text-[var(--color-tx2)]',
        sub: notificationChannelStatus?.error,
        onClick: () => navigate('/integrations'),
      },
    ],
    [onlineAgents, totalAgents, criticalAlerts, offlineAgents, silentAgents, notificationChannelStatus, navigate]
  );

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

  const handleGenerateToken = async () => {
    const created = await generateEnrollmentToken();
    if (!created) return;
    setEnrolToken(created.token);
    setEnrolExpires(created.expiresAt);
    setEnrolOpen(true);
  };

  return (
    <div className="space-y-4">
      <PageHeader
        title={t('dashboard.title')}
        subtitle={t('dashboard.subtitle')}
        primaryAction={
          currentRole === 'Admin' ? (
            <button type="button" onClick={() => void handleGenerateToken()} className="cbc-btn-primary">
              <Plus className="w-4 h-4" />
              {t('dashboard.enrol')}
            </button>
          ) : undefined
        }
        secondaryActions={
          currentRole !== 'ReadOnly' ? (
            <button
              type="button"
              onClick={() => exportCSV('agents')}
              className="cbc-btn-secondary"
            >
              <Download className="w-3.5 h-3.5" />
              CSV
            </button>
          ) : undefined
        }
      />

      {totalAgents === 0 ? (
        <div className="cbc-card py-20 px-8 text-center">
          <div className="w-24 h-24 rounded-3xl bg-[var(--color-ln2)] border border-[var(--color-ln)] flex items-center justify-center mx-auto text-[var(--color-tx3)]">
            <ServerOff className="w-10 h-10" />
          </div>
          <h2 className="text-lg font-extrabold mt-5">{t('dashboard.emptyTitle')}</h2>
          <p className="text-[13px] leading-relaxed text-[#777777] mt-2 max-w-md mx-auto">
            {t('dashboard.emptyBody')}
          </p>
          {currentRole === 'Admin' && (
            <button type="button" onClick={() => void handleGenerateToken()} className="cbc-btn-primary mt-5">
              {t('dashboard.enrolFirst')}
            </button>
          )}
        </div>
      ) : (
        <>
          <PulseStrip items={pulseItems} />

          <div className="cbc-card overflow-hidden">
            <div className="flex items-center justify-between px-[18px] py-3.5 border-b border-[var(--color-ln)]">
              <div className="flex items-center gap-2.5">
                <h2 className="text-sm font-bold m-0">{t('dashboard.triage')}</h2>
                <span className="px-2 py-0.5 rounded-full bg-[var(--color-ln2)] text-[var(--color-tx2)] text-[11px] font-semibold">
                  {triageAlerts.length}
                </span>
              </div>
              <button
                type="button"
                onClick={() => navigate('/alerts')}
                className="text-[12.5px] font-semibold text-[#A68523] hover:text-[var(--color-tx)] flex items-center gap-1"
              >
                {t('dashboard.viewAlerts')}
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </div>
            {triageAlerts.length === 0 ? (
              <div className="py-12 text-center text-sm text-[var(--color-tx2)]">
                <CheckCircle2 className="w-8 h-8 text-emerald-500 mx-auto mb-2" />
                Aucune alerte ouverte à traiter.
              </div>
            ) : (
              <table className="w-full border-collapse">
                <tbody>
                  {triageAlerts.map((alt) => {
                    const style = triageSeverityStyle(alt.severity);
                    return (
                      <tr
                        key={alt.id}
                        className="border-b border-[var(--color-ln2)] hover:bg-[var(--color-ln2)] cursor-pointer"
                        onClick={() => navigate('/alerts')}
                      >
                        <td className="py-3 px-[18px] w-[104px]">
                          <span
                            className={`inline-block px-2 py-0.5 rounded-md text-[10.5px] font-bold tracking-wide border ${style.bg} ${style.fg} ${style.bd}`}
                          >
                            {style.short}
                          </span>
                        </td>
                        <td className="py-3 px-2 text-[13px] font-bold w-32">{alt.agentName}</td>
                        <td className="py-3 px-2 text-[13px] text-[var(--color-tx2)]">{alt.message}</td>
                        <td className="py-3 px-2 tnum text-[12.5px] text-[var(--color-tx2)] w-16">{alt.timestamp}</td>
                        <td className="py-3 px-[18px] text-right w-[118px]">
                          {currentRole !== 'ReadOnly' && (
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                handleOpenAckModal(alt);
                              }}
                              className="cbc-btn-secondary py-1.5"
                            >
                              Acquitter
                            </button>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
        </>
      )}

      {totalAgents > 0 && (
        <>
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Chart 1: Évolution de la charge globale (Col-7 on Desktop) */}
        <div className="lg:col-span-7 cbc-card p-5 flex flex-col justify-between">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-base font-bold text-[var(--color-tx)] tracking-tight flex items-center gap-2">
                <TrendingUp className="w-4 h-4 text-[#D0B335]" />
                Évolution de la charge système (24h)
              </h3>
              <p className="text-xs text-[var(--color-tx2)] mt-0.5">
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
        <div className="lg:col-span-5 cbc-card p-5 flex flex-col justify-between">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-2">
            <div>
              <h3 className="text-base font-bold text-[var(--color-tx)] tracking-tight flex items-center gap-2">
                <PieChartIcon className="w-4 h-4 text-[#D0B335]" />
                Répartition globale du parc
              </h3>
              <p className="text-xs text-[var(--color-tx2)] mt-0.5">Distribution par OS, statut ou gravité d'alerte</p>
            </div>

            <div className="flex items-center bg-[var(--color-ln2)] p-0.5 rounded-xl text-[11px] font-bold">
              <button
                onClick={() => setPieMode('os')}
                className={`px-2.5 py-1 rounded-lg transition-colors cursor-pointer ${
                  pieMode === 'os' ? 'bg-[var(--color-panel)] text-[var(--color-tx)] shadow-xs' : 'text-[var(--color-tx2)] hover:text-[var(--color-tx)]'
                }`}
              >
                Système OS
              </button>
              <button
                onClick={() => setPieMode('status')}
                className={`px-2.5 py-1 rounded-lg transition-colors cursor-pointer ${
                  pieMode === 'status' ? 'bg-[var(--color-panel)] text-[var(--color-tx)] shadow-xs' : 'text-[var(--color-tx2)] hover:text-[var(--color-tx)]'
                }`}
              >
                Statut
              </button>
              <button
                onClick={() => setPieMode('alerts')}
                className={`px-2.5 py-1 rounded-lg transition-colors cursor-pointer ${
                  pieMode === 'alerts' ? 'bg-[var(--color-panel)] text-[var(--color-tx)] shadow-xs' : 'text-[var(--color-tx2)] hover:text-[var(--color-tx)]'
                }`}
              >
                Alertes
              </button>
            </div>
          </div>

          <div className="h-64 w-full flex items-center justify-center relative">
            {pieChartData.length === 0 ? (
              <div className="text-xs text-[var(--color-tx3)] font-medium text-center">
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
                    formatter={(value) => <span className="text-xs font-bold text-[var(--color-tx2)] mr-2">{value}</span>}
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
        <div className="lg:col-span-8 cbc-card overflow-hidden">
          <div className="p-5 border-b border-[var(--color-ln2)] flex items-center justify-between">
            <div>
              <h3 className="text-base font-bold text-[var(--color-tx)] tracking-tight flex items-center gap-2">
                <Server className="w-4 h-4 text-[#D0B335]" />
                Agents récents & Métriques en temps réel
              </h3>
              <p className="text-xs text-[var(--color-tx2)] mt-0.5">
                Aperçu rapide des 10 dernières machines enrôlées
              </p>
            </div>
            <button
              onClick={() => navigate('/agents')}
              className="text-xs font-bold text-[#8D771B] hover:text-[var(--color-tx)] transition-colors cursor-pointer"
            >
              Voir tous les agents ({agents.length}) →
            </button>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-[var(--color-ln2)]/70 text-[11px] font-bold text-[var(--color-tx2)] uppercase tracking-wider border-b border-[var(--color-ln2)]">
                  <th className="py-3 px-4">Agent / Hostname</th>
                  <th className="py-3 px-4">OS</th>
                  <th className="py-3 px-4">Statut</th>
                  <th className="py-3 px-4 min-w-[120px]">Charge CPU</th>
                  <th className="py-3 px-4 min-w-[120px]">Mémoire RAM</th>
                  <th className="py-3 px-4 text-center">Alertes</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--color-ln2)] text-xs text-[var(--color-tx2)]">
                {agents.length === 0 && (
                  <tr>
                    <td colSpan={6} className="py-8 px-4 text-center text-[var(--color-tx3)]">
                      Aucun agent chargé. Déconnectez-vous, reconnectez-vous, puis rafraîchissez la page.
                    </td>
                  </tr>
                )}
                {agents.slice(0, 10).map((ag) => (
                  <tr
                    key={ag.id}
                    onClick={() => navigateToAgentDetail(ag.id)}
                    className="hover:bg-[var(--color-ln2)]/80 transition-colors cursor-pointer group"
                  >
                    <td className="py-3 px-4">
                      <div className="font-bold text-[var(--color-tx)] group-hover:text-[#A68523] transition-colors">
                        {ag.name}
                      </div>
                      <div className="text-[11px] text-[var(--color-tx3)] font-mono truncate max-w-[180px]">
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
                        <span className="text-[var(--color-tx3)] text-xs">-</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Recent Alerts Widget (Col-4 on Desktop) */}
        <div className="lg:col-span-4 cbc-card flex flex-col overflow-hidden">
          <div className="p-5 border-b border-[var(--color-ln2)] flex items-center justify-between">
            <div>
              <h3 className="text-base font-bold text-[var(--color-tx)] tracking-tight flex items-center gap-2">
                <Bell className="w-4 h-4 text-rose-500" />
                Dernières alertes
              </h3>
              <p className="text-xs text-[var(--color-tx2)] mt-0.5">Alertes système non résolues</p>
            </div>
            <button
              onClick={() => navigate('/alerts')}
              className="text-xs font-bold text-[#8D771B] hover:text-[var(--color-tx)] cursor-pointer"
            >
              Toutes →
            </button>
          </div>

          <div className="flex-1 overflow-y-auto divide-y divide-[var(--color-ln2)] p-2">
            {openAlerts.length === 0 ? (
              <div className="p-8 text-center text-xs text-[var(--color-tx2)]">
                <CheckCircle2 className="w-10 h-10 text-emerald-500 mx-auto mb-2" />
                Toutes les alertes sont traitées.
              </div>
            ) : (
              openAlerts.slice(0, 5).map((alt) => (
                <div key={alt.id} className="p-3 hover:bg-[var(--color-ln2)] rounded-xl transition-colors">
                  <div className="flex items-center justify-between mb-1">
                    <Badge type="severity" value={alt.severity} size="sm" />
                    <span className="text-[10px] text-[var(--color-tx3)]">{alt.timestamp}</span>
                  </div>
                  <p className="text-xs font-bold text-[var(--color-tx)] mt-1">{alt.agentName}</p>
                  <p className="text-xs text-[var(--color-tx2)] line-clamp-2 mt-0.5 leading-relaxed">
                    {alt.message}
                  </p>
                  {currentRole !== 'ReadOnly' && (
                    <div className="mt-2 flex justify-end">
                      <button
                        onClick={() => handleOpenAckModal(alt)}
                        className="text-[11px] font-bold text-[#A68523] hover:text-[#8D771B] cursor-pointer"
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
        </>
      )}

      {/* Acknowledge Modal */}
      <AcknowledgeModal
        isOpen={ackModalOpen}
        onClose={() => setAckModalOpen(false)}
        alert={targetAlertToAck}
        onConfirm={handleConfirmAck}
      />

      <EnrolmentSheet
        open={enrolOpen}
        token={enrolToken}
        expiresAt={enrolExpires}
        onClose={() => setEnrolOpen(false)}
      />
    </div>
  );
};
