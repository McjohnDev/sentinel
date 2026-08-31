/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import { Construction, ExternalLink } from 'lucide-react';
import { PageHeader } from '../layout/PageHeader';

export interface PlannedCapabilityProps {
  title: string;
  subtitle: string;
  /** Référence au plan (ex. « Lot 2 — FS9+ »). */
  lot: string;
  /** Ce que la capacité fera une fois livrée. */
  description: string;
  /** Éléments prévus, formulés au futur — jamais comme un état actuel. */
  planned: string[];
  /** Ce qui existe déjà et couvre partiellement le besoin, si applicable. */
  availableToday?: Array<{ label: string; hint: string }>;
  /** Prérequis côté client ou infrastructure. */
  prerequisites?: string[];
}

/**
 * Écran de capacité planifiée mais non livrée.
 *
 * Plusieurs écrans présentaient des fonctionnalités inexistantes comme si
 * elles fonctionnaient : listes de scénarios avec un historique d'exécution
 * inventé, indicateurs « Opérationnel » et « Dernier ping 4 s » codés en dur
 * pour des intégrations jamais contactées, boutons de publication affichant un
 * message de succès sans rien envoyer.
 *
 * Sur un produit de supervision bancaire, un écran qui affirme qu'une
 * automatisation s'est exécutée alors qu'elle n'existe pas est plus dangereux
 * qu'un écran vide : il fonde des décisions d'exploitation sur une fiction.
 * Ce composant annonce la capacité, son périmètre et son lot, sans jamais
 * afficher d'état d'exécution.
 */
export const PlannedCapability: React.FC<PlannedCapabilityProps> = ({
  title,
  subtitle,
  lot,
  description,
  planned,
  availableToday,
  prerequisites,
}) => (
  <div className="space-y-5">
    <PageHeader title={title} subtitle={subtitle} />

    <div className="cbc-card p-6">
      <div className="flex items-start gap-4">
        <div className="w-10 h-10 rounded-xl bg-amber-50 text-amber-700 grid place-items-center shrink-0">
          <Construction className="w-5 h-5" />
        </div>
        <div className="min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="text-[15px] font-extrabold tracking-tight">Capacité non livrée</h3>
            <span className="px-2 py-0.5 rounded-md bg-slate-100 text-slate-600 border border-slate-200 text-[10.5px] font-bold">
              {lot}
            </span>
          </div>
          <p className="text-[13px] text-slate-600 mt-2 leading-relaxed max-w-3xl">{description}</p>
        </div>
      </div>

      <div className="mt-5 grid grid-cols-1 lg:grid-cols-2 gap-5">
        <div>
          <h4 className="text-[10.5px] font-bold uppercase tracking-wider text-slate-400 mb-2.5">
            Prévu dans ce périmètre
          </h4>
          <ul className="space-y-1.5">
            {planned.map((item) => (
              <li key={item} className="text-[12.5px] text-slate-700 flex gap-2">
                <span className="text-slate-300 shrink-0">—</span>
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </div>

        {prerequisites && prerequisites.length > 0 && (
          <div>
            <h4 className="text-[10.5px] font-bold uppercase tracking-wider text-slate-400 mb-2.5">
              Prérequis
            </h4>
            <ul className="space-y-1.5">
              {prerequisites.map((item) => (
                <li key={item} className="text-[12.5px] text-slate-700 flex gap-2">
                  <span className="text-slate-300 shrink-0">—</span>
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>

    {availableToday && availableToday.length > 0 && (
      <div className="cbc-card p-6">
        <h4 className="text-[13.5px] font-bold mb-1">Disponible dès aujourd'hui</h4>
        <p className="text-[12.5px] text-slate-500 mb-4">
          Ces fonctions couvrent une partie du besoin sans attendre la livraison
          ci-dessus.
        </p>
        <ul className="space-y-3">
          {availableToday.map((item) => (
            <li key={item.label} className="flex gap-2.5">
              <ExternalLink className="w-3.5 h-3.5 text-[#A68523] mt-0.5 shrink-0" />
              <div>
                <div className="text-[13px] font-bold">{item.label}</div>
                <div className="text-[12.5px] text-slate-600">{item.hint}</div>
              </div>
            </li>
          ))}
        </ul>
      </div>
    )}
  </div>
);
