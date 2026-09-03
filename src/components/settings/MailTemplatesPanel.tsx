/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Eye, Mail, RotateCcw, Save, Send, Webhook } from 'lucide-react';
import { MailTemplate, mailTemplatesService } from '../../services/api/settings.service';
import { useApp } from '../../context/AppContext';

/**
 * Réglage du courriel par vérification, et essai du canal n8n (point 8).
 *
 * Un gabarit par vérification : « disque plein » et « service arrêté » ne se
 * racontent pas de la même façon, et un courriel unique pour tout obligerait
 * le lecteur à deviner ce qui s'est passé.
 *
 * L'aperçu rend le gabarit sans rien envoyer. Sans lui, la première alerte
 * réelle sert de test — au plus mauvais moment, et devant les destinataires.
 *
 * Le webhook signé est le canal par lequel n8n est déclenché. Son essai porte
 * `test: true` pour qu'un scénario puisse le reconnaître et ne pas le traiter
 * comme un incident.
 */

const KIND_LABEL: Record<string, string> = {
  alert: 'Alertes',
  task: 'Actions',
  system: 'Système',
};

export const MailTemplatesPanel: React.FC = () => {
  const { currentRole, addToast } = useApp();
  const isAdmin = currentRole === 'Admin';

  const [rows, setRows] = useState<MailTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<string | null>(null);
  const [subject, setSubject] = useState('');
  const [bodyHtml, setBodyHtml] = useState('');
  const [preview, setPreview] = useState<{ subject: string; body_html: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      const data = await mailTemplatesService.list();
      setRows(data.filter((r) => r.scope === 'global'));
    } catch {
      setError('Gabarits indisponibles.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  const grouped = useMemo(() => {
    const out: Record<string, MailTemplate[]> = {};
    for (const r of rows) (out[r.kind] ||= []).push(r);
    return out;
  }, [rows]);

  const current = rows.find((r) => `${r.kind}/${r.event_key}` === selected) || null;

  const open = (row: MailTemplate) => {
    setSelected(`${row.kind}/${row.event_key}`);
    setSubject(row.subject);
    setBodyHtml(row.body_html);
    setPreview(null);
    setError(null);
  };

  const onPreview = async () => {
    setBusy(true);
    setError(null);
    try {
      setPreview(await mailTemplatesService.preview(subject, bodyHtml));
    } catch {
      setError('Aperçu impossible.');
    } finally {
      setBusy(false);
    }
  };

  const onSave = async () => {
    if (!current) return;
    setBusy(true);
    setError(null);
    try {
      await mailTemplatesService.save({
        kind: current.kind,
        event_key: current.event_key,
        subject,
        body_html: bodyHtml,
      });
      await reload();
      addToast({ type: 'success', title: 'Gabarit enregistré', message: current.event_key });
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Enregistrement impossible.');
    } finally {
      setBusy(false);
    }
  };

  const onReset = async () => {
    if (!current) return;
    setBusy(true);
    try {
      await mailTemplatesService.reset(current.kind, current.event_key);
      const fresh = await mailTemplatesService.list();
      setRows(fresh.filter((r) => r.scope === 'global'));
      const restored = fresh.find(
        (r) => r.kind === current.kind && r.event_key === current.event_key && r.scope === 'global'
      );
      if (restored) {
        setSubject(restored.subject);
        setBodyHtml(restored.body_html);
      }
      setPreview(null);
      addToast({ type: 'success', title: 'Gabarit livré rétabli', message: current.event_key });
    } catch {
      setError('Rétablissement impossible.');
    } finally {
      setBusy(false);
    }
  };

  const onTestWebhook = async () => {
    setBusy(true);
    try {
      const res = await mailTemplatesService.testWebhook();
      addToast({ type: 'success', title: 'Webhook reçu', message: res.url });
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
      addToast({
        type: 'error',
        title: 'Webhook non abouti',
        message: typeof detail === 'string' ? detail : 'Vérifier la configuration.',
      });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-5">
      <div className="cbc-card p-5 flex items-start justify-between gap-4 flex-wrap">
        <div className="flex items-start gap-3 min-w-0">
          <Webhook className="w-5 h-5 text-[#A68523] shrink-0 mt-0.5" />
          <div>
            <h3 className="text-[14px] font-bold m-0">Déclenchement n8n</h3>
            <p className="text-[12.5px] text-[var(--color-tx2)] mt-1.5 mb-0 max-w-2xl">
              Chaque alerte est postée sur le webhook signé (HMAC) configuré dans
              Intégrations. C’est le canal par lequel n8n est déclenché. L’essai envoie
              une charge marquée <code className="tnum">test: true</code>, qu’un scénario
              peut reconnaître pour ne pas la traiter comme un incident réel.
            </p>
          </div>
        </div>
        {isAdmin && (
          <button
            type="button"
            disabled={busy}
            onClick={() => void onTestWebhook()}
            className="cbc-btn-secondary py-2 px-3.5 text-[12.5px] inline-flex items-center gap-2 disabled:opacity-50"
          >
            <Send className="w-3.5 h-3.5" />
            Tester le webhook
          </button>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[300px_1fr] gap-5">
        <div className="cbc-card overflow-hidden self-start">
          <div className="px-4 py-3 border-b border-[var(--color-ln2)] flex items-center gap-2">
            <Mail className="w-4 h-4 text-[var(--color-tx3)]" />
            <span className="text-[13px] font-bold">Vérifications</span>
          </div>
          {loading ? (
            <p className="px-4 py-4 text-[12.5px] text-[var(--color-tx2)] m-0">Chargement…</p>
          ) : (
            <div className="max-h-[460px] overflow-y-auto">
              {Object.entries(grouped).map(([kind, list]) => (
                <div key={kind}>
                  <div className="px-4 py-1.5 bg-[var(--color-ln2)] text-[10.5px] font-bold uppercase tracking-wider text-[var(--color-tx3)]">
                    {KIND_LABEL[kind] || kind}
                  </div>
                  {list.map((row) => {
                    const id = `${row.kind}/${row.event_key}`;
                    return (
                      <button
                        key={id}
                        type="button"
                        onClick={() => open(row)}
                        className={`w-full text-left px-4 py-2 text-[12.5px] border-b border-[var(--color-ln2)] hover:bg-[var(--color-ln2)] ${
                          selected === id ? 'bg-amber-50/60 font-semibold' : ''
                        }`}
                      >
                        <span className="tnum">{row.event_key}</span>
                        {row.description && (
                          <span className="block text-[11.5px] text-[var(--color-tx2)]">{row.description}</span>
                        )}
                      </button>
                    );
                  })}
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="cbc-card p-5">
          {!current ? (
            <p className="text-[12.5px] text-[var(--color-tx2)] m-0">
              Choisir une vérification pour régler le courriel qu’elle envoie.
            </p>
          ) : (
            <>
              <div className="flex items-center justify-between gap-3 flex-wrap mb-4">
                <h3 className="text-[14px] font-bold m-0 tnum">
                  {current.kind} / {current.event_key}
                </h3>
                {isAdmin && (
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => void onPreview()}
                      className="cbc-btn-secondary py-1.5 px-3 text-[12.5px] inline-flex items-center gap-1.5 disabled:opacity-50"
                    >
                      <Eye className="w-3.5 h-3.5" />
                      Aperçu
                    </button>
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => void onReset()}
                      className="cbc-btn-secondary py-1.5 px-3 text-[12.5px] inline-flex items-center gap-1.5 disabled:opacity-50"
                      title="Revient au gabarit livré avec le produit"
                    >
                      <RotateCcw className="w-3.5 h-3.5" />
                      Rétablir
                    </button>
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => void onSave()}
                      className="cbc-btn-primary py-1.5 px-3 text-[12.5px] inline-flex items-center gap-1.5 disabled:opacity-50"
                    >
                      <Save className="w-3.5 h-3.5" />
                      Enregistrer
                    </button>
                  </div>
                )}
              </div>

              <label className="block text-[11px] font-semibold uppercase tracking-wider text-[var(--color-tx3)] mb-1.5">
                Objet
              </label>
              <input
                value={subject}
                disabled={!isAdmin || busy}
                onChange={(e) => setSubject(e.target.value)}
                className="cbc-input py-1.5 text-[13px] w-full"
              />

              <label className="block text-[11px] font-semibold uppercase tracking-wider text-[var(--color-tx3)] mt-4 mb-1.5">
                Corps (HTML)
              </label>
              <textarea
                value={bodyHtml}
                disabled={!isAdmin || busy}
                onChange={(e) => setBodyHtml(e.target.value)}
                rows={12}
                className="cbc-input py-2 text-[12px] w-full font-mono"
              />
              <p className="text-[11.5px] text-[var(--color-tx2)] mt-2 mb-0">
                Champs disponibles : <code>{'{hostname}'}</code> <code>{'{severity}'}</code>{' '}
                <code>{'{message}'}</code> <code>{'{value}'}</code> <code>{'{threshold}'}</code>{' '}
                <code>{'{mount}'}</code> <code>{'{timestamp}'}</code>. Un champ inconnu est laissé
                tel quel plutôt que de faire échouer l’envoi.
              </p>

              {error && <p className="text-[12.5px] text-rose-600 mt-3 mb-0">{error}</p>}

              {preview && (
                <div className="mt-5 border-t border-[var(--color-ln2)] pt-4">
                  <div className="text-[10.5px] font-bold uppercase tracking-wider text-[var(--color-tx3)] mb-2">
                    Aperçu — rien n’a été envoyé
                  </div>
                  <div className="text-[13px] font-bold mb-2">{preview.subject}</div>
                  <div
                    className="border border-[var(--color-ln)] rounded-xl p-3 bg-[var(--color-panel)] max-h-[320px] overflow-y-auto"
                    // Contenu produit par la plateforme à partir du gabarit que
                    // l'administrateur vient de saisir : c'est précisément ce
                    // qu'il demande à voir rendu.
                    dangerouslySetInnerHTML={{ __html: preview.body_html }}
                  />
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
};
