import { AgentStatus, AlertSeverity, AlertStatus, OperatingSystem } from '../../types';

export function sevMeta(sev: AlertSeverity) {
  if (sev === 'critical') {
    return { label: 'Critique', short: 'CRIT', fg: '#fff', bg: '#E11D48', bd: '#E11D48', text: 'text-white', fill: 'bg-rose-600' };
  }
  if (sev === 'major' || sev === 'warning') {
    return { label: sev === 'warning' ? 'Warning' : 'Majeure', short: sev === 'warning' ? 'WARN' : 'MAJ', fg: '#fff', bg: '#F59E0B', bd: '#F59E0B', text: 'text-white', fill: 'bg-amber-500' };
  }
  if (sev === 'minor') {
    return { label: 'Mineure', short: 'MIN', fg: '#fff', bg: '#FB923C', bd: '#FB923C', text: 'text-white', fill: 'bg-orange-400' };
  }
  return { label: 'Info', short: 'INFO', fg: '#fff', bg: '#2563EB', bd: '#2563EB', text: 'text-white', fill: 'bg-blue-600' };
}

/**
 * Statut de livraison d'une notification (mail CBC / webhook).
 *
 * Le serveur écrit `sent | failed | skipped | pending` (voir
 * AlertService._notify). L'interface testait auparavant la valeur `'error'`,
 * que le serveur n'écrit jamais : un envoi en échec s'affichait donc en vert.
 */
export function deliveryMeta(status?: string) {
  switch ((status || '').toLowerCase()) {
    case 'sent':
      return { label: 'Livré', ok: true, failed: false, fg: 'text-emerald-600', badge: 'bg-emerald-50 text-emerald-700' };
    case 'failed':
      return { label: 'Échec', ok: false, failed: true, fg: 'text-rose-500', badge: 'bg-rose-50 text-rose-700' };
    case 'skipped':
      return { label: 'Non applicable', ok: false, failed: false, fg: 'text-slate-400', badge: 'bg-slate-100 text-slate-600' };
    case 'pending':
      return { label: 'En cours', ok: false, failed: false, fg: 'text-amber-600', badge: 'bg-amber-50 text-amber-700' };
    default:
      return { label: 'Non envoyé', ok: false, failed: false, fg: 'text-slate-300', badge: 'bg-slate-100 text-slate-500' };
  }
}

export function alertStatusMeta(status: AlertStatus) {
  if (status === 'open') return { label: 'Ouverte', bg: 'bg-rose-50', fg: 'text-rose-800', bd: 'border-rose-200' };
  if (status === 'resolved') return { label: 'Résolue', bg: 'bg-emerald-50', fg: 'text-emerald-800', bd: 'border-emerald-200' };
  return { label: 'Acquittée', bg: 'bg-slate-100', fg: 'text-slate-700', bd: 'border-slate-300' };
}

export function agentStatusMeta(status: AgentStatus) {
  if (status === 'online') return { label: 'En ligne', c: '#047857', bg: 'bg-emerald-50', bd: 'border-emerald-200' };
  if (status === 'offline') return { label: 'Hors ligne', c: '#BE123C', bg: 'bg-rose-50', bd: 'border-rose-200' };
  if (status === 'obsolete') return { label: 'Obsolète', c: '#B45309', bg: 'bg-amber-50', bd: 'border-amber-200' };
  return { label: 'Révoqué', c: '#334155', bg: 'bg-slate-100', bd: 'border-slate-300' };
}

export function osMeta(os: OperatingSystem) {
  if (os === 'windows') return { label: 'Windows', bg: 'bg-blue-50', fg: 'text-blue-700', bd: 'border-blue-200' };
  if (os === 'linux') return { label: 'Linux', bg: 'bg-amber-50', fg: 'text-amber-800', bd: 'border-amber-200' };
  return { label: 'macOS', bg: 'bg-purple-50', fg: 'text-purple-700', bd: 'border-purple-200' };
}

export function metricTone(value: number | null | undefined, warn = 80, crit = 90) {
  if (value == null) return { fg: 'text-slate-300', bg: 'bg-transparent' };
  if (value >= crit) return { fg: 'text-rose-800', bg: 'bg-rose-50' };
  if (value >= warn) return { fg: 'text-amber-800', bg: 'bg-amber-50' };
  return { fg: 'text-slate-700', bg: 'bg-transparent' };
}

export function gaugeColor(value: number | null | undefined, warn = 80, crit = 90) {
  if (value == null) return '#94A3B8';
  if (value >= crit) return '#E11D48';
  if (value >= warn) return '#D97706';
  return '#059669';
}
