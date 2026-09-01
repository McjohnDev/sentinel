/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, Lock, RefreshCw } from 'lucide-react';
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { useApp } from '../context/AppContext';
import { agentsService } from '../services/api/agents.service';
import { AgentRuntimePanel } from '../components/agents/AgentRuntimePanel';
import { EditableAgentField } from '../components/agents/EditableAgentField';
import { AgentOwnerField } from '../components/agents/AgentOwnerField';
import { MonitoringPlanPanel } from '../components/agents/MonitoringPlanPanel';
import { Agent, Alert } from '../types';
import { AcknowledgeModal } from '../components/common/AcknowledgeModal';
import { Modal } from '../components/common/Modal';
import { AlertDrawer } from '../components/ui/AlertDrawer';
import { agentStatusMeta, gaugeColor, sevMeta } from '../components/ui/tones';

const TABS = [
  { id: 'vue', label: 'Vue' },
  { id: 'metriques', label: 'Métriques' },
  { id: 'alertes', label: 'Alertes' },
  // Un seul onglet de configuration. L'ancien ne portait que les seuils et
  // les partitions, que le plan de supervision couvre désormais entièrement :
  // deux onglets auraient présenté les mêmes réglages à deux endroits, sans
  // qu'on sache lequel fait foi.
  { id: 'config', label: 'Configuration' },
] as const;

type TabId = (typeof TABS)[number]['id'];

export const AgentDetailView: React.FC = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const {
        setSelectedAgentId,
        agents,
    alerts,
    currentRole,
    globalThresholds,
    revokeAgent,
    deleteAgent,
    acknowledgeAlert,
    resolveAlert,
  } = useApp();

  const [fetched, setFetched] = useState<Agent | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [checking, setChecking] = useState(false);

  const fromList = agents.find((a) => a.id === id);
  const agent = fetched && fetched.id === id ? fetched : fromList;

  const [tab, setTab] = useState<TabId>('vue');
  const [drawer, setDrawer] = useState<Alert | null>(null);
  const [hostPartitions, setHostPartitions] = useState<
    Array<{ name: string; mount: string; letter?: string | null; label?: string | null; percent?: number; total_gb?: number }>
  >([]);
  const [ackTarget, setAckTarget] = useState<Alert | null>(null);
  const [resolveTarget, setResolveTarget] = useState<Alert | null>(null);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [revokeOpen, setRevokeOpen] = useState(false);
  const [history, setHistory] = useState<Array<{ t: string; cpu?: number; ram?: number; disk?: number }>>([]);
  // Pas de valeur par défaut : pré-remplir avec un nom de service inventé
  // laissait croire que cet hôte l'héberge. L'opérateur saisit le sien.

  useEffect(() => {
    if (!id) return;
    let cancelled = false;
    setLoadError(false);
    agentsService
      .getAgent(id)
      .then((row) => {
        if (cancelled) return;
        setFetched(row);
        setSelectedAgentId(row.id);
      })
      .catch(() => {
        if (!cancelled) setLoadError(true);
      });
    return () => {
      cancelled = true;
    };
  }, [id, setSelectedAgentId]);

  const refreshPresence = async () => {
    if (!id) return;
    setChecking(true);
    try {
      const row = await agentsService.getAgent(id);
      setFetched(row);
    } catch {
      setLoadError(true);
    } finally {
      setChecking(false);
    }
  };

  /** Relit la fiche après une modification, pour afficher l'état réellement
   *  enregistré par le serveur plutôt que ce que le formulaire a envoyé. */
  const reloadAgent = useCallback(async () => {
    if (!id) return;
    try {
      setFetched(await agentsService.getAgent(id));
    } catch {
      /* la fiche reste sur les dernières valeurs connues */
    }
  }, [id]);

  useEffect(() => {
    let cancelled = false;
    if (!agent?.id || tab !== 'config') return;
    agentsService
      .getAgentPartitions(agent.id)
      .then((res) => {
        if (cancelled) return;
        // Seules les partitions découvertes sont utiles ici : elles
        // alimentent la liste de choix du plan. Les règles de seuil, elles,
        // sont chargées par le panneau depuis le plan lui-même — les lire
        // aussi ici entretiendrait deux copies de la même donnée.
        setHostPartitions(res.partitions || []);
      })
      .catch(() => {
        if (!cancelled)
          setHostPartitions(
            agent.metrics.partitions?.map((p) => ({
              name: p.name,
              mount: p.mountPoint,
              letter: p.letter,
              label: p.label,
              percent: p.usedPercent,
              total_gb: p.totalGb,
            })) || []
          );
      });
    return () => {
      cancelled = true;
    };
  }, [agent?.id, agent?.metrics.partitions, tab]);

  const hostAlerts = alerts.filter((a) => a.agentId === agent?.id);
  const openAlerts = hostAlerts.filter((a) => a.status === 'open');

  useEffect(() => {
    if (id) setSelectedAgentId(id);
  }, [id, setSelectedAgentId]);

  useEffect(() => {
    if (!agent?.id || tab !== 'metriques') return;
    let cancelled = false;
    const names = [
      { key: 'cpu' as const, name: 'cpu.total.utilization' },
      { key: 'ram' as const, name: 'memory.used.percent' },
      { key: 'disk' as const, name: 'disk.used.percent' },
    ];
    Promise.all(names.map(async ({ key, name }) => ({ key, res: await agentsService.getAgentMetricHistory(agent.id, { name, hours: 24, step: '5m' }) })))
      .then((rows) => {
        if (cancelled) return;
        const byTs: Record<string, { t: string; cpu?: number; ram?: number; disk?: number }> = {};
        for (const { key, res } of rows) {
          for (const series of res.result || []) {
            for (const p of series.points || []) {
              const t = new Date(p.ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
              byTs[p.ts] = { ...(byTs[p.ts] || { t }), [key]: p.value };
            }
          }
        }
        setHistory(Object.keys(byTs).sort().map((k) => byTs[k]));
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [agent?.id, tab]);

  if (!id || (loadError && !agent)) {
    return (
      <div className="cbc-card p-16 text-center">
        <p className="font-bold">Hôte introuvable</p>
        <p className="text-sm text-slate-500 mt-2">Cet agent n’est plus dans l’inventaire (supprimé ou jamais enrôlé).</p>
        <button type="button" className="cbc-btn-secondary mt-4" onClick={() => navigate('/agents')}>
          Retour au parc
        </button>
      </div>
    );
  }

  if (!agent) {
    return (
      <div className="cbc-card p-16 text-center">
        <p className="font-bold">Chargement de l’hôte…</p>
      </div>
    );
  }

  const st = agentStatusMeta(agent.status);
  const gauges = [
    { label: 'CPU', value: agent.metrics.cpu, detail: agent.status === 'offline' ? 'Dernière mesure' : 'cpu.total.utilization', w: globalThresholds.cpuWarning, c: globalThresholds.cpuCritical },
    { label: 'Mémoire', value: agent.metrics.ram, detail: `${agent.metrics.ramUsedGb?.toFixed?.(1) || '—'} / ${agent.metrics.ramTotalGb || '—'} Go`, w: globalThresholds.ramWarning, c: globalThresholds.ramCritical },
    { label: 'Disque', value: agent.metrics.disk, detail: `${agent.metrics.diskUsedGb?.toFixed?.(1) || '—'} / ${agent.metrics.diskTotalGb || '—'} Go`, w: globalThresholds.diskWarning, c: globalThresholds.diskCritical },
  ];

  const partitionOptions = hostPartitions.length
    ? hostPartitions
    : (agent?.metrics.partitions || []).map((p) => ({
        name: p.name,
        mount: p.mountPoint,
        letter: p.letter,
        label: p.label,
        percent: p.usedPercent,
        total_gb: p.totalGb,
      }));

  const formatPartitionOption = (p: { name: string; mount: string; letter?: string | null; label?: string | null; total_gb?: number }) => {
    const letter = p.letter ? `${p.letter}:` : '';
    const label = p.label ? ` ${p.label}` : '';
    const size = p.total_gb != null ? ` · ${p.total_gb} Go` : '';
    return `${letter || p.name}${label ? ` (${p.label})` : ''} — ${p.mount}${size}`.replace(/\s+/g, ' ').trim();
  };

  return (
    <div className="space-y-4">
      <button type="button" onClick={() => navigate('/agents')} className="flex items-center gap-1.5 text-[12.5px] font-semibold text-slate-500 hover:text-slate-900">
        <ArrowLeft className="w-4 h-4" />
        Parc
      </button>

      <div className="cbc-card px-[22px] pt-5">
        <div className="flex items-start justify-between gap-5">
          <div>
            <div className="flex items-center gap-2.5 flex-wrap">
              {/* Nom d'hôte affiché — attribué par l'exploitation, modifiable.
                  À distinguer du nom machine (`hostname`), constaté par
                  l'agent et verrouillé. */}
              <EditableAgentField
                agent={agent}
                field="name"
                value={agent.name}
                placeholder="Nom de l'hôte"
                className="text-xl font-extrabold tracking-tight"
                onSaved={reloadAgent}
              />
              {/* Identifiant attribué par la plateforme : court exprès, pour
                  pouvoir être dicté et recherché. */}
              <span
                className="tnum px-2 py-0.5 rounded-md bg-slate-100 border border-slate-200 text-[11.5px] font-bold text-slate-600"
                title="Identifiant attribué par la plateforme"
              >
                {agent.id}
              </span>
              <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-md border text-[11.5px] font-bold ${st.bg} ${st.bd}`} style={{ color: st.c }}>
                <span className="w-1.5 h-1.5 rounded-full" style={{ background: st.c }} />
                {st.label}
              </span>
              {agent.uninstalled && (
                <span className="px-2 py-0.5 rounded-md bg-slate-200 text-slate-700 text-[11px] font-semibold">
                  Agent désinstallé{agent.uninstalledAt ? ` le ${String(agent.uninstalledAt).split('T')[0]}` : ''}
                </span>
              )}
            </div>

            {/* Champs constatés par l'agent : affichés en lecture seule et
                signalés comme tels. Les corriger depuis l'interface
                produirait un inventaire qui contredit la machine réelle. */}
            <div className="tnum text-[12.5px] text-slate-500 mt-2.5 flex items-center gap-1.5 flex-wrap">
              <Lock className="w-3 h-3 text-slate-400" aria-hidden />
              <span title="Constaté par l'agent — non modifiable">
                {agent.hostname} · {agent.ipAddress} · {agent.os} {agent.osVersion} · agent {agent.agentVersion}
                {agent.cpuCores ? ` · ${agent.cpuCores} vCPU` : ''}
                {agent.ramTotalGb ? ` · ${agent.ramTotalGb} Go` : ''}
                {agent.vlanObserved ? ` · VLAN ${agent.vlanObserved} étiqueté` : ''}
              </span>
            </div>

            <div className="flex items-center gap-2 mt-2.5 flex-wrap">
              <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Site</span>
              <EditableAgentField
                agent={agent}
                field="location"
                value={agent.location}
                placeholder="Non renseigné"
                className="text-[12.5px] text-slate-700"
                onSaved={reloadAgent}
              />
              <span className="text-slate-300">·</span>
              <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">VLAN</span>
              <EditableAgentField
                agent={agent}
                field="vlan"
                value={agent.vlan || ''}
                placeholder="Non renseigné"
                className="text-[12.5px] text-slate-700"
                onSaved={reloadAgent}
              />
              {/* Provenance du VLAN retenu. Un VLAN déduit du plan d'adressage
                  et un VLAN saisi à la main n'engagent pas la même confiance :
                  l'exploitant doit pouvoir les distinguer d'un coup d'œil. */}
              {!agent.vlan && agent.vlanEffective && (
                <span
                  className="text-[12.5px] text-slate-700"
                  title={
                    agent.vlanSource === 'derived'
                      ? `Déduit du plan d'adressage — sous-réseau ${agent.vlanSubnet}`
                      : "Étiqueté par l'hôte lui-même"
                  }
                >
                  {agent.vlanEffective}
                  <span className="ml-1.5 px-1.5 py-0.5 rounded-md bg-slate-100 text-slate-500 border border-slate-200 text-[10px] font-bold">
                    {agent.vlanSource === 'derived' ? 'déduit' : 'hôte'}
                  </span>
                </span>
              )}
              {agent.vlanSource === 'derived' && agent.vlanLabel && (
                <span className="text-[12px] text-slate-500">{agent.vlanLabel}</span>
              )}
              {/* La divergence est le fait intéressant : un hôte rebranché sur
                  un autre port étiquette — ou se déduit — un VLAN que la fiche
                  ignore encore. On la montre plutôt que de choisir laquelle des
                  valeurs est « la bonne ». */}
              {agent.vlan &&
                agent.vlanDerived &&
                agent.vlanDerived !== agent.vlan.replace(/\s/g, '') && (
                  <span
                    className="px-1.5 py-0.5 rounded-md bg-amber-50 text-amber-700 border border-amber-200 text-[10.5px] font-bold"
                    title={`Le plan d'adressage place ${agent.ipAddress} dans le VLAN ${agent.vlanDerived} (${agent.vlanSubnet})`}
                  >
                    plan : {agent.vlanDerived}
                  </span>
                )}
              {agent.vlanObserved &&
                agent.vlanObserved !== (agent.vlan || agent.vlanDerived || '') && (
                  <span
                    className="px-1.5 py-0.5 rounded-md bg-amber-50 text-amber-700 border border-amber-200 text-[10.5px] font-bold"
                    title={`L'hôte étiquette le VLAN ${agent.vlanObserved}`}
                  >
                    hôte : {agent.vlanObserved}
                  </span>
                )}
              <span className="text-slate-300">·</span>
              <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Responsable</span>
              <AgentOwnerField
                agent={agent}
                canEdit={currentRole === 'Admin'}
                onSaved={reloadAgent}
              />
              <span className="text-slate-300">·</span>
              <span className="tnum text-xs text-slate-600">
                {agent.customThresholds ? 'Seuils surchargés' : 'Seuils hérités'}
              </span>
              <span className="text-slate-300">·</span>
              <span className="text-[12.5px] text-slate-500">Dernier contact {agent.lastHeartbeat}</span>
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <button
              type="button"
              onClick={() => void refreshPresence()}
              disabled={checking}
              className="cbc-btn-secondary"
              title="Relit le dernier ping reçu par la plateforme. L’hôte ne peut pas être joint depuis le centre."
            >
              <RefreshCw className={`w-3.5 h-3.5 ${checking ? 'animate-spin' : ''}`} />
              {checking ? 'Vérification…' : 'Actualiser le statut'}
            </button>
          </div>
        </div>
        <div className="flex gap-0.5 mt-5 -mx-[22px] px-3.5 border-t border-slate-200 bg-slate-50 rounded-b-xl overflow-x-auto">
          {TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => setTab(t.id)}
              className={`px-3.5 py-3 border-0 bg-transparent text-[12.5px] whitespace-nowrap border-b-2 ${
                tab === t.id ? 'border-[#D0B335] text-slate-900 font-bold' : 'border-transparent text-slate-500 font-semibold'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      {agent.status === 'offline' && (
        <div className="cbc-card px-5 py-4 border border-rose-200 bg-rose-50">
          <p className="text-sm font-bold text-rose-800 m-0">Hôte hors ligne — fiche toujours consultable</p>
          <p className="text-[13px] text-rose-800/80 mt-1.5 mb-0">
            La plateforme ne peut pas pinguer l’agent (connexion sortante uniquement). Les jauges ci-dessous
            sont la <strong>dernière mesure reçue</strong> ({agent.lastHeartbeat}). Dès que l’agent envoie un
            ping, le statut passe à En ligne. Utilisez « Actualiser le statut » pour relire le dernier contact.
          </p>
        </div>
      )}

      {tab === 'vue' && (
        <>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {gauges.map((g) => {
              const off = g.value == null;
              const color = gaugeColor(g.value, g.w, g.c);
              const deg = (off ? 0 : g.value!) * 3.6;
              const chip = off ? 'Hors ligne' : g.value! >= g.c ? 'Seuil critique' : g.value! >= g.w ? "Seuil d'attention" : 'Dans les seuils';
              return (
                <div key={g.label} className="cbc-card p-[18px] flex items-center gap-4">
                  <div
                    className="w-24 h-24 rounded-full shrink-0 grid place-items-center"
                    style={{ background: `conic-gradient(${color} ${deg}deg, #F1F5F9 0)` }}
                  >
                    <div className="w-[74px] h-[74px] rounded-full bg-white grid place-items-center">
                      <span className="tnum text-lg font-extrabold">{off ? '—' : `${Math.round(g.value!)}%`}</span>
                    </div>
                  </div>
                  <div>
                    <div className="text-[13px] font-bold">{g.label}</div>
                    <div className="text-[11.5px] leading-relaxed text-[#777] mt-1.5">{off ? 'Aucune donnée — agent hors ligne' : g.detail}</div>
                    <div className="inline-block mt-2 px-2 py-0.5 rounded-md text-[11px] font-semibold" style={{ color, background: `${color}18` }}>
                      {chip}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Panneau « Exécution sur l'hôte » (point 9).
                Il remplace deux listes — services et fichiers surveillés —
                qui étaient inventées en dur dans ce composant, avec une
                pastille verte fixe : elles affichaient « Running » pour des
                services que personne n'avait jamais interrogés. Le vrai
                paramétrage de supervision arrive au lot B. */}
            <AgentRuntimePanel agent={agent} />
            <div className="cbc-card overflow-hidden">
              <div className="px-[18px] py-3.5 border-b border-slate-200">
                <h2 className="text-sm font-bold m-0">Alertes ouvertes</h2>
              </div>
              {openAlerts.length === 0 ? (
                <div className="p-10 text-center">
                  <div className="text-[13px] font-bold">Aucune alerte ouverte</div>
                  <div className="text-xs text-[#777] mt-1.5">Cet hôte respecte les règles héritées.</div>
                </div>
              ) : (
                openAlerts.map((a) => {
                  const sev = sevMeta(a.severity);
                  return (
                    <button
                      key={a.id}
                      type="button"
                      onClick={() => setDrawer(a)}
                      className="w-full text-left px-[18px] py-3.5 border-b border-slate-50 hover:bg-slate-50"
                    >
                      <div className="flex items-center gap-2">
                        <span className="px-2 py-0.5 rounded-md text-[10.5px] font-bold text-white" style={{ background: sev.bg }}>
                          {sev.label}
                        </span>
                        <span className="text-[11.5px] text-slate-400">{a.type}</span>
                        <span className="tnum text-[11.5px] text-slate-400 ml-auto">{a.timestamp}</span>
                      </div>
                      <div className="text-[12.5px] text-slate-700 mt-2">{a.message}</div>
                    </button>
                  );
                })
              )}
            </div>
          </div>
        </>
      )}

      {tab === 'metriques' && (
        <div className="cbc-card p-5 h-80">
          {history.length === 0 ? (
            <p className="text-sm text-slate-500">Historique TSDB indisponible — affichage des jauges live uniquement.</p>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={history}>
                <XAxis dataKey="t" tick={{ fontSize: 11 }} />
                <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} />
                <Tooltip />
                <Line type="monotone" dataKey="cpu" stroke="#D0B335" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="ram" stroke="#64748B" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="disk" stroke="#059669" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>
      )}

      {tab === 'alertes' && (
        <div className="cbc-card overflow-hidden">
          {hostAlerts.length === 0 ? (
            <p className="p-10 text-center text-sm text-slate-500">Aucune alerte pour cet hôte.</p>
          ) : (
            hostAlerts.map((a) => (
              <button key={a.id} type="button" onClick={() => setDrawer(a)} className="w-full text-left px-4 py-3 border-b border-slate-50 hover:bg-slate-50">
                <span className="text-[13px] font-semibold">{a.message}</span>
                <span className="tnum text-xs text-slate-400 ml-2">{a.timestamp}</span>
              </button>
            ))
          )}
        </div>
      )}

      {tab === 'config' && (
        <MonitoringPlanPanel
          agentId={agent.id}
          discoveredMounts={partitionOptions.map((p) => p.mount).filter(Boolean)}
          canEdit={currentRole === 'Admin' || currentRole === 'Operator'}
        />
      )}

      <AlertDrawer
        alert={drawer}
        onClose={() => setDrawer(null)}
        canAck={currentRole !== 'ReadOnly'}
        onAck={(a) => {
          setDrawer(null);
          setAckTarget(a);
        }}
        onResolve={(a) => {
          setDrawer(null);
          setResolveTarget(a);
        }}
        onOpenHost={() => setDrawer(null)}
      />
      <AcknowledgeModal
        isOpen={!!resolveTarget}
        onClose={() => setResolveTarget(null)}
        alert={resolveTarget}
        mode="resolve"
        onConfirm={(id, c, n) => { resolveAlert(id, c, n); setResolveTarget(null); }}
      />
      <AcknowledgeModal isOpen={!!ackTarget} onClose={() => setAckTarget(null)} alert={ackTarget} onConfirm={(id, c, n) => { acknowledgeAlert(id, c, n); setAckTarget(null); }} />
      <Modal isOpen={revokeOpen} onClose={() => setRevokeOpen(false)} title="Révoquer" footer={<><button type="button" className="cbc-btn-secondary" onClick={() => setRevokeOpen(false)}>Annuler</button><button type="button" className="px-3 py-2 rounded-lg bg-amber-600 text-white text-xs font-semibold" onClick={() => { revokeAgent(agent.id); setRevokeOpen(false); }}>Révoquer</button></>}>
        <p className="text-sm text-slate-600">Révoquer {agent.name} ?</p>
      </Modal>
      <Modal isOpen={deleteOpen} onClose={() => setDeleteOpen(false)} title="Supprimer" footer={<><button type="button" className="cbc-btn-secondary" onClick={() => setDeleteOpen(false)}>Annuler</button><button type="button" className="px-3 py-2 rounded-lg bg-rose-600 text-white text-xs font-semibold" onClick={() => { deleteAgent(agent.id); setDeleteOpen(false); navigate('/agents'); }}>Supprimer</button></>}>
        <p className="text-sm text-slate-600">Supprimer définitivement {agent.name} ?</p>
      </Modal>
    </div>
  );
};
