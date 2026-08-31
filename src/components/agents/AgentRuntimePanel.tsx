/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import { AlertTriangle, Clock, FileCog, FolderTree, HardDrive, Shield, Terminal, User } from 'lucide-react';
import { Agent } from '../../types';

/**
 * « Où et comment l'agent tourne » sur la machine (point 9).
 *
 * Avant ce panneau, répondre à « l'agent est-il installé en service ou lancé
 * à la main ? », « sous quel compte ? », « quel fichier de configuration
 * a-t-il réellement chargé ? » imposait d'ouvrir une session sur l'hôte —
 * c'est-à-dire précisément ce que la supervision centralisée doit éviter.
 */

const MODE_LABELS: Record<string, string> = {
  service: 'Service Windows',
  systemd: 'Unité systemd',
  launchd: 'Démon launchd',
  docker: 'Conteneur Docker',
  console: 'Console (lancement manuel)',
  unknown: 'Indéterminé',
};

const PACKAGING_LABELS: Record<string, string> = {
  binary: 'Binaire packagé',
  docker: 'Image conteneur',
  source: 'Sources Python',
};

function formatUptime(seconds?: number | null): string {
  if (seconds == null) return '—';
  const d = Math.floor(seconds / 86400);
  const h = Math.floor((seconds % 86400) / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (d > 0) return `${d}j ${h}h`;
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
}

const Row: React.FC<{ icon: React.ReactNode; label: string; children: React.ReactNode }> = ({
  icon,
  label,
  children,
}) => (
  <div className="flex items-start gap-2.5 px-[18px] py-2.5 border-b border-slate-50 last:border-0">
    <span className="text-slate-400 mt-0.5 shrink-0">{icon}</span>
    <div className="min-w-0 flex-1">
      <div className="text-[10.5px] font-bold uppercase tracking-wider text-slate-400">{label}</div>
      <div className="text-[12.5px] text-slate-700 break-all">{children}</div>
    </div>
  </div>
);

export const AgentRuntimePanel: React.FC<{ agent: Agent }> = ({ agent }) => {
  const runtime = agent.runtime;

  if (!runtime) {
    return (
      <div className="cbc-card overflow-hidden">
        <div className="px-[18px] py-3.5 border-b border-slate-200">
          <h2 className="text-sm font-bold m-0">Exécution sur l'hôte</h2>
        </div>
        <div className="px-[18px] py-6 text-[12.5px] text-slate-500">
          Cet hôte n'a pas encore transmis son descriptif d'exécution. Il sera
          renseigné au prochain battement d'un agent en version 1.2 ou
          supérieure.
        </div>
      </div>
    );
  }

  const mode = runtime.run_mode || 'unknown';
  // Un agent lancé à la main ne survit pas à une déconnexion de session ni à
  // un redémarrage : le signaler vaut mieux que de l'afficher comme un mode
  // d'exécution parmi d'autres.
  const isManual = mode === 'console' || mode === 'unknown';

  return (
    <div className="cbc-card overflow-hidden">
      <div className="px-[18px] py-3.5 border-b border-slate-200 flex items-center justify-between">
        <h2 className="text-sm font-bold m-0">Exécution sur l'hôte</h2>
        <span
          className={`px-2 py-0.5 rounded-full text-[11px] font-semibold ${
            isManual ? 'bg-amber-50 text-amber-700' : 'bg-emerald-50 text-emerald-700'
          }`}
        >
          {MODE_LABELS[mode] || mode}
        </span>
      </div>

      {isManual && (
        <div className="mx-[18px] mt-3 mb-1 flex items-start gap-2 rounded-lg bg-amber-50 px-3 py-2 text-[12px] text-amber-800">
          <AlertTriangle className="w-3.5 h-3.5 mt-0.5 shrink-0" />
          <span>
            Agent lancé hors service : il ne redémarrera pas automatiquement
            après un redémarrage de la machine ou une fermeture de session.
          </span>
        </div>
      )}

      <Row icon={<Terminal className="w-3.5 h-3.5" />} label="Processus">
        PID {runtime.pid ?? '—'}
        {runtime.service_name ? ` · ${runtime.service_name}` : ''}
        {' · actif depuis '}
        {formatUptime(runtime.uptime_seconds)}
      </Row>

      <Row icon={<User className="w-3.5 h-3.5" />} label="Compte d'exécution">
        {runtime.run_as_user || '—'}
        {runtime.elevated === true && (
          <span className="ml-2 inline-flex items-center gap-1 text-[11px] font-semibold text-amber-700">
            <Shield className="w-3 h-3" />
            privilèges élevés
          </span>
        )}
      </Row>

      <Row icon={<FolderTree className="w-3.5 h-3.5" />} label="Installation">
        {runtime.install_dir || '—'}
      </Row>

      <Row icon={<HardDrive className="w-3.5 h-3.5" />} label="Exécutable">
        {runtime.executable_path || '—'}
        {runtime.packaging && (
          <span className="ml-2 text-[11px] text-slate-500">
            ({PACKAGING_LABELS[runtime.packaging] || runtime.packaging})
          </span>
        )}
      </Row>

      {/* Le fichier réellement chargé, pas celui que la documentation
          suppose : c'est la réponse à « pourquoi ma configuration n'est-elle
          pas prise en compte ? ». */}
      <Row icon={<FileCog className="w-3.5 h-3.5" />} label="Configuration chargée">
        {runtime.config_path || (
          <span className="text-amber-700">Aucune — l'agent tourne sur ses valeurs par défaut</span>
        )}
      </Row>

      <Row icon={<Clock className="w-3.5 h-3.5" />} label="Liaison">
        {runtime.server_url || '—'}
        {runtime.tls_verify === false && (
          <span className="ml-2 text-[11px] font-semibold text-rose-700">TLS non vérifié</span>
        )}
        {runtime.buffer_records ? (
          <span className="ml-2 text-[11px] text-amber-700">
            {runtime.buffer_records} mesure(s) en attente d'envoi
          </span>
        ) : null}
      </Row>

      {runtime.last_error && (
        <div className="px-[18px] py-3 bg-rose-50 text-[12px] text-rose-800 break-all">
          <span className="font-semibold">Dernière erreur : </span>
          {runtime.last_error}
        </div>
      )}

      <div className="px-[18px] py-3 text-[11px] text-slate-400">
        {runtime.platform} · Python {runtime.python_version}
        {runtime.plugins?.length ? ` · ${runtime.plugins.length} collecteur(s)` : ''}
      </div>
    </div>
  );
};
