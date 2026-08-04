/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState, useMemo } from 'react';
import { useApp } from '../context/AppContext';
import { Badge } from '../components/common/Badge';
import { Modal } from '../components/common/Modal';
import { AcknowledgeModal } from '../components/common/AcknowledgeModal';
import { EmptyState } from '../components/common/EmptyState';
import { AlertSeverity, AlertType, AlertStatus, Alert } from '../types';
import {
  Bell,
  Search,
  CheckCheck,
  Download,
  SlidersHorizontal,
  X,
  ExternalLink,
  Clock,
  UserCheck,
  AlertTriangle,
  CheckCircle2,
  ShieldAlert,
  User as UserIcon,
  MessageSquare,
} from 'lucide-react';

export const AlertsListView: React.FC = () => {
  const {
    alerts,
    currentRole,
    currentUser,
    acknowledgeAlert,
    acknowledgeAllAlerts,
    exportCSV,
    navigateToAgentDetail,
  } = useApp();

  // Search & Filters state
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedSeverities, setSelectedSeverities] = useState<AlertSeverity[]>([]);
  const [selectedTypes, setSelectedTypes] = useState<AlertType[]>([]);
  const [selectedStatuses, setSelectedStatuses] = useState<AlertStatus[]>([]);
  const [filtersOpen, setFiltersOpen] = useState(false);

  // Single Acknowledge Modal State
  const [ackModalOpen, setAckModalOpen] = useState(false);
  const [targetAlertToAck, setTargetAlertToAck] = useState<Alert | null>(null);

  // Bulk Acknowledge Modal State
  const [bulkAckModalOpen, setBulkAckModalOpen] = useState(false);
  const [bulkOperatorName, setBulkOperatorName] = useState('');
  const [bulkComment, setBulkComment] = useState('');

  const handleOpenBulkAckModal = () => {
    setBulkOperatorName(currentUser?.name || 'Administrateur CBC');
    setBulkComment('Acquittement massif d\'urgence et prise en charge des alertes en cours.');
    setBulkAckModalOpen(true);
  };

  const handleConfirmBulkAck = (e: React.FormEvent) => {
    e.preventDefault();
    if (!bulkOperatorName.trim()) return;
    acknowledgeAllAlerts(bulkOperatorName, bulkComment);
    setBulkAckModalOpen(false);
  };

  // Filtering
  const filteredAlerts = useMemo(() => {
    return alerts.filter((alt) => {
      // Search term
      const matchesSearch =
        alt.agentName.toLowerCase().includes(searchTerm.toLowerCase()) ||
        alt.message.toLowerCase().includes(searchTerm.toLowerCase());

      if (!matchesSearch) return false;

      // Severity
      if (selectedSeverities.length > 0 && !selectedSeverities.includes(alt.severity)) {
        return false;
      }

      // Type
      if (selectedTypes.length > 0 && !selectedTypes.includes(alt.type)) {
        return false;
      }

      // Status
      if (selectedStatuses.length > 0 && !selectedStatuses.includes(alt.status)) {
        return false;
      }

      return true;
    });
  }, [alerts, searchTerm, selectedSeverities, selectedTypes, selectedStatuses]);

  const activeFiltersCount =
    (selectedSeverities.length > 0 ? 1 : 0) +
    (selectedTypes.length > 0 ? 1 : 0) +
    (selectedStatuses.length > 0 ? 1 : 0);

  const resetFilters = () => {
    setSearchTerm('');
    setSelectedSeverities([]);
    setSelectedTypes([]);
    setSelectedStatuses([]);
  };

  const handleOpenAckModal = (alt: Alert) => {
    setTargetAlertToAck(alt);
    setAckModalOpen(true);
  };

  const handleConfirmSingleAck = (alertId: string, comment: string, operatorName: string) => {
    acknowledgeAlert(alertId, comment, operatorName);
    setAckModalOpen(false);
    setTargetAlertToAck(null);
  };

  const openAlertsCount = alerts.filter((a) => a.status === 'open').length;
  const criticalOpenAlertsCount = alerts.filter((a) => a.status === 'open' && a.severity === 'critical').length;
  const acknowledgedAlertsCount = alerts.filter((a) => a.status === 'acknowledged').length;
  const totalAlertsCount = alerts.length;

  return (
    <div className="space-y-6">
      {/* View Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white p-5 rounded-2xl border border-slate-200/80 shadow-xs">
        <div>
          <h2 className="text-xl font-black text-slate-900 tracking-tight flex items-center gap-2">
            <Bell className="w-5 h-5 text-rose-500" />
            Centre de Gestion des Alertes System
          </h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Surveillance continue et traçabilité des anomalies — CBC Infrastructure
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {currentRole === 'Admin' && openAlertsCount > 0 && (
            <button
              onClick={handleOpenBulkAckModal}
              className="inline-flex items-center gap-2 px-3.5 py-2 bg-[#D0B335] hover:bg-[#b89d2d] text-slate-950 text-xs font-bold rounded-xl shadow-xs transition-colors cursor-pointer"
            >
              <CheckCheck className="w-4 h-4" />
              Tout acquitter ({openAlertsCount})
            </button>
          )}

          {currentRole !== 'ReadOnly' && (
            <button
              onClick={() => exportCSV('alerts')}
              className="inline-flex items-center gap-2 px-3.5 py-2 bg-slate-900 hover:bg-slate-800 text-white text-xs font-semibold rounded-xl transition-colors shadow-xs"
            >
              <Download className="w-4 h-4 text-slate-300" />
              Exporter CSV
            </button>
          )}
        </div>
      </div>

      {/* Contextual KPI Stats Bar */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <div className="bg-white p-3.5 rounded-2xl border border-slate-200/80 shadow-xs flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-slate-100 text-slate-700 flex items-center justify-center font-bold">
            <Bell className="w-4 h-4" />
          </div>
          <div>
            <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wide">Total Historique</p>
            <p className="text-lg font-black text-slate-900">{totalAlertsCount}</p>
          </div>
        </div>

        <div className="bg-white p-3.5 rounded-2xl border border-slate-200/80 shadow-xs flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-amber-50 text-amber-600 flex items-center justify-center font-bold">
            <AlertTriangle className="w-4 h-4" />
          </div>
          <div>
            <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wide">Alertes En Cours</p>
            <p className="text-lg font-black text-amber-600">{openAlertsCount}</p>
          </div>
        </div>

        <div className="bg-white p-3.5 rounded-2xl border border-slate-200/80 shadow-xs flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-rose-50 text-rose-600 flex items-center justify-center font-bold">
            <ShieldAlert className="w-4 h-4" />
          </div>
          <div>
            <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wide">Critiques Absolues</p>
            <p className="text-lg font-black text-rose-600">{criticalOpenAlertsCount}</p>
          </div>
        </div>

        <div className="bg-white p-3.5 rounded-2xl border border-slate-200/80 shadow-xs flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center font-bold">
            <CheckCircle2 className="w-4 h-4" />
          </div>
          <div>
            <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wide">Acquittées (Traité)</p>
            <p className="text-lg font-black text-emerald-600">{acknowledgedAlertsCount}</p>
          </div>
        </div>
      </div>

      {/* Filter Bar */}
      <div className="bg-white p-4 rounded-2xl border border-slate-200/80 shadow-xs space-y-3">
        <div className="flex flex-col sm:flex-row items-center justify-between gap-3">
          <div className="relative w-full sm:w-96">
            <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-3" />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Rechercher par agent ou description..."
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

        {/* Collapsible Filters */}
        {filtersOpen && (
          <div className="pt-3 border-t border-slate-100 grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs animate-in fade-in slide-in-from-top-2">
            {/* Severity */}
            <div>
              <label className="block font-bold text-slate-700 mb-1.5">Niveau de gravité</label>
              <div className="flex flex-wrap gap-2">
                {(['critical', 'warning', 'info'] as AlertSeverity[]).map((sev) => {
                  const isSelected = selectedSeverities.includes(sev);
                  return (
                    <button
                      key={sev}
                      onClick={() =>
                        setSelectedSeverities((prev) =>
                          isSelected ? prev.filter((s) => s !== sev) : [...prev, sev]
                        )
                      }
                      className={`px-2.5 py-1 rounded-lg border font-semibold text-xs capitalize transition-colors ${
                        isSelected
                          ? 'bg-slate-900 text-white border-slate-900'
                          : 'bg-slate-50 text-slate-600 border-slate-200 hover:bg-slate-100'
                      }`}
                    >
                      {sev === 'critical' ? 'Critique' : sev === 'warning' ? 'Warning' : 'Info'}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Type */}
            <div>
              <label className="block font-bold text-slate-700 mb-1.5">Type d'anomalie</label>
              <div className="flex flex-wrap gap-2">
                {(['cpu', 'ram', 'disk', 'offline'] as AlertType[]).map((tp) => {
                  const isSelected = selectedTypes.includes(tp);
                  return (
                    <button
                      key={tp}
                      onClick={() =>
                        setSelectedTypes((prev) =>
                          isSelected ? prev.filter((t) => t !== tp) : [...prev, tp]
                        )
                      }
                      className={`px-2.5 py-1 rounded-lg border font-semibold text-xs uppercase transition-colors ${
                        isSelected
                          ? 'bg-slate-900 text-white border-slate-900'
                          : 'bg-slate-50 text-slate-600 border-slate-200 hover:bg-slate-100'
                      }`}
                    >
                      {tp}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Status */}
            <div>
              <label className="block font-bold text-slate-700 mb-1.5">Statut de traitement</label>
              <div className="flex flex-wrap gap-2">
                {(['open', 'acknowledged', 'resolved'] as AlertStatus[]).map((st) => {
                  const isSelected = selectedStatuses.includes(st);
                  return (
                    <button
                      key={st}
                      onClick={() =>
                        setSelectedStatuses((prev) =>
                          isSelected ? prev.filter((s) => s !== st) : [...prev, st]
                        )
                      }
                      className={`px-2.5 py-1 rounded-lg border font-semibold text-xs transition-colors ${
                        isSelected
                          ? 'bg-slate-900 text-white border-slate-900'
                          : 'bg-slate-50 text-slate-600 border-slate-200 hover:bg-slate-100'
                      }`}
                    >
                      {st === 'open' ? 'Ouverte' : st === 'acknowledged' ? 'Acquittée' : 'Résolue'}
                    </button>
                  );
                })}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Main Alerts Table */}
      <div className="bg-white rounded-2xl border border-slate-200/80 shadow-xs overflow-hidden">
        {filteredAlerts.length === 0 ? (
          <EmptyState
            icon={<Bell className="w-8 h-8 text-slate-400" />}
            title="Aucune alerte à afficher"
            description="Aucune anomalie ne correspond à vos critères de recherche actuels."
            actionLabel="Réinitialiser les filtres"
            onAction={resetFilters}
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-slate-50/70 text-[11px] font-bold text-slate-500 uppercase tracking-wider border-b border-slate-100">
                  <th className="py-3 px-4">Gravité</th>
                  <th className="py-3 px-4">Agent concerné</th>
                  <th className="py-3 px-4">Type</th>
                  <th className="py-3 px-4">Date & Heure</th>
                  <th className="py-3 px-4">Statut</th>
                  <th className="py-3 px-4 max-w-md">Message / Description</th>
                  <th className="py-3 px-4 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-xs text-slate-700">
                {filteredAlerts.map((alt) => (
                  <tr
                    key={alt.id}
                    className={`hover:bg-slate-50/80 transition-colors ${
                      alt.severity === 'critical' && alt.status === 'open' ? 'bg-rose-50/30' : ''
                    }`}
                  >
                    <td className="py-3.5 px-4">
                      <Badge type="severity" value={alt.severity} size="sm" />
                    </td>
                    <td className="py-3.5 px-4 font-bold text-slate-900">
                      <button
                        onClick={() => navigateToAgentDetail(alt.agentId)}
                        className="hover:text-blue-600 flex items-center gap-1 transition-colors"
                      >
                        {alt.agentName}
                        <ExternalLink className="w-3 h-3 text-slate-400" />
                      </button>
                    </td>
                    <td className="py-3.5 px-4">
                      <span className="font-mono text-[11px] font-bold uppercase px-2 py-0.5 rounded bg-slate-100 text-slate-700">
                        {alt.type}
                      </span>
                    </td>
                    <td className="py-3.5 px-4 text-slate-400 font-mono text-[11px]">
                      <span className="flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        {alt.timestamp}
                      </span>
                    </td>
                    <td className="py-3.5 px-4">
                      <Badge type="alertStatus" value={alt.status} size="sm" />
                    </td>
                    <td className="py-3.5 px-4 font-medium text-slate-900 leading-relaxed">
                      {alt.message}
                      {alt.acknowledgedBy && (
                        <div className="mt-1 text-[11px] text-slate-500 flex items-center gap-1">
                          <UserCheck className="w-3 h-3 text-emerald-600" />
                          Acquitté par {alt.acknowledgedBy} le {alt.acknowledgedAt}
                          {alt.comment && <span className="italic">"{alt.comment}"</span>}
                        </div>
                      )}
                    </td>
                    <td className="py-3.5 px-4 text-right">
                      {alt.status === 'open' && currentRole !== 'ReadOnly' && (
                        <button
                          onClick={() => handleOpenAckModal(alt)}
                          className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold rounded-xl shadow-xs transition-colors"
                        >
                          Acquitter
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Single Acknowledge Modal */}
      <AcknowledgeModal
        isOpen={ackModalOpen}
        onClose={() => setAckModalOpen(false)}
        alert={targetAlertToAck}
        onConfirm={handleConfirmSingleAck}
      />

      {/* Bulk Acknowledge Modal */}
      <Modal
        isOpen={bulkAckModalOpen}
        onClose={() => setBulkAckModalOpen(false)}
        title="Prise en charge & Acquittement Global (En Lot)"
        footer={
          <>
            <button
              type="button"
              onClick={() => setBulkAckModalOpen(false)}
              className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold rounded-xl transition-colors cursor-pointer"
            >
              Annuler
            </button>
            <button
              type="button"
              onClick={handleConfirmBulkAck}
              disabled={!bulkOperatorName.trim()}
              className="px-4 py-2 bg-[#D0B335] hover:bg-[#b89d2d] text-slate-950 text-xs font-bold rounded-xl shadow-xs transition-colors flex items-center gap-2 cursor-pointer disabled:opacity-50"
            >
              <CheckCheck className="w-4 h-4" />
              Acquitter les {openAlertsCount} alertes
            </button>
          </>
        }
      >
        <form onSubmit={handleConfirmBulkAck} className="space-y-4">
          <div className="p-3.5 bg-amber-50 border border-amber-200 rounded-xl space-y-1 text-amber-900">
            <div className="flex items-center gap-2 font-bold text-xs">
              <AlertTriangle className="w-4 h-4 text-amber-600" />
              <span>Conformité & Audit Bancaire</span>
            </div>
            <p className="text-xs text-amber-800 leading-relaxed">
              Vous allez acquitter simultanément <strong>{openAlertsCount} alerte(s)</strong> en cours. Conformément aux exigences COBAC & ISO 27001, veuillez saisir l'identifiant de l'intervenant responsable et le motif d'action.
            </p>
          </div>

          <div>
            <label className="block text-xs font-bold text-slate-800 mb-1 flex items-center gap-1.5">
              <UserIcon className="w-3.5 h-3.5 text-blue-600" />
              Nom de l'opérateur / Intervenant responsable <span className="text-rose-500">*</span>
            </label>
            <input
              type="text"
              required
              value={bulkOperatorName}
              onChange={(e) => setBulkOperatorName(e.target.value)}
              placeholder="Ex: Jean-Paul Nkouam (Superviseur SOC / Banque)"
              className="w-full px-3 py-2 bg-white border border-slate-200 rounded-xl text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-[#D0B335] font-medium shadow-2xs"
            />
          </div>

          <div>
            <label className="block text-xs font-bold text-slate-800 mb-1 flex items-center gap-1.5">
              <MessageSquare className="w-3.5 h-3.5 text-slate-500" />
              Motif de l'acquittement global
            </label>
            <textarea
              rows={2}
              value={bulkComment}
              onChange={(e) => setBulkComment(e.target.value)}
              placeholder="Ex: Prise en charge globale suite à l'intervention technique sur le réseau principal..."
              className="w-full px-3 py-2 bg-white border border-slate-200 rounded-xl text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-[#D0B335] font-medium shadow-2xs resize-none"
            />
          </div>
        </form>
      </Modal>
    </div>
  );
};
