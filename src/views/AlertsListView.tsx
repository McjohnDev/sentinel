/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useMemo, useState } from 'react';
import { MailCheck } from 'lucide-react';
import { useApp } from '../context/AppContext';
import { alertsService } from '../services/api/alerts.service';
import { useI18n } from '../i18n';
import { Alert, AlertSeverity, AlertStatus, AlertType } from '../types';
import { PageHeader } from '../components/layout/PageHeader';
import { FilterChip } from '../components/ui/FilterChip';
import { AlertDrawer } from '../components/ui/AlertDrawer';
import { alertStatusMeta, deliveryMeta, sevMeta } from '../components/ui/tones';
import { AcknowledgeModal } from '../components/common/AcknowledgeModal';
import { Modal } from '../components/common/Modal';

export const AlertsListView: React.FC = () => {
  const { t } = useI18n();
  const {
    alerts,
    users,
    currentRole,
    currentUser,
    addToast,
    refreshFleet,
    acknowledgeAlert,
    acknowledgeAllAlerts,
    resolveAlert,
    navigateToAgentDetail,
    globalThresholds,
  } = useApp();

  const [severities, setSeverities] = useState<AlertSeverity[]>([]);
  const [statuses, setStatuses] = useState<AlertStatus[]>([]);
  const [types, setTypes] = useState<AlertType[]>([]);
  const [drawer, setDrawer] = useState<Alert | null>(null);
  const [ackTarget, setAckTarget] = useState<Alert | null>(null);
  const [resolveTarget, setResolveTarget] = useState<Alert | null>(null);
  const [bulkOpen, setBulkOpen] = useState(false);

  const toggle = <T,>(arr: T[], val: T, set: (n: T[]) => void) =>
    set(arr.includes(val) ? arr.filter((x) => x !== val) : [...arr, val]);

  const filtered = useMemo(
    () =>
      alerts.filter((a) => {
        if (severities.length && !severities.includes(a.severity)) return false;
        if (statuses.length && !statuses.includes(a.status)) return false;
        if (types.length && !types.includes(a.type)) return false;
        return true;
      }),
    [alerts, severities, statuses, types]
  );

  const canWrite = currentRole !== 'ReadOnly';

  return (
    <div className="space-y-5">
      <PageHeader
        title={t('alerts.title')}
        subtitle={`${t('alerts.subtitle')} — ${filtered.length}`}
        secondaryActions={
          canWrite ? (
            <button type="button" onClick={() => setBulkOpen(true)} className="cbc-btn-secondary">
              {t('alerts.ackAll')}
            </button>
          ) : undefined
        }
      />

      <div className="cbc-card overflow-hidden">
        <div className="px-4 py-3 border-b border-[var(--color-ln)] flex items-center gap-5 flex-wrap">
          <div className="flex items-center gap-2">
            <span className="text-[10.5px] font-bold uppercase tracking-wider text-[var(--color-tx3)]">{t('alerts.severity')}</span>
            {/* Les quatre gravités du référentiel (ALR-004). 'warning' est une
                valeur héritée que serialize_severity replie sur 'major' côté
                serveur : elle n'atteint jamais le client et ne doit donc pas
                avoir de filtre. */}
            {(['critical', 'major', 'minor', 'info'] as AlertSeverity[]).map((s) => (
              <FilterChip key={s} label={sevMeta(s).label} active={severities.includes(s)} onClick={() => toggle(severities, s, setSeverities)} />
            ))}
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[10.5px] font-bold uppercase tracking-wider text-[var(--color-tx3)]">{t('alerts.status')}</span>
            {(['open', 'acknowledged', 'resolved'] as AlertStatus[]).map((s) => (
              <FilterChip key={s} label={alertStatusMeta(s).label} active={statuses.includes(s)} onClick={() => toggle(statuses, s, setStatuses)} />
            ))}
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[10.5px] font-bold uppercase tracking-wider text-[var(--color-tx3)]">{t('alerts.family')}</span>
            {(['cpu', 'ram', 'disk', 'offline'] as AlertType[]).map((s) => (
              <FilterChip key={s} label={s} active={types.includes(s)} onClick={() => toggle(types, s, setTypes)} />
            ))}
          </div>
        </div>

        {filtered.length === 0 ? (
          <div className="py-16 text-center">
            <div className="text-[15px] font-bold">{t('alerts.none')}</div>
            <div className="text-[13px] text-[#777] mt-2">{t('alerts.noneHint')}</div>
          </div>
        ) : (
          <table className="w-full border-collapse">
            <thead>
              <tr className="bg-[var(--color-ln2)] border-b border-[var(--color-ln)]">
                {[t('alerts.severity'), t('alerts.status'), t('alerts.colHost'), t('alerts.colMessage'), t('alerts.colDetected'), t('alerts.colNotif'), ''].map((c) => (
                  <th key={c || 'act'} className="text-left px-3 py-2.5 text-[10.5px] font-bold uppercase tracking-wider text-[var(--color-tx3)] whitespace-nowrap">
                    {c}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.map((a) => {
                const sev = sevMeta(a.severity);
                const st = alertStatusMeta(a.status);
                return (
                  <tr
                    key={a.id}
                    onClick={() => setDrawer(a)}
                    className={`border-b border-[var(--color-ln2)] hover:bg-[var(--color-ln2)] cursor-pointer ${
                      a.severity === 'critical' && a.status === 'open' ? 'bg-rose-50/40' : ''
                    }`}
                  >
                    <td className="p-3">
                      <span className="inline-block px-2 py-0.5 rounded-md text-[10.5px] font-bold text-white" style={{ background: sev.bg }}>
                        {sev.label}
                      </span>
                    </td>
                    <td className="p-3">
                      <span className={`inline-flex px-2 py-0.5 rounded-md border text-[11px] font-semibold ${st.bg} ${st.fg} ${st.bd}`}>
                        {st.label}
                      </span>
                    </td>
                    <td className="p-3 text-[13px] font-bold whitespace-nowrap">{a.agentName}</td>
                    <td className="p-3 text-[13px] text-[var(--color-tx2)]">{a.message}</td>
                    <td className="p-3 tnum text-[12.5px] text-[var(--color-tx2)] whitespace-nowrap">{a.timestamp}</td>
                    <td className="p-3 text-center">
                      <MailCheck
                        className={`inline-block w-4 h-4 ${deliveryMeta(a.mailStatus).fg}`}
                        aria-label={`Mail : ${deliveryMeta(a.mailStatus).label}`}
                      />
                    </td>
                    <td className="p-3 pr-4 text-right">
                      {canWrite && a.status === 'open' ? (
                        <button
                          type="button"
                          className="cbc-btn-secondary py-1.5"
                          onClick={(e) => {
                            e.stopPropagation();
                            setAckTarget(a);
                          }}
                        >
                          {t('alerts.ack')}
                        </button>
                      ) : (
                        <span className="text-xs text-[var(--color-tx3)]">—</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      <AlertDrawer
        // L'alerte vivante, relue de la liste : un instantane pris a
        // l'ouverture continuerait d'afficher « non attribuee » apres une
        // attribution reussie, et le geste passerait pour sans effet.
        alert={drawer ? alerts.find((a) => a.id === drawer.id) ?? drawer : null}
        onClose={() => setDrawer(null)}
        canAck={canWrite}
        onAck={(a) => {
          setDrawer(null);
          setAckTarget(a);
        }}
        onResolve={(a) => {
          setDrawer(null);
          setResolveTarget(a);
        }}
        // Seuls les comptes actifs peuvent prendre en charge : confier un
        // incident à un compte désactivé revient à ne le confier à personne,
        // en donnant l'apparence du contraire. Le serveur le refuse aussi.
        currentUserId={currentUser?.id ?? null}
        assignables={users
          .filter((u) => u.status === 'active')
          .map((u) => ({ id: u.id, name: u.name }))}
        onAssign={async (a, userId) => {
          try {
            await alertsService.assign(a.id, userId);
            await refreshFleet();
            addToast({
              type: 'success',
              title: userId ? 'Alerte attribuée' : 'Attribution retirée',
              message: a.message,
            });
          } catch {
            addToast({
              type: 'error',
              title: 'Attribution impossible',
              message: 'Vérifier que le compte est actif et l’alerte encore ouverte.',
            });
          }
        }}
        fleetReminderHours={globalThresholds.alertReminderHours ?? 12}
        onSetReminder={async (a, hours) => {
          try {
            await alertsService.setReminder(a.id, hours);
            await refreshFleet();
            addToast({
              type: 'success',
              title: 'Relance modifiée',
              message:
                hours === null
                  ? 'Cette alerte suit de nouveau le réglage du parc.'
                  : hours === 0
                    ? 'Cette alerte ne sera plus relancée.'
                    : `Rappel toutes les ${hours} h tant que l’alerte reste ouverte.`,
            });
          } catch {
            addToast({
              type: 'error',
              title: 'Réglage impossible',
              message: 'Vérifier que l’alerte est encore ouverte.',
            });
          }
        }}
        onOpenHost={(id) => {
          setDrawer(null);
          navigateToAgentDetail(id);
        }}
      />

      <AcknowledgeModal
        isOpen={!!resolveTarget}
        onClose={() => setResolveTarget(null)}
        alert={resolveTarget}
        mode="resolve"
        onConfirm={(id, c, n) => {
          resolveAlert(id, c, n);
          setResolveTarget(null);
        }}
      />

      <AcknowledgeModal
        isOpen={!!ackTarget}
        onClose={() => setAckTarget(null)}
        alert={ackTarget}
        onConfirm={(id, comment, name) => {
          acknowledgeAlert(id, comment, name);
          setAckTarget(null);
        }}
      />

      <Modal
        isOpen={bulkOpen}
        onClose={() => setBulkOpen(false)}
        title="Tout acquitter"
        footer={
          <>
            <button type="button" className="cbc-btn-secondary" onClick={() => setBulkOpen(false)}>
              Annuler
            </button>
            <button
              type="button"
              className="cbc-btn-primary"
              onClick={() => {
                acknowledgeAllAlerts(currentUser?.name || 'Opérateur CBC', 'Acquittement massif');
                setBulkOpen(false);
              }}
            >
              Confirmer
            </button>
          </>
        }
      >
        <p className="text-sm text-[var(--color-tx2)]">Acquitter toutes les alertes ouvertes ? Un commentaire d'urgence sera enregistré.</p>
      </Modal>
    </div>
  );
};
