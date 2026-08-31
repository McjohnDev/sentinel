/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { createContext, useContext, useMemo, useState, ReactNode } from 'react';

export type Lang = 'fr' | 'en';

const messages = {
  fr: {
    'nav.main': 'Menu principal',
    'nav.group.exploit': 'Exploiter',
    'nav.group.analyze': 'Analyser',
    'nav.group.automate': 'Automatiser',
    'nav.group.admin': 'Administrer',
    'nav.group.configure': 'Configurer',
    'nav.trends': 'Tendances',
    'nav.automation': 'Scénarios',
    'nav.rules': 'Règles',
    'nav.integrations': 'Intégrations',
    'nav.audit': 'Audit',
    'nav.profile': 'Profil',
    'nav.dashboard': 'Tableau de bord',
    'nav.agents': 'Parc',
    'nav.alerts': 'Alertes',
    'nav.logs': 'Journaux',
    'nav.dashboards': 'Tableaux',
    'nav.network': 'Réseau',
    'nav.reports': 'Rapports',
    'nav.actions': 'Actions',
    'nav.approvals': 'Approbations',
    'nav.pilot': 'Pilot & UAT',
    'nav.users': 'Utilisateurs',
    'nav.settings': 'Paramètres',
    'nav.logout': 'Quitter',
    'dashboard.title': 'Tableau de bord',
    'dashboard.subtitle': 'Ce qui demande une action maintenant.',
    'dashboard.enrol': 'Enrôler un agent',
    'dashboard.triage': 'À traiter',
    'dashboard.viewAlerts': 'Voir toutes les alertes',
    'dashboard.emptyTitle': 'Aucun agent enrôlé',
    'dashboard.emptyBody':
      "Générez un jeton d'enrôlement, installez l'agent sur un premier hôte, puis attendez son heartbeat initial.",
    'dashboard.enrolFirst': 'Enrôler le premier agent',
    'lang.switch': 'EN',
    'dashboards.title': 'Tableaux personnalisés',
    'dashboards.subtitle': 'Composez des widgets et partagez-les (DSH-003).',
    'dashboards.create': 'Créer un tableau',
    'dashboards.shared': 'Partagé',
    'dashboards.empty': 'Aucun tableau. Créez-en un pour démarrer.',
    'network.title': 'Périmètre réseau',
    'network.subtitle': 'Équipements SNMP/ICMP — pas des hôtes agent (AGT-029).',
    'network.probe': 'Sonder',
    'network.probeAll': 'Sonder tout',
    'network.add': 'Ajouter un équipement',
    'reports.title': 'Rapports',
    'reports.subtitle': 'Export CSV/PDF à la demande et planifications (DSH-007).',
    'reports.csv': 'Télécharger CSV',
    'reports.pdf': 'Télécharger PDF',
    'login.tagline': 'Plateforme de supervision — Commercial Bank Cameroun',
    'login.email': 'Adresse email',
    'login.identifier': "Nom d'utilisateur ou adresse email",
    'login.identifierPlaceholder': 'prenom.nom ou prenom.nom@cbcam.cm',
    'login.password': 'Mot de passe',
    'login.showPassword': 'Afficher le mot de passe',
    'login.submit': 'Se connecter',
    'login.submitting': 'Connexion…',
    'login.forgot': 'Mot de passe oublié ?',
    'login.or': 'ou',
    'login.sso': 'Connexion institutionnelle (SSO)',
    'login.ssoSoon': 'Bientôt',
    'login.ssoHint': "Les comptes d'annuaire se connectent avec le formulaire ci-dessus.",
    'login.errEmail': 'Veuillez saisir une adresse email bancaire valide.',
    'login.errIdentifier': "Veuillez saisir votre nom d'utilisateur ou votre adresse email.",
    'login.errPassword': 'Veuillez saisir votre mot de passe.',
    'login.errCredentials': 'Identifiants invalides',
    'alerts.title': 'Alertes',
    'alerts.subtitle': 'Plan de travail',
    'alerts.ackAll': 'Tout acquitter',
    'alerts.severity': 'Gravité',
    'alerts.status': 'Statut',
    'alerts.family': 'Famille',
    'alerts.none': 'Aucune alerte',
    'alerts.noneHint': 'Aucune alerte ne correspond aux filtres sélectionnés.',
    'alerts.colHost': 'Hôte',
    'alerts.colMessage': 'Message',
    'alerts.colDetected': 'Détectée',
    'alerts.colNotif': 'Notif.',
    'alerts.ack': 'Acquitter',
    'alerts.resolve': 'Résoudre',
    'alerts.timeline': 'Chronologie',
    'alerts.notifications': 'Notifications',
    'alerts.viewHost': "Voir l'hôte",
    'alerts.mail': 'Mail CBC',
    'alerts.webhook': 'Webhook',
    'alerts.noEvents': 'Aucun évènement enregistré.',
    'alerts.timelineError': 'Chronologie indisponible',
    'common.loading': 'Chargement…',
    'common.cancel': 'Annuler',
    'common.refresh': 'Actualiser',
  },
  en: {
    'nav.main': 'Main menu',
    'nav.group.exploit': 'Operate',
    'nav.group.analyze': 'Analyze',
    'nav.group.automate': 'Automate',
    'nav.group.admin': 'Administer',
    'nav.group.configure': 'Configure',
    'nav.trends': 'Trends',
    'nav.automation': 'Playbooks',
    'nav.rules': 'Rules',
    'nav.integrations': 'Integrations',
    'nav.audit': 'Audit',
    'nav.profile': 'Profile',
    'nav.dashboard': 'Dashboard',
    'nav.agents': 'Fleet',
    'nav.alerts': 'Alerts',
    'nav.logs': 'Logs',
    'nav.dashboards': 'Boards',
    'nav.network': 'Network',
    'nav.reports': 'Reports',
    'nav.actions': 'Actions',
    'nav.approvals': 'Approvals',
    'nav.pilot': 'Pilot & UAT',
    'nav.users': 'Users',
    'nav.settings': 'Settings',
    'nav.logout': 'Sign out',
    'dashboard.title': 'Dashboard',
    'dashboard.subtitle': 'What needs action right now.',
    'dashboard.enrol': 'Enrol an agent',
    'dashboard.triage': 'To handle',
    'dashboard.viewAlerts': 'View all alerts',
    'dashboard.emptyTitle': 'No agents enrolled',
    'dashboard.emptyBody':
      'Generate an enrolment token, install the agent on a first host, then wait for its initial heartbeat.',
    'dashboard.enrolFirst': 'Enrol the first agent',
    'lang.switch': 'FR',
    'dashboards.title': 'Custom dashboards',
    'dashboards.subtitle': 'Compose widgets and share them (DSH-003).',
    'dashboards.create': 'Create board',
    'dashboards.shared': 'Shared',
    'dashboards.empty': 'No boards yet. Create one to get started.',
    'network.title': 'Network perimeter',
    'network.subtitle': 'SNMP/ICMP devices — not agent hosts (AGT-029).',
    'network.probe': 'Probe',
    'network.probeAll': 'Probe all',
    'network.add': 'Add device',
    'reports.title': 'Reports',
    'reports.subtitle': 'On-demand CSV/PDF export and schedules (DSH-007).',
    'reports.csv': 'Download CSV',
    'reports.pdf': 'Download PDF',
    'login.tagline': 'Monitoring platform — Commercial Bank Cameroun',
    'login.email': 'Email address',
    'login.identifier': 'Username or email address',
    'login.identifierPlaceholder': 'firstname.lastname or firstname.lastname@cbcam.cm',
    'login.password': 'Password',
    'login.showPassword': 'Show password',
    'login.submit': 'Sign in',
    'login.submitting': 'Signing in…',
    'login.forgot': 'Forgot your password?',
    'login.or': 'or',
    'login.sso': 'Corporate sign-in (SSO)',
    'login.ssoSoon': 'Soon',
    'login.ssoHint': 'Directory accounts sign in with the form above.',
    'login.errEmail': 'Enter a valid bank email address.',
    'login.errIdentifier': 'Enter your username or email address.',
    'login.errPassword': 'Enter your password.',
    'login.errCredentials': 'Invalid credentials',
    'alerts.title': 'Alerts',
    'alerts.subtitle': 'Work queue',
    'alerts.ackAll': 'Acknowledge all',
    'alerts.severity': 'Severity',
    'alerts.status': 'Status',
    'alerts.family': 'Family',
    'alerts.none': 'No alerts',
    'alerts.noneHint': 'No alert matches the selected filters.',
    'alerts.colHost': 'Host',
    'alerts.colMessage': 'Message',
    'alerts.colDetected': 'Detected',
    'alerts.colNotif': 'Notif.',
    'alerts.ack': 'Acknowledge',
    'alerts.resolve': 'Resolve',
    'alerts.timeline': 'Timeline',
    'alerts.notifications': 'Notifications',
    'alerts.viewHost': 'View host',
    'alerts.mail': 'CBC Mail',
    'alerts.webhook': 'Webhook',
    'alerts.noEvents': 'No event recorded.',
    'alerts.timelineError': 'Timeline unavailable',
    'common.loading': 'Loading…',
    'common.cancel': 'Cancel',
    'common.refresh': 'Refresh',
  },
} as const;

export type MsgKey = keyof typeof messages.fr;

/**
 * Clé de traduction.
 *
 * `MsgKey` conserve l'autocomplétion et la détection de faute de frappe sur
 * les clés connues, tandis que `(string & {})` autorise les clés calculées —
 * les libellés de navigation sont construits dynamiquement. Sans cette
 * ouverture, six appels légitimes étaient en erreur de typage.
 */
export type TranslationKey = MsgKey | (string & {});

interface I18nContextValue {
  lang: Lang;
  setLang: (lang: Lang) => void;
  /** Retourne la traduction, à défaut le français, à défaut la clé elle-même. */
  t: (key: TranslationKey) => string;
}

const I18nContext = createContext<I18nContextValue | null>(null);

export const I18nProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [lang, setLangState] = useState<Lang>(() => {
    const stored = localStorage.getItem('cbc_lang');
    return stored === 'en' ? 'en' : 'fr';
  });

  const setLang = (next: Lang) => {
    localStorage.setItem('cbc_lang', next);
    setLangState(next);
  };

  const value = useMemo<I18nContextValue>(
    () => ({
      lang,
      setLang,
      // Repli explicite : langue courante -> français -> clé brute. Afficher
      // la clé plutôt qu'une chaîne vide rend une traduction manquante
      // visible en recette au lieu de produire un libellé invisible.
      t: (key) => {
        const table = messages[lang] as Record<string, string>;
        const fallback = messages.fr as Record<string, string>;
        return table[key] ?? fallback[key] ?? key;
      },
    }),
    [lang]
  );

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
};

export function useI18n() {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error('useI18n requires I18nProvider');
  return ctx;
}
