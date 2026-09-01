/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../context/AppContext';
import { GlobalThresholds, MessagingNotificationConfig, ServicesMonitoringConfig, FilesMonitoringConfig, DataRetentionConfig, AvailabilityPolicy } from '../types';
import { Modal } from '../components/common/Modal';
import { VlanPlanPanel } from '../components/settings/VlanPlanPanel';
import { MailTemplatesPanel } from '../components/settings/MailTemplatesPanel';
import { groupsService, MachineGroup, ConfigRevision, CoverageRow, CoverageOverlap } from '../services/api/groups.service';
import {
  Sliders,
  MessageSquare,
  Clock,
  Key,
  Plus,
  Trash2,
  Send,
  Save,
  RotateCcw,
  Copy,
  Check,
  Cpu,
  Database,
  HardDrive,
  ShieldCheck,
  CheckCircle2,
  Lock,
  Building2,
  FileText,
  Download,
  BadgeCheck,
  Sparkles,
  Layers,
  File,
  Users,
  Map,
  Activity,
  RefreshCw,
  Network,
  Mail,
} from 'lucide-react';
import { settingsService } from '../services/api/settings.service';
import { PageHeader } from '../components/layout/PageHeader';
import { LdapPanel } from '../components/settings/LdapPanel';
import type { LucideIcon } from 'lucide-react';

type SettingsTab =
  | 'thresholds'
  | 'messaging'
  | 'groups'
  | 'coverage'
  | 'services'
  | 'files'
  | 'availability'
  | 'retention'
  | 'tokens'
  | 'platform'
  | 'ldap'
  | 'vlan'
  | 'templates';

const SETTINGS_NAV: Array<{ id: SettingsTab; label: string; icon: LucideIcon }> = [
  { id: 'thresholds', label: "Seuils d'alerte", icon: Sliders },
  { id: 'messaging', label: 'Notifications API CBC', icon: MessageSquare },
  { id: 'groups', label: 'Groupes & config', icon: Users },
  { id: 'coverage', label: 'Couverture PS', icon: Map },
  { id: 'services', label: 'Supervision services', icon: Layers },
  { id: 'files', label: 'Supervision fichiers', icon: File },
  { id: 'availability', label: 'Fenêtres horaires', icon: Clock },
  { id: 'retention', label: 'Rétention des données', icon: Clock },
  { id: 'tokens', label: "Jetons d'enrôlement", icon: Key },
  { id: 'platform', label: 'Plateforme', icon: Activity },
  { id: 'ldap', label: 'Annuaire (LDAP)', icon: ShieldCheck },
  { id: 'vlan', label: 'Plan d’adressage', icon: Network },
  { id: 'templates', label: 'Courriels par vérification', icon: Mail },
];

export const SettingsView: React.FC = () => {
  const navigate = useNavigate();
  const {
    globalThresholds,
    messagingConfig,
    availabilityPolicy,
    retentionConfig,
    enrollmentTokens,
    currentRole,
    updateGlobalThresholds,
    updateMessagingConfig,
    updateAvailabilityPolicy,
    updateRetentionConfig,
    generateEnrollmentToken,
    addToast,
  } = useApp();

  const [activeTab, setActiveTab] = useState<SettingsTab>('thresholds');
  const [platformStatus, setPlatformStatus] = useState<{
    status: string;
    checked_at?: string;
    unhealthy_count?: number;
    components?: Record<string, { status: string; error?: string }>;
    latency?: Record<string, { count?: number; p95_s?: number | null; budget_s?: number; within_budget?: boolean | null }>;
  } | null>(null);

  // Form states
  const [thresholdsForm, setThresholdsForm] = useState<GlobalThresholds>({
    ...globalThresholds,
    diskMountRules: globalThresholds.diskMountRules || [],
  });

  useEffect(() => {
    setThresholdsForm({
      ...globalThresholds,
      diskMountRules: globalThresholds.diskMountRules || [],
    });
  }, [globalThresholds]);
  const [messagingForm, setMessagingForm] = useState<MessagingNotificationConfig>(messagingConfig);
  const [availabilityForm, setAvailabilityForm] = useState<AvailabilityPolicy>(availabilityPolicy);
  const [retentionForm, setRetentionForm] = useState<DataRetentionConfig>(retentionConfig);
  const [newRecipient, setNewRecipient] = useState('');
  const [testMailTo, setTestMailTo] = useState('');
  const [testMailBusy, setTestMailBusy] = useState(false);
  const [formError, setFormError] = useState('');

  const [groups, setGroups] = useState<MachineGroup[]>([]);
  const [selectedGroupId, setSelectedGroupId] = useState<string>('');
  const [revisions, setRevisions] = useState<ConfigRevision[]>([]);
  const [newGroupName, setNewGroupName] = useState('');
  const [assignAgentId, setAssignAgentId] = useState('');
  const [publishJson, setPublishJson] = useState(
    '{\n  "services_monitoring": {"enabled": true, "services": []},\n  "files_monitoring": {"enabled": true, "files": []},\n  "metrics": {\n    "processes": {"watched": []},\n    "disk": {"path": "/", "alert_mounts": []}\n  },\n  "agent": {"heartbeat_interval": 30}\n}'
  );
  const [publishNote, setPublishNote] = useState('');
  const [coverageRows, setCoverageRows] = useState<CoverageRow[]>([]);
  const [overlaps, setOverlaps] = useState<CoverageOverlap[]>([]);
  const [discoveredPartitions, setDiscoveredPartitions] = useState<
    Array<{ name: string; mount: string; letter?: string | null; label?: string | null; host_count?: number }>
  >([]);

  useEffect(() => {
    if (activeTab !== 'thresholds') return;
    settingsService
      .getDiscoveredPartitions()
      .then(setDiscoveredPartitions)
      .catch(() => setDiscoveredPartitions([]));
  }, [activeTab]);

  const refreshGroups = async () => {
    try {
      const data = await groupsService.list();
      setGroups(data);
      if (!selectedGroupId && data[0]) setSelectedGroupId(data[0].id);
    } catch {
      /* ignore */
    }
  };

  const refreshCoverage = async () => {
    try {
      const [map, ov] = await Promise.all([groupsService.coverageMap(), groupsService.overlaps()]);
      setCoverageRows(map);
      setOverlaps(ov);
    } catch {
      /* ignore */
    }
  };

  useEffect(() => {
    if (activeTab === 'groups') {
      void refreshGroups();
    }
    if (activeTab === 'coverage') {
      void refreshCoverage();
    }
    if (activeTab === 'platform') {
      void settingsService
        .getPlatformStatus()
        .then(setPlatformStatus)
        .catch(() => setPlatformStatus(null));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab]);

  useEffect(() => {
    if (!selectedGroupId) {
      setRevisions([]);
      return;
    }
    groupsService
      .revisions(selectedGroupId)
      .then(setRevisions)
      .catch(() => setRevisions([]));
  }, [selectedGroupId]);

  // Token Modal
  const [tokenModalOpen, setTokenModalOpen] = useState(false);
  const [currentTokenCode, setCurrentTokenCode] = useState<string | null>(null);
  const [copiedTokenId, setCopiedTokenId] = useState<string | null>(null);

  const handleSaveThresholds = (e: React.FormEvent) => {
    e.preventDefault();
    setFormError('');

    if (thresholdsForm.cpuWarning >= thresholdsForm.cpuCritical) {
      setFormError('Le seuil CPU Warning doit être strictement inférieur au seuil Critique.');
      return;
    }
    if (thresholdsForm.ramWarning >= thresholdsForm.ramCritical) {
      setFormError('Le seuil RAM Warning doit être strictement inférieur au seuil Critique.');
      return;
    }
    if (thresholdsForm.diskWarning >= thresholdsForm.diskCritical) {
      setFormError('Le seuil Disque Warning doit être strictement inférieur au seuil Critique.');
      return;
    }
    for (const rule of thresholdsForm.diskMountRules || []) {
      const mount = rule.mount?.trim();
      if (!mount) {
        setFormError('Chaque plafond de partition doit avoir un point de montage (ex. /u01).');
        return;
      }
      if (rule.warning >= rule.critical) {
        setFormError(`Pour ${mount}, le Warning doit être strictement inférieur au Critique.`);
        return;
      }
    }

    updateGlobalThresholds({
      ...thresholdsForm,
      diskMountRules: (thresholdsForm.diskMountRules || []).map((r) => ({
        ...r,
        mount: r.mount.trim(),
      })),
    });
  };

  const handleAddRecipient = () => {
    if (!newRecipient || !newRecipient.includes('@')) {
      addToast({
        type: 'error',
        title: 'Destinataire invalide',
        message: 'Veuillez renseigner une adresse email valide.',
      });
      return;
    }
    if (messagingForm.recipients.includes(newRecipient)) {
      addToast({
        type: 'warning',
        title: 'Adresse existante',
        message: 'Ce destinataire fait déjà partie de la liste.',
      });
      return;
    }
    setMessagingForm({ ...messagingForm, recipients: [...messagingForm.recipients, newRecipient] });
    setNewRecipient('');
  };

  const handleRemoveRecipient = (recipient: string) => {
    setMessagingForm({ ...messagingForm, recipients: messagingForm.recipients.filter(r => r !== recipient) });
  };

  const handleSaveMessaging = (e: React.FormEvent) => {
    e.preventDefault();
    updateMessagingConfig(messagingForm);
  };

  const handleTestMessaging = async () => {
    if (currentRole !== 'Admin') return;
    const to = (testMailTo || messagingForm.recipients[0] || '').trim();
    if (!to) {
      addToast({
        type: 'error',
        title: 'Destinataire manquant',
        message: 'Ajoutez un destinataire ou saisissez une adresse pour le mail de test.',
      });
      return;
    }
    if (!messagingForm.enabled) {
      addToast({
        type: 'warning',
        title: 'Messagerie désactivée',
        message: 'Cochez « Activer les notifications » et enregistrez avant le test.',
      });
      return;
    }
    if (!messagingForm.apiEndpoint || !messagingForm.apiKey) {
      addToast({
        type: 'error',
        title: 'API non configurée',
        message: 'Renseignez endpoint + clé API, puis Enregistrer.',
      });
      return;
    }
    setTestMailBusy(true);
    addToast({
      type: 'info',
      title: 'Envoi du mail de test…',
      message: `Vers ${to}`,
    });
    try {
      await settingsService.sendTestMail({ to, subject: 'SENTINEL · Mail de test' });
      addToast({
        type: 'success',
        title: 'Mail envoyé',
        message: `Le mail de test a été accepté par l’API CBC pour ${to}.`,
      });
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        'Échec d’envoi — vérifiez endpoint, clé, réseau et /health de l’API Mail.';
      addToast({
        type: 'error',
        title: 'Échec du mail de test',
        message: String(detail),
      });
    } finally {
      setTestMailBusy(false);
    }
  };

  const handleSaveRetention = (e: React.FormEvent) => {
    e.preventDefault();
    updateRetentionConfig(retentionForm);
  };

  const handleGenerateToken = async () => {
    const created = await generateEnrollmentToken();
    if (!created) return;
    setCurrentTokenCode(created.token);
    setTokenModalOpen(true);
  };

  const handleCopyCode = (code: string, id: string) => {
    navigator.clipboard.writeText(code);
    setCopiedTokenId(id);
    setTimeout(() => setCopiedTokenId(null), 2000);
  };

  return (
    <div className="space-y-5">
      <PageHeader
        title="Paramètres"
        subtitle="Réglages de plateforme — seuils, notifications, rétention et jetons."
      />

      {currentRole !== 'Admin' && (
        <div className="p-4 bg-amber-50 border border-amber-200 rounded-2xl text-xs text-amber-900 font-medium">
          Note: Seul un <strong>Administrateur</strong> a les privilèges pour modifier la configuration globale.
        </div>
      )}

      <div className="flex flex-col lg:flex-row gap-5 items-start">
        <aside className="cbc-card w-full lg:w-[240px] shrink-0 overflow-hidden lg:sticky lg:top-6">
          <div className="px-3.5 py-3 border-b border-slate-200">
            <div className="text-[10.5px] font-bold uppercase tracking-wider text-slate-400">Configuration</div>
          </div>
          <nav className="p-2 flex lg:flex-col gap-0.5 overflow-x-auto lg:overflow-visible">
            {SETTINGS_NAV.map((item) => {
              const Icon = item.icon;
              const active = activeTab === item.id;
              const label =
                item.id === 'tokens'
                  ? `${item.label} (${enrollmentTokens.length})`
                  : item.label;
              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => setActiveTab(item.id)}
                  className={`flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-left text-[12.5px] font-semibold whitespace-nowrap transition-colors ${
                    active
                      ? 'bg-[#D0B335]/10 text-slate-900 border border-[#D0B335]/30'
                      : 'text-slate-500 border border-transparent hover:bg-slate-50 hover:text-slate-800'
                  }`}
                >
                  <Icon className={`w-4 h-4 shrink-0 ${active ? 'text-[#A68523]' : 'text-slate-400'}`} />
                  <span className="leading-snug">{label}</span>
                </button>
              );
            })}
          </nav>
        </aside>

        <div className="flex-1 min-w-0 space-y-5">
      {/* TAB 1: THRESHOLDS */}
      {activeTab === 'thresholds' && (
        <div className="bg-white p-6 rounded-2xl border border-slate-200/80 shadow-xs space-y-6">
          {formError && (
            <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl text-xs text-rose-700 font-bold">
              {formError}
            </div>
          )}

          <form onSubmit={handleSaveThresholds} className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {/* CPU */}
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
                    value={thresholdsForm.cpuWarning}
                    onChange={(e) => setThresholdsForm({ ...thresholdsForm, cpuWarning: Number(e.target.value) })}
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
                    value={thresholdsForm.cpuCritical}
                    onChange={(e) => setThresholdsForm({ ...thresholdsForm, cpuCritical: Number(e.target.value) })}
                    className="w-full p-2 bg-white border border-slate-200 rounded-lg text-xs font-bold text-rose-600"
                  />
                </div>
              </div>

              {/* RAM */}
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
                    value={thresholdsForm.ramWarning}
                    onChange={(e) => setThresholdsForm({ ...thresholdsForm, ramWarning: Number(e.target.value) })}
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
                    value={thresholdsForm.ramCritical}
                    onChange={(e) => setThresholdsForm({ ...thresholdsForm, ramCritical: Number(e.target.value) })}
                    className="w-full p-2 bg-white border border-slate-200 rounded-lg text-xs font-bold text-rose-600"
                  />
                </div>
              </div>

              {/* DISK */}
              <div className="p-4 bg-slate-50 rounded-xl border border-slate-200/80 space-y-4">
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center gap-1.5">
                  <HardDrive className="w-4 h-4 text-purple-500" /> Seuils Disque (%)
                </h4>
                <p className="text-[11px] text-slate-500 leading-relaxed">
                  Défaut pour les partitions alertées sans plafond dédié.
                </p>
                <div>
                  <label className="block text-xs text-slate-600 font-medium mb-1">Warning (%)</label>
                  <input
                    type="number"
                    min="1"
                    max="99"
                    disabled={currentRole !== 'Admin'}
                    value={thresholdsForm.diskWarning}
                    onChange={(e) => setThresholdsForm({ ...thresholdsForm, diskWarning: Number(e.target.value) })}
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
                    value={thresholdsForm.diskCritical}
                    onChange={(e) => setThresholdsForm({ ...thresholdsForm, diskCritical: Number(e.target.value) })}
                    className="w-full p-2 bg-white border border-slate-200 rounded-lg text-xs font-bold text-rose-600"
                  />
                </div>
              </div>
            </div>

            <div className="p-4 bg-slate-50 rounded-xl border border-slate-200/80 space-y-3">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h4 className="text-xs font-bold uppercase tracking-wider text-slate-700">
                    Plafonds par partition (défaut flotte)
                  </h4>
                  <p className="text-[11px] text-slate-500 mt-1 leading-relaxed">
                    Défauts pour tout le parc. Pour un hôte précis, préférez{' '}
                    <strong>Agents → Configuration</strong> (sélection depuis les partitions rapportées par l’agent).
                  </p>
                </div>
                {currentRole === 'Admin' && (
                  <button
                    type="button"
                    onClick={() =>
                      setThresholdsForm({
                        ...thresholdsForm,
                        diskMountRules: [
                          ...(thresholdsForm.diskMountRules || []),
                          {
                            mount:
                              discoveredPartitions.find(
                                (p) => !(thresholdsForm.diskMountRules || []).some((r) => r.mount === p.mount)
                              )?.mount || '',
                            warning: thresholdsForm.diskWarning,
                            critical: thresholdsForm.diskCritical,
                          },
                        ],
                      })
                    }
                    className="shrink-0 inline-flex items-center gap-1 px-2.5 py-1.5 text-[11px] font-bold rounded-lg bg-white border border-slate-200 text-slate-700 hover:border-[#D0B335]"
                  >
                    <Plus className="w-3.5 h-3.5" /> Ajouter
                  </button>
                )}
              </div>

              {discoveredPartitions.length === 0 && (
                <p className="text-[11px] text-amber-700 bg-amber-50 border border-amber-100 rounded-lg px-3 py-2">
                  Aucune partition découverte pour l’instant. Les agents envoient la lettre / le nom / le montage à chaque heartbeat.
                </p>
              )}

              {(thresholdsForm.diskMountRules || []).length === 0 ? (
                <p className="text-[11px] text-slate-400 italic">Aucun plafond spécifique — le défaut disque s’applique.</p>
              ) : (
                <div className="space-y-2">
                  {(thresholdsForm.diskMountRules || []).map((rule, idx) => (
                    <div
                      key={`mount-rule-${idx}`}
                      className="grid grid-cols-1 sm:grid-cols-[minmax(0,1.4fr)_1fr_1fr_auto] gap-2 items-end"
                    >
                      <div>
                        <label className="block text-[10px] text-slate-500 font-medium mb-1">Partition</label>
                        <select
                          disabled={currentRole !== 'Admin'}
                          value={rule.mount}
                          onChange={(e) => {
                            const next = [...(thresholdsForm.diskMountRules || [])];
                            next[idx] = { ...next[idx], mount: e.target.value };
                            setThresholdsForm({ ...thresholdsForm, diskMountRules: next });
                          }}
                          className="w-full p-2 bg-white border border-slate-200 rounded-lg text-xs font-mono font-bold text-slate-900"
                        >
                          <option value="">— Sélectionner —</option>
                          {discoveredPartitions.map((p) => (
                            <option key={p.mount} value={p.mount}>
                              {(p.letter ? `${p.letter}: ` : '') +
                                (p.label ? `${p.label} · ` : '') +
                                p.mount +
                                (p.host_count ? ` (${p.host_count} hôte${p.host_count > 1 ? 's' : ''})` : '')}
                            </option>
                          ))}
                          {rule.mount && !discoveredPartitions.some((p) => p.mount === rule.mount) && (
                            <option value={rule.mount}>{rule.mount}</option>
                          )}
                        </select>
                      </div>
                      <div>
                        <label className="block text-[10px] text-slate-500 font-medium mb-1">Warning (%)</label>
                        <input
                          type="number"
                          min="1"
                          max="99"
                          disabled={currentRole !== 'Admin'}
                          value={rule.warning}
                          onChange={(e) => {
                            const next = [...(thresholdsForm.diskMountRules || [])];
                            next[idx] = { ...next[idx], warning: Number(e.target.value) };
                            setThresholdsForm({ ...thresholdsForm, diskMountRules: next });
                          }}
                          className="w-full p-2 bg-white border border-slate-200 rounded-lg text-xs font-bold text-slate-900"
                        />
                      </div>
                      <div>
                        <label className="block text-[10px] text-slate-500 font-medium mb-1">Critique (%)</label>
                        <input
                          type="number"
                          min="1"
                          max="100"
                          disabled={currentRole !== 'Admin'}
                          value={rule.critical}
                          onChange={(e) => {
                            const next = [...(thresholdsForm.diskMountRules || [])];
                            next[idx] = { ...next[idx], critical: Number(e.target.value) };
                            setThresholdsForm({ ...thresholdsForm, diskMountRules: next });
                          }}
                          className="w-full p-2 bg-white border border-slate-200 rounded-lg text-xs font-bold text-rose-600"
                        />
                      </div>
                      {currentRole === 'Admin' && (
                        <button
                          type="button"
                          aria-label="Supprimer"
                          onClick={() => {
                            const next = (thresholdsForm.diskMountRules || []).filter((_, i) => i !== idx);
                            setThresholdsForm({ ...thresholdsForm, diskMountRules: next });
                          }}
                          className="p-2 rounded-lg border border-slate-200 text-slate-500 hover:text-rose-600 hover:border-rose-200 bg-white"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="p-4 bg-slate-50 rounded-xl border border-slate-200/80">
                <label className="block text-xs font-bold text-slate-700 mb-1">Durée avant alerte (secondes)</label>
                <p className="text-[11px] text-slate-500 mb-2">La métrique doit rester au-dessus du seuil pendant cette durée — un pic isolé n’alerte pas.</p>
                <input
                  type="number"
                  min="0"
                  disabled={currentRole !== 'Admin'}
                  value={thresholdsForm.durationSeconds ?? 300}
                  onChange={(e) => setThresholdsForm({ ...thresholdsForm, durationSeconds: Number(e.target.value) })}
                  className="w-full p-2 bg-white border border-slate-200 rounded-lg text-xs font-bold text-slate-900"
                />
              </div>
              <div className="p-4 bg-slate-50 rounded-xl border border-slate-200/80">
                <label className="block text-xs font-bold text-slate-700 mb-1">Escalade si non acquittée (minutes)</label>
                <p className="text-[11px] text-slate-500 mb-2">Passe en Critique et re-notifie (mail CBC + webhook HMAC).</p>
                <input
                  type="number"
                  min="1"
                  disabled={currentRole !== 'Admin'}
                  value={thresholdsForm.escalateAfterMinutes ?? 15}
                  onChange={(e) => setThresholdsForm({ ...thresholdsForm, escalateAfterMinutes: Number(e.target.value) })}
                  className="w-full p-2 bg-white border border-slate-200 rounded-lg text-xs font-bold text-slate-900"
                />
              </div>
            </div>

            {currentRole === 'Admin' && (
              <div className="flex justify-end pt-4 border-t border-slate-100">
                <button
                  type="submit"
                  className="px-5 py-2.5 bg-[#D0B335] hover:bg-[#b89d2d] text-slate-950 text-xs font-bold rounded-xl shadow-xs flex items-center gap-1.5"
                >
                  <Save className="w-4 h-4" />
                  Sauvegarder les seuils globaux
                </button>
              </div>
            )}
          </form>
        </div>
      )}

      {/* TAB 2: MESSAGING API CBC */}
      {activeTab === 'messaging' && (
        <div className="bg-white p-6 rounded-2xl border border-slate-200/80 shadow-xs space-y-6">
          <form onSubmit={handleSaveMessaging} className="space-y-6">
            {/* Destinataires */}
            <div className="space-y-3">
              <h4 className="text-sm font-bold text-slate-900 tracking-tight">
                Destinataires des notifications d'alerte
              </h4>

              <div className="flex items-center gap-2">
                <input
                  type="email"
                  value={newRecipient}
                  onChange={(e) => setNewRecipient(e.target.value)}
                  placeholder="nom@cbcam.cm"
                  disabled={currentRole !== 'Admin'}
                  className="w-full sm:w-80 p-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-900 font-medium focus:outline-none focus:ring-2 focus:ring-[#D0B335]"
                />
                {currentRole === 'Admin' && (
                  <button
                    type="button"
                    onClick={handleAddRecipient}
                    className="px-4 py-2.5 bg-slate-900 text-white text-xs font-bold rounded-xl flex items-center gap-1 hover:bg-slate-800"
                  >
                    <Plus className="w-4 h-4" />
                    Ajouter
                  </button>
                )}
              </div>

              <div className="flex flex-wrap gap-2 pt-2">
                {messagingForm.recipients.map((rec) => (
                  <span
                    key={rec}
                    className="inline-flex items-center gap-2 px-3 py-1.5 bg-slate-100 text-slate-800 rounded-xl text-xs font-semibold border border-slate-200"
                  >
                    {rec}
                    {currentRole === 'Admin' && (
                      <button
                        type="button"
                        onClick={() => handleRemoveRecipient(rec)}
                        className="text-slate-400 hover:text-rose-600"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </span>
                ))}
              </div>
            </div>

            {/* API de messagerie CBC Config */}
            <div className="pt-4 border-t border-slate-100 space-y-4">
              <h4 className="text-sm font-bold text-slate-900 tracking-tight">
                Configuration de l'API de messagerie interne CBC
              </h4>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-bold text-slate-700 mb-1">Endpoint API</label>
                  <input
                    type="text"
                    disabled={currentRole !== 'Admin'}
                    value={messagingForm.apiEndpoint}
                    onChange={(e) => setMessagingForm({ ...messagingForm, apiEndpoint: e.target.value })}
                    placeholder="https://api.cbc.internal/messaging"
                    className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs font-mono font-bold text-slate-900"
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold text-slate-700 mb-1">Clé API</label>
                  <input
                    type="password"
                    disabled={currentRole !== 'Admin'}
                    value={messagingForm.apiKey}
                    onChange={(e) => setMessagingForm({ ...messagingForm, apiKey: e.target.value })}
                    placeholder="••••••••••••••••"
                    className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs font-mono font-bold text-slate-900"
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold text-slate-700 mb-1">Timeout (secondes)</label>
                  <input
                    type="number"
                    disabled={currentRole !== 'Admin'}
                    value={messagingForm.apiTimeout}
                    onChange={(e) => setMessagingForm({ ...messagingForm, apiTimeout: Number(e.target.value) })}
                    className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs font-mono font-bold text-slate-900"
                  />
                </div>
                <div className="flex items-center gap-2 pt-6">
                  <input
                    type="checkbox"
                    id="messagingEnabled"
                    disabled={currentRole !== 'Admin'}
                    checked={messagingForm.enabled}
                    onChange={(e) => setMessagingForm({ ...messagingForm, enabled: e.target.checked })}
                    className="w-4 h-4 text-[#D0B335] rounded focus:ring-[#D0B335]"
                  />
                  <label htmlFor="messagingEnabled" className="text-xs font-bold text-slate-700">
                    Activer les notifications
                  </label>
                </div>
                <p className="text-[11px] text-slate-500 col-span-full">
                  Les mails utilisent des gabarits HTML par type d'alerte et par action (plugin + statut),
                  avec surcharge possible par hôte. Enregistrez endpoint, clé API et au moins un destinataire
                  ici — c'est cette configuration (pas seulement les variables d'environnement) qui déclenche l'envoi.
                </p>
                <div className="col-span-full pt-2 space-y-2">
                  <label className="block text-xs font-bold text-slate-700">Mail de test — destinataire</label>
                  <div className="flex flex-wrap gap-2 items-center">
                    <input
                      type="email"
                      disabled={currentRole !== 'Admin'}
                      value={testMailTo}
                      onChange={(e) => setTestMailTo(e.target.value)}
                      placeholder={messagingForm.recipients[0] || 'vous@cbcam.cm'}
                      className="w-full sm:w-80 p-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs font-medium text-slate-900"
                    />
                    <span className="text-[11px] text-slate-400">
                      Vide = premier destinataire de la liste
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-500">
                    Plus tard : chaque hôte aura un propriétaire ; le mail ira au propriétaire, avec la
                    hiérarchie (manager) en copie.
                  </p>
                </div>
              </div>
            </div>

            <div className="pt-4 border-t border-slate-100 space-y-4">
              <h4 className="text-sm font-bold text-slate-900 tracking-tight">Webhook HMAC (INT-003)</h4>
              <p className="text-[11px] text-slate-500">POST JSON signé : en-tête X-CBC-Signature = sha256=&lt;hmac&gt;. Aucun compte cloud.</p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-bold text-slate-700 mb-1">URL webhook</label>
                  <input
                    type="text"
                    disabled={currentRole !== 'Admin'}
                    value={messagingForm.webhookUrl || ''}
                    onChange={(e) => setMessagingForm({ ...messagingForm, webhookUrl: e.target.value })}
                    placeholder="https://itsm.interne.cbc/hooks/alerts"
                    className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs font-mono font-bold text-slate-900"
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold text-slate-700 mb-1">Secret HMAC</label>
                  <input
                    type="password"
                    disabled={currentRole !== 'Admin'}
                    value={messagingForm.webhookSecret || ''}
                    onChange={(e) => setMessagingForm({ ...messagingForm, webhookSecret: e.target.value })}
                    placeholder="••••••••"
                    className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs font-mono font-bold text-slate-900"
                  />
                </div>
                <div className="flex items-center gap-2 pt-2">
                  <input
                    type="checkbox"
                    id="webhookEnabled"
                    disabled={currentRole !== 'Admin'}
                    checked={Boolean(messagingForm.webhookEnabled)}
                    onChange={(e) => setMessagingForm({ ...messagingForm, webhookEnabled: e.target.checked })}
                    className="w-4 h-4 text-[#D0B335] rounded focus:ring-[#D0B335]"
                  />
                  <label htmlFor="webhookEnabled" className="text-xs font-bold text-slate-700">
                    Activer le webhook signé
                  </label>
                </div>
              </div>
            </div>

            {/* Actions */}
            {currentRole === 'Admin' && (
              <div className="pt-4 border-t border-slate-100 flex items-center gap-3">
                <button
                  type="submit"
                  className="inline-flex items-center gap-2 px-4 py-2.5 bg-[#D0B335] hover:bg-[#b89d2d] text-slate-950 text-xs font-bold rounded-xl shadow-xs transition-colors"
                >
                  <Save className="w-4 h-4" />
                  Enregistrer la configuration
                </button>
                <button
                  type="button"
                  disabled={testMailBusy}
                  onClick={handleTestMessaging}
                  className="inline-flex items-center gap-2 px-4 py-2.5 bg-slate-100 hover:bg-slate-200 text-slate-800 text-xs font-bold rounded-xl transition-colors border border-slate-200 disabled:opacity-60"
                >
                  <Send className="w-4 h-4" />
                  {testMailBusy ? 'Envoi…' : 'Envoyer un mail de test'}
                </button>
              </div>
            )}
          </form>
        </div>
      )}

      {activeTab === 'groups' && (
        <div className="bg-white p-6 rounded-2xl border border-slate-200/80 shadow-xs space-y-6">
          <div>
            <h3 className="text-sm font-black text-slate-900">Groupes de machines & config distante (AGT-008)</h3>
            <p className="text-xs text-slate-500 mt-1">
              Publiez une config versionnée. Les agents du groupe la reçoivent au prochain heartbeat (sans SSH).
            </p>
          </div>

          <div className="flex flex-wrap gap-2 items-end">
            <div>
              <label className="block text-[11px] font-bold text-slate-600 mb-1">Nouveau groupe</label>
              <input
                value={newGroupName}
                onChange={(e) => setNewGroupName(e.target.value)}
                disabled={currentRole !== 'Admin'}
                className="px-3 py-2 rounded-xl border border-slate-200 text-xs w-56"
                placeholder="Agence"
              />
            </div>
            {currentRole === 'Admin' && (
              <button
                type="button"
                onClick={async () => {
                  if (!newGroupName.trim()) return;
                  await groupsService.create(newGroupName.trim());
                  setNewGroupName('');
                  addToast({ type: 'success', title: 'Groupe créé', message: newGroupName });
                  await refreshGroups();
                }}
                className="px-3 py-2 rounded-xl bg-slate-900 text-white text-xs font-bold"
              >
                Créer
              </button>
            )}
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="space-y-3">
              <label className="block text-xs font-bold text-slate-700">Groupe</label>
              <select
                value={selectedGroupId}
                onChange={(e) => setSelectedGroupId(e.target.value)}
                className="w-full px-3 py-2 rounded-xl border border-slate-200 text-xs"
              >
                <option value="">—</option>
                {groups.map((g) => (
                  <option key={g.id} value={g.id}>
                    {g.name} (v{g.current_version}, {g.agent_count} agents)
                  </option>
                ))}
              </select>

              <div className="flex gap-2 items-end">
                <div className="flex-1">
                  <label className="block text-[11px] font-bold text-slate-600 mb-1">Assigner agent (ID)</label>
                  <input
                    value={assignAgentId}
                    onChange={(e) => setAssignAgentId(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl border border-slate-200 text-xs font-mono"
                    placeholder="uuid agent"
                  />
                </div>
                {currentRole !== 'ReadOnly' && (
                  <button
                    type="button"
                    disabled={!selectedGroupId || !assignAgentId.trim()}
                    onClick={async () => {
                      await groupsService.assign(assignAgentId.trim(), selectedGroupId);
                      addToast({ type: 'success', title: 'Agent assigné', message: 'Config sera poussée au prochain heartbeat' });
                      await refreshGroups();
                    }}
                    className="px-3 py-2 rounded-xl bg-[#D0B335] text-slate-950 text-xs font-bold disabled:opacity-40"
                  >
                    Assigner
                  </button>
                )}
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">Payload JSON à publier</label>
                <textarea
                  rows={12}
                  value={publishJson}
                  onChange={(e) => setPublishJson(e.target.value)}
                  disabled={currentRole !== 'Admin'}
                  className="w-full px-3 py-2 rounded-xl border border-slate-200 text-[11px] font-mono"
                />
                <input
                  value={publishNote}
                  onChange={(e) => setPublishNote(e.target.value)}
                  placeholder="Note de version"
                  disabled={currentRole !== 'Admin'}
                  className="mt-2 w-full px-3 py-2 rounded-xl border border-slate-200 text-xs"
                />
                {currentRole === 'Admin' && (
                  <button
                    type="button"
                    className="mt-2 px-4 py-2 rounded-xl bg-slate-900 text-white text-xs font-bold"
                    onClick={async () => {
                      if (!selectedGroupId) return;
                      try {
                        const payload = JSON.parse(publishJson);
                        const res = await groupsService.publish(selectedGroupId, payload, publishNote || undefined);
                        addToast({ type: 'success', title: 'Config publiée', message: `Version ${res.version}` });
                        const revs = await groupsService.revisions(selectedGroupId);
                        setRevisions(revs);
                        await refreshGroups();
                      } catch (err) {
                        addToast({ type: 'error', title: 'Publication échouée', message: String(err) });
                      }
                    }}
                  >
                    Publier
                  </button>
                )}
              </div>
            </div>

            <div>
              <h4 className="text-xs font-bold text-slate-700 mb-2">Historique / rollback</h4>
              <div className="space-y-2 max-h-[420px] overflow-auto">
                {revisions.length === 0 ? (
                  <p className="text-xs text-slate-500">Aucune révision.</p>
                ) : (
                  revisions.map((r) => (
                    <div key={r.id} className="p-3 rounded-xl border border-slate-200 bg-slate-50 text-xs">
                      <div className="flex justify-between items-center gap-2">
                        <span className="font-bold">v{r.version}</span>
                        <span className="text-slate-400">{r.created_by || '—'}</span>
                      </div>
                      <p className="text-slate-600 mt-1">{r.note || '—'}</p>
                      {currentRole === 'Admin' && (
                        <button
                          type="button"
                          className="mt-2 text-[11px] font-bold text-blue-700"
                          onClick={async () => {
                            const res = await groupsService.rollback(selectedGroupId, r.version);
                            addToast({ type: 'success', title: 'Rollback', message: `Nouvelle version ${res.version}` });
                            setRevisions(await groupsService.revisions(selectedGroupId));
                            await refreshGroups();
                          }}
                        >
                          Rollback vers cette version
                        </button>
                      )}
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'coverage' && (
        <div className="bg-white p-6 rounded-2xl border border-slate-200/80 shadow-xs space-y-6">
          <div>
            <h3 className="text-sm font-black text-slate-900">Carte de couverture PowerShell (DES-004)</h3>
            <p className="text-xs text-slate-500 mt-1">
              Plugins livrés vs inventaire CBC. Signalez les chevauchements script+agent (AGT-014).
            </p>
          </div>
          <table className="w-full text-xs">
            <thead className="text-left text-slate-500 uppercase text-[10px]">
              <tr>
                <th className="py-2">Check</th>
                <th className="py-2">Plugin</th>
                <th className="py-2">Statut</th>
                <th className="py-2">Sprint</th>
                <th className="py-2">Notes</th>
              </tr>
            </thead>
            <tbody>
              {coverageRows.map((row) => (
                <tr key={row.check_id} className="border-t border-slate-100">
                  <td className="py-2 font-mono font-bold">{row.check_id}</td>
                  <td className="py-2">{row.plugin}</td>
                  <td className="py-2">{row.status}</td>
                  <td className="py-2">{row.sprint}</td>
                  <td className="py-2 text-slate-500">{row.notes || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>

          <div>
            <h4 className="text-xs font-bold text-slate-800 mb-2">Chevauchements actifs</h4>
            {overlaps.length === 0 ? (
              <p className="text-xs text-slate-500">Aucun chevauchement signalé.</p>
            ) : (
              <ul className="space-y-2">
                {overlaps.map((o) => (
                  <li key={o.id} className="flex justify-between gap-3 text-xs p-2 rounded-lg bg-amber-50 border border-amber-100">
                    <span>
                      {o.hostname || o.agent_id} · {o.check_id} ↔ {o.plugin}
                    </span>
                    {currentRole !== 'ReadOnly' && (
                      <button
                        type="button"
                        className="font-bold text-emerald-700"
                        onClick={async () => {
                          await groupsService.clearOverlap(o.id);
                          await refreshCoverage();
                        }}
                      >
                        Lever
                      </button>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}

      {/* TAB 3: SUPERVISION SERVICES */}
      {(activeTab === 'services' || activeTab === 'files') && (
        <div className="bg-white p-6 rounded-2xl border border-slate-200/80 shadow-xs">
          <h4 className="text-sm font-bold text-slate-900 tracking-tight m-0">
            La supervision se règle désormais par hôte
          </h4>
          <p className="text-[13px] leading-relaxed text-slate-600 mt-3">
            Les services et fichiers à surveiller dépendent de la machine :
            une passerelle SWIFT et un poste bureautique n'ont ni les mêmes
            services ni les mêmes fichiers critiques. Un réglage global n'aurait
            de sens sur aucun des deux.
          </p>
          <p className="text-[13px] leading-relaxed text-slate-600">
            Ouvrez la fiche d'un hôte, onglet <strong>Supervision</strong> : vous
            y choisissez les partitions et leurs seuils, les services avec leur
            état attendu, et les fichiers avec leur condition — présence exigée
            ou présence interdite.
          </p>
          <div className="mt-4 rounded-lg bg-amber-50 border border-amber-200 px-4 py-3 text-[12.5px] text-amber-900">
            Ces deux écrans annonçaient auparavant « mise à jour avec succès »
            sans rien enregistrer : ni côté interface, ni côté serveur. Le
            paramétrage disparaissait au rafraîchissement.
          </div>
          <button
            type="button"
            onClick={() => navigate('/agents')}
            className="cbc-btn-primary mt-5"
          >
            Ouvrir le parc
          </button>
        </div>
      )}

      {/* TAB 5: FENÊTRES HORAIRES */}
      {activeTab === 'availability' && (
        <div className="bg-white p-6 rounded-2xl border border-slate-200/80 shadow-xs space-y-6">
          <form onSubmit={(e) => { e.preventDefault(); updateAvailabilityPolicy(availabilityForm); }} className="space-y-6">
            <div className="flex items-center justify-between">
              <h4 className="text-sm font-bold text-slate-900 tracking-tight">
                Configuration des fenêtres horaires de disponibilité
              </h4>
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="availabilityEnabled"
                  disabled={currentRole !== 'Admin'}
                  checked={availabilityForm.enabled}
                  onChange={(e) => setAvailabilityForm({ ...availabilityForm, enabled: e.target.checked })}
                  className="w-4 h-4 text-[#D0B335] rounded focus:ring-[#D0B335]"
                />
                <label htmlFor="availabilityEnabled" className="text-xs font-bold text-slate-700">
                  Activer les fenêtres horaires
                </label>
              </div>
            </div>

            <div className="space-y-3">
              <h4 className="text-sm font-bold text-slate-900 tracking-tight">
                Fenêtres horaires par jour
              </h4>
              <p className="text-xs text-slate-500">
                Définissez les plages horaires pendant lesquelles les postes de travail doivent être disponibles.
                En dehors de ces plages, l'absence d'un poste ne générera pas d'alerte.
              </p>

              <div className="space-y-4">
                {['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'].map((day) => (
                  <div key={day} className="p-4 bg-slate-50 rounded-xl border border-slate-200/80">
                    <div className="flex items-center justify-between mb-3">
                      <span className="text-xs font-bold text-slate-800 capitalize">{day}</span>
                      <button
                        type="button"
                        onClick={() => {
                          const newTimeWindows = { ...availabilityForm.timeWindows };
                          if (!newTimeWindows[day]) {
                            newTimeWindows[day] = [{ start: '08:00', end: '18:00' }];
                          }
                          setAvailabilityForm({ ...availabilityForm, timeWindows: newTimeWindows });
                        }}
                        disabled={currentRole !== 'Admin'}
                        className="text-xs text-slate-600 hover:text-slate-900"
                      >
                        + Ajouter plage
                      </button>
                    </div>
                    
                    {availabilityForm.timeWindows[day]?.map((window, index) => (
                      <div key={index} className="flex items-center gap-2 mb-2">
                        <input
                          type="time"
                          value={window.start}
                          onChange={(e) => {
                            const newTimeWindows = { ...availabilityForm.timeWindows };
                            newTimeWindows[day][index].start = e.target.value;
                            setAvailabilityForm({ ...availabilityForm, timeWindows: newTimeWindows });
                          }}
                          disabled={currentRole !== 'Admin'}
                          className="w-32 p-2 bg-white border border-slate-200 rounded-lg text-xs font-mono"
                        />
                        <span className="text-xs text-slate-500">→</span>
                        <input
                          type="time"
                          value={window.end}
                          onChange={(e) => {
                            const newTimeWindows = { ...availabilityForm.timeWindows };
                            newTimeWindows[day][index].end = e.target.value;
                            setAvailabilityForm({ ...availabilityForm, timeWindows: newTimeWindows });
                          }}
                          disabled={currentRole !== 'Admin'}
                          className="w-32 p-2 bg-white border border-slate-200 rounded-lg text-xs font-mono"
                        />
                        {currentRole === 'Admin' && (
                          <button
                            type="button"
                            onClick={() => {
                              const newTimeWindows = { ...availabilityForm.timeWindows };
                              newTimeWindows[day].splice(index, 1);
                              setAvailabilityForm({ ...availabilityForm, timeWindows: newTimeWindows });
                            }}
                            className="text-slate-400 hover:text-rose-600"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        )}
                      </div>
                    ))}
                  </div>
                ))}
              </div>
            </div>

            <div className="pt-4 border-t border-slate-100">
              <label className="block text-xs font-bold text-slate-700 mb-1">Seuil offline personnalisé (secondes, optionnel)</label>
              <input
                type="number"
                disabled={currentRole !== 'Admin'}
                value={availabilityForm.offlineThresholdSeconds || ''}
                onChange={(e) => setAvailabilityForm({ ...availabilityForm, offlineThresholdSeconds: e.target.value ? Number(e.target.value) : undefined })}
                placeholder="Laisser vide pour utiliser le seuil par défaut"
                className="w-full sm:w-40 p-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs font-mono font-bold text-slate-900"
              />
              <p className="text-xs text-slate-500 mt-1">
                Remplace le seuil par défaut (90s pour serveurs, 7200s pour postes) si défini
              </p>
            </div>

            {/* Actions */}
            {currentRole === 'Admin' && (
              <div className="pt-4 border-t border-slate-100 flex items-center gap-3">
                <button
                  type="submit"
                  className="inline-flex items-center gap-2 px-4 py-2.5 bg-[#D0B335] hover:bg-[#b89d2d] text-slate-950 text-xs font-bold rounded-xl shadow-xs transition-colors"
                >
                  <Save className="w-4 h-4" />
                  Enregistrer la configuration
                </button>
              </div>
            )}
          </form>
        </div>
      )}

      {/* TAB 6: RÉTENTION DES DONNÉES */}
      {activeTab === 'retention' && (
        <div className="bg-white p-6 rounded-2xl border border-slate-200/80 shadow-xs space-y-6">
          <form onSubmit={handleSaveRetention} className="space-y-6">
            <h4 className="text-sm font-bold text-slate-900 tracking-tight">
              Politique d'archivage et de suppression automatique
            </h4>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
              <div className="p-4 bg-slate-50 rounded-xl border border-slate-200/80 space-y-3">
                <label className="block text-xs font-bold text-slate-800">
                  Rétention de l'historique des alertes (en jours)
                </label>
                <input
                  type="number"
                  min="1"
                  max="365"
                  disabled={currentRole !== 'Admin'}
                  value={retentionForm.alertsDays}
                  onChange={(e) => setRetentionForm({ ...retentionForm, alertsDays: Number(e.target.value) })}
                  className="w-full p-2.5 bg-white border border-slate-200 rounded-xl text-xs font-bold text-slate-900"
                />
                <p className="text-[11px] text-slate-500 leading-relaxed">
                  Archivage automatique dans l'historique d'audit à 00:00 UTC.
                </p>
              </div>

              <div className="p-4 bg-slate-50 rounded-xl border border-slate-200/80 space-y-3">
                <label className="block text-xs font-bold text-slate-800">
                  Rétention des logs d'heartbeat (en jours)
                </label>
                <input
                  type="number"
                  min="1"
                  max="365"
                  disabled={currentRole !== 'Admin'}
                  value={retentionForm.heartbeatsDays}
                  onChange={(e) => setRetentionForm({ ...retentionForm, heartbeatsDays: Number(e.target.value) })}
                  className="w-full p-2.5 bg-white border border-slate-200 rounded-xl text-xs font-bold text-slate-900"
                />
                <p className="text-[11px] text-slate-500 leading-relaxed">
                  Purge des métriques brutes à 01:00 UTC.
                </p>
              </div>
            </div>

            {currentRole === 'Admin' && (
              <div className="flex justify-end pt-4 border-t border-slate-100">
                <button
                  type="submit"
                  className="px-5 py-2.5 bg-[#D0B335] hover:bg-[#b89d2d] text-slate-950 text-xs font-bold rounded-xl shadow-xs flex items-center gap-1.5"
                >
                  <Save className="w-4 h-4" />
                  Sauvegarder la rétention
                </button>
              </div>
            )}
          </form>
        </div>
      )}

      {/* TAB 4: ENROLLMENT TOKENS */}
      {activeTab === 'tokens' && (
        <div className="bg-white rounded-2xl border border-slate-200/80 shadow-xs overflow-hidden space-y-4 p-6">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-100">
            <div>
              <h4 className="text-sm font-bold text-slate-900 tracking-tight">
                Jetons d'enrôlement générés
              </h4>
              <p className="text-xs text-slate-500">
                Les jetons permettent d'authentifier les nouveaux agents lors de l'installation
              </p>
            </div>

            {currentRole === 'Admin' && (
              <button
                onClick={() => void handleGenerateToken()}
                className="px-4 py-2 bg-[#D0B335] hover:bg-[#b89d2d] text-slate-950 text-xs font-bold rounded-xl shadow-xs flex items-center gap-1.5 cursor-pointer"
              >
                <Plus className="w-4 h-4" />
                Générer un nouveau jeton
              </button>
            )}
          </div>

          {/* Token KPI Summary Bar */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 py-1">
            <div className="p-3 bg-slate-50 border border-slate-200/60 rounded-xl flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-slate-200/70 text-slate-700 flex items-center justify-center font-bold">
                <Key className="w-4 h-4" />
              </div>
              <div>
                <p className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Total Jetons</p>
                <p className="text-base font-black text-slate-900">{enrollmentTokens.length}</p>
              </div>
            </div>

            <div className="p-3 bg-emerald-50/60 border border-emerald-200/60 rounded-xl flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-emerald-100 text-emerald-700 flex items-center justify-center font-bold">
                <CheckCircle2 className="w-4 h-4" />
              </div>
              <div>
                <p className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Jetons Actifs</p>
                <p className="text-base font-black text-emerald-700">
                  {enrollmentTokens.filter((t) => t.status === 'active').length}
                </p>
              </div>
            </div>

            <div className="p-3 bg-blue-50/60 border border-blue-200/60 rounded-xl flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-blue-100 text-blue-700 flex items-center justify-center font-bold">
                <BadgeCheck className="w-4 h-4" />
              </div>
              <div>
                <p className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Consommés</p>
                <p className="text-base font-black text-blue-700">
                  {enrollmentTokens.filter((t) => t.status === 'consumed').length}
                </p>
              </div>
            </div>

            <div className="p-3 bg-slate-100/80 border border-slate-200/80 rounded-xl flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-slate-200 text-slate-600 flex items-center justify-center font-bold">
                <Clock className="w-4 h-4" />
              </div>
              <div>
                <p className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Expirés / Inactifs</p>
                <p className="text-base font-black text-slate-700">
                  {enrollmentTokens.filter((t) => t.status === 'expired').length}
                </p>
              </div>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-slate-50 text-[11px] font-bold text-slate-500 uppercase tracking-wider border-b border-slate-100">
                  <th className="py-3 px-4">Code Jeton</th>
                  <th className="py-3 px-4">Créé par</th>
                  <th className="py-3 px-4">Date de création</th>
                  <th className="py-3 px-4">Date d'expiration</th>
                  <th className="py-3 px-4">Statut</th>
                  <th className="py-3 px-4 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-xs text-slate-700">
                {enrollmentTokens.map((tok) => (
                  <tr key={tok.id} className="hover:bg-slate-50">
                    <td className="py-3.5 px-4 font-mono font-bold text-slate-900">{tok.token}</td>
                    <td className="py-3.5 px-4 font-medium">{tok.createdBy}</td>
                    <td className="py-3.5 px-4 text-slate-400 font-mono">{tok.createdAt}</td>
                    <td className="py-3.5 px-4 text-slate-400 font-mono">{tok.expiresAt}</td>
                    <td className="py-3.5 px-4">
                      <span
                        className={`px-2.5 py-0.5 rounded-full text-[11px] font-bold ${
                          tok.status === 'active'
                            ? 'bg-emerald-100 text-emerald-800'
                            : tok.status === 'consumed'
                            ? 'bg-blue-100 text-blue-800'
                            : 'bg-slate-100 text-slate-500'
                        }`}
                      >
                        {tok.status === 'active'
                          ? 'Actif'
                          : tok.status === 'consumed'
                          ? 'Consommé'
                          : 'Expiré'}
                      </span>
                    </td>
                    <td className="py-3.5 px-4 text-right">
                      <button
                        onClick={() => handleCopyCode(tok.token, tok.id)}
                        className="px-2.5 py-1 bg-slate-100 hover:bg-slate-200 text-slate-800 text-xs font-semibold rounded-lg flex items-center gap-1 ml-auto"
                      >
                        {copiedTokenId === tok.id ? (
                          <Check className="w-3.5 h-3.5 text-emerald-600" />
                        ) : (
                          <Copy className="w-3.5 h-3.5" />
                        )}
                        {copiedTokenId === tok.id ? 'Copié' : 'Copier'}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {activeTab === 'ldap' && <LdapPanel />}

      {activeTab === 'vlan' && <VlanPlanPanel />}

      {activeTab === 'templates' && <MailTemplatesPanel />}

      {activeTab === 'platform' && (
        <div className="bg-white p-6 rounded-2xl border border-slate-200/80 shadow-xs space-y-4">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h3 className="text-sm font-black text-slate-900">Santé plateforme (NFR-010)</h3>
              <p className="text-xs text-slate-500 mt-1">
                Postgres, Redis, VictoriaMetrics, Loki + budgets de latence (FS7).
              </p>
            </div>
            <button
              type="button"
              className="inline-flex items-center gap-1 px-3 py-2 rounded-xl bg-slate-900 text-white text-xs font-bold"
              onClick={async () => {
                try {
                  setPlatformStatus(await settingsService.getPlatformStatus());
                } catch {
                  setPlatformStatus(null);
                }
              }}
            >
              <RefreshCw className="w-3.5 h-3.5" />
              Rafraîchir
            </button>
          </div>
          {!platformStatus ? (
            <p className="text-xs text-slate-500">Impossible de charger le statut.</p>
          ) : (
            <>
              <p className="text-sm font-bold">
                Statut global:{' '}
                <span
                  className={
                    platformStatus.status === 'healthy'
                      ? 'text-emerald-700'
                      : platformStatus.status === 'degraded'
                        ? 'text-amber-700'
                        : 'text-rose-700'
                  }
                >
                  {platformStatus.status}
                </span>
                {platformStatus.checked_at ? (
                  <span className="text-xs font-medium text-slate-400 ml-2">{platformStatus.checked_at}</span>
                ) : null}
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {Object.entries(
                  (platformStatus.components || {}) as Record<string, { status?: string; error?: string }>
                ).map(([name, c]) => (
                  <div key={name} className="p-3 rounded-xl border border-slate-200 bg-slate-50 text-xs">
                    <p className="font-bold uppercase tracking-wide text-slate-600">{name}</p>
                    <p className="mt-1 font-semibold">{c.status}</p>
                    {c.error ? <p className="text-rose-600 mt-1">{c.error}</p> : null}
                  </div>
                ))}
              </div>
              {platformStatus.latency && (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2">
                  {(['collect_to_ingest', 'detect_to_notify', 'page_load', 'api_rtt'] as const).map((key) => {
                    const row = platformStatus.latency?.[key];
                    if (!row) return null;
                    return (
                      <div key={key} className="p-3 rounded-xl border border-slate-200 text-xs">
                        <p className="font-bold text-slate-700">{key}</p>
                        <p className="mt-1">
                          n={row.count ?? 0} · p95={row.p95_s ?? '—'}s · budget={row.budget_s ?? '—'}s ·{' '}
                          {row.within_budget == null ? 'n/a' : row.within_budget ? 'OK' : 'BREACH'}
                        </p>
                      </div>
                    );
                  })}
                </div>
              )}
            </>
          )}
        </div>
      )}

        </div>
      </div>

      {/* New Token Modal */}
      <Modal
        isOpen={tokenModalOpen}
        onClose={() => setTokenModalOpen(false)}
        title="Nouveau jeton d'enrôlement généré"
        footer={
          <button
            onClick={() => setTokenModalOpen(false)}
            className="px-4 py-2 bg-slate-900 text-white text-xs font-bold rounded-xl"
          >
            Fermer
          </button>
        }
      >
        <div className="space-y-4">
          <p className="text-xs text-slate-600">
            Ce jeton est valide pendant 24 heures et permet l'enrôlement automatique d'un nouvel agent dans le parc informatique de la CBC.
          </p>

          <div className="p-4 bg-slate-900 rounded-xl text-center">
            <span className="text-xs text-slate-400 block mb-1">Code du jeton</span>
            <div className="text-lg font-mono font-bold text-[#D0B335] tracking-widest">
              {currentTokenCode}
            </div>
          </div>
        </div>
      </Modal>
    </div>
  );
};
