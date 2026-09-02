/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useCallback, useEffect, useState } from 'react';
import { KeyRound, Save, Send, Server, ShieldAlert } from 'lucide-react';
import { SmtpConfig, smtpService } from '../../services/api/settings.service';
import { useApp } from '../../context/AppContext';

/**
 * Services d'alerte : relais SMTP interne.
 *
 * Second canal, à côté de l'API Mail CBC et du webhook signé. Les trois
 * coexistent délibérément — une plateforme de supervision qui perd sa seule
 * voie de notification devient muette au moment précis où elle doit parler.
 *
 * Le mot de passe n'est jamais réaffiché : l'API ne le rend pas, et le champ
 * reste vide à l'ouverture. Laisser le champ vide conserve le mot de passe
 * enregistré ; il faut le saisir pour le remplacer.
 */

const ENCRYPTIONS = [
  { value: 'none', label: 'Aucun (port 25 en clair)' },
  { value: 'starttls', label: 'STARTTLS (587)' },
  { value: 'ssl', label: 'SSL/TLS (465)' },
];

export const AlertServicesPanel: React.FC = () => {
  const { currentRole, addToast } = useApp();
  const isAdmin = currentRole === 'Admin';

  const [cfg, setCfg] = useState<SmtpConfig | null>(null);
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      setCfg(await smtpService.get());
    } catch {
      setError('Configuration SMTP indisponible.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  const patch = (next: Partial<SmtpConfig>) => setCfg((c) => (c ? { ...c, ...next } : c));

  const onSave = async () => {
    if (!cfg) return;
    setBusy(true);
    setError(null);
    try {
      const saved = await smtpService.save({
        enabled: cfg.enabled,
        host: cfg.host || '',
        port: cfg.port,
        auth: cfg.auth,
        username: cfg.username || '',
        encryption: cfg.encryption,
        from_address: cfg.from_address || '',
        from_name: cfg.from_name || '',
        // Champ laissé vide = mot de passe conservé. L'envoyer vide
        // l'effacerait à chaque enregistrement.
        ...(password ? { password } : {}),
      });
      setCfg(saved);
      setPassword('');
      addToast({ type: 'success', title: 'Relais SMTP enregistré', message: saved.host || '' });
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Enregistrement impossible.');
    } finally {
      setBusy(false);
    }
  };

  const onTest = async () => {
    setBusy(true);
    try {
      const res = await smtpService.test();
      addToast({ type: 'success', title: 'Courriel d’essai envoyé', message: res.to });
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
      addToast({
        type: 'error',
        title: 'Essai non abouti',
        message: typeof detail === 'string' ? detail : 'Vérifier le relais.',
      });
    } finally {
      setBusy(false);
    }
  };

  if (loading) {
    return <div className="cbc-card p-6 text-[12.5px] text-slate-500">Chargement…</div>;
  }
  if (!cfg) {
    return <div className="cbc-card p-6 text-[12.5px] text-slate-500">{error || 'Indisponible.'}</div>;
  }

  const plaintextAuth = cfg.auth && cfg.encryption === 'none';

  return (
    <div className="space-y-5">
      <div className="cbc-card p-6">
        <div className="flex items-start gap-4">
          <div className="w-10 h-10 rounded-xl bg-amber-50 text-[#A68523] grid place-items-center shrink-0">
            <Server className="w-5 h-5" />
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex items-center justify-between gap-3 flex-wrap">
              <h3 className="text-[15px] font-extrabold tracking-tight m-0">Relais SMTP interne</h3>
              <label className="inline-flex items-center gap-2 text-[12.5px] font-semibold">
                <input
                  type="checkbox"
                  checked={cfg.enabled}
                  disabled={!isAdmin || busy}
                  onChange={(e) => patch({ enabled: e.target.checked })}
                />
                Activé
              </label>
            </div>
            <p className="text-[12.5px] text-slate-600 mt-2 mb-0 max-w-3xl">
              Second canal de notification, à côté de l’API Mail CBC et du webhook n8n.
              Les trois coexistent volontairement : un relais interne reste joignable
              quand l’API est en panne, et inversement.
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-5">
          <Field label="Serveur">
            <input
              value={cfg.host || ''}
              disabled={!isAdmin || busy}
              placeholder="smtp.exemple.local"
              onChange={(e) => patch({ host: e.target.value })}
              className="cbc-input py-1.5 text-[13px] w-full tnum"
            />
          </Field>
          <Field label="Port">
            <input
              type="number"
              value={cfg.port}
              disabled={!isAdmin || busy}
              onChange={(e) => patch({ port: Number(e.target.value) })}
              className="cbc-input py-1.5 text-[13px] w-full tnum"
            />
          </Field>
          <Field label="Chiffrement">
            <select
              value={cfg.encryption}
              disabled={!isAdmin || busy}
              onChange={(e) => patch({ encryption: e.target.value })}
              className="cbc-input py-1.5 text-[13px] w-full"
            >
              {ENCRYPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Authentification">
            <label className="inline-flex items-center gap-2 text-[12.5px] mt-2">
              <input
                type="checkbox"
                checked={cfg.auth}
                disabled={!isAdmin || busy}
                onChange={(e) => patch({ auth: e.target.checked })}
              />
              Le relais exige un compte
            </label>
          </Field>

          {cfg.auth && (
            <>
              <Field label="Identifiant">
                <input
                  value={cfg.username || ''}
                  disabled={!isAdmin || busy}
                  onChange={(e) => patch({ username: e.target.value })}
                  className="cbc-input py-1.5 text-[13px] w-full tnum"
                />
              </Field>
              <Field label="Mot de passe">
                <input
                  type="password"
                  value={password}
                  disabled={!isAdmin || busy}
                  placeholder={cfg.password_set ? '•••••••• (inchangé)' : 'non renseigné'}
                  onChange={(e) => setPassword(e.target.value)}
                  className="cbc-input py-1.5 text-[13px] w-full"
                />
                <p className="text-[11px] text-slate-500 mt-1 mb-0">
                  Jamais réaffiché. Laisser vide conserve le mot de passe enregistré.
                </p>
              </Field>
            </>
          )}

          <Field label="Adresse d’expéditeur">
            <input
              value={cfg.from_address || ''}
              disabled={!isAdmin || busy}
              placeholder="sentinel@exemple.com"
              onChange={(e) => patch({ from_address: e.target.value })}
              className="cbc-input py-1.5 text-[13px] w-full tnum"
            />
          </Field>
          <Field label="Nom d’expéditeur">
            <input
              value={cfg.from_name || ''}
              disabled={!isAdmin || busy}
              placeholder="Sentinel"
              onChange={(e) => patch({ from_name: e.target.value })}
              className="cbc-input py-1.5 text-[13px] w-full"
            />
          </Field>
        </div>

        {plaintextAuth && (
          <div className="mt-4 p-3 rounded-xl bg-amber-50 border border-amber-200 flex items-start gap-2.5">
            <ShieldAlert className="w-4 h-4 text-amber-700 shrink-0 mt-0.5" />
            <p className="text-[12px] text-amber-900 m-0">
              Authentification demandée sans chiffrement : l’identifiant et le mot de
              passe circulent en clair sur le réseau. Acceptable sur un lien interne
              maîtrisé ; préférer STARTTLS si le relais le propose.
            </p>
          </div>
        )}

        {error && <p className="text-[12.5px] text-rose-600 mt-3 mb-0">{error}</p>}

        {isAdmin && (
          <div className="flex items-center gap-2.5 mt-5">
            <button
              type="button"
              disabled={busy}
              onClick={() => void onSave()}
              className="cbc-btn-primary py-2 px-3.5 text-[12.5px] inline-flex items-center gap-2 disabled:opacity-50"
            >
              <Save className="w-3.5 h-3.5" />
              Enregistrer
            </button>
            <button
              type="button"
              disabled={busy || !cfg.enabled}
              onClick={() => void onTest()}
              title={cfg.enabled ? 'Envoie un courriel d’essai' : 'Activer le relais d’abord'}
              className="cbc-btn-secondary py-2 px-3.5 text-[12.5px] inline-flex items-center gap-2 disabled:opacity-50"
            >
              <Send className="w-3.5 h-3.5" />
              Envoyer un essai
            </button>
          </div>
        )}
      </div>

      <div className="cbc-card p-5 flex items-start gap-3">
        <KeyRound className="w-4 h-4 text-slate-400 shrink-0 mt-0.5" />
        <p className="text-[12.5px] text-slate-600 m-0">
          Les autres canaux se règlent ailleurs : l’<strong>API Mail CBC</strong> dans
          « Notifications API CBC », le <strong>webhook signé qui déclenche n8n</strong>{' '}
          dans « Courriels par vérification », où se trouve aussi son essai.
        </p>
      </div>
    </div>
  );
};

const Field: React.FC<{ label: string; children: React.ReactNode }> = ({ label, children }) => (
  <div>
    <label className="block text-[11px] font-semibold uppercase tracking-wider text-slate-400 mb-1.5">
      {label}
    </label>
    {children}
  </div>
);
