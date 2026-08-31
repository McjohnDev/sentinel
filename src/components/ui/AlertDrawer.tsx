import React, { useEffect, useState } from 'react';
import { ChevronDown, X } from 'lucide-react';
import { Alert } from '../../types';
import { alertsService, AlertTimelineEvent } from '../../services/api/alerts.service';
import { alertStatusMeta, deliveryMeta, sevMeta } from './tones';

interface AlertDrawerProps {
  alert: Alert | null;
  onClose: () => void;
  onAck: (alert: Alert) => void;
  onResolve: (alert: Alert) => void;
  onOpenHost: (agentId: string) => void;
  canAck: boolean;
}

/** Libellés des actions enregistrées par AlertService._record_event. */
const ACTION_LABELS: Record<string, string> = {
  opened: 'Ouverte',
  acknowledged: 'Acquittée',
  resolved: 'Résolue',
  auto_resolved: 'Résolue automatiquement (retour sous le seuil)',
  escalated: 'Escaladée',
  severity_changed: 'Gravité modifiée',
  suppressed: 'Supprimée (fenêtre de maintenance)',
};

const ACTION_COLORS: Record<string, string> = {
  opened: '#E11D48',
  acknowledged: '#64748B',
  resolved: '#059669',
  auto_resolved: '#059669',
  escalated: '#B45309',
  severity_changed: '#F59E0B',
  suppressed: '#94A3B8',
};

export const AlertDrawer: React.FC<AlertDrawerProps> = ({
  alert,
  onClose,
  onAck,
  onResolve,
  onOpenHost,
  canAck,
}) => {
  const alertId = alert?.id ?? null;
  const [events, setEvents] = useState<AlertTimelineEvent[]>([]);
  const [timelineError, setTimelineError] = useState<string | null>(null);
  const [loadingTimeline, setLoadingTimeline] = useState(false);

  // La chronologie vient du serveur (ALR-005). Elle était auparavant
  // fabriquée côté client, avec des livraisons toujours affichées en succès.
  useEffect(() => {
    if (!alertId) {
      setEvents([]);
      return;
    }
    let cancelled = false;
    setLoadingTimeline(true);
    setTimelineError(null);
    alertsService
      .getAlertTimeline(alertId)
      .then((rows) => {
        if (!cancelled) setEvents(rows);
      })
      .catch(() => {
        if (!cancelled) setTimelineError('Chronologie indisponible');
      })
      .finally(() => {
        if (!cancelled) setLoadingTimeline(false);
      });
    return () => {
      cancelled = true;
    };
  }, [alertId]);

  if (!alert) return null;
  const sev = sevMeta(alert.severity);
  const st = alertStatusMeta(alert.status);
  const open = alert.status === 'open';
  const ack = alert.status === 'acknowledged' || alert.status === 'resolved';
  const resolved = alert.status === 'resolved';
  const mail = deliveryMeta(alert.mailStatus);
  const webhook = deliveryMeta(alert.webhookStatus);

  const steps = [
    { label: 'Ouverte', on: true },
    { label: 'Acquittée', on: ack },
    { label: 'Résolue', on: resolved },
  ];

  return (
    <>
      <div className="fixed inset-0 z-40 bg-slate-950/30 animate-fade-in" onClick={onClose} />
      <aside className="fixed top-0 right-0 bottom-0 w-full max-w-[480px] bg-white border-l border-slate-200 z-41 flex flex-col" style={{ zIndex: 41 }}>
        <div className="px-5 py-5 border-b border-slate-200">
          <div className="flex items-start justify-between gap-3">
            <div>
              <div className="tnum text-[11px] font-bold tracking-wide text-slate-400">ALERTE {alert.id}</div>
              <h2 className="text-[17px] font-extrabold tracking-tight mt-2 mb-0">{alert.message}</h2>
              <div className="flex items-center gap-2 mt-2.5 flex-wrap">
                <span className="px-2 py-0.5 rounded-md text-[10.5px] font-bold text-white" style={{ background: sev.bg }}>
                  {sev.label}
                </span>
                <button type="button" onClick={() => onOpenHost(alert.agentId)} className="text-[13px] font-bold text-[#A68523]">
                  {alert.agentName}
                </button>
                <span className="text-xs text-slate-400">· {alert.type}</span>
              </div>
            </div>
            <button type="button" onClick={onClose} className="w-[30px] h-[30px] grid place-items-center rounded-lg text-slate-400 hover:bg-slate-100 shrink-0">
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>
        <div className="px-5 py-5 border-b border-slate-200">
          <div className="flex items-center">
            {steps.map((s, i) => (
              <span key={s.label} className={`flex items-center ${i < 2 ? 'flex-1' : ''}`}>
                <span className={`w-4 h-4 rounded-full border-2 shrink-0 ${s.on ? 'bg-[#D0B335] border-[#D0B335]' : 'bg-white border-slate-200'}`} />
                <span className={`text-xs font-semibold ml-2 whitespace-nowrap ${s.on ? 'text-slate-900' : 'text-slate-400'}`}>
                  {s.label}
                </span>
                {i < 2 && <span className="flex-1 h-0.5 bg-slate-200 mx-2.5" />}
              </span>
            ))}
          </div>
        </div>
        <div className="px-5 py-5 flex-1 overflow-y-auto">
          <div className="text-[10.5px] font-bold uppercase tracking-wider text-slate-400 mb-3.5">Chronologie</div>
          {loadingTimeline && <div className="text-[12.5px] text-slate-400 pb-4">Chargement…</div>}
          {timelineError && <div className="text-[12.5px] text-rose-600 pb-4">{timelineError}</div>}
          {!loadingTimeline && !timelineError && events.length === 0 && (
            <div className="text-[12.5px] text-slate-400 pb-4">Aucun évènement enregistré.</div>
          )}
          {events.map((e, i) => (
            <div key={e.id} className="flex gap-3.5 pb-4">
              <div className="flex flex-col items-center shrink-0">
                <span
                  className="w-2 h-2 rounded-full mt-1"
                  style={{ background: ACTION_COLORS[e.action] || '#94A3B8' }}
                />
                {i < events.length - 1 && <span className="w-px flex-1 bg-slate-200 mt-1 min-h-[22px]" />}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-baseline gap-2.5">
                  <span className="tnum text-xs font-bold">{e.created_at}</span>
                  <span className="text-[12.5px] text-slate-700">
                    {ACTION_LABELS[e.action] || e.action}
                    {e.actor ? ` · ${e.actor}` : ''}
                  </span>
                </div>
                {e.comment && (
                  <div className="tnum text-[11.5px] leading-relaxed text-slate-400 mt-1">{e.comment}</div>
                )}
              </div>
            </div>
          ))}

          {/* Livraison des notifications — état réel écrit par le serveur
              (sent / failed / skipped / pending), pas une valeur décorative. */}
          <div className="text-[10.5px] font-bold uppercase tracking-wider text-slate-400 mb-3.5 mt-2">
            Notifications
          </div>
          <div className="space-y-2">
            <div className="flex items-center gap-2.5">
              <span className="text-[12.5px] text-slate-700 flex-1">Mail CBC</span>
              <span className={`px-2 py-0.5 rounded-md text-[10.5px] font-bold ${mail.badge}`}>{mail.label}</span>
            </div>
            <div className="flex items-center gap-2.5">
              <span className="text-[12.5px] text-slate-700 flex-1">Webhook</span>
              <span className={`px-2 py-0.5 rounded-md text-[10.5px] font-bold ${webhook.badge}`}>{webhook.label}</span>
            </div>
          </div>
        </div>
        <div className="px-5 py-4 border-t border-slate-200 bg-slate-50 flex gap-2">
          {canAck && open && (
            <button type="button" onClick={() => onAck(alert)} className="cbc-btn-secondary">
              Acquitter
            </button>
          )}
          {/* ALR-005 — clôture manuelle. Le service et l'API existaient déjà,
              mais aucune vue n'exposait l'action : une alerte ne pouvait pas
              être résolue depuis l'interface. */}
          {canAck && !resolved && (
            <button type="button" onClick={() => onResolve(alert)} className="cbc-btn-secondary">
              Résoudre
            </button>
          )}
          {!open && (
            <span className={`px-3 py-2 rounded-lg border text-[12.5px] font-semibold ${st.bg} ${st.fg} ${st.bd}`}>
              {st.label}
            </span>
          )}
          <button type="button" onClick={() => onOpenHost(alert.agentId)} className="cbc-btn-secondary">
            Voir l'hôte
          </button>
          <button type="button" className="cbc-btn-secondary ml-auto">
            Lancer un scénario
            <ChevronDown className="w-3.5 h-3.5" />
          </button>
        </div>
      </aside>
    </>
  );
};
