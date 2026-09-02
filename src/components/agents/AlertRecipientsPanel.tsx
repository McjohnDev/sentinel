/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useEffect, useState } from 'react';
import { AlertTriangle, Mail, Plus, X } from 'lucide-react';
import { agentsService } from '../../services/api/agents.service';
import { useApp } from '../../context/AppContext';

/**
 * Destinataires des alertes d'un hôte.
 *
 * Le destinataire principal ne se saisit pas : c'est le responsable de l'hôte,
 * ou les membres de l'équipe responsable, dont l'adresse vient de l'annuaire.
 * Une liste tenue à la main divergerait le jour où quelqu'un change de poste,
 * et les alertes partiraient encore vers une personne qui n'a plus la machine
 * en charge — sans que rien ne le signale.
 *
 * La copie, elle, ne se déduit de rien : un prestataire, le métier
 * propriétaire de l'application. Elle se saisit donc ici, hôte par hôte.
 *
 * Le panneau affiche les adresses **résolues**, pas seulement configurées.
 * C'est ce qui rend visible le cas où un hôte sans responsable n'alerte
 * personne : sans cela, l'écran dit « responsable : aucun » et laisse deviner
 * la conséquence, qu'on ne découvre qu'au premier incident manqué.
 */

interface Resolved {
  to: string[];
  cc: string[];
}

interface Props {
  agentId: string;
  /** Copies enregistrées sur l'hôte. */
  cc: string[];
  /** Ce qui partira réellement, responsable et équipe compris. */
  resolved: Resolved;
  canEdit: boolean;
  onSaved: () => void;
}

export const AlertRecipientsPanel: React.FC<Props> = ({
  agentId,
  cc,
  resolved,
  canEdit,
  onSaved,
}) => {
  const { addToast } = useApp();
  const [rows, setRows] = useState<string[]>(cc);
  const [draft, setDraft] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setRows(cc);
  }, [cc]);

  const dirty = rows.join('|') !== cc.join('|');
  const nobody = resolved.to.length === 0;

  const add = () => {
    const address = draft.trim();
    if (!address) return;
    if (!address.includes('@')) {
      addToast({
        type: 'error',
        title: 'Adresse invalide',
        message: `« ${address} » n’est pas une adresse. Le relais rejetterait le message entier.`,
      });
      return;
    }
    if (rows.some((r) => r.toLowerCase() === address.toLowerCase())) {
      setDraft('');
      return;
    }
    setRows([...rows, address]);
    setDraft('');
  };

  const save = async () => {
    setBusy(true);
    try {
      await agentsService.patch(agentId, { alert_cc: rows });
      addToast({ type: 'success', title: 'Copies enregistrées', message: `${rows.length} adresse(s).` });
      onSaved();
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
      addToast({
        type: 'error',
        title: 'Enregistrement impossible',
        message: typeof detail === 'string' ? detail : 'Vérifier les adresses saisies.',
      });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="cbc-card p-5">
      <div className="flex items-center gap-2 mb-1">
        <Mail className="w-4 h-4 text-[#A68523]" />
        <h3 className="text-[14px] font-extrabold tracking-tight m-0">Destinataires des alertes</h3>
      </div>
      <p className="text-[12px] text-slate-500 mt-0 mb-4">
        Le destinataire principal vient du responsable de l’hôte et de l’équipe
        responsable — leur adresse est celle de l’annuaire. Seules les copies se
        saisissent ici.
      </p>

      {nobody ? (
        <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 flex items-start gap-2.5 mb-4">
          <AlertTriangle className="w-4 h-4 text-rose-700 shrink-0 mt-0.5" />
          <p className="text-[12px] text-rose-900 m-0">
            <strong>Aucune alerte ne partira pour cet hôte.</strong> Il n’a ni
            responsable ni équipe responsable, et aucune liste de secours n’est
            configurée. L’envoi échoue avant même que le relais soit sollicité :
            ce n’est pas une panne de messagerie. Attribuer un responsable
            ci-dessus.
          </p>
        </div>
      ) : (
        <div className="mb-4">
          <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-1.5">
            Destinataires
          </div>
          <div className="flex flex-wrap gap-1.5">
            {resolved.to.map((address) => (
              <span
                key={address}
                className="inline-flex items-center px-2 py-1 rounded-lg bg-emerald-50 border border-emerald-200 text-[12px] text-emerald-900"
              >
                {address}
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-1.5">
        En copie
      </div>

      {rows.length === 0 ? (
        <p className="text-[12.5px] text-slate-500 m-0 mb-3">Personne en copie.</p>
      ) : (
        <div className="flex flex-wrap gap-1.5 mb-3">
          {rows.map((address) => (
            <span
              key={address}
              className="inline-flex items-center gap-1.5 px-2 py-1 rounded-lg bg-slate-100 border border-slate-200 text-[12px]"
            >
              {address}
              {canEdit && (
                <button
                  type="button"
                  onClick={() => setRows(rows.filter((r) => r !== address))}
                  className="text-slate-400 hover:text-rose-600"
                  title="Retirer"
                >
                  <X className="w-3 h-3" />
                </button>
              )}
            </span>
          ))}
        </div>
      )}

      {canEdit && (
        <>
          <div className="flex items-center gap-2">
            <input
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  add();
                }
              }}
              placeholder="prestataire@exemple.cm"
              className="cbc-input py-1.5 text-[12.5px] flex-1"
            />
            <button
              type="button"
              onClick={add}
              className="cbc-btn-secondary py-1.5 px-3 text-[12.5px] inline-flex items-center gap-1.5"
            >
              <Plus className="w-3.5 h-3.5" />
              Ajouter
            </button>
          </div>

          {dirty && (
            <div className="flex justify-end mt-3">
              <button
                type="button"
                disabled={busy}
                onClick={() => void save()}
                className="cbc-btn-primary py-2 px-4 text-[12.5px] disabled:opacity-50"
              >
                {busy ? 'Enregistrement…' : 'Enregistrer les copies'}
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
};
