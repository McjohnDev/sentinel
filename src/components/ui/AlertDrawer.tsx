import React, { useEffect, useState } from 'react';
import { Bell, UserCheck, X } from 'lucide-react';
import { Alert } from '../../types';
import { alertsService, AlertTimelineEvent } from '../../services/api/alerts.service';
import { alertStatusMeta, deliveryMeta, sevMeta } from './tones';

interface AlertDrawerProps {
  alert: Alert | null;
  onClose: () => void;
  onAck: (alert: Alert) => void;
  onResolve: (alert: Alert) => void;
  /** Comptes pouvant prendre en charge une alerte. */
  assignables?: Array<{ id: string; name: string }>;
  onAssign?: (alert: Alert, userId: string | null) => void;
  /** Delai de relance de cette alerte. `null` : reglage du parc, `0` : aucune. */
  onSetReminder?: (alert: Alert, hours: number | null) => void;
  /** Delai du parc, pour nommer ce que « Reglage du parc » signifie ici. */
  fleetReminderHours?: number | null;
  /** Compte connecté, pour proposer « M'attribuer » — le geste le plus courant. */
  currentUserId?: string | null;
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
  assignables = [],
  onAssign,
  onSetReminder,
  fleetReminderHours,
  currentUserId,
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
      <aside className="fixed top-0 right-0 bottom-0 w-full max-w-[480px] bg-[var(--color-panel)] border-l border-[var(--color-ln)] z-41 flex flex-col" style={{ zIndex: 41 }}>
        <div className="px-5 py-5 border-b border-[var(--color-ln)]">
          <div className="flex items-start justify-between gap-3">
            <div>
              <div className="tnum text-[11px] font-bold tracking-wide text-[var(--color-tx3)]">ALERTE {alert.id}</div>
              <h2 className="text-[17px] font-extrabold tracking-tight mt-2 mb-0">{alert.message}</h2>
              <div className="flex items-center gap-2 mt-2.5 flex-wrap">
                <span className="px-2 py-0.5 rounded-md text-[10.5px] font-bold text-white" style={{ background: sev.bg }}>
                  {sev.label}
                </span>
                <button type="button" onClick={() => onOpenHost(alert.agentId)} className="text-[13px] font-bold text-[#A68523]">
                  {alert.agentName}
                </button>
                <span className="text-xs text-[var(--color-tx3)]">· {alert.type}</span>
              </div>
            </div>
            <button type="button" onClick={onClose} className="w-[30px] h-[30px] grid place-items-center rounded-lg text-[var(--color-tx3)] hover:bg-[var(--color-ln2)] shrink-0">
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>
        <div className="px-5 py-5 border-b border-[var(--color-ln)]">
          <div className="flex items-center">
            {steps.map((s, i) => (
              <span key={s.label} className={`flex items-center ${i < 2 ? 'flex-1' : ''}`}>
                <span className={`w-4 h-4 rounded-full border-2 shrink-0 ${s.on ? 'bg-[#D0B335] border-[#D0B335]' : 'bg-[var(--color-panel)] border-[var(--color-ln)]'}`} />
                <span className={`text-xs font-semibold ml-2 whitespace-nowrap ${s.on ? 'text-[var(--color-tx)]' : 'text-[var(--color-tx3)]'}`}>
                  {s.label}
                </span>
                {i < 2 && <span className="flex-1 h-0.5 bg-slate-200 mx-2.5" />}
              </span>
            ))}
          </div>
        </div>
        <div className="px-5 py-5 flex-1 overflow-y-auto">
          <div className="text-[10.5px] font-bold uppercase tracking-wider text-[var(--color-tx3)] mb-3.5">Chronologie</div>
          {loadingTimeline && <div className="text-[12.5px] text-[var(--color-tx3)] pb-4">Chargement…</div>}
          {timelineError && <div className="text-[12.5px] text-rose-600 pb-4">{timelineError}</div>}
          {!loadingTimeline && !timelineError && events.length === 0 && (
            <div className="text-[12.5px] text-[var(--color-tx3)] pb-4">Aucun évènement enregistré.</div>
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
                  <span className="text-[12.5px] text-[var(--color-tx2)]">
                    {ACTION_LABELS[e.action] || e.action}
                    {e.actor ? ` · ${e.actor}` : ''}
                  </span>
                </div>
                {e.comment && (
                  <div className="tnum text-[11.5px] leading-relaxed text-[var(--color-tx3)] mt-1">{e.comment}</div>
                )}
              </div>
            </div>
          ))}

          {/* Livraison des notifications — état réel écrit par le serveur
              (sent / failed / skipped / pending), pas une valeur décorative. */}
          {/* Workflow interne (point 9). Trois moments distincts : le verdict
              dit si l'incident est réel, la prise en charge dit qui le traite.
              Une alerte validée sans responsable reste ouverte pendant que
              chacun suppose qu'un autre s'en occupe. */}
          <div className="text-[10.5px] font-bold uppercase tracking-wider text-[var(--color-tx3)] mb-3.5 mt-2">
            Traitement
          </div>
          <div className="space-y-2.5 mb-5">
            <div className="flex items-center gap-2.5">
              <span className="text-[12.5px] text-[var(--color-tx2)] flex-1">Validation</span>
              {alert.verdict === 'real' ? (
                <span className="px-2 py-0.5 rounded-md text-[10.5px] font-bold bg-rose-50 text-rose-700 border border-rose-200">
                  incident réel
                </span>
              ) : alert.verdict === 'false_positive' ? (
                <span className="px-2 py-0.5 rounded-md text-[10.5px] font-bold bg-[var(--color-ln2)] text-[var(--color-tx2)] border border-[var(--color-ln)]">
                  faux positif
                </span>
              ) : (
                <span className="text-[12px] text-[var(--color-tx3)]">non prononcée</span>
              )}
            </div>

            {/* Bloc mis en avant plutôt qu'une ligne parmi d'autres : une
                alerte sans responsable reste ouverte pendant que chacun
                suppose qu'un autre s'en occupe. L'état « non attribuée » doit
                sauter aux yeux, et l'action être à portée immédiate. */}
            <div
              className={`rounded-xl border p-3 ${
                alert.assignedToUsername
                  ? 'bg-emerald-50/60 border-emerald-200'
                  : 'bg-amber-50 border-amber-300'
              }`}
            >
              <div className="flex items-center gap-2 mb-2">
                <UserCheck
                  className={`w-4 h-4 ${alert.assignedToUsername ? 'text-emerald-700' : 'text-amber-700'}`}
                />
                <span className="text-[12.5px] font-bold">Prise en charge</span>
              </div>

              {alert.assignedToUsername ? (
                <p className="text-[13px] m-0 mb-2">
                  <strong>{alert.assignedToUsername}</strong>
                  {alert.assignedBy ? (
                    <span className="text-[var(--color-tx2)]"> — confiée par {alert.assignedBy}</span>
                  ) : null}
                </p>
              ) : (
                <p className="text-[12.5px] text-amber-900 m-0 mb-2">
                  Personne n’en a la charge. Tant qu’elle n’est attribuée à personne,
                  cette alerte reste ouverte sans que quiconque s’en occupe.
                </p>
              )}

              {onAssign && !resolved && (
                <div className="flex items-center gap-2 flex-wrap">
                  {currentUserId && alert.assignedTo !== currentUserId && (
                    <button
                      type="button"
                      onClick={() => onAssign(alert, currentUserId)}
                      className="cbc-btn-primary py-1.5 px-3 text-[12.5px]"
                    >
                      M’attribuer
                    </button>
                  )}
                  <select
                    value={alert.assignedTo || ''}
                    onChange={(e) => onAssign(alert, e.target.value || null)}
                    className="cbc-input py-1.5 text-[12.5px] flex-1 min-w-[150px]"
                  >
                    <option value="">Confier à…</option>
                    {assignables.map((u) => (
                      <option key={u.id} value={u.id}>
                        {u.name}
                      </option>
                    ))}
                  </select>
                </div>
              )}
            </div>

            {/* La relance n'est pas un detail de configuration : c'est ce qui
                empeche une alerte prise en charge puis oubliee de sombrer.
                Elle se regle ici, au moment ou l'on juge l'incident, parce que
                c'est la seule fois ou l'on sait s'il merite un rappel dans une
                heure, dans un jour, ou plus du tout. */}
            {onSetReminder && !resolved && (
              <div className="rounded-xl border border-[var(--color-ln)] p-3">
                <div className="flex items-center gap-2 mb-2">
                  <Bell className="w-4 h-4 text-[var(--color-tx2)]" />
                  <span className="text-[12.5px] font-bold">Relance par courriel</span>
                  {(alert.reminderCount || 0) > 0 && (
                    <span className="text-[11.5px] text-[var(--color-tx2)]">
                      — {alert.reminderCount} rappel{(alert.reminderCount || 0) > 1 ? 's' : ''} deja
                      envoye{(alert.reminderCount || 0) > 1 ? 's' : ''}
                    </span>
                  )}
                </div>
                <select
                  value={
                    alert.reminderHours === null || alert.reminderHours === undefined
                      ? ''
                      : String(alert.reminderHours)
                  }
                  onChange={(e) =>
                    onSetReminder(alert, e.target.value === '' ? null : Number(e.target.value))
                  }
                  className="cbc-input py-1.5 text-[12.5px] w-full"
                >
                  <option value="">
                    Reglage du parc
                    {fleetReminderHours !== null && fleetReminderHours !== undefined
                      ? fleetReminderHours === 0
                        ? ' (aucune relance)'
                        : ` (${fleetReminderHours} h)`
                      : ''}
                  </option>
                  <option value="0.5">Toutes les 30 minutes</option>
                  <option value="1">Toutes les heures</option>
                  <option value="3">Toutes les 3 heures</option>
                  <option value="12">Toutes les 12 heures</option>
                  <option value="24">Une fois par jour</option>
                  <option value="0">Ne plus relancer cette alerte</option>
                </select>
                <p className="text-[11.5px] text-[var(--color-tx2)] mt-2 mb-0">
                  Le rappel continue tant que l'alerte est ouverte, meme prise en
                  charge : c'est l'alerte attribuee puis oubliee qu'il rattrape. La
                  resolution y met fin.
                </p>
              </div>
            )}

            {alert.acknowledgedBy && (
              <div className="flex items-center gap-2.5">
                <span className="text-[12.5px] text-[var(--color-tx2)] flex-1">Validée par</span>
                <span className="text-[12.5px] text-[var(--color-tx2)]">{alert.acknowledgedBy}</span>
              </div>
            )}
            {alert.resolvedBy && (
              <div className="flex items-center gap-2.5">
                <span className="text-[12.5px] text-[var(--color-tx2)] flex-1">Résolue par</span>
                <span className="text-[12.5px] text-[var(--color-tx2)]">{alert.resolvedBy}</span>
              </div>
            )}
          </div>

          <div className="text-[10.5px] font-bold uppercase tracking-wider text-[var(--color-tx3)] mb-3.5 mt-2">
            Notifications
          </div>
          <div className="space-y-2">
            <div className="flex items-center gap-2.5">
              <span className="text-[12.5px] text-[var(--color-tx2)] flex-1">Mail CBC</span>
              <span className={`px-2 py-0.5 rounded-md text-[10.5px] font-bold ${mail.badge}`}>{mail.label}</span>
            </div>
            <div className="flex items-center gap-2.5">
              <span className="text-[12.5px] text-[var(--color-tx2)] flex-1">Webhook</span>
              <span className={`px-2 py-0.5 rounded-md text-[10.5px] font-bold ${webhook.badge}`}>{webhook.label}</span>
            </div>
          </div>
        </div>
        <div className="px-5 py-4 border-t border-[var(--color-ln)] bg-[var(--color-ln2)] flex gap-2">
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

        </div>
      </aside>
    </>
  );
};
