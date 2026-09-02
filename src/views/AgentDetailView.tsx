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
import { alertsService } from '../services/api/alerts.service';
import { AgentRuntimePanel } from '../components/agents/AgentRuntimePanel';
import { EditableAgentField } from '../components/agents/EditableAgentField';
import { AgentOwnerField } from '../components/agents/AgentOwnerField';
import { HostInventoryPanel } from '../components/agents/HostInventoryPanel';
import { MonitoringPlanPanel } from '../components/agents/MonitoringPlanPanel';
import { AlertRecipientsPanel } from '../components/agents/AlertRecipientsPanel';
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
  { id: 'inventaire', label: 'Inventaire' },
] as const;

type TabId = (typeof TABS)[number]['id'];

/**
 * Périodes du graphe de métriques.
 *
 * Le pas suit la fenêtre : une heure au pas de la minute montre les
 * variations réelles, sept jours au pas de l'heure restent lisibles. Une
 * fenêtre de 24 h au pas de 5 minutes — l'ancien réglage figé — rendait un
 * hôte fraîchement enrôlé parfaitement plat, faute de données sur la majeure
 * partie de la période.
 */
const RANGES = [
  { id: '1h', label: '1 h', hours: 1, step: '1m' },
  { id: '6h', label: '6 h', hours: 6, step: '2m' },
  { id: '24h', label: '24 h', hours: 24, step: '5m' },
  { id: '7d', label: '7 j', hours: 168, step: '1h' },
] as const;

type RangeId = (typeof RANGES)[number]['id'];

export const AgentDetailView: React.FC = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const {
        setSelectedAgentId,
        agents,
    alerts,
    currentRole,
    globalThresholds,
    users,
    currentUser,
    addToast,
    refreshFleet,
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
  // Une heure par défaut : c'est la fenêtre utile pour diagnostiquer, et la
  // seule qui montre quelque chose sur un hôte enrôlé depuis peu.
  const [range, setRange] = useState<RangeId>('1h');
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
    const window = RANGES.find((r) => r.id === range) || RANGES[0];
    Promise.all(
      names.map(async ({ key, name }) => ({
        key,
        res: await agentsService.getAgentMetricHistory(agent.id, {
          name,
          hours: window.hours,
          step: window.step,
        }),
      }))
    )
      .then((rows) => {
        if (cancelled) return;
        const byTs: Record<string, { t: string; cpu?: number; ram?: number; disk?: number }> = {};
        for (const { key, res } of rows) {
          for (const series of res.result || []) {
            for (const p of series.points || []) {
              const moment = new Date(p.ts);
              const t =
                window.hours > 24
                  ? moment.toLocaleDateString([], { day: '2-digit', month: '2-digit' })
                  : moment.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
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
  }, [agent?.id, tab, range]);

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
        <div className="cbc-card p-5">
          <div className="flex items-center justify-between gap-3 flex-wrap mb-4">
            {/* Une légende, qui manquait : sans elle, une courbe plate ne se
                distingue pas d'une mesure figée. Le disque est légitimement
                plat — son occupation ne bouge pas d'une minute à l'autre. */}
            <div className="flex items-center gap-4 flex-wrap">
              {[
                { label: 'CPU', color: '#D0B335' },
                { label: 'Mémoire', color: '#64748B' },
                { label: 'Disque', color: '#059669' },
              ].map((serie) => (
                <span key={serie.label} className="inline-flex items-center gap-1.5 text-[12px] text-slate-600">
                  <span className="w-3 h-0.5 rounded" style={{ background: serie.color }} />
                  {serie.label}
                </span>
              ))}
            </div>
            <div className="inline-flex rounded-lg border border-slate-200 overflow-hidden">
              {RANGES.map((r) => (
                <button
                  key={r.id}
                  type="button"
                  onClick={() => setRange(r.id)}
                  className={`px-2.5 py-1 text-[12px] font-semibold ${
                    range === r.id ? 'bg-slate-900 text-white' : 'text-slate-600 hover:bg-slate-50'
                  }`}
                >
                  {r.label}
                </button>
              ))}
            </div>
          </div>

          <div className="h-72">
            {history.length === 0 ? (
              <p className="text-sm text-slate-500">
                Aucune mesure sur cette période. Un hôte enrôlé depuis peu n’a pas encore
                d’historique : essayer une fenêtre plus courte.
              </p>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={history}>
                  <XAxis dataKey="t" tick={{ fontSize: 11 }} minTickGap={24} />
                  <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} unit="%" />
                  <Tooltip formatter={(v: number) => `${Math.round(v * 10) / 10} %`} />
                  <Line type="monotone" dataKey="cpu" name="CPU" stroke="#D0B335" strokeWidth={2} dot={false} />
                  <Line type="monotone" dataKey="ram" name="Mémoire" stroke="#64748B" strokeWidth={2} dot={false} />
                  <Line type="monotone" dataKey="disk" name="Disque" stroke="#059669" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            )}
          </div>
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

      {tab === 'inventaire' && <HostInventoryPanel agentId={agent.id} />}

      {tab === 'config' && (
        <div className="space-y-5">
          <MonitoringPlanPanel
            agentId={agent.id}
            discoveredMounts={partitionOptions.map((p) => p.mount).filter(Boolean)}
            canEdit={currentRole === 'Admin' || currentRole === 'Operator'}
          />
          {/* A cote du plan de surveillance : decider ce qu'on surveille et
              savoir qui sera prevenu sont deux moities du meme geste. Une
              verification dont l'alerte ne parvient a personne ne surveille
              rien. */}
          <AlertRecipientsPanel
            agentId={agent.id}
            cc={agent.alertCc ?? []}
            resolved={agent.alertRecipients ?? { to: [], cc: [] }}
            canEdit={currentRole === 'Admin' || currentRole === 'Operator'}
            onSaved={reloadAgent}
          />
        </div>
      )}

      <AlertDrawer
        // L'alerte vivante, relue de la liste : un instantane pris a
        // l'ouverture continuerait d'afficher « non attribuee » apres une
        // attribution reussie, et le geste passerait pour sans effet.
        alert={drawer ? alerts.find((a) => a.id === drawer.id) ?? drawer : null}
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
        // La prise en charge manquait ici : le tiroir ouvert depuis la fiche
        // d'hôte n'affichait qu'un état en lecture seule, sans moyen d'agir.
        currentUserId={currentUser?.id ?? null}
        assignables={users
          .filter((u) => u.status === 'active')
          .map((u) => ({ id: u.id, name: u.name }))}
        onAssign={async (a, userId) => {
          try {
            await alertsService.assign(a.id, userId);
            await refreshFleet();
            addToast({
              type: 'success',
              title: userId ? 'Alerte attribuée' : 'Attribution retirée',
              message: a.message,
            });
          } catch {
            addToast({
              type: 'error',
              title: 'Attribution impossible',
              message: 'Vérifier que le compte est actif et l’alerte encore ouverte.',
            });
          }
        }}
        fleetReminderHours={globalThresholds.alertReminderHours ?? 3}
        onSetReminder={async (a, hours) => {
          try {
            await alertsService.setReminder(a.id, hours);
            await refreshFleet();
            addToast({
              type: 'success',
              title: 'Relance modifiée',
              message:
                hours === null
                  ? 'Cette alerte suit de nouveau le réglage du parc.'
                  : hours === 0
                    ? 'Cette alerte ne sera plus relancée.'
                    : `Rappel toutes les ${hours} h tant que l’alerte reste ouverte.`,
            });
          } catch {
            addToast({
              type: 'error',
              title: 'Réglage impossible',
              message: 'Vérifier que l’alerte est encore ouverte.',
            });
          }
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
