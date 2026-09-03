/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Mail, KeyRound, Workflow, MessageSquare } from 'lucide-react';
import { useApp } from '../context/AppContext';
import { PageHeader } from '../components/layout/PageHeader';

/**
 * Intégrations sortantes.
 *
 * Cet écran affichait « Opérationnel » et « Dernier ping 4 s » pour des
 * intégrations qui n'avaient jamais été contactées : l'état était dérivé d'un
 * simple drapeau de configuration, et l'hôte « smtp.cbcam.cm:587 · STARTTLS »
 * était codé en dur alors que la plateforme n'envoie pas de SMTP — elle passe
 * par l'API Mail CBC.
 *
 * Un canal *configuré* n'est pas un canal *joignable*. La distinction est
 * faite explicitement ici : cet écran rend compte de la configuration, et
 * renvoie vers les emplacements où l'état réel est mesuré (santé plateforme,
 * statut de livraison porté par chaque alerte).
 */
export const IntegrationsView: React.FC = () => {
  const { messagingConfig, currentRole } = useApp();
  const navigate = useNavigate();

  const mailConfigured = Boolean(messagingConfig.enabled && messagingConfig.apiEndpoint);
  const webhookConfigured = Boolean(messagingConfig.webhookEnabled && messagingConfig.webhookUrl);
  const recipients = messagingConfig.recipients?.length
    ? messagingConfig.recipients.join(' · ')
    : null;

  const cards = [
    {
      icon: Mail,
      title: 'API Mail CBC',
      configured: mailConfigured,
      lines: [
        messagingConfig.apiEndpoint || 'Aucun point d’accès renseigné',
        recipients ? `Destinataires — ${recipients}` : 'Aucun destinataire configuré',
        "L'état de livraison réel est porté par chaque alerte (colonne Notif.)",
      ],
    },
    {
      icon: KeyRound,
      title: 'Webhook signé (HMAC)',
      configured: webhookConfigured,
      lines: [
        messagingConfig.webhookUrl || 'Aucune URL renseignée',
        webhookConfigured ? 'Secret HMAC défini (jamais affiché)' : 'Aucun secret défini',
        'Signature X-CBC-Signature sur chaque envoi',
      ],
    },
    {
      icon: Workflow,
      title: 'n8n',
      configured: false,
      planned: 'Lot 2',
      lines: [
        'Aucun runtime n8n raccordé à cette plateforme',
        'Un système externe peut déjà consommer le webhook signé',
      ],
    },
    {
      icon: MessageSquare,
      title: 'SMS',
      configured: false,
      planned: 'Hors périmètre Lot 1',
      lines: [
        'Aucun fournisseur SMS intégré',
        'Peut être raccordé via le webhook signé',
      ],
    },
  ];

  return (
    <div className="space-y-5">
      <PageHeader
        title="Intégrations"
        subtitle="Canaux sortants — état de configuration."
      />

      <div className="p-3.5 bg-[var(--color-ln2)] border border-[var(--color-ln)] rounded-2xl text-[12.5px] text-[var(--color-tx2)]">
        Cet écran indique ce qui est <strong>configuré</strong>. Un canal
        configuré n'est pas nécessairement joignable : l'état de livraison réel
        figure sur chaque alerte, et la santé des composants dans{' '}
        <button
          type="button"
          className="font-semibold text-[#A68523] hover:underline"
          onClick={() => navigate('/settings')}
        >
          Paramètres → Plateforme
        </button>
        .
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {cards.map((card) => {
          const Icon = card.icon;
          return (
            <div key={card.title} className="cbc-card p-5">
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-2.5 min-w-0">
                  <div className="w-9 h-9 rounded-xl bg-[var(--color-ln2)] text-[var(--color-tx2)] grid place-items-center shrink-0">
                    <Icon className="w-4 h-4" />
                  </div>
                  <h3 className="text-[14px] font-extrabold tracking-tight truncate">{card.title}</h3>
                </div>
                <span
                  className={`px-2 py-0.5 rounded-md border text-[10.5px] font-bold shrink-0 ${
                    card.configured
                      ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
                      : 'bg-[var(--color-ln2)] text-[var(--color-tx2)] border-[var(--color-ln)]'
                  }`}
                >
                  {card.configured ? 'Configuré' : card.planned || 'Non configuré'}
                </span>
              </div>
              <ul className="mt-3 space-y-1.5">
                {card.lines.map((line) => (
                  <li key={line} className="text-[12.5px] text-[var(--color-tx2)] break-all">
                    {line}
                  </li>
                ))}
              </ul>
            </div>
          );
        })}
      </div>

      {currentRole === 'Admin' && (
        <button
          type="button"
          className="cbc-btn-secondary"
          onClick={() => navigate('/settings')}
        >
          Configurer les notifications
        </button>
      )}
    </div>
  );
};
