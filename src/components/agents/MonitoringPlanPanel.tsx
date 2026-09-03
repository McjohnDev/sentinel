/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useCallback, useEffect, useState } from 'react';
import { AlertTriangle, Check, FileWarning, Plus, RotateCcw, Server, Trash2 } from 'lucide-react';
import {
  CheckSeverity,
  FileCondition,
  MonitoredFileRule,
  MonitoredServiceRule,
  MonitoringPlan,
  HostInventory,
  PartitionRule,
  ServiceState,
  agentsService,
} from '../../services/api/agents.service';

/**
 * Onglet « Configuration » d'un hôte : son plan de supervision (points 6-7).
 *
 * Unique endroit où se règle ce qu'on surveille sur une machine. Il remplace
 * trois écrans distincts :
 *
 * - l'ancien onglet « Configuration », qui ne portait que les seuils et les
 *   partitions — désormais couverts ici, et qui aurait présenté les mêmes
 *   réglages en double sans qu'on sache lequel fait foi ;
 * - les panneaux « Services surveillés » et « Fichiers surveillés » de la
 *   vue d'ensemble, dont la liste était inventée en dur dans le composant
 *   avec une pastille verte fixe ;
 * - les onglets correspondants de Paramètres, qui annonçaient « mise à jour
 *   avec succès » sans rien enregistrer, ni côté interface ni côté serveur.
 */

const SEVERITIES: CheckSeverity[] = ['minor', 'major', 'critical'];

const SEVERITY_LABELS: Record<CheckSeverity, string> = {
  minor: 'Mineure',
  major: 'Majeure',
  critical: 'Critique',
};

interface Props {
  agentId: string;
  /** Partitions réellement remontées par l'hôte, pour ne proposer que l'existant. */
  discoveredMounts: string[];
  canEdit: boolean;
}

export const MonitoringPlanPanel: React.FC<Props> = ({ agentId, discoveredMounts, canEdit }) => {
  const [plan, setPlan] = useState<MonitoringPlan | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  // Services réellement offerts par l'hôte, pour que l'exploitant choisisse
  // au lieu de saisir. Une faute de frappe produirait une surveillance qui
  // ne surveille rien : le service resterait « inconnu » plutôt qu'« arrêté ».
  const [offeredServices, setOfferedServices] = useState<HostInventory['services']>([]);
  const [heartbeat, setHeartbeat] = useState<number | null>(null);
  const [savingHeartbeat, setSavingHeartbeat] = useState(false);
  const [heartbeatError, setHeartbeatError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setPlan(await agentsService.getMonitoringPlan(agentId));
    } catch {
      setError("Plan de supervision introuvable pour cet hôte.");
    } finally {
      setLoading(false);
    }
  }, [agentId]);

  useEffect(() => {
    let cancelled = false;
    agentsService
      .getAgent(agentId)
      .then((row) => {
        if (!cancelled) setHeartbeat(row.heartbeatIntervalSeconds ?? null);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [agentId]);

  const saveHeartbeat = async () => {
    setSavingHeartbeat(true);
    setHeartbeatError(null);
    try {
      await agentsService.patchAgent(agentId, { heartbeat_interval_seconds: heartbeat });
    } catch (err) {
      // Le serveur explique la borne franchie : la relayer telle quelle,
      // « valeur invalide » n'apprendrait rien.
      const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
      setHeartbeatError(typeof detail === 'string' ? detail : 'Cadence refusée.');
    } finally {
      setSavingHeartbeat(false);
    }
  };

  useEffect(() => {
    let cancelled = false;
    agentsService
      .getInventory(agentId)
      .then((inv) => {
        if (!cancelled) setOfferedServices(inv.services || []);
      })
      .catch(() => {
        // Inventaire pas encore remonté : on retombe sur la saisie libre
        // plutôt que d'empêcher toute configuration.
        if (!cancelled) setOfferedServices([]);
      });
    return () => {
      cancelled = true;
    };
  }, [agentId]);

  useEffect(() => {
    void load();
  }, [load]);

  const mutate = (patch: Partial<MonitoringPlan>) => {
    setPlan((prev) => (prev ? { ...prev, ...patch } : prev));
    setSaved(false);
  };

  /** Rend l'hôte aux seuils globaux de la plateforme.
   *
   *  Vider les trois paires plutôt que d'y recopier les valeurs globales :
   *  une copie figerait l'hôte sur les seuils du jour et le déconnecterait
   *  de toute évolution ultérieure de la politique centrale.
   */
  const resetToInherited = () => {
    if (!plan) return;
    mutate({
      cpu: { warning: null, critical: null, inherited: true },
      ram: { warning: null, critical: null, inherited: true },
      disk: { ...plan.disk, warning: null, critical: null, inherited: true },
    });
  };

  const save = async () => {
    if (!plan) return;
    // Contrôle local avant l'aller-retour : le serveur refuse aussi, mais
    // signaler l'incohérence à la saisie évite un échec inexpliqué.
    for (const [key, pair] of [
      ['CPU', plan.cpu],
      ['RAM', plan.ram],
      ['Disque', plan.disk],
    ] as const) {
      if (pair.warning != null && pair.critical != null && pair.warning >= pair.critical) {
        setError(`${key} : le seuil d'avertissement doit être inférieur au seuil critique.`);
        return;
      }
    }

    setSaving(true);
    setError(null);
    try {
      const updated = await agentsService.updateMonitoringPlan(agentId, {
        cpu: { warning: plan.cpu.warning, critical: plan.cpu.critical },
        ram: { warning: plan.ram.warning, critical: plan.ram.critical },
        disk: {
          warning: plan.disk.warning,
          critical: plan.disk.critical,
          partitions: plan.disk.partitions,
        },
        services: plan.services,
        files: plan.files,
      });
      setPlan(updated);
      setSaved(true);
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Enregistrement impossible.');
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <div className="cbc-card p-6 text-[13px] text-slate-500">Chargement du plan…</div>;
  if (!plan) return <div className="cbc-card p-6 text-[13px] text-rose-600">{error}</div>;

  const disabled = !canEdit || saving;
  const allInherited =
    plan.cpu.warning == null &&
    plan.cpu.critical == null &&
    plan.ram.warning == null &&
    plan.ram.critical == null &&
    plan.disk.warning == null &&
    plan.disk.critical == null;

  const thresholdRow = (
    label: string,
    pair: { warning: number | null; critical: number | null; inherited?: boolean },
    onChange: (next: { warning: number | null; critical: number | null }) => void,
  ) => (
    <div className="grid grid-cols-[130px_1fr_1fr] gap-3 items-center py-2">
      <div className="text-[12.5px] font-semibold text-slate-700">
        {label}
        {pair.inherited && (
          <span className="ml-1.5 text-[10.5px] font-normal text-slate-400">hérité</span>
        )}
      </div>
      <label className="flex items-center gap-2">
        <span className="text-[11px] text-slate-500 w-20">Avertis.</span>
        <input
          type="number"
          min={0}
          max={100}
          value={pair.warning ?? ''}
          placeholder="global"
          disabled={disabled}
          onChange={(e) =>
            onChange({ warning: e.target.value === '' ? null : Number(e.target.value), critical: pair.critical })
          }
          className="cbc-input py-1 text-[13px]"
        />
      </label>
      <label className="flex items-center gap-2">
        <span className="text-[11px] text-slate-500 w-20">Critique</span>
        <input
          type="number"
          min={0}
          max={100}
          value={pair.critical ?? ''}
          placeholder="global"
          disabled={disabled}
          onChange={(e) =>
            onChange({ warning: pair.warning, critical: e.target.value === '' ? null : Number(e.target.value) })
          }
          className="cbc-input py-1 text-[13px]"
        />
      </label>
    </div>
  );

  return (
    <div className="flex flex-col gap-4">
      {/* Cadence propre à cet hôte. Un serveur SWIFT mérite dix secondes là où
          un poste de bureau se contente d'une minute : imposer la même cadence
          à tout le parc oblige à choisir entre surveiller trop peu les
          machines critiques et trop souvent les autres. */}
      <div className="cbc-card p-[18px]">
        <div className="flex items-center justify-between gap-4 flex-wrap">
          <div className="min-w-0">
            <h2 className="text-sm font-bold m-0">Cadence de battement</h2>
            <p className="text-[12.5px] text-slate-500 mt-1 mb-0 max-w-2xl">
              Laisser vide pour suivre la cadence du parc. Le réglage descend à l’hôte
              au battement suivant, sans intervention sur la machine.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <input
              type="number"
              min={5}
              max={60}
              placeholder="parc"
              disabled={disabled}
              value={heartbeat ?? ''}
              onChange={(e) => setHeartbeat(e.target.value === '' ? null : Number(e.target.value))}
              className="cbc-input py-1.5 text-[13px] w-24 tnum"
            />
            <span className="text-[12.5px] text-slate-500">secondes</span>
            {canEdit && (
              <button
                type="button"
                disabled={disabled || savingHeartbeat}
                onClick={() => void saveHeartbeat()}
                className="cbc-btn-secondary py-1.5 px-3 text-[12.5px] disabled:opacity-50"
              >
                {savingHeartbeat ? 'Envoi…' : 'Appliquer'}
              </button>
            )}
          </div>
        </div>
        {heartbeatError && (
          <p className="text-[12.5px] text-rose-600 mt-2.5 mb-0">{heartbeatError}</p>
        )}
      </div>

      {/* --- CPU / RAM / Disque --- */}
      <div className="cbc-card overflow-hidden">
        <div className="px-[18px] py-3.5 border-b border-slate-200 flex items-start justify-between gap-4">
          <div>
            <h2 className="text-sm font-bold m-0">Seuils</h2>
            <p className="text-[11.5px] text-slate-500 mt-1 mb-0">
              CPU et mémoire sont supervisés par défaut. Laisser un champ vide
              pour suivre le seuil global de la plateforme.
            </p>
            <p className="text-[11px] text-slate-400 mt-1 mb-0">
              Héritage : Global → Groupe → Hôte
            </p>
          </div>
          {canEdit && !allInherited && (
            <button type="button" className="cbc-btn-secondary shrink-0" disabled={disabled} onClick={resetToInherited}>
              <RotateCcw className="w-3.5 h-3.5" />
              Rétablir l'héritage
            </button>
          )}
        </div>
        <div className="px-[18px] py-2">
          {thresholdRow('Processeur', plan.cpu, (v) => mutate({ cpu: { ...plan.cpu, ...v } }))}
          {thresholdRow('Mémoire', plan.ram, (v) => mutate({ ram: { ...plan.ram, ...v } }))}
          {thresholdRow('Disque (défaut)', plan.disk, (v) => mutate({ disk: { ...plan.disk, ...v } }))}
        </div>
      </div>

      {/* --- Partitions --- */}
      <div className="cbc-card overflow-hidden">
        <div className="px-[18px] py-3.5 border-b border-slate-200 flex items-center justify-between">
          <div>
            <h2 className="text-sm font-bold m-0">Partitions surveillées</h2>
            <p className="text-[11.5px] text-slate-500 mt-1 mb-0">
              Sans sélection, seule la partition principale est évaluée.
            </p>
          </div>
          {canEdit && (
            <button
              type="button"
              className="cbc-btn-secondary disabled:opacity-50"
              // Rien a choisir : proposer l'ajout produirait une regle vide,
              // enregistree puis silencieusement ignoree cote serveur.
              disabled={disabled || discoveredMounts.length === 0}
              onClick={() =>
                mutate({
                  disk: {
                    ...plan.disk,
                    partitions: [
                      ...plan.disk.partitions,
                      { mount: discoveredMounts[0] || '', warning: 85, critical: 95 },
                    ],
                  },
                })
              }
            >
              <Plus className="w-3.5 h-3.5" />
              Ajouter
            </button>
          )}
        </div>
        {discoveredMounts.length === 0 && (
          <p className="px-[18px] pt-3 pb-0 text-[12.5px] text-amber-800 m-0">
            Aucune partition remontée par cet hôte. L’agent transmet ses disques à
            chaque battement : si la liste reste vide, c’est qu’aucun battement n’est
            parvenu depuis son démarrage.
          </p>
        )}
        {plan.disk.partitions.length === 0 ? (
          <p className="px-[18px] py-4 text-[12.5px] text-slate-500 m-0">
            Aucune partition ciblée.
            {discoveredMounts.length > 0 &&
              ` ${discoveredMounts.length} partition(s) disponible(s) : ${discoveredMounts.join(', ')}.`}
          </p>
        ) : (
          plan.disk.partitions.map((p, i) => (
            <PartitionRow
              key={i}
              rule={p}
              mounts={discoveredMounts}
              disabled={disabled}
              onChange={(next) => {
                const partitions = [...plan.disk.partitions];
                partitions[i] = next;
                mutate({ disk: { ...plan.disk, partitions } });
              }}
              onRemove={() =>
                mutate({
                  disk: { ...plan.disk, partitions: plan.disk.partitions.filter((_, j) => j !== i) },
                })
              }
            />
          ))
        )}
      </div>

      {/* --- Services --- */}
      <div className="cbc-card overflow-hidden">
        <div className="px-[18px] py-3.5 border-b border-slate-200 flex items-center justify-between">
          <div>
            <h2 className="text-sm font-bold m-0 flex items-center gap-1.5">
              <Server className="w-4 h-4 text-slate-400" />
              Services
            </h2>
            <p className="text-[11.5px] text-slate-500 mt-1 mb-0">
              L'état attendu se règle par service : on alerte aussi bien sur un
              service critique arrêté que sur un service qui devrait le rester.
            </p>
          </div>
          {canEdit && (
            <button
              type="button"
              className="cbc-btn-secondary"
              disabled={disabled}
              onClick={() =>
                mutate({
                  services: [
                    ...plan.services,
                    { name: '', expected_state: 'running', severity: 'major', enabled: true },
                  ],
                })
              }
            >
              <Plus className="w-3.5 h-3.5" />
              Ajouter
            </button>
          )}
        </div>
        {plan.services.length === 0 ? (
          <p className="px-[18px] py-4 text-[12.5px] text-slate-500 m-0">
            Aucun service surveillé sur cet hôte — c'est un choix valide.
          </p>
        ) : (
          plan.services.map((svc, i) => (
            <ServiceRow
              key={i}
              rule={svc}
              disabled={disabled}
              offered={offeredServices}
              onChange={(next) => {
                const services = [...plan.services];
                services[i] = next;
                mutate({ services });
              }}
              onRemove={() => mutate({ services: plan.services.filter((_, j) => j !== i) })}
            />
          ))
        )}
      </div>

      {/* --- Fichiers --- */}
      <div className="cbc-card overflow-hidden">
        <div className="px-[18px] py-3.5 border-b border-slate-200 flex items-center justify-between">
          <div>
            <h2 className="text-sm font-bold m-0 flex items-center gap-1.5">
              <FileWarning className="w-4 h-4 text-slate-400" />
              Fichiers
            </h2>
            <p className="text-[11.5px] text-slate-500 mt-1 mb-0">
              Alerter sur l'absence d'un fichier attendu, ou sur l'apparition
              d'un fichier qui ne devrait pas être là.
            </p>
          </div>
          {canEdit && (
            <button
              type="button"
              className="cbc-btn-secondary"
              disabled={disabled}
              onClick={() =>
                mutate({
                  files: [
                    ...plan.files,
                    { path: '', condition: 'must_exist', severity: 'major', max_size_mb: null, enabled: true },
                  ],
                })
              }
            >
              <Plus className="w-3.5 h-3.5" />
              Ajouter
            </button>
          )}
        </div>
        {plan.files.length === 0 ? (
          <p className="px-[18px] py-4 text-[12.5px] text-slate-500 m-0">Aucun fichier surveillé.</p>
        ) : (
          plan.files.map((file, i) => (
            <FileRow
              key={i}
              rule={file}
              disabled={disabled}
              onChange={(next) => {
                const files = [...plan.files];
                files[i] = next;
                mutate({ files });
              }}
              onRemove={() => mutate({ files: plan.files.filter((_, j) => j !== i) })}
            />
          ))
        )}
      </div>

      {/* --- Publication --- */}
      <div className="cbc-card px-[18px] py-3.5 flex items-center justify-between gap-4 flex-wrap">
        <div className="text-[12px] text-slate-500">
          Plan v{plan.version}
          {plan.version_acked >= plan.version ? (
            <span className="ml-2 inline-flex items-center gap-1 text-emerald-700 font-semibold">
              <Check className="w-3.5 h-3.5" />
              appliqué par l'agent
            </span>
          ) : (
            <span className="ml-2 inline-flex items-center gap-1 text-amber-700 font-semibold">
              <AlertTriangle className="w-3.5 h-3.5" />
              en attente d'application (v{plan.version_acked} sur l'hôte)
            </span>
          )}
        </div>
        <div className="flex items-center gap-3">
          {error && <span className="text-[12px] text-rose-600">{error}</span>}
          {saved && !error && <span className="text-[12px] text-emerald-700">Plan publié.</span>}
          {canEdit && (
            <button type="button" className="cbc-btn-primary" disabled={disabled} onClick={() => void save()}>
              {saving ? 'Publication…' : 'Publier le plan'}
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

const RemoveButton: React.FC<{ onClick: () => void; disabled: boolean }> = ({ onClick, disabled }) => (
  <button
    type="button"
    onClick={onClick}
    disabled={disabled}
    className="p-1.5 rounded text-slate-400 hover:text-rose-600 hover:bg-rose-50 disabled:opacity-40"
    title="Retirer"
  >
    <Trash2 className="w-3.5 h-3.5" />
  </button>
);

const SeveritySelect: React.FC<{
  value: CheckSeverity;
  disabled: boolean;
  onChange: (v: CheckSeverity) => void;
}> = ({ value, disabled, onChange }) => (
  <select
    value={value}
    disabled={disabled}
    onChange={(e) => onChange(e.target.value as CheckSeverity)}
    className="cbc-input py-1 text-[13px]"
  >
    {SEVERITIES.map((s) => (
      <option key={s} value={s}>
        {SEVERITY_LABELS[s]}
      </option>
    ))}
  </select>
);

const PartitionRow: React.FC<{
  rule: PartitionRule;
  mounts: string[];
  disabled: boolean;
  onChange: (r: PartitionRule) => void;
  onRemove: () => void;
}> = ({ rule, mounts, disabled, onChange, onRemove }) => (
  <div className="grid grid-cols-[1fr_110px_110px_auto] gap-2.5 items-center px-[18px] py-2.5 border-b border-slate-50">
    {/* Une liste deroulante, non un champ libre avec datalist.
        Le datalist ne se montrait qu'en tapant : l'ecran n'annoncait jamais
        « voici les partitions de cet hote ». Il etait de surcroit rendu
        *dans* chaque ligne de regle -- sans regle existante, aucune ligne,
        donc aucune suggestion possible. On choisit desormais parmi ce que
        l'hote remonte, comme pour les services. */}
    <select
      value={!rule.mount || mounts.includes(rule.mount) ? rule.mount : '__absente__'}
      disabled={disabled}
      onChange={(e) => onChange({ ...rule, mount: e.target.value })}
      className="cbc-input py-1 text-[13px] tnum"
    >
      <option value="">Choisir une partition…</option>
      {mounts.map((m) => (
        <option key={m} value={m}>
          {m}
        </option>
      ))}
      {/* Une regle posee sur une partition que l'hote ne remonte plus est
          conservee et signalee, jamais effacee en silence : un disque
          demonte ou temporairement absent ne doit pas faire disparaitre le
          seuil que l'exploitant a defini pour lui. */}
      {rule.mount && !mounts.includes(rule.mount) && (
        <option value="__absente__">{rule.mount} — non remontée actuellement</option>
      )}
    </select>
    <input
      type="number"
      value={rule.warning}
      disabled={disabled}
      onChange={(e) => onChange({ ...rule, warning: Number(e.target.value) })}
      className="cbc-input py-1 text-[13px]"
    />
    <input
      type="number"
      value={rule.critical}
      disabled={disabled}
      onChange={(e) => onChange({ ...rule, critical: Number(e.target.value) })}
      className="cbc-input py-1 text-[13px]"
    />
    <RemoveButton onClick={onRemove} disabled={disabled} />
  </div>
);

/**
 * Choix d'un service parmi ceux que l'hôte déclare offrir.
 *
 * Repli sur la saisie libre quand l'inventaire n'est pas encore remonté — un
 * hôte fraîchement enrôlé n'a pas encore envoyé le sien, et bloquer la
 * configuration jusque-là serait pire que le risque de faute de frappe. Un
 * nom déjà saisi qui ne figure pas dans la liste est conservé et signalé,
 * jamais effacé en silence.
 */
const ServiceNamePicker: React.FC<{
  value: string;
  disabled: boolean;
  offered: HostInventory['services'];
  onChange: (name: string) => void;
}> = ({ value, disabled, offered, onChange }) => {
  const known = offered.some((s) => s.name === value);

  if (!offered.length) {
    return (
      <input
        value={value}
        disabled={disabled}
        placeholder="nom du service (inventaire non encore remonté)"
        onChange={(e) => onChange(e.target.value)}
        className="cbc-input py-1 text-[13px] tnum"
      />
    );
  }

  return (
    <div className="flex items-center gap-1.5 min-w-0">
      <select
        value={known ? value : ''}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value)}
        className="cbc-input py-1 text-[13px] tnum min-w-0 flex-1"
      >
        <option value="">Choisir un service…</option>
        {offered.map((s) => (
          <option key={s.name} value={s.name}>
            {s.display_name && s.display_name !== s.name ? `${s.name} — ${s.display_name}` : s.name}
          </option>
        ))}
      </select>
      {value && !known && (
        <span
          className="px-1.5 py-0.5 rounded-md bg-amber-50 text-amber-700 border border-amber-200 text-[10.5px] font-bold shrink-0"
          title={`« ${value} » ne figure pas dans l'inventaire de cet hôte. Le service a peut-être été renommé ou désinstallé.`}
        >
          absent
        </span>
      )}
    </div>
  );
};

const ServiceRow: React.FC<{
  rule: MonitoredServiceRule;
  disabled: boolean;
  offered: HostInventory['services'];
  onChange: (r: MonitoredServiceRule) => void;
  onRemove: () => void;
}> = ({ rule, disabled, offered, onChange, onRemove }) => (
  <div className="grid grid-cols-[1fr_150px_130px_auto] gap-2.5 items-center px-[18px] py-2.5 border-b border-slate-50">
    <ServiceNamePicker
      value={rule.name}
      disabled={disabled}
      offered={offered}
      onChange={(name) => onChange({ ...rule, name })}
    />
    <select
      value={rule.expected_state}
      disabled={disabled}
      onChange={(e) => onChange({ ...rule, expected_state: e.target.value as ServiceState })}
      className="cbc-input py-1 text-[13px]"
    >
      <option value="running">Doit tourner</option>
      <option value="stopped">Doit être arrêté</option>
    </select>
    <SeveritySelect
      value={rule.severity}
      disabled={disabled}
      onChange={(severity) => onChange({ ...rule, severity })}
    />
    <RemoveButton onClick={onRemove} disabled={disabled} />
  </div>
);

const FileRow: React.FC<{
  rule: MonitoredFileRule;
  disabled: boolean;
  onChange: (r: MonitoredFileRule) => void;
  onRemove: () => void;
}> = ({ rule, disabled, onChange, onRemove }) => (
  <div className="grid grid-cols-[1fr_170px_130px_100px_auto] gap-2.5 items-center px-[18px] py-2.5 border-b border-slate-50">
    <input
      value={rule.path}
      disabled={disabled}
      placeholder="/var/log/swift.log"
      onChange={(e) => onChange({ ...rule, path: e.target.value })}
      className="cbc-input py-1 text-[13px] tnum"
    />
    <select
      value={rule.condition}
      disabled={disabled}
      onChange={(e) => onChange({ ...rule, condition: e.target.value as FileCondition })}
      className="cbc-input py-1 text-[13px]"
    >
      <option value="must_exist">Doit exister</option>
      <option value="must_not_exist">Ne doit pas exister</option>
    </select>
    <SeveritySelect
      value={rule.severity}
      disabled={disabled}
      onChange={(severity) => onChange({ ...rule, severity })}
    />
    <input
      type="number"
      min={0}
      value={rule.max_size_mb ?? ''}
      disabled={disabled || rule.condition === 'must_not_exist'}
      placeholder="Mo max"
      title="Plafond de taille en Mo (facultatif)"
      onChange={(e) =>
        onChange({ ...rule, max_size_mb: e.target.value === '' ? null : Number(e.target.value) })
      }
      className="cbc-input py-1 text-[13px]"
    />
    <RemoveButton onClick={onRemove} disabled={disabled} />
  </div>
);
