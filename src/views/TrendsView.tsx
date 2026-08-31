/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { useApp } from '../context/AppContext';
import { PageHeader } from '../components/layout/PageHeader';
import { SegmentedControl } from '../components/layout/SegmentedControl';
import { agentsService } from '../services/api/agents.service';

type Range = '24h' | '7j' | '30j';

const RANGE_HOURS: Record<Range, number> = { '24h': 24, '7j': 24 * 7, '30j': 24 * 30 };
// Pas d'échantillonnage adapté à la fenêtre : ~100 points quelle que soit la
// durée, pour rester lisible sans surcharger la base de séries temporelles.
const RANGE_STEP: Record<Range, string> = { '24h': '15m', '7j': '2h', '30j': '8h' };

interface Point {
  t: string;
  cpu: number | null;
  ram: number | null;
}

/**
 * Tendances du parc.
 *
 * Cet écran fabriquait ses séries : il indexait `cpuHistory` modulo des
 * étiquettes codées en dur (`Lun`…`Dim`, `S1`…`S12`), un historique lui-même
 * alimenté par une marche aléatoire côté navigateur. Le sélecteur 7j/30j ne
 * changeait donc que le nombre d'étiquettes — jamais la fenêtre de données —
 * et la base de séries temporelles n'était jamais interrogée.
 *
 * Les points proviennent désormais de VictoriaMetrics, via l'endpoint
 * d'historique réel, et la fenêtre choisie est réellement appliquée.
 */
export const TrendsView: React.FC = () => {
  const { agents } = useApp();
  const [range, setRange] = useState<Range>('7j');
  const [points, setPoints] = useState<Point[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Moyenne de parc : on agrège l'historique de chaque hôte en ligne.
  const agentIds = useMemo(
    () => agents.filter((a) => a.status === 'online').map((a) => a.id),
    [agents]
  );

  const load = useCallback(async () => {
    if (agentIds.length === 0) {
      setPoints([]);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const hours = RANGE_HOURS[range];
      const step = RANGE_STEP[range];

      const series = await Promise.all(
        agentIds.slice(0, 25).map(async (id) => {
          const [cpu, ram] = await Promise.all([
            agentsService.getAgentMetricHistory(id, { name: 'cpu.percent', hours, step }),
            agentsService.getAgentMetricHistory(id, { name: 'memory.percent', hours, step }),
          ]);
          return { cpu, ram };
        })
      );

      // Regroupement par horodatage : chaque hôte peut avoir des trous.
      const cpuByTs = new Map<string, number[]>();
      const ramByTs = new Map<string, number[]>();
      const collect = (
        target: Map<string, number[]>,
        result: Array<{ points: Array<{ ts: string; value: number }> }> | undefined
      ) => {
        for (const s of result ?? []) {
          for (const p of s.points ?? []) {
            if (!Number.isFinite(p.value)) continue;
            const bucket = target.get(p.ts) ?? [];
            bucket.push(p.value);
            target.set(p.ts, bucket);
          }
        }
      };
      for (const s of series) {
        collect(cpuByTs, s.cpu?.result);
        collect(ramByTs, s.ram?.result);
      }

      const timestamps = Array.from(new Set([...cpuByTs.keys(), ...ramByTs.keys()])).sort();
      const avg = (xs?: number[]) =>
        xs && xs.length ? Math.round((xs.reduce((a, b) => a + b, 0) / xs.length) * 10) / 10 : null;

      setPoints(
        timestamps.map((ts) => ({
          t: new Date(ts).toLocaleString('fr-FR', {
            day: '2-digit',
            month: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
          }),
          cpu: avg(cpuByTs.get(ts)),
          ram: avg(ramByTs.get(ts)),
        }))
      );
    } catch {
      setError("L'historique n'a pas pu être chargé depuis la base de séries temporelles.");
      setPoints([]);
    } finally {
      setLoading(false);
    }
  }, [agentIds, range]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div className="space-y-5">
      <PageHeader
        title="Tendances"
        subtitle={`Moyenne du parc — ${agentIds.length} hôte(s) en ligne.`}
        secondaryActions={
          <SegmentedControl
            options={(['24h', '7j', '30j'] as Range[]).map((r) => ({
              id: r,
              label: r === '24h' ? '24 h' : r === '7j' ? '7 j' : '30 j',
              active: range === r,
              onClick: () => setRange(r),
            }))}
          />
        }
      />

      <div className="cbc-card p-5">
        {loading ? (
          <div className="h-[320px] grid place-items-center text-[13px] text-slate-400">
            Chargement de l'historique…
          </div>
        ) : error ? (
          <div className="h-[320px] grid place-items-center text-center px-6">
            <div>
              <div className="text-[14px] font-bold text-rose-700">{error}</div>
              <div className="text-[12.5px] text-slate-500 mt-2">
                Vérifier l'état de VictoriaMetrics dans Paramètres → Plateforme.
              </div>
            </div>
          </div>
        ) : points.length === 0 ? (
          <div className="h-[320px] grid place-items-center text-center px-6">
            <div>
              <div className="text-[15px] font-bold">Aucune donnée sur cette période</div>
              <div className="text-[12.5px] text-slate-500 mt-2 max-w-md">
                {agentIds.length === 0
                  ? 'Aucun hôte en ligne. Les tendances apparaîtront dès la première remontée de métriques.'
                  : "L'historique ne couvre pas encore cette fenêtre. Choisir une période plus courte."}
              </div>
            </div>
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={320}>
            <AreaChart data={points} margin={{ top: 8, right: 8, bottom: 0, left: -18 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" vertical={false} />
              <XAxis dataKey="t" tick={{ fontSize: 11, fill: '#94A3B8' }} minTickGap={32} />
              <YAxis domain={[0, 100]} tick={{ fontSize: 11, fill: '#94A3B8' }} unit="%" />
              <Tooltip
                contentStyle={{ fontSize: 12, borderRadius: 12, border: '1px solid #E2E8F0' }}
                formatter={(v: number | null) => (v == null ? '—' : `${v} %`)}
              />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Area
                type="monotone"
                dataKey="cpu"
                name="CPU"
                stroke="#D0B335"
                fill="#D0B335"
                fillOpacity={0.15}
                connectNulls
              />
              <Area
                type="monotone"
                dataKey="ram"
                name="RAM"
                stroke="#2563EB"
                fill="#2563EB"
                fillOpacity={0.12}
                connectNulls
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
};
