/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useCallback, useEffect, useState } from 'react';
import { PlugZap, RefreshCw, Search, ShieldCheck } from 'lucide-react';
import { settingsService } from '../../services/api/settings.service';
import { useApp } from '../../context/AppContext';

type LdapSettings = Awaited<ReturnType<typeof settingsService.getLdapSettings>>;
type ProbeResult = Awaited<ReturnType<typeof settingsService.probeLdapUser>>;

const ROLE_LABELS: Record<string, string> = {
  admin: 'Administrateur',
  operator: 'Opérateur',
  security: 'Sécurité',
  read_only: 'Lecture seule',
};

/**
 * Panneau d'annuaire (LDAP / Active Directory).
 *
 * La configuration se fait par variables d'environnement du serveur : les
 * secrets (mot de passe du compte de service) ne transitent donc jamais par
 * l'interface, et le serveur ne les renvoie pas. Cet écran sert à *vérifier*
 * la configuration en place — joignabilité, filtre, correspondance des
 * groupes — avant d'ouvrir l'authentification annuaire aux utilisateurs.
 */
export const LdapPanel: React.FC = () => {
  const { addToast, currentRole } = useApp();

  const [settings, setSettings] = useState<LdapSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ ok: boolean; stage: string; detail: string } | null>(null);

  const [probeName, setProbeName] = useState('');
  const [probing, setProbing] = useState(false);
  const [probeResult, setProbeResult] = useState<ProbeResult | null>(null);

  type Mapping = Awaited<ReturnType<typeof settingsService.listLdapRoleMappings>>['data'][number];
  const [mappings, setMappings] = useState<Mapping[]>([]);
  const [newKind, setNewKind] = useState<'group' | 'user'>('group');
  const [newValue, setNewValue] = useState('');
  const [newRole, setNewRole] = useState('operator');
  const [newPriority, setNewPriority] = useState(100);
  const [savingMapping, setSavingMapping] = useState(false);

  const canEdit = currentRole === 'Admin';

  const load = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const [cfg, maps] = await Promise.all([
        settingsService.getLdapSettings(),
        settingsService.listLdapRoleMappings().catch(() => ({ data: [] })),
      ]);
      setSettings(cfg);
      setMappings(maps.data);
    } catch {
      setLoadError("La configuration de l'annuaire n'a pas pu être lue.");
      setSettings(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const runTest = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const result = await settingsService.testLdap();
      setTestResult(result);
      addToast({
        type: result.ok ? 'success' : 'error',
        title: result.ok ? 'Annuaire joignable' : 'Test en échec',
        message: result.detail,
      });
    } catch {
      addToast({ type: 'error', title: 'Test impossible', message: 'Le test n\'a pas pu être lancé.' });
    } finally {
      setTesting(false);
    }
  };

  const runProbe = async () => {
    if (!probeName.trim()) return;
    setProbing(true);
    setProbeResult(null);
    try {
      setProbeResult(await settingsService.probeLdapUser(probeName.trim()));
    } catch (err: any) {
      addToast({
        type: 'error',
        title: 'Résolution impossible',
        message: err?.response?.data?.detail || "Le compte n'a pas pu être résolu.",
      });
    } finally {
      setProbing(false);
    }
  };

  const addMapping = async () => {
    if (!newValue.trim()) return;
    setSavingMapping(true);
    try {
      await settingsService.createLdapRoleMapping({
        kind: newKind,
        value: newValue.trim(),
        role: newRole,
        priority: newPriority,
      });
      setNewValue('');
      await load();
      addToast({
        type: 'success',
        title: 'Correspondance ajoutée',
        message: 'Le rôle sera appliqué à la prochaine connexion.',
      });
    } catch (err: any) {
      addToast({
        type: 'error',
        title: 'Ajout impossible',
        message: err?.response?.data?.detail || "La correspondance n'a pas été enregistrée.",
      });
    } finally {
      setSavingMapping(false);
    }
  };

  const removeMapping = async (id: string) => {
    try {
      await settingsService.deleteLdapRoleMapping(id);
      await load();
      addToast({ type: 'success', title: 'Correspondance supprimée', message: '' });
    } catch {
      addToast({
        type: 'error',
        title: 'Suppression impossible',
        message: "La correspondance n'a pas été supprimée.",
      });
    }
  };

  if (loading) {
    return <div className="cbc-card p-6 text-[13px] text-[var(--color-tx3)]">Chargement…</div>;
  }

  if (loadError || !settings) {
    return (
      <div className="cbc-card p-4 border border-rose-200 bg-rose-50">
        <p className="text-[13px] font-semibold text-rose-800">{loadError}</p>
      </div>
    );
  }

  const statusTone = settings.operational
    ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
    : settings.enabled
      ? 'bg-rose-50 text-rose-800 border-rose-200'
      : 'bg-[var(--color-ln2)] text-[var(--color-tx2)] border-[var(--color-ln)]';

  const statusLabel = settings.operational
    ? 'Opérationnel'
    : settings.enabled
      ? 'Activé mais non opérationnel'
      : 'Désactivé';

  const row = (label: string, value: React.ReactNode) => (
    <div className="flex items-start justify-between gap-4 py-2 border-b border-[var(--color-ln2)] last:border-0">
      <span className="text-[12px] text-[var(--color-tx2)] shrink-0">{label}</span>
      <span className="text-[12.5px] font-semibold text-[var(--color-tx)] text-right break-all">{value}</span>
    </div>
  );

  return (
    <div className="space-y-4">
      <div className="cbc-card p-5">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <h3 className="text-[15px] font-extrabold tracking-tight flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-[#A68523]" />
              Annuaire d'entreprise (LDAP / Active Directory)
            </h3>
            <p className="text-[12.5px] text-[var(--color-tx2)] mt-1 max-w-2xl">
              Les identifiants ne sont jamais stockés par la plateforme :
              l'authentification est une liaison directe à l'annuaire. Le rôle
              est réaligné sur les groupes à chaque connexion.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <span className={`px-2.5 py-1 rounded-lg border text-[11px] font-bold ${statusTone}`}>
              {statusLabel}
            </span>
            <button type="button" className="cbc-btn-secondary" onClick={() => void load()}>
              <RefreshCw className="w-3.5 h-3.5" />
              Actualiser
            </button>
          </div>
        </div>

        {settings.enabled && !settings.library_available && (
          <div className="mt-4 p-3 rounded-xl bg-amber-50 border border-amber-200 text-[12px] text-amber-900">
            Le paquet <code>ldap3</code> n'est pas installé sur le serveur.
            L'authentification annuaire est inactive et les comptes locaux
            restent utilisables.
          </div>
        )}

        <div className="mt-4 grid grid-cols-1 lg:grid-cols-2 gap-x-8">
          <div>
            {row('Serveur', settings.server_uri || <span className="text-[var(--color-tx3)]">non renseigné</span>)}
            {row('Base de recherche', settings.user_search_base || <span className="text-[var(--color-tx3)]">non renseignée</span>)}
            {row('Filtre', <code className="text-[11.5px]">{settings.user_filter}</code>)}
            {row(
              'Compte de service',
              settings.bind_dn_configured ? 'Configuré' : <span className="text-[var(--color-tx3)]">anonyme</span>
            )}
          </div>
          <div>
            {row('LDAPS', settings.use_ssl ? 'Oui' : 'Non')}
            {row('START TLS', settings.start_tls ? 'Oui' : 'Non')}
            {row(
              'Vérification du certificat',
              settings.tls_verify ? (
                'Activée'
              ) : (
                <span className="text-rose-600">Désactivée — test uniquement</span>
              )
            )}
            {row('Rôle par défaut', ROLE_LABELS[settings.default_role] || settings.default_role)}
          </div>
        </div>
      </div>

      <div className="cbc-card p-5">
        <h4 className="text-[13.5px] font-bold mb-1">Correspondance groupes → rôles</h4>
        <p className="text-[12px] text-[var(--color-tx2)] mb-3">
          Le premier groupe correspondant l'emporte. Sans correspondance, le
          rôle par défaut s'applique — volontairement le moins privilégié.
        </p>
        {Object.keys(settings.role_mapping || {}).length === 0 ? (
          <p className="text-[12.5px] text-[var(--color-tx3)]">
            Aucune correspondance définie : tous les comptes d'annuaire
            recevront le rôle « {ROLE_LABELS[settings.default_role] || settings.default_role} ».
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full border-collapse">
              <thead>
                <tr className="bg-[var(--color-ln2)] border-b border-[var(--color-ln)]">
                  <th className="text-left px-3 py-2 text-[10.5px] font-bold uppercase tracking-wider text-[var(--color-tx3)]">
                    Groupe (DN)
                  </th>
                  <th className="text-left px-3 py-2 text-[10.5px] font-bold uppercase tracking-wider text-[var(--color-tx3)]">
                    Rôle attribué
                  </th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(settings.role_mapping as Record<string, string>).map(([dn, role]) => (
                  <tr key={dn} className="border-b border-[var(--color-ln2)]">
                    <td className="p-3 text-[12px] font-mono break-all">{dn}</td>
                    <td className="p-3 text-[12.5px] font-semibold">{ROLE_LABELS[role] || role}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="cbc-card p-5">
        <h4 className="text-[13.5px] font-bold mb-1">Attribution des rôles</h4>
        <p className="text-[12px] text-[var(--color-tx2)] mb-4 max-w-3xl">
          Ces correspondances sont propres à cette application : elles sont
          enregistrées dans sa base, <strong>aucun groupe n'a à être créé dans
          Active Directory</strong> et le compte de service reste en lecture
          seule. Un compte d'annuaire sans correspondance ne reçoit que la
          consultation. La priorité la plus basse l'emporte ; à priorité égale,
          une attribution nominative prime sur un groupe.
        </p>

        {mappings.length === 0 ? (
          <p className="text-[12.5px] text-[var(--color-tx3)] mb-4">
            Aucune correspondance : tous les comptes d'annuaire sont en lecture
            seule et l'administration reste assurée par les comptes locaux.
          </p>
        ) : (
          <div className="overflow-x-auto mb-4">
            <table className="w-full border-collapse">
              <thead>
                <tr className="bg-[var(--color-ln2)] border-b border-[var(--color-ln)]">
                  {['Type', 'Identité', 'Rôle', 'Priorité', ''].map((c) => (
                    <th
                      key={c || 'act'}
                      className="text-left px-3 py-2 text-[10.5px] font-bold uppercase tracking-wider text-[var(--color-tx3)] whitespace-nowrap"
                    >
                      {c}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {mappings.map((m) => (
                  <tr key={m.id} className="border-b border-[var(--color-ln2)]">
                    <td className="p-3 text-[12px]">{m.kind === 'user' ? 'Compte' : 'Groupe'}</td>
                    <td className="p-3 text-[12px] font-mono break-all">{m.value}</td>
                    <td className="p-3 text-[12.5px] font-semibold">
                      {ROLE_LABELS[m.role] || m.role}
                    </td>
                    <td className="p-3 tnum text-[12.5px]">{m.priority}</td>
                    <td className="p-3 text-right">
                      {canEdit && (
                        <button
                          type="button"
                          className="text-[12px] font-semibold text-rose-600 hover:underline"
                          onClick={() => void removeMapping(m.id)}
                        >
                          Retirer
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {canEdit && (
          <div className="flex flex-wrap gap-2 items-center pt-3 border-t border-[var(--color-ln2)]">
            <select
              value={newKind}
              onChange={(e) => setNewKind(e.target.value as 'group' | 'user')}
              className="px-2.5 py-2 bg-[var(--color-panel)] border border-[var(--color-ln)] rounded-xl text-xs font-semibold"
            >
              <option value="group">Groupe (DN)</option>
              <option value="user">Compte (identifiant)</option>
            </select>
            <input
              type="text"
              value={newValue}
              onChange={(e) => setNewValue(e.target.value)}
              placeholder={
                newKind === 'group'
                  ? 'CN=Sentinel_Ops,OU=GROUPES,DC=gie,DC=local'
                  : 'jdupont'
              }
              className="flex-1 min-w-[260px] px-3 py-2 bg-[var(--color-panel)] border border-[var(--color-ln)] rounded-xl text-xs focus:outline-none focus:ring-2 focus:ring-[#D0B335]"
            />
            <select
              value={newRole}
              onChange={(e) => setNewRole(e.target.value)}
              className="px-2.5 py-2 bg-[var(--color-panel)] border border-[var(--color-ln)] rounded-xl text-xs font-semibold"
            >
              <option value="admin">Administrateur</option>
              <option value="operator">Opérateur</option>
              <option value="security">Sécurité</option>
              <option value="read_only">Lecture seule</option>
            </select>
            <input
              type="number"
              value={newPriority}
              onChange={(e) => setNewPriority(Number(e.target.value) || 100)}
              className="w-[90px] px-3 py-2 bg-[var(--color-panel)] border border-[var(--color-ln)] rounded-xl text-xs"
              title="Priorité — la plus basse l'emporte"
            />
            <button
              type="button"
              className="cbc-btn-secondary"
              onClick={() => void addMapping()}
              disabled={savingMapping || !newValue.trim()}
            >
              Ajouter
            </button>
          </div>
        )}
      </div>

      <div className="cbc-card p-5">
        <h4 className="text-[13.5px] font-bold mb-3">Vérifications</h4>

        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            className="cbc-btn-secondary"
            onClick={() => void runTest()}
            disabled={!canEdit || testing || !settings.enabled}
          >
            <PlugZap className="w-3.5 h-3.5" />
            {testing ? 'Test en cours…' : 'Tester la connexion'}
          </button>
          {!settings.enabled && (
            <span className="text-[12px] text-[var(--color-tx3)]">
              Activer <code>LDAP_ENABLED</code> côté serveur pour lancer un test.
            </span>
          )}
        </div>

        {testResult && (
          <div
            className={`mt-3 p-3 rounded-xl border text-[12.5px] ${
              testResult.ok
                ? 'bg-emerald-50 border-emerald-200 text-emerald-900'
                : 'bg-rose-50 border-rose-200 text-rose-900'
            }`}
          >
            <span className="font-bold">{testResult.ok ? 'Succès' : 'Échec'}</span>
            {' · '}
            <span className="font-mono text-[11.5px]">{testResult.stage}</span>
            <div className="mt-1">{testResult.detail}</div>
          </div>
        )}

        <div className="mt-5 pt-4 border-t border-[var(--color-ln2)]">
          <h5 className="text-[12.5px] font-bold mb-1">Résoudre un compte</h5>
          <p className="text-[12px] text-[var(--color-tx2)] mb-3">
            Valide le filtre et la correspondance des groupes avant d'ouvrir
            l'authentification aux utilisateurs. Aucun mot de passe n'est
            demandé : le compte n'est pas authentifié, seulement résolu.
          </p>
          <div className="flex flex-wrap gap-2">
            <input
              type="text"
              value={probeName}
              onChange={(e) => setProbeName(e.target.value)}
              placeholder="Identifiant annuaire (ex: j.dupont)"
              className="flex-1 min-w-[220px] px-3 py-2 bg-[var(--color-panel)] border border-[var(--color-ln)] rounded-xl text-xs focus:outline-none focus:ring-2 focus:ring-[#D0B335]"
            />
            <button
              type="button"
              className="cbc-btn-secondary"
              onClick={() => void runProbe()}
              disabled={!canEdit || probing || !probeName.trim() || !settings.operational}
            >
              <Search className="w-3.5 h-3.5" />
              {probing ? 'Recherche…' : 'Résoudre'}
            </button>
          </div>

          {probeResult && (
            <div className="mt-3 p-3 rounded-xl border border-[var(--color-ln)] bg-[var(--color-ln2)] text-[12.5px]">
              {!probeResult.found ? (
                <span className="text-rose-700 font-semibold">
                  {probeResult.detail || 'Compte introuvable'}
                </span>
              ) : (
                <div className="space-y-1">
                  {row('Identifiant', probeResult.username)}
                  {row('Nom affiché', probeResult.display_name || '—')}
                  {row('Courriel', probeResult.email || '—')}
                  {row('DN', <span className="font-mono text-[11.5px]">{probeResult.dn}</span>)}
                  {row(
                    'Rôle attribué',
                    <span className="font-bold text-[#8D771B]">
                      {ROLE_LABELS[probeResult.resolved_role || ''] || probeResult.resolved_role}
                    </span>
                  )}
                  {row('Groupes', probeResult.groups?.length ? probeResult.groups.length : '0')}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
