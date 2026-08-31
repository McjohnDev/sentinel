/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import { PlannedCapability } from '../components/common/PlannedCapability';

/**
 * Scénarios d'automatisation (n8n) — Lot 2.
 *
 * Cet écran présentait cinq scénarios codés en dur avec un historique
 * d'exécution inventé (numéro de run décrémenté, « dernier run : hier 02:11 »,
 * compteurs hebdomadaires, tous les runs en succès), un interrupteur
 * d'activation qui ne modifiait que l'état local du navigateur et affichait un
 * message de succès, et un bouton « Ouvrir dans n8n » sans action.
 *
 * Aucun runtime n8n n'existe : ni service dans les fichiers Compose, ni
 * registre de scénarios, ni API de déclenchement, ni stockage d'historique.
 * Le plan de sprint classe explicitement ce thème en Lot 2 (« ne pas démarrer
 * avant M4 »). L'écran annonce donc la capacité sans simuler son exécution.
 */
export const AutomationView: React.FC = () => (
  <PlannedCapability
    title="Scénarios d'automatisation"
    subtitle="Boucle fermée n8n — planifié pour le Lot 2."
    lot="Lot 2 — FS9+"
    description={
      "La plateforme déclenchera des scénarios d'automatisation lors d'un " +
      "évènement de supervision (disque saturé, service arrêté, hôte hors " +
      "ligne hors fenêtre), avec approbation humaine préalable pour les " +
      "actions sensibles et journalisation complète dans la piste d'audit."
    }
    planned={[
      "Registre de scénarios avec déclencheur, périmètre d'hôtes et approbation requise",
      'Cinq scénarios de démarrage fournis (disque, service, hors ligne, CPU, enrôlement)',
      "Historique d'exécution réel : horodatage, résultat, sortie de l'action",
      'Exécution à blanc (dry-run) distincte de l’exécution réelle',
      "Traçabilité de bout en bout : déclencheur, approbateur, résultat",
    ]}
    prerequisites={[
      'Jalon M4 franchi (recette du Lot 1 signée)',
      'Instance n8n fournie et raccordée au réseau de supervision',
      "Politique CBC d'approbation des actions distantes validée",
    ]}
    availableToday={[
      {
        label: 'Alertes et notifications',
        hint: "Les évènements qui déclencheront ces scénarios sont déjà détectés, notifiés par l'API Mail CBC et par webhook signé.",
      },
      {
        label: 'Webhook signé (HMAC)',
        hint: "Paramètres → Notifications : un système externe peut déjà recevoir les alertes signées et déclencher sa propre automatisation.",
      },
      {
        label: 'Configuration centralisée par groupe',
        hint: 'Paramètres → Groupes & config : appliquer un changement à un parc entier sans intervention sur chaque machine.',
      },
    ]}
  />
);
