/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useMemo, useState } from 'react';
import { useApp } from '../context/AppContext';
import { PageHeader } from '../components/layout/PageHeader';

const FAMILIES = [
  { id: 'cpu', label: 'CPU haute durée', metric: 'cpu.total.utilization' },
  { id: 'ram', label: 'RAM', metric: 'memory.used.percent' },
  { id: 'disk', label: 'Disque', metric: 'disk.used.percent' },
  { id: 'heartbeat', label: 'Heartbeat', metric: 'agent.heartbeat' },
  { id: 'window', label: 'Hors fenêtre', metric: 'availability.window' },
  { id: 'maint', label: 'Maintenance', metric: 'maintenance.window' },
] as const;

export const RulesView: React.FC = () => {
  const { globalThresholds, updateGlobalThresholds, currentRole, alerts } = useApp();
  const [family, setFamily] = useState<(typeof FAMILIES)[number]['id']>('cpu');
  const [warning, setWarning] = useState(globalThresholds.cpuWarning);
  const [critical, setCritical] = useState(globalThresholds.cpuCritical);
  const [duration, setDuration] = useState(globalThresholds.durationSeconds || 300);
  const [escalate, setEscalate] = useState(globalThresholds.escalateAfterMinutes || 15);
  const canEdit = currentRole === 'Admin';
  const selected = FAMILIES.find((f) => f.id === family)!;
  const durationMin = Math.round(duration / 60) || 1;

  const yesterdayHits = useMemo(() => {
    const type = family === 'ram' ? 'ram' : family === 'disk' ? 'disk' : family === 'cpu' ? 'cpu' : 'offline';
    return alerts.filter((a) => a.type === type).length;
  }, [alerts, family]);

  const sentence =
    family === 'heartbeat'
      ? `Si aucun heartbeat n'est reçu pendant ${durationMin} min, une alerte majeure part vers Mail DSI.`
      : family === 'window'
        ? `Si l'hôte est hors ligne hors fenêtre de présence, une alerte majeure part vers Mail DSI.`
        : family === 'maint'
          ? `Pendant une fenêtre de maintenance, les alertes de ce type sont silencieuses.`
          : `Si ${selected.metric} dépasse ${critical} % pendant ${durationMin} min, une alerte majeure part vers Mail DSI et le scénario associé.`;

  return (
    <div className="space-y-5">
      <PageHeader title="Règles" subtitle="Seuils, durées et phrase en français." />

      <div className="grid grid-cols-1 lg:grid-cols-[280px_1fr] gap-4">
        <div className="cbc-card overflow-hidden">
          {FAMILIES.map((f) => (
            <button
              key={f.id}
              type="button"
              onClick={() => setFamily(f.id)}
              className={`w-full text-left px-4 py-3 border-b border-slate-50 last:border-0 ${family === f.id ? 'bg-[#D0B335]/10' : 'hover:bg-slate-50'}`}
            >
              <div className="text-[13px] font-bold">{f.label}</div>
              <div className="tnum text-[11.5px] text-slate-400 mt-1">{f.metric}</div>
            </button>
          ))}
        </div>

        <div className="space-y-4">
          <div className="px-4 py-3 rounded-xl bg-[#D0B335]/10 border border-[#D0B335]/30 text-[13.5px] leading-relaxed text-[#3F3007]">
            {sentence}
          </div>

          <form
            className="cbc-card p-5 space-y-4"
            onSubmit={(e) => {
              e.preventDefault();
              if (warning >= critical) return;
              updateGlobalThresholds({
                ...globalThresholds,
                cpuWarning: family === 'cpu' ? warning : globalThresholds.cpuWarning,
                cpuCritical: family === 'cpu' ? critical : globalThresholds.cpuCritical,
                ramWarning: family === 'ram' ? warning : globalThresholds.ramWarning,
                ramCritical: family === 'ram' ? critical : globalThresholds.ramCritical,
                diskWarning: family === 'disk' ? warning : globalThresholds.diskWarning,
                diskCritical: family === 'disk' ? critical : globalThresholds.diskCritical,
                durationSeconds: duration,
                escalateAfterMinutes: escalate,
              });
            }}
          >
            {['cpu', 'ram', 'disk'].includes(family) && (
              <div className="grid grid-cols-2 gap-3.5">
                <label className="block">
                  <span className="text-xs font-semibold text-slate-700">Warning %</span>
                  <input type="number" value={warning} onChange={(e) => setWarning(Number(e.target.value))} className="cbc-input mt-1.5" disabled={!canEdit} />
                </label>
                <label className="block">
                  <span className="text-xs font-semibold text-slate-700">Critique %</span>
                  <input type="number" value={critical} onChange={(e) => setCritical(Number(e.target.value))} className="cbc-input mt-1.5" disabled={!canEdit} />
                </label>
              </div>
            )}
            <div className="grid grid-cols-2 gap-3.5">
              <label className="block">
                <span className="text-xs font-semibold text-slate-700">Durée avant déclenchement (s)</span>
                <input type="number" value={duration} onChange={(e) => setDuration(Number(e.target.value))} className="cbc-input mt-1.5" disabled={!canEdit} />
              </label>
              <label className="block">
                <span className="text-xs font-semibold text-slate-700">Escalade après (min)</span>
                <input type="number" value={escalate} onChange={(e) => setEscalate(Number(e.target.value))} className="cbc-input mt-1.5" disabled={!canEdit} />
              </label>
            </div>
            <div className="text-[12.5px] text-slate-500">
              Test 24 h : <strong className="text-slate-800">{yesterdayHits} déclenchement(s)</strong> sur cette famille.
            </div>
            {canEdit && (
              <button type="submit" className="cbc-btn-primary">
                Enregistrer
              </button>
            )}
          </form>
        </div>
      </div>
    </div>
  );
};
