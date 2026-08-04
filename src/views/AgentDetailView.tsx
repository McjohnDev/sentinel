/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState } from 'react';
import { useApp } from '../context/AppContext';
import { Badge } from '../components/common/Badge';
import { GaugeChart } from '../components/common/GaugeChart';
import { ProgressBar } from '../components/common/ProgressBar';
import { Modal } from '../components/common/Modal';
import { AcknowledgeModal } from '../components/common/AcknowledgeModal';
import { CustomThresholds, Alert } from '../types';
import {
  ArrowLeft,
  Server,
  Activity,
  Bell,
  Sliders,
  RefreshCw,
  ShieldOff,
  Trash2,
  HardDrive,
  Cpu,
  Database,
  CheckCircle2,
  RotateCcw,
  Save,
} from 'lucide-react';

export const AgentDetailView: React.FC = () => {
  const {
    selectedAgentId,
    agents,
    alerts,
    currentRole,
    globalThresholds,
    setActiveView,
    revokeAgent,
    deleteAgent,
    acknowledgeAlert,
    updateAgentThresholds,
    resetAgentThresholds,
    refreshData,
  } = useApp();

  const [activeTab, setActiveTab] = useState<'overview' | 'metrics' | 'alerts' | 'config'>('overview');

  // Modal States
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [revokeModalOpen, setRevokeModalOpen] = useState(false);
  const [ackModalOpen, setAckModalOpen] = useState(false);
  const [targetAlertToAck, setTargetAlertToAck] = useState<Alert | null>(null);

  const handleOpenAckModal = (alt: Alert) => {
    setTargetAlertToAck(alt);
    setAckModalOpen(true);
  };

  const handleConfirmAck = (alertId: string, comment: string, operatorName: string) => {
    acknowledgeAlert(alertId, comment, operatorName);
    setAckModalOpen(false);
    setTargetAlertToAck(null);
  };

  const agent = agents.find((a) => a.id === selectedAgentId) || agents[0];
  const agentAlerts = alerts.filter((a) => a.agentId === agent.id);
  const activeAgentAlerts = agentAlerts.filter((a) => a.status === 'open');

  // Threshold Form State
  const initialThresholds: CustomThresholds = agent.customThresholds || {
    cpuWarning: globalThresholds.cpuWarning,
    cpuCritical: globalThresholds.cpuCritical,
    ramWarning: globalThresholds.ramWarning,
    ramCritical: globalThresholds.ramCritical,
    diskWarning: globalThresholds.diskWarning,
    diskCritical: globalThresholds.diskCritical,
  };

  const [thresholds, setThresholds] = useState<CustomThresholds>(initialThresholds);
  const [configError, setConfigError] = useState('');

  const handleSaveConfig = (e: React.FormEvent) => {
    e.preventDefault();
    setConfigError('');

    if (thresholds.cpuWarning >= thresholds.cpuCritical) {
      setConfigError('Le seuil CPU Warning doit être strictement inférieur au seuil Critique.');
      return;
    }
    if (thresholds.ramWarning >= thresholds.ramCritical) {
      setConfigError('Le seuil RAM Warning doit être strictement inférieur au seuil Critique.');
      return;
    }
    if (thresholds.diskWarning >= thresholds.diskCritical) {
      setConfigError('Le seuil Disque Warning doit être strictly inférieur au seuil Critique.');
      return;
    }

    updateAgentThresholds(agent.id, thresholds);
  };

  const handleResetConfig = () => {
    resetAgentThresholds(agent.id);
    setThresholds({
      cpuWarning: globalThresholds.cpuWarning,
      cpuCritical: globalThresholds.cpuCritical,
      ramWarning: globalThresholds.ramWarning,
      ramCritical: globalThresholds.ramCritical,
      diskWarning: globalThresholds.diskWarning,
      diskCritical: globalThresholds.diskCritical,
    });
  };

  return (
    <div className="space-y-6">
      {/* Top Header Card */}
      <div className="bg-white p-6 rounded-2xl border border-slate-200/80 shadow-xs space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setActiveView('agents')}
              className="p-2 text-slate-500 hover:text-slate-900 bg-slate-100 hover:bg-slate-200 rounded-xl transition-colors"
              aria-label="Retour à la liste"
            >
              <ArrowLeft className="w-5 h-5" />
            </button>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-xl font-black text-slate-900 tracking-tight">{agent.name}</h2>
                <Badge type="os" value={agent.os} size="sm" />
                <Badge type="status" value={agent.status} size="sm" />
              </div>
              <p className="text-xs text-slate-500 font-mono mt-0.5">
                {agent.hostname} • IP: <span className="font-bold text-slate-700">{agent.ipAddress}</span> • {agent.location}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={refreshData}
              className="p-2 text-slate-600 hover:text-slate-900 bg-slate-100 hover:bg-slate-200 rounded-xl transition-colors"
              title="Rafraîchir les métriques"
            >
              <RefreshCw className="w-4 h-4" />
            </button>

            {currentRole === 'Admin' && (
              <>
                {agent.status !== 'revoked' && (
                  <button
                    onClick={() => setRevokeModalOpen(true)}
                    className="px-3.5 py-2 bg-amber-50 hover:bg-amber-100 text-amber-900 border border-amber-200/80 text-xs font-bold rounded-xl transition-colors flex items-center gap-1.5"
                  >
                    <ShieldOff className="w-4 h-4 text-amber-600" />
                    Révoquer
                  </button>
                )}
                <button
                  onClick={() => setDeleteModalOpen(true)}
                  className="px-3.5 py-2 bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 text-xs font-bold rounded-xl transition-colors flex items-center gap-1.5"
                >
                  <Trash2 className="w-4 h-4 text-rose-600" />
                  Supprimer
                </button>
              </>
            )}
          </div>
        </div>

        {/* Quick Spec Pills */}
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 pt-3 border-t border-slate-100 text-xs">
          <div>
            <span className="text-slate-400 block text-[11px]">Dernier Heartbeat</span>
            <span className="font-bold text-slate-800">{agent.lastHeartbeat}</span>
          </div>
          <div>
            <span className="text-slate-400 block text-[11px]">Temps d'activité (Uptime)</span>
            <span className="font-bold text-slate-800 font-mono">{agent.metrics.uptime}</span>
          </div>
          <div>
            <span className="text-slate-400 block text-[11px]">Agent de supervision</span>
            <span className="font-bold text-[#8D771B] font-mono">{agent.agentVersion || 'CBC Agent v1.0'}</span>
          </div>
          <div>
            <span className="text-slate-400 block text-[11px]">OS & Distribution</span>
            <span className="font-bold text-slate-800 font-mono">{agent.osVersion}</span>
          </div>
          <div>
            <span className="text-slate-400 block text-[11px]">Date d'enrôlement</span>
            <span className="font-bold text-slate-800">{agent.enrollmentDate}</span>
          </div>
        </div>
      </div>

      {/* Navigation Tabs */}
      <div className="flex border-b border-slate-200 space-x-2 bg-white px-4 pt-2 rounded-t-2xl">
        <button
          onClick={() => setActiveTab('overview')}
          className={`pb-3 px-4 text-xs font-bold border-b-2 flex items-center gap-2 transition-colors ${
            activeTab === 'overview'
              ? 'border-[#D0B335] text-slate-900'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <Server className="w-4 h-4" />
          Vue d'ensemble
        </button>
        <button
          onClick={() => setActiveTab('metrics')}
          className={`pb-3 px-4 text-xs font-bold border-b-2 flex items-center gap-2 transition-colors ${
            activeTab === 'metrics'
              ? 'border-[#D0B335] text-slate-900'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <Activity className="w-4 h-4" />
          Métriques détaillées
        </button>
        <button
          onClick={() => setActiveTab('alerts')}
          className={`pb-3 px-4 text-xs font-bold border-b-2 flex items-center gap-2 transition-colors ${
            activeTab === 'alerts'
              ? 'border-[#D0B335] text-slate-900'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <Bell className="w-4 h-4" />
          Alertes ({activeAgentAlerts.length})
        </button>
        <button
          onClick={() => setActiveTab('config')}
          className={`pb-3 px-4 text-xs font-bold border-b-2 flex items-center gap-2 transition-colors ${
            activeTab === 'config'
              ? 'border-[#D0B335] text-slate-900'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <Sliders className="w-4 h-4" />
          Configuration (Seuils)
        </button>
      </div>

      {/* TAB 1: OVERVIEW */}
      {activeTab === 'overview' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Gauges Card */}
          <div className="lg:col-span-2 bg-white p-6 rounded-2xl border border-slate-200/80 shadow-xs space-y-6">
            <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider flex items-center gap-2">
              <Cpu className="w-4 h-4 text-[#D0B335]" />
              Consommation en temps réel
            </h3>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <GaugeChart
                title="Processeur CPU"
                value={agent.metrics.cpu}
                subValue={`${agent.metrics.cpu}% utilisé`}
                warningThreshold={thresholds.cpuWarning}
                criticalThreshold={thresholds.cpuCritical}
              />
              <GaugeChart
                title="Mémoire RAM"
                value={agent.metrics.ram}
                subValue={`${agent.metrics.ramUsedGb} Go / ${agent.metrics.ramTotalGb} Go`}
                warningThreshold={thresholds.ramWarning}
                criticalThreshold={thresholds.ramCritical}
              />
              <GaugeChart
                title="Espace Disque"
                value={agent.metrics.disk}
                subValue={`${agent.metrics.diskUsedGb} Go / ${agent.metrics.diskTotalGb} Go`}
                warningThreshold={thresholds.diskWarning}
                criticalThreshold={thresholds.diskCritical}
              />
            </div>
          </div>

          {/* System Info & Active Alerts Side Card */}
          <div className="bg-white p-6 rounded-2xl border border-slate-200/80 shadow-xs space-y-5">
            <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider flex items-center gap-2">
              <Bell className="w-4 h-4 text-rose-500" />
              Alertes actives ({activeAgentAlerts.length})
            </h3>

            <div className="space-y-3 max-h-72 overflow-y-auto">
              {activeAgentAlerts.length === 0 ? (
                <div className="p-4 text-center text-xs text-slate-500">
                  <CheckCircle2 className="w-8 h-8 text-emerald-500 mx-auto mb-1" />
                  Aucune alerte active sur cet agent.
                </div>
              ) : (
                activeAgentAlerts.map((alt) => (
                  <div key={alt.id} className="p-3 bg-slate-50 rounded-xl border border-slate-200/60 text-xs">
                    <div className="flex justify-between items-center mb-1">
                      <Badge type="severity" value={alt.severity} size="sm" />
                      <span className="text-[10px] text-slate-400">{alt.timestamp}</span>
                    </div>
                    <p className="font-medium text-slate-800 mt-1">{alt.message}</p>
                    {currentRole !== 'ReadOnly' && (
                      <button
                        onClick={() => acknowledgeAlert(alt.id)}
                        className="mt-2 text-[11px] font-bold text-blue-600 hover:underline"
                      >
                        Acquitter
                      </button>
                    )}
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: DETAILED METRICS */}
      {activeTab === 'metrics' && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-xs space-y-3">
              <div className="flex justify-between items-center">
                <span className="text-xs font-bold text-slate-500 uppercase">Processeur CPU</span>
                <Cpu className="w-4 h-4 text-[#D0B335]" />
              </div>
              <div className="text-2xl font-black text-slate-900">{agent.metrics.cpu}%</div>
              <ProgressBar value={agent.metrics.cpu} type="cpu" size="md" />
              <div className="text-[11px] text-slate-400">
                Seuils: Warning {thresholds.cpuWarning}% / Critique {thresholds.cpuCritical}%
              </div>
            </div>

            <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-xs space-y-3">
              <div className="flex justify-between items-center">
                <span className="text-xs font-bold text-slate-500 uppercase">Mémoire RAM</span>
                <Database className="w-4 h-4 text-blue-500" />
              </div>
              <div className="text-2xl font-black text-slate-900">
                {agent.metrics.ram}%{' '}
                <span className="text-xs font-normal text-slate-500">
                  ({agent.metrics.ramUsedGb} / {agent.metrics.ramTotalGb} Go)
                </span>
              </div>
              <ProgressBar value={agent.metrics.ram} type="ram" size="md" />
              <div className="text-[11px] text-slate-400">
                Seuils: Warning {thresholds.ramWarning}% / Critique {thresholds.ramCritical}%
              </div>
            </div>

            <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-xs space-y-3">
              <div className="flex justify-between items-center">
                <span className="text-xs font-bold text-slate-500 uppercase">Disque principal</span>
                <HardDrive className="w-4 h-4 text-purple-500" />
              </div>
              <div className="text-2xl font-black text-slate-900">
                {agent.metrics.disk}%{' '}
                <span className="text-xs font-normal text-slate-500">
                  ({agent.metrics.diskUsedGb} / {agent.metrics.diskTotalGb} Go)
                </span>
              </div>
              <ProgressBar value={agent.metrics.disk} type="disk" size="md" />
              <div className="text-[11px] text-slate-400">
                Seuils: Warning {thresholds.diskWarning}% / Critique {thresholds.diskCritical}%
              </div>
            </div>
          </div>

          {/* Partition breakdown if available */}
          {agent.metrics.partitions && (
            <div className="bg-white p-6 rounded-2xl border border-slate-200/80 shadow-xs space-y-4">
              <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider flex items-center gap-2">
                <HardDrive className="w-4 h-4 text-[#D0B335]" />
                Partitions & Points de montage
              </h3>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {agent.metrics.partitions.map((part, idx) => (
                  <div key={idx} className="p-4 bg-slate-50 rounded-xl border border-slate-200/60 space-y-2">
                    <div className="flex justify-between items-center">
                      <span className="font-bold text-xs text-slate-900">{part.name}</span>
                      <span className="font-mono text-[11px] text-slate-500 bg-white px-2 py-0.5 rounded border border-slate-200">
                        {part.mountPoint}
                      </span>
                    </div>
                    <div className="text-xs text-slate-600">
                      {part.usedGb} Go / {part.totalGb} Go utilisé
                    </div>
                    <ProgressBar value={part.usedPercent} type="disk" size="sm" />
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* TAB 3: ALERTS */}
      {activeTab === 'alerts' && (
        <div className="bg-white rounded-2xl border border-slate-200/80 shadow-xs overflow-hidden">
          <div className="p-5 border-b border-slate-100">
            <h3 className="text-base font-bold text-slate-900 tracking-tight">
              Historique des alertes pour cet agent ({agentAlerts.length})
            </h3>
          </div>

          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-slate-50 text-[11px] font-bold text-slate-500 uppercase tracking-wider border-b border-slate-100">
                <th className="py-3 px-4">Gravité</th>
                <th className="py-3 px-4">Statut</th>
                <th className="py-3 px-4">Date & Heure</th>
                <th className="py-3 px-4">Message</th>
                <th className="py-3 px-4 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-xs text-slate-700">
              {agentAlerts.length === 0 ? (
                <tr>
                  <td colSpan={5} className="py-8 text-center text-slate-400">
                    Aucune alerte enregistrée pour cet agent.
                  </td>
                </tr>
              ) : (
                agentAlerts.map((alt) => (
                  <tr key={alt.id} className="hover:bg-slate-50">
                    <td className="py-3 px-4">
                      <Badge type="severity" value={alt.severity} size="sm" />
                    </td>
                    <td className="py-3 px-4">
                      <Badge type="alertStatus" value={alt.status} size="sm" />
                    </td>
                    <td className="py-3 px-4 text-slate-400 font-mono">{alt.timestamp}</td>
                    <td className="py-3 px-4 font-medium text-slate-900 leading-relaxed">
                      {alt.message}
                      {alt.acknowledgedBy && (
                        <div className="mt-1 text-[11px] text-slate-500 font-normal">
                          Acquitté par <strong className="text-slate-700">{alt.acknowledgedBy}</strong> le {alt.acknowledgedAt}
                          {alt.comment && <span className="italic block text-slate-600">"{alt.comment}"</span>}
                        </div>
                      )}
                    </td>
                    <td className="py-3 px-4 text-right">
                      {alt.status === 'open' && currentRole !== 'ReadOnly' && (
                        <button
                          onClick={() => handleOpenAckModal(alt)}
                          className="px-2.5 py-1 bg-blue-50 text-blue-700 hover:bg-blue-100 font-bold rounded-lg text-xs transition-colors cursor-pointer"
                        >
                          Acquitter
                        </button>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* TAB 4: CONFIGURATION (THRESHOLDS) */}
      {activeTab === 'config' && (
        <div className="bg-white p-6 rounded-2xl border border-slate-200/80 shadow-xs space-y-6">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-4 border-b border-slate-100">
            <div>
              <h3 className="text-base font-bold text-slate-900 tracking-tight flex items-center gap-2">
                <Sliders className="w-4 h-4 text-[#D0B335]" />
                Seuils d'alerte personnalisés pour cet agent
              </h3>
              <p className="text-xs text-slate-500 mt-0.5">
                Surpasse la configuration globale pour cette machine spécifique
              </p>
            </div>

            {agent.customThresholds ? (
              <span className="text-xs font-bold text-amber-700 bg-amber-50 border border-amber-200 px-3 py-1 rounded-full">
                Seuils surchargés (Personnalisés)
              </span>
            ) : (
              <span className="text-xs font-medium text-slate-500 bg-slate-100 border border-slate-200 px-3 py-1 rounded-full">
                Utilise les seuils globaux
              </span>
            )}
          </div>

          {currentRole !== 'Admin' && (
            <div className="p-3 bg-amber-50 border border-amber-200 rounded-xl text-xs text-amber-900">
              Seul un <strong>Administrateur</strong> peut modifier les seuils d'alerte.
            </div>
          )}

          {configError && (
            <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl text-xs text-rose-700 font-semibold">
              {configError}
            </div>
          )}

          <form onSubmit={handleSaveConfig} className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {/* CPU Thresholds */}
              <div className="p-4 bg-slate-50 rounded-xl border border-slate-200/80 space-y-4">
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center gap-1.5">
                  <Cpu className="w-4 h-4 text-[#D0B335]" /> Seuils CPU (%)
                </h4>
                <div>
                  <label className="block text-xs text-slate-600 font-medium mb-1">Warning (%)</label>
                  <input
                    type="number"
                    min="1"
                    max="99"
                    disabled={currentRole !== 'Admin'}
                    value={thresholds.cpuWarning}
                    onChange={(e) => setThresholds({ ...thresholds, cpuWarning: Number(e.target.value) })}
                    className="w-full p-2 bg-white border border-slate-200 rounded-lg text-xs font-bold text-slate-900"
                  />
                </div>
                <div>
                  <label className="block text-xs text-slate-600 font-medium mb-1">Critique (%)</label>
                  <input
                    type="number"
                    min="1"
                    max="100"
                    disabled={currentRole !== 'Admin'}
                    value={thresholds.cpuCritical}
                    onChange={(e) => setThresholds({ ...thresholds, cpuCritical: Number(e.target.value) })}
                    className="w-full p-2 bg-white border border-slate-200 rounded-lg text-xs font-bold text-slate-900 text-rose-600"
                  />
                </div>
              </div>

              {/* RAM Thresholds */}
              <div className="p-4 bg-slate-50 rounded-xl border border-slate-200/80 space-y-4">
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center gap-1.5">
                  <Database className="w-4 h-4 text-blue-500" /> Seuils RAM (%)
                </h4>
                <div>
                  <label className="block text-xs text-slate-600 font-medium mb-1">Warning (%)</label>
                  <input
                    type="number"
                    min="1"
                    max="99"
                    disabled={currentRole !== 'Admin'}
                    value={thresholds.ramWarning}
                    onChange={(e) => setThresholds({ ...thresholds, ramWarning: Number(e.target.value) })}
                    className="w-full p-2 bg-white border border-slate-200 rounded-lg text-xs font-bold text-slate-900"
                  />
                </div>
                <div>
                  <label className="block text-xs text-slate-600 font-medium mb-1">Critique (%)</label>
                  <input
                    type="number"
                    min="1"
                    max="100"
                    disabled={currentRole !== 'Admin'}
                    value={thresholds.ramCritical}
                    onChange={(e) => setThresholds({ ...thresholds, ramCritical: Number(e.target.value) })}
                    className="w-full p-2 bg-white border border-slate-200 rounded-lg text-xs font-bold text-slate-900 text-rose-600"
                  />
                </div>
              </div>

              {/* Disk Thresholds */}
              <div className="p-4 bg-slate-50 rounded-xl border border-slate-200/80 space-y-4">
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center gap-1.5">
                  <HardDrive className="w-4 h-4 text-purple-500" /> Seuils Disque (%)
                </h4>
                <div>
                  <label className="block text-xs text-slate-600 font-medium mb-1">Warning (%)</label>
                  <input
                    type="number"
                    min="1"
                    max="99"
                    disabled={currentRole !== 'Admin'}
                    value={thresholds.diskWarning}
                    onChange={(e) => setThresholds({ ...thresholds, diskWarning: Number(e.target.value) })}
                    className="w-full p-2 bg-white border border-slate-200 rounded-lg text-xs font-bold text-slate-900"
                  />
                </div>
                <div>
                  <label className="block text-xs text-slate-600 font-medium mb-1">Critique (%)</label>
                  <input
                    type="number"
                    min="1"
                    max="100"
                    disabled={currentRole !== 'Admin'}
                    value={thresholds.diskCritical}
                    onChange={(e) => setThresholds({ ...thresholds, diskCritical: Number(e.target.value) })}
                    className="w-full p-2 bg-white border border-slate-200 rounded-lg text-xs font-bold text-slate-900 text-rose-600"
                  />
                </div>
              </div>
            </div>

            {currentRole === 'Admin' && (
              <div className="flex items-center justify-between pt-4 border-t border-slate-100">
                <button
                  type="button"
                  onClick={handleResetConfig}
                  className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold rounded-xl flex items-center gap-1.5"
                >
                  <RotateCcw className="w-3.5 h-3.5" />
                  Réinitialiser aux seuils globaux
                </button>

                <button
                  type="submit"
                  className="px-5 py-2.5 bg-[#D0B335] hover:bg-[#b89d2d] text-slate-950 text-xs font-bold rounded-xl shadow-xs flex items-center gap-1.5"
                >
                  <Save className="w-4 h-4" />
                  Enregistrer les seuils
                </button>
              </div>
            )}
          </form>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      <Modal
        isOpen={deleteModalOpen}
        onClose={() => setDeleteModalOpen(false)}
        title="Supprimer cet agent ?"
        footer={
          <>
            <button
              onClick={() => setDeleteModalOpen(false)}
              className="px-4 py-2 bg-slate-100 text-slate-700 text-xs font-semibold rounded-xl"
            >
              Annuler
            </button>
            <button
              onClick={() => {
                deleteAgent(agent.id);
                setDeleteModalOpen(false);
              }}
              className="px-4 py-2 bg-rose-600 text-white text-xs font-bold rounded-xl shadow-xs"
            >
              Confirmer la suppression
            </button>
          </>
        }
      >
        <p className="text-xs text-slate-700">
          Êtes-vous sûr de vouloir supprimer définitivement l'agent{' '}
          <strong>{agent.name}</strong> ? Toutes ses données télémetriques et son historique d'alertes seront effacés de la base de données.
        </p>
      </Modal>

      {/* Revoke Confirmation Modal */}
      <Modal
        isOpen={revokeModalOpen}
        onClose={() => setRevokeModalOpen(false)}
        title="Révoquer cet agent ?"
        footer={
          <>
            <button
              onClick={() => setRevokeModalOpen(false)}
              className="px-4 py-2 bg-slate-100 text-slate-700 text-xs font-semibold rounded-xl"
            >
              Annuler
            </button>
            <button
              onClick={() => {
                revokeAgent(agent.id);
                setRevokeModalOpen(false);
              }}
              className="px-4 py-2 bg-amber-600 text-white text-xs font-bold rounded-xl shadow-xs"
            >
              Confirmer la révocation
            </button>
          </>
        }
      >
        <p className="text-xs text-slate-700">
          En révoquant cet agent, il passera en statut "Révoqué" et se verra refuser l'accès au serveur avec un code HTTP 401.
        </p>
      </Modal>

      {/* Acknowledge Alert Modal */}
      <AcknowledgeModal
        isOpen={ackModalOpen}
        onClose={() => setAckModalOpen(false)}
        alert={targetAlertToAck}
        onConfirm={handleConfirmAck}
      />
    </div>
  );
};
