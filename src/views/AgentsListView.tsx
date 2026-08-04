/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState, useMemo } from 'react';
import { useApp } from '../context/AppContext';
import { Badge } from '../components/common/Badge';
import { ProgressBar } from '../components/common/ProgressBar';
import { EmptyState } from '../components/common/EmptyState';
import { Modal } from '../components/common/Modal';
import { OperatingSystem, AgentStatus, Agent } from '../types';
import {
  Search,
  Filter,
  Download,
  Server,
  ChevronUp,
  ChevronDown,
  X,
  SlidersHorizontal,
  ShieldOff,
  Eye,
  Settings as SettingsIcon,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Activity,
} from 'lucide-react';

export const AgentsListView: React.FC = () => {
  const {
    agents,
    currentRole,
    navigateToAgentDetail,
    revokeAgent,
    exportCSV,
  } = useApp();

  // Search & Filter state
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedOS, setSelectedOS] = useState<OperatingSystem[]>([]);
  const [selectedStatus, setSelectedStatus] = useState<AgentStatus[]>([]);
  const [alertFilter, setAlertFilter] = useState<'all' | 'hasAlerts' | 'criticalOnly'>('all');
  const [filtersOpen, setFiltersOpen] = useState(false);

  // Sorting & Pagination
  const [sortField, setSortField] = useState<keyof Agent | 'cpu' | 'ram' | 'disk'>('name');
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc');
  const [pageSize, setPageSize] = useState<number>(20);
  const [currentPage, setCurrentPage] = useState<number>(1);

  // Revoke Modal State
  const [revokeModalOpen, setRevokeModalOpen] = useState(false);
  const [targetAgentToRevoke, setTargetAgentToRevoke] = useState<Agent | null>(null);

  // Contextual KPI Stats
  const totalAgentsCount = agents.length;
  const onlineAgentsCount = useMemo(() => agents.filter((a) => a.status === 'online').length, [agents]);
  const offlineAgentsCount = useMemo(() => agents.filter((a) => a.status === 'offline').length, [agents]);
  const warningAgentsCount = useMemo(() => agents.filter((a) => a.status === 'warning' || a.openAlertsCount > 0).length, [agents]);

  // Filter logic
  const filteredAgents = useMemo(() => {
    return agents.filter((ag) => {
      // Search filter
      const matchesSearch =
        ag.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        ag.hostname.toLowerCase().includes(searchTerm.toLowerCase()) ||
        ag.ipAddress.includes(searchTerm);

      if (!matchesSearch) return false;

      // OS filter
      if (selectedOS.length > 0 && !selectedOS.includes(ag.os)) {
        return false;
      }

      // Status filter
      if (selectedStatus.length > 0 && !selectedStatus.includes(ag.status)) {
        return false;
      }

      // Alerts filter
      if (alertFilter === 'hasAlerts' && ag.activeAlertsCount === 0) return false;
      if (alertFilter === 'criticalOnly' && ag.activeAlertsCount === 0) return false;

      return true;
    });
  }, [agents, searchTerm, selectedOS, selectedStatus, alertFilter]);

  // Sort logic
  const sortedAgents = useMemo(() => {
    return [...filteredAgents].sort((a, b) => {
      let valA: any = a[sortField as keyof Agent];
      let valB: any = b[sortField as keyof Agent];

      if (sortField === 'cpu') {
        valA = a.metrics.cpu;
        valB = b.metrics.cpu;
      } else if (sortField === 'ram') {
        valA = a.metrics.ram;
        valB = b.metrics.ram;
      } else if (sortField === 'disk') {
        valA = a.metrics.disk;
        valB = b.metrics.disk;
      }

      if (typeof valA === 'string') {
        return sortDirection === 'asc' ? valA.localeCompare(valB) : valB.localeCompare(valA);
      }
      return sortDirection === 'asc' ? valA - valB : valB - valA;
    });
  }, [filteredAgents, sortField, sortDirection]);

  // Pagination logic
  const totalPages = Math.ceil(sortedAgents.length / pageSize) || 1;
  const paginatedAgents = useMemo(() => {
    const start = (currentPage - 1) * pageSize;
    return sortedAgents.slice(start, start + pageSize);
  }, [sortedAgents, currentPage, pageSize]);

  const handleSort = (field: keyof Agent | 'cpu' | 'ram' | 'disk') => {
    if (sortField === field) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDirection('asc');
    }
  };

  const activeFiltersCount =
    (selectedOS.length > 0 ? 1 : 0) +
    (selectedStatus.length > 0 ? 1 : 0) +
    (alertFilter !== 'all' ? 1 : 0);

  const resetFilters = () => {
    setSearchTerm('');
    setSelectedOS([]);
    setSelectedStatus([]);
    setAlertFilter('all');
  };

  const handleConfirmRevoke = () => {
    if (targetAgentToRevoke) {
      revokeAgent(targetAgentToRevoke.id);
      setRevokeModalOpen(false);
      setTargetAgentToRevoke(null);
    }
  };

  return (
    <div className="space-y-6">
      {/* View Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white p-5 rounded-2xl border border-slate-200/80 shadow-xs">
        <div>
          <h2 className="text-xl font-black text-slate-900 tracking-tight flex items-center gap-2">
            <Server className="w-5 h-5 text-[#D0B335]" />
            Gestion & Surveillance des Agents
          </h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Liste consolidée des machines enrôlées — CBC Cameroon Infrastructure
          </p>
        </div>

        {currentRole !== 'ReadOnly' && (
          <button
            onClick={() => exportCSV('agents')}
            className="inline-flex items-center gap-2 px-3.5 py-2 bg-slate-900 hover:bg-slate-800 text-white text-xs font-semibold rounded-xl transition-colors shadow-xs"
          >
            <Download className="w-4 h-4 text-slate-300" />
            Exporter CSV ({filteredAgents.length})
          </button>
        )}
      </div>

      {/* Contextual KPI Stats Bar */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <div className="bg-white p-3.5 rounded-2xl border border-slate-200/80 shadow-xs flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-slate-100 text-slate-700 flex items-center justify-center font-bold">
            <Server className="w-4 h-4" />
          </div>
          <div>
            <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wide">Total Enrôlés</p>
            <p className="text-lg font-black text-slate-900">{totalAgentsCount}</p>
          </div>
        </div>

        <div className="bg-white p-3.5 rounded-2xl border border-slate-200/80 shadow-xs flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center font-bold">
            <CheckCircle2 className="w-4 h-4" />
          </div>
          <div>
            <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wide">En Ligne</p>
            <p className="text-lg font-black text-emerald-600">{onlineAgentsCount}</p>
          </div>
        </div>

        <div className="bg-white p-3.5 rounded-xl border border-slate-200/80 shadow-xs flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-rose-50 text-rose-600 flex items-center justify-center font-bold">
            <XCircle className="w-4 h-4" />
          </div>
          <div>
            <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wide">Hors Ligne</p>
            <p className="text-lg font-black text-rose-600">{offlineAgentsCount}</p>
          </div>
        </div>

        <div className="bg-white p-3.5 rounded-2xl border border-slate-200/80 shadow-xs flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-amber-50 text-amber-600 flex items-center justify-center font-bold">
            <AlertTriangle className="w-4 h-4" />
          </div>
          <div>
            <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wide">En Alerte</p>
            <p className="text-lg font-black text-amber-600">{warningAgentsCount}</p>
          </div>
        </div>
      </div>

      {/* Search Bar & Filter Controls */}
      <div className="bg-white p-4 rounded-2xl border border-slate-200/80 shadow-xs space-y-3">
        <div className="flex flex-col sm:flex-row items-center justify-between gap-3">
          {/* Search Input */}
          <div className="relative w-full sm:w-96">
            <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-3" />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Rechercher par nom, hostname ou IP..."
              className="w-full pl-10 pr-9 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-[#D0B335] focus:bg-white transition-all font-medium"
            />
            {searchTerm && (
              <button
                onClick={() => setSearchTerm('')}
                className="absolute right-3 top-2.5 text-slate-400 hover:text-slate-600"
              >
                <X className="w-4 h-4" />
              </button>
            )}
          </div>

          {/* Filter Toggle & Active Filter Tags */}
          <div className="flex items-center gap-2 w-full sm:w-auto justify-end">
            <button
              onClick={() => setFiltersOpen(!filtersOpen)}
              className={`inline-flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-semibold border transition-all ${
                filtersOpen || activeFiltersCount > 0
                  ? 'bg-amber-50 text-slate-900 border-[#D0B335]/60 font-bold'
                  : 'bg-slate-50 text-slate-700 border-slate-200 hover:bg-slate-100'
              }`}
            >
              <SlidersHorizontal className="w-4 h-4 text-[#8D771B]" />
              Filtres avancés
              {activeFiltersCount > 0 && (
                <span className="w-5 h-5 rounded-full bg-[#D0B335] text-slate-950 font-bold text-[10px] flex items-center justify-center">
                  {activeFiltersCount}
                </span>
              )}
            </button>

            {activeFiltersCount > 0 && (
              <button
                onClick={resetFilters}
                className="text-xs text-rose-600 hover:text-rose-800 font-semibold px-2 py-1"
              >
                Réinitialiser
              </button>
            )}
          </div>
        </div>

        {/* Collapsible Advanced Filters Drawer */}
        {filtersOpen && (
          <div className="pt-3 border-t border-slate-100 grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs animate-in fade-in slide-in-from-top-2">
            {/* Filter OS */}
            <div>
              <label className="block font-bold text-slate-700 mb-1.5">Système d'exploitation</label>
              <div className="flex flex-wrap gap-2">
                {(['windows', 'linux', 'macos'] as OperatingSystem[]).map((os) => {
                  const isSelected = selectedOS.includes(os);
                  return (
                    <button
                      key={os}
                      onClick={() =>
                        setSelectedOS((prev) =>
                          isSelected ? prev.filter((o) => o !== os) : [...prev, os]
                        )
                      }
                      className={`px-2.5 py-1 rounded-lg border font-semibold text-xs capitalize transition-colors ${
                        isSelected
                          ? 'bg-slate-900 text-white border-slate-900'
                          : 'bg-slate-50 text-slate-600 border-slate-200 hover:bg-slate-100'
                      }`}
                    >
                      {os}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Filter Status */}
            <div>
              <label className="block font-bold text-slate-700 mb-1.5">Statut de connexion</label>
              <div className="flex flex-wrap gap-2">
                {(['online', 'offline', 'obsolete', 'revoked'] as AgentStatus[]).map((st) => {
                  const isSelected = selectedStatus.includes(st);
                  return (
                    <button
                      key={st}
                      onClick={() =>
                        setSelectedStatus((prev) =>
                          isSelected ? prev.filter((s) => s !== st) : [...prev, st]
                        )
                      }
                      className={`px-2.5 py-1 rounded-lg border font-semibold text-xs capitalize transition-colors ${
                        isSelected
                          ? 'bg-slate-900 text-white border-slate-900'
                          : 'bg-slate-50 text-slate-600 border-slate-200 hover:bg-slate-100'
                      }`}
                    >
                      {st === 'online'
                        ? 'En ligne'
                        : st === 'offline'
                        ? 'Hors ligne'
                        : st === 'obsolete'
                        ? 'Obsolète'
                        : 'Révoqué'}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Filter Alerts */}
            <div>
              <label className="block font-bold text-slate-700 mb-1.5">Alertes actives</label>
              <select
                value={alertFilter}
                onChange={(e) => setAlertFilter(e.target.value as any)}
                className="w-full p-2 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-900 font-medium focus:outline-none focus:ring-2 focus:ring-[#D0B335]"
              >
                <option value="all">Tous les agents</option>
                <option value="hasAlerts">Avec alertes actives uniquement</option>
                <option value="criticalOnly">Alertes critiques uniquement</option>
              </select>
            </div>
          </div>
        )}
      </div>

      {/* Main Agents Data Table */}
      <div className="bg-white rounded-2xl border border-slate-200/80 shadow-xs overflow-hidden">
        {paginatedAgents.length === 0 ? (
          <EmptyState
            icon={<Server className="w-8 h-8 text-slate-400" />}
            title="Aucun agent trouvé"
            description="Aucune machine ne correspond aux critères de recherche et de filtrage sélectionnés."
            actionLabel="Réinitialiser les filtres"
            onAction={resetFilters}
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-slate-50/70 text-[11px] font-bold text-slate-500 uppercase tracking-wider border-b border-slate-100 select-none">
                  <th
                    onClick={() => handleSort('name')}
                    className="py-3 px-4 cursor-pointer hover:bg-slate-100/60"
                  >
                    <div className="flex items-center gap-1">
                      Agent / Hostname
                      {sortField === 'name' && (sortDirection === 'asc' ? <ChevronUp className="w-3.5 h-3.5 text-[#D0B335]" /> : <ChevronDown className="w-3.5 h-3.5 text-[#D0B335]" />)}
                    </div>
                  </th>
                  <th className="py-3 px-4">OS</th>
                  <th
                    onClick={() => handleSort('status')}
                    className="py-3 px-4 cursor-pointer hover:bg-slate-100/60"
                  >
                    <div className="flex items-center gap-1">
                      Statut
                      {sortField === 'status' && (sortDirection === 'asc' ? <ChevronUp className="w-3.5 h-3.5 text-[#D0B335]" /> : <ChevronDown className="w-3.5 h-3.5 text-[#D0B335]" />)}
                    </div>
                  </th>
                  <th
                    onClick={() => handleSort('cpu')}
                    className="py-3 px-4 cursor-pointer hover:bg-slate-100/60 min-w-[110px]"
                  >
                    <div className="flex items-center gap-1">
                      CPU
                      {sortField === 'cpu' && (sortDirection === 'asc' ? <ChevronUp className="w-3.5 h-3.5 text-[#D0B335]" /> : <ChevronDown className="w-3.5 h-3.5 text-[#D0B335]" />)}
                    </div>
                  </th>
                  <th
                    onClick={() => handleSort('ram')}
                    className="py-3 px-4 cursor-pointer hover:bg-slate-100/60 min-w-[110px]"
                  >
                    <div className="flex items-center gap-1">
                      RAM
                      {sortField === 'ram' && (sortDirection === 'asc' ? <ChevronUp className="w-3.5 h-3.5 text-[#D0B335]" /> : <ChevronDown className="w-3.5 h-3.5 text-[#D0B335]" />)}
                    </div>
                  </th>
                  <th
                    onClick={() => handleSort('disk')}
                    className="py-3 px-4 cursor-pointer hover:bg-slate-100/60 min-w-[110px]"
                  >
                    <div className="flex items-center gap-1">
                      Disque
                      {sortField === 'disk' && (sortDirection === 'asc' ? <ChevronUp className="w-3.5 h-3.5 text-[#D0B335]" /> : <ChevronDown className="w-3.5 h-3.5 text-[#D0B335]" />)}
                    </div>
                  </th>
                  <th className="py-3 px-4">Uptime</th>
                  <th className="py-3 px-4 text-center">Alertes</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-xs text-slate-700">
                {paginatedAgents.map((ag) => (
                  <tr
                    key={ag.id}
                    className="hover:bg-slate-50/80 transition-colors group"
                  >
                    <td
                      onClick={() => navigateToAgentDetail(ag.id)}
                      className="py-3.5 px-4 cursor-pointer"
                    >
                      <div className="font-bold text-slate-900 group-hover:text-blue-600 transition-colors">
                        {ag.name}
                      </div>
                      <div className="text-[11px] text-slate-400 font-mono">
                        {ag.hostname} • <span className="text-slate-500">{ag.ipAddress}</span>
                      </div>
                    </td>
                    <td className="py-3.5 px-4">
                      <div className="flex flex-col gap-0.5">
                        <Badge type="os" value={ag.os} size="sm" />
                        <span className="text-[10px] text-slate-500 font-mono truncate max-w-[140px]" title={ag.osVersion}>
                          {ag.osVersion}
                        </span>
                      </div>
                    </td>
                    <td className="py-3.5 px-4">
                      <Badge type="status" value={ag.status} size="sm" />
                    </td>
                    <td className="py-3.5 px-4">
                      <ProgressBar value={ag.metrics.cpu} type="cpu" size="sm" />
                    </td>
                    <td className="py-3.5 px-4">
                      <ProgressBar value={ag.metrics.ram} type="ram" size="sm" />
                    </td>
                    <td className="py-3.5 px-4">
                      <ProgressBar value={ag.metrics.disk} type="disk" size="sm" />
                    </td>
                    <td className="py-3.5 px-4 text-slate-500 font-mono text-[11px]">
                      {ag.metrics.uptime}
                    </td>
                    <td className="py-3.5 px-4 text-center">
                      {ag.activeAlertsCount > 0 ? (
                        <span className="inline-flex items-center justify-center w-5 h-5 rounded-full bg-rose-600 text-white font-bold text-[10px]">
                          {ag.activeAlertsCount}
                        </span>
                      ) : (
                        <span className="text-slate-300">-</span>
                      )}
                    </td>
                    <td className="py-3.5 px-4 text-right">
                      <div className="flex items-center justify-end gap-1">
                        <button
                          onClick={() => navigateToAgentDetail(ag.id)}
                          className="p-1.5 text-slate-500 hover:text-blue-600 hover:bg-slate-100 rounded-lg transition-colors"
                          title="Détails de l'agent"
                        >
                          <Eye className="w-4 h-4" />
                        </button>
                        {currentRole === 'Admin' && (
                          <>
                            <button
                              onClick={() => navigateToAgentDetail(ag.id)}
                              className="p-1.5 text-slate-500 hover:text-amber-600 hover:bg-slate-100 rounded-lg transition-colors"
                              title="Configurer les seuils"
                            >
                              <SettingsIcon className="w-4 h-4" />
                            </button>
                            {ag.status !== 'revoked' && (
                              <button
                                onClick={() => {
                                  setTargetAgentToRevoke(ag);
                                  setRevokeModalOpen(true);
                                }}
                                className="p-1.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition-colors"
                                title="Révoquer cet agent"
                              >
                                <ShieldOff className="w-4 h-4" />
                              </button>
                            )}
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination Footer */}
        <div className="p-4 bg-slate-50 border-t border-slate-100 flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-slate-500">
          <div className="flex items-center gap-2">
            <span>Afficher par page :</span>
            <select
              value={pageSize}
              onChange={(e) => {
                setPageSize(Number(e.target.value));
                setCurrentPage(1);
              }}
              className="px-2 py-1 bg-white border border-slate-200 rounded-lg text-xs font-semibold text-slate-900 focus:outline-none"
            >
              <option value={10}>10</option>
              <option value={20}>20</option>
              <option value={50}>50</option>
            </select>
            <span>
              Affichage {sortedAgents.length > 0 ? (currentPage - 1) * pageSize + 1 : 0} à{' '}
              {Math.min(currentPage * pageSize, sortedAgents.length)} sur {sortedAgents.length} agents
            </span>
          </div>

          <div className="flex items-center gap-1.5">
            <button
              onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
              disabled={currentPage === 1}
              className="px-3 py-1.5 bg-white border border-slate-200 rounded-lg font-semibold text-slate-700 disabled:opacity-40 hover:bg-slate-100"
            >
              Précédent
            </button>
            <span className="px-2 font-bold text-slate-900">
              {currentPage} / {totalPages}
            </span>
            <button
              onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
              disabled={currentPage === totalPages}
              className="px-3 py-1.5 bg-white border border-slate-200 rounded-lg font-semibold text-slate-700 disabled:opacity-40 hover:bg-slate-100"
            >
              Suivant
            </button>
          </div>
        </div>
      </div>

      {/* Revoke Agent Confirmation Modal */}
      <Modal
        isOpen={revokeModalOpen}
        onClose={() => setRevokeModalOpen(false)}
        title="Confirmation de révocation"
        footer={
          <>
            <button
              onClick={() => setRevokeModalOpen(false)}
              className="px-4 py-2 bg-slate-100 text-slate-700 text-xs font-semibold rounded-xl hover:bg-slate-200"
            >
              Annuler
            </button>
            <button
              onClick={handleConfirmRevoke}
              className="px-4 py-2 bg-rose-600 text-white text-xs font-bold rounded-xl hover:bg-rose-700 shadow-sm"
            >
              Révoquer définitivement
            </button>
          </>
        }
      >
        <div className="space-y-3">
          <p className="text-xs text-slate-700 leading-relaxed">
            Êtes-vous absolument sûr de vouloir révoquer l'agent{' '}
            <strong className="text-slate-900">{targetAgentToRevoke?.name}</strong> (
            <code className="bg-slate-100 px-1 py-0.5 rounded text-rose-600">
              {targetAgentToRevoke?.hostname}
            </code>
            ) ?
          </p>
          <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl text-xs text-rose-800">
            <strong>Conséquence :</strong> L'agent passera en statut "Révoqué" et recevra un code HTTP 401 lors de sa prochaine synchronisation de heartbeat. Il ne pourra plus transmettre de métriques.
          </div>
        </div>
      </Modal>
    </div>
  );
};
