/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useMemo, useState } from 'react';
import { MoreHorizontal, Plus, Search } from 'lucide-react';
import { useSearchParams } from 'react-router-dom';
import { useApp } from '../context/AppContext';
import { AgentStatus, OperatingSystem } from '../types';
import { PageHeader } from '../components/layout/PageHeader';
import { FilterChip } from '../components/ui/FilterChip';
import { EnrolmentSheet } from '../components/ui/EnrolmentSheet';
import { agentStatusMeta, metricTone, osMeta } from '../components/ui/tones';
import { Modal } from '../components/common/Modal';

export const AgentsListView: React.FC = () => {
  const { agents, currentRole, navigateToAgentDetail, revokeAgent, exportCSV, generateEnrollmentToken } = useApp();
  const [params, setParams] = useSearchParams();
  const [q, setQ] = useState('');
  const [osF, setOsF] = useState<OperatingSystem[]>([]);
  const [alertsOnly, setAlertsOnly] = useState(false);
  const [view, setView] = useState<string | null>(null);
  const statusF = (params.get('status') as AgentStatus | 'all' | null) || 'all';
  const [enrolOpen, setEnrolOpen] = useState(false);
  const [token, setToken] = useState<string | null>(null);
  const [expiresAt, setExpiresAt] = useState('');
  const [revokeId, setRevokeId] = useState<string | null>(null);

  const groups = useMemo(() => Array.from(new Set(agents.map((a) => a.location).filter(Boolean))), [agents]);

  const toggleOs = (os: OperatingSystem) =>
    setOsF((prev) => (prev.includes(os) ? prev.filter((x) => x !== os) : [...prev, os]));

  const filtered = useMemo(() => {
    return agents.filter((ag) => {
      const hay = `${ag.id} ${ag.name} ${ag.hostname} ${ag.ipAddress}`.toLowerCase();
      if (q.trim() && !hay.includes(q.trim().toLowerCase())) return false;
      if (osF.length && !osF.includes(ag.os)) return false;
      if (alertsOnly && ag.activeAlertsCount === 0) return false;
      if (view && ag.location !== view) return false;
      if (statusF === 'online' && ag.status !== 'online') return false;
      if (statusF === 'offline' && ag.status !== 'offline') return false;
      return true;
    });
  }, [agents, q, osF, alertsOnly, view, statusF]);

  // Le jeton est désormais émis par le serveur : l'appel est asynchrone et
  // peut échouer. Ouvrir la fenêtre avant d'avoir le jeton afficherait un
  // code vide, ou celui de la génération précédente.
  const openEnrol = async () => {
    const created = await generateEnrollmentToken();
    if (!created) return;
    setToken(created.token);
    setExpiresAt(created.expiresAt);
    setEnrolOpen(true);
  };

  const target = agents.find((a) => a.id === revokeId);

  return (
    <div className="space-y-5">
      <PageHeader
        title="Parc"
        subtitle={`Hôtes supervisés — ${agents.filter((a) => a.status === 'online').length} sur ${agents.length} enrôlés.`}
        primaryAction={
          currentRole === 'Admin' ? (
            <button type="button" onClick={() => void openEnrol()} className="cbc-btn-primary">
              <Plus className="w-4 h-4" />
              Enrôler un agent
            </button>
          ) : undefined
        }
        secondaryActions={
          currentRole !== 'ReadOnly' ? (
            <button type="button" onClick={() => exportCSV('agents')} className="cbc-btn-secondary">
              Exporter CSV
            </button>
          ) : undefined
        }
      />

      <div className="cbc-card overflow-hidden">
        <div className="px-4 py-3 border-b border-[var(--color-ln)] flex items-center gap-3 flex-wrap">
          <div className="relative flex-1 min-w-[220px]">
            <Search className="absolute left-2.5 top-2.5 w-4 h-4 text-[var(--color-tx3)]" />
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="ID, nom, hostname, IP…"
              className="w-full pl-8 pr-3 py-2 border border-[var(--color-ln)] rounded-lg text-[13px] bg-[var(--color-ln2)] outline-none focus:border-[#D0B335] focus:bg-[var(--color-panel)]"
            />
          </div>
          {(['linux', 'windows', 'macos'] as OperatingSystem[]).map((os) => (
            <FilterChip key={os} label={osMeta(os).label} active={osF.includes(os)} onClick={() => toggleOs(os)} />
          ))}
          <FilterChip label="A des alertes" active={alertsOnly} onClick={() => setAlertsOnly(!alertsOnly)} />
          <FilterChip
            label="En ligne"
            active={statusF === 'online'}
            onClick={() => setParams(statusF === 'online' ? {} : { status: 'online' })}
          />
          <FilterChip
            label="Hors ligne"
            active={statusF === 'offline'}
            onClick={() => setParams(statusF === 'offline' ? {} : { status: 'offline' })}
          />
          <div className="w-px h-5 bg-slate-200" />
          <span className="text-[10.5px] font-bold uppercase tracking-wider text-[var(--color-tx3)]">Vues</span>
          {groups.slice(0, 4).map((g) => (
            <FilterChip key={g} label={g} active={view === g} onClick={() => setView(view === g ? null : g)} pill />
          ))}
        </div>

        {filtered.length === 0 ? (
          <div className="py-16 text-center">
            <div className="text-[15px] font-bold">Aucun hôte</div>
            <div className="text-[13px] text-[#777] mt-2">Aucun hôte ne correspond à ces filtres.</div>
            <button
              type="button"
              className="cbc-btn-secondary mt-4"
              onClick={() => {
                setQ('');
                setOsF([]);
                setAlertsOnly(false);
                setView(null);
                setParams({});
              }}
            >
              Réinitialiser
            </button>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full border-collapse">
              <thead>
                <tr className="bg-[var(--color-ln2)] border-b border-[var(--color-ln)]">
                  {['Statut', 'ID', 'Nom', 'Hostname', 'OS', 'Site', 'CPU', 'RAM', 'Disque', 'Heartbeat', 'Alertes', 'Config', ''].map(
                    (c, i) => (
                      <th
                        key={c || i}
                        className={`px-3 py-2.5 text-[10.5px] font-bold uppercase tracking-wider text-[var(--color-tx3)] whitespace-nowrap ${
                          i >= 6 && i <= 8 ? 'text-right' : 'text-left'
                        }`}
                      >
                        {c}
                      </th>
                    )
                  )}
                </tr>
              </thead>
              <tbody>
                {filtered.map((h) => {
                  const st = agentStatusMeta(h.status);
                  const os = osMeta(h.os);
                  const cpu = metricTone(h.metrics.cpu);
                  const ram = metricTone(h.metrics.ram);
                  const dsk = metricTone(h.metrics.disk);
                  return (
                    <tr
                      key={h.id}
                      onClick={() => navigateToAgentDetail(h.id)}
                      className="border-b border-[var(--color-ln2)] hover:bg-[var(--color-ln2)] cursor-pointer"
                    >
                      <td className="p-3">
                        <span className="inline-flex items-center gap-1.5">
                          <span className="w-2 h-2 rounded-full shrink-0" style={{ background: st.c }} />
                          <span className="text-xs font-semibold" style={{ color: st.c }}>
                            {st.label}
                          </span>
                        </span>
                      </td>
                      {/* Identifiant attribué par la plateforme : court exprès,
                          pour être dicté au téléphone et recherché tel quel. */}
                      <td className="p-3 whitespace-nowrap">
                        <span className="tnum px-1.5 py-0.5 rounded bg-[var(--color-ln2)] text-[var(--color-tx2)] text-[11.5px] font-bold">
                          {h.id}
                        </span>
                      </td>
                      <td className="p-3 text-[13px] font-bold whitespace-nowrap">{h.name}</td>
                      {/* Nom machine constaté par l'agent — distinct du nom
                          d'hôte affiché ci-contre, et non modifiable. */}
                      <td className="p-3 tnum text-xs text-[var(--color-tx2)] whitespace-nowrap">{h.hostname}</td>
                      <td className="p-3 whitespace-nowrap">
                        <span className={`inline-block px-2 py-0.5 rounded-md border text-[11px] font-semibold ${os.bg} ${os.fg} ${os.bd}`}>
                          {os.label}
                        </span>
                      </td>
                      <td className="p-3">
                        <span className="px-2 py-0.5 rounded-md bg-[var(--color-ln2)] text-[var(--color-tx2)] text-[11px] font-semibold">
                          {h.location || '—'}
                        </span>
                      </td>
                      <td className="p-3 text-right">
                        <span className={`tnum inline-block px-1.5 py-0.5 rounded-md text-xs font-bold ${cpu.bg} ${cpu.fg}`}>
                          {`${Math.round(h.metrics.cpu)}%`}
                        </span>
                      </td>
                      <td className="p-3 text-right">
                        <span className={`tnum inline-block px-1.5 py-0.5 rounded-md text-xs font-bold ${ram.bg} ${ram.fg}`}>
                          {`${Math.round(h.metrics.ram)}%`}
                        </span>
                      </td>
                      <td className="p-3 text-right">
                        <span className={`tnum inline-block px-1.5 py-0.5 rounded-md text-xs font-bold ${dsk.bg} ${dsk.fg}`}>
                          {`${Math.round(h.metrics.disk)}%`}
                        </span>
                      </td>
                      <td className="p-3 tnum text-xs text-[var(--color-tx2)] whitespace-nowrap">{h.lastHeartbeat}</td>
                      <td className="p-3 text-center">
                        {h.activeAlertsCount > 0 ? (
                          <span className="tnum inline-block min-w-[22px] px-1.5 py-0.5 rounded-full bg-rose-50 text-rose-600 text-[11.5px] font-bold">
                            {h.activeAlertsCount}
                          </span>
                        ) : (
                          <span className="text-xs text-[var(--color-tx3)]">—</span>
                        )}
                      </td>
                      <td className="p-3 whitespace-nowrap">
                        {h.customThresholds ? (
                          <span className="px-2 py-0.5 rounded-md bg-[#D0B335]/10 border border-[#D0B335]/30 text-[#A68523] text-[11px] font-semibold">
                            Surcharge
                          </span>
                        ) : (
                          <span className="tnum text-xs text-[var(--color-tx2)]">héritée</span>
                        )}
                      </td>
                      <td className="p-3 pr-4 text-right">
                        {currentRole === 'Admin' && (
                          <button
                            type="button"
                            title="Révoquer"
                            onClick={(e) => {
                              e.stopPropagation();
                              setRevokeId(h.id);
                            }}
                            className="w-7 h-7 border border-[var(--color-ln)] bg-[var(--color-panel)] rounded-lg text-[var(--color-tx2)] grid place-items-center hover:bg-[var(--color-ln2)]"
                          >
                            <MoreHorizontal className="w-3.5 h-3.5" />
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <EnrolmentSheet open={enrolOpen} token={token} expiresAt={expiresAt} onClose={() => setEnrolOpen(false)} />

      <Modal
        isOpen={!!revokeId}
        onClose={() => setRevokeId(null)}
        title="Révoquer l'agent"
        footer={
          <>
            <button type="button" className="cbc-btn-secondary" onClick={() => setRevokeId(null)}>
              Annuler
            </button>
            <button
              type="button"
              className="px-3 py-2 rounded-lg bg-rose-600 text-white text-[12.5px] font-semibold"
              onClick={() => {
                if (revokeId) revokeAgent(revokeId);
                setRevokeId(null);
              }}
            >
              Révoquer
            </button>
          </>
        }
      >
        <p className="text-sm text-[var(--color-tx2)]">
          Révoquer <strong>{target?.name}</strong> ? L'agent cessera d'être authentifié (401) jusqu'à un nouvel enrôlement.
        </p>
      </Modal>
    </div>
  );
};
