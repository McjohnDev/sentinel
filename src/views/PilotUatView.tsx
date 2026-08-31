/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useEffect, useState } from 'react';
import { Plus, Download, ShieldCheck } from 'lucide-react';
import { useApp } from '../context/AppContext';
import { PageHeader } from '../components/layout/PageHeader';
import { pilotService, PilotHost, UatCase } from '../services/api/pilot.service';
import { groupsService, CoverageRow } from '../services/api/groups.service';

const FAMILY_LABELS: Record<number, string> = {
  1: '1 — Fleet onboarding',
  3: '3 — Alerting E2E',
  4: '4 — Resilience',
  5: '5 — History & reporting',
};

export const PilotUatView: React.FC = () => {
  const { addToast, currentRole } = useApp();
  const [hosts, setHosts] = useState<PilotHost[]>([]);
  const [cases, setCases] = useState<UatCase[]>([]);
  const [uatSummary, setUatSummary] = useState<Record<string, unknown> | null>(null);
  const [coverage, setCoverage] = useState<CoverageRow[]>([]);
  const [covSummary, setCovSummary] = useState<Record<string, unknown> | null>(null);
  const [pack, setPack] = useState<Record<string, unknown> | null>(null);
  const [hostname, setHostname] = useState('');
  const [familyFilter, setFamilyFilter] = useState<number | 'all'>('all');
  const [signName, setSignName] = useState('');
  const [signRole, setSignRole] = useState('cbc_ops');

  const refresh = async () => {
    const [h, u, c, p] = await Promise.all([
      pilotService.listHosts(),
      pilotService.listUat(familyFilter === 'all' ? undefined : familyFilter),
      groupsService.coverageMap(),
      pilotService.getAcceptancePack(),
    ]);
    setHosts(h);
    setCases(u.data || []);
    setUatSummary(u.summary || null);
    setCoverage(c);
    setPack(p);
    setCovSummary((p as { coverage?: Record<string, unknown> }).coverage || null);
  };

  useEffect(() => {
    void refresh().catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [familyFilter]);

  const canEdit = currentRole === 'Admin' || currentRole === 'Operator';

  return (
    <div className="space-y-5">
      <PageHeader
        title="Pilot & UAT"
        subtitle="FS8 — hôtes pilotes, familles Part K, pack d'acceptation."
        secondaryActions={
          <button
            type="button"
            className="cbc-btn-secondary"
            onClick={async () => {
              const data = await pilotService.getAcceptancePack();
              setPack(data);
              const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
              const url = URL.createObjectURL(blob);
              const a = document.createElement('a');
              a.href = url;
              a.download = 'cbc-lot1-acceptance-pack.json';
              a.click();
              URL.revokeObjectURL(url);
            }}
          >
            <Download className="w-4 h-4" />
            Pack d'acceptation
          </button>
        }
      />

      {/* Go/No-Go */}
      {pack && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {[
            ['Open Musts = 0', (pack as { go_no_go?: { coverage_zero_open_musts?: boolean } }).go_no_go?.coverage_zero_open_musts],
            ['UAT Lot1 complete', (pack as { go_no_go?: { uat_lot1_complete?: boolean } }).go_no_go?.uat_lot1_complete],
            ['Ready for M4', (pack as { go_no_go?: { ready_for_m4?: boolean } }).go_no_go?.ready_for_m4],
          ].map(([label, ok]) => (
            <div key={String(label)} className="p-3 rounded-2xl border border-slate-200 bg-white text-xs">
              <p className="font-bold text-slate-600">{label}</p>
              <p className={`mt-1 text-sm font-black ${ok ? 'text-emerald-700' : 'text-amber-700'}`}>
                {ok ? 'YES' : 'NO'}
              </p>
            </div>
          ))}
        </div>
      )}

      {/* Pilot hosts */}
      <div className="cbc-card p-5 space-y-3">
        <h2 className="text-sm font-black">Pilot fleet (FS8-01)</h2>
        {canEdit && (
          <div className="flex flex-wrap gap-2">
            <input
              value={hostname}
              onChange={(e) => setHostname(e.target.value)}
              placeholder="hostname"
              className="px-3 py-2 rounded-xl border text-xs"
            />
            <button
              type="button"
              className="inline-flex items-center gap-1 px-3 py-2 rounded-xl bg-slate-900 text-white text-xs font-bold"
              onClick={async () => {
                if (!hostname.trim()) return;
                await pilotService.createHost({ hostname: hostname.trim() });
                setHostname('');
                await refresh();
              }}
            >
              <Plus className="w-4 h-4" />
              Add pilot
            </button>
          </div>
        )}
        <div className="space-y-2">
          {hosts.length === 0 && <p className="text-xs text-slate-500">No pilot hosts yet.</p>}
          {hosts.map((h) => {
            const cl = h.checklist || {};
            return (
              <div key={h.id} className="p-3 rounded-xl bg-slate-50 border border-slate-200 text-xs space-y-2">
                <div className="flex justify-between gap-2">
                  <p className="font-bold">
                    {h.hostname} · <span className="text-slate-500">{h.status}</span>
                  </p>
                  {currentRole === 'Admin' && (
                    <button
                      type="button"
                      className="text-rose-600 font-bold"
                      onClick={async () => {
                        await pilotService.deleteHost(h.id);
                        await refresh();
                      }}
                    >
                      Remove
                    </button>
                  )}
                </div>
                <div className="flex flex-wrap gap-3">
                  {(['enroll', 'first_metrics', 'heartbeat_ok', 'alerts_visible'] as const).map((key) => (
                    <label key={key} className="inline-flex items-center gap-1 font-semibold">
                      <input
                        type="checkbox"
                        disabled={!canEdit}
                        checked={Boolean(cl[key])}
                        onChange={async (e) => {
                          const next = { ...cl, [key]: e.target.checked };
                          await pilotService.updateHost(h.id, {
                            enroll: Boolean(next.enroll),
                            first_metrics: Boolean(next.first_metrics),
                            heartbeat_ok: Boolean(next.heartbeat_ok),
                            alerts_visible: Boolean(next.alerts_visible),
                          });
                          await refresh();
                        }}
                      />
                      {key}
                    </label>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* UAT cases */}
      <div className="cbc-card p-5 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-sm font-black">UAT families (Part K)</h2>
          <select
            className="px-3 py-1.5 rounded-xl border text-xs"
            value={familyFilter === 'all' ? 'all' : String(familyFilter)}
            onChange={(e) =>
              setFamilyFilter(e.target.value === 'all' ? 'all' : Number(e.target.value))
            }
          >
            <option value="all">All Lot 1 families</option>
            {[1, 3, 4, 5].map((f) => (
              <option key={f} value={f}>
                {FAMILY_LABELS[f]}
              </option>
            ))}
          </select>
        </div>
        {uatSummary && (
          <p className="text-[11px] text-slate-500">
            Open cases: {((uatSummary.open_case_ids as string[]) || []).join(', ') || 'none'}
          </p>
        )}
        <table className="w-full text-xs">
          <thead className="text-left text-[10px] uppercase text-slate-500">
            <tr>
              <th className="py-2">Case</th>
              <th className="py-2">Title</th>
              <th className="py-2">Refs</th>
              <th className="py-2">Status</th>
              <th className="py-2">Evidence</th>
            </tr>
          </thead>
          <tbody>
            {cases.map((c) => (
              <tr key={c.id} className="border-t border-slate-100">
                <td className="py-2 font-mono font-bold">{c.case_id}</td>
                <td className="py-2">{c.title}</td>
                <td className="py-2 text-slate-500 max-w-[140px] truncate">{c.requirement_refs}</td>
                <td className="py-2">
                  {canEdit ? (
                    <select
                      className="border rounded-lg px-2 py-1"
                      value={c.status}
                      onChange={async (e) => {
                        await pilotService.updateUat(c.case_id, {
                          status: e.target.value,
                          evidence: c.evidence || `Recorded ${new Date().toISOString()}`,
                        });
                        addToast({ type: 'success', title: c.case_id, message: e.target.value });
                        await refresh();
                      }}
                    >
                      {['pending', 'pass', 'fail', 'blocked', 'waived'].map((s) => (
                        <option key={s} value={s}>
                          {s}
                        </option>
                      ))}
                    </select>
                  ) : (
                    c.status
                  )}
                </td>
                <td className="py-2 max-w-[180px] truncate" title={c.evidence || ''}>
                  {c.evidence || '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Extinction */}
      <div className="cbc-card p-5 space-y-3">
        <div className="flex flex-wrap justify-between gap-2 items-center">
          <h2 className="text-sm font-black">Script extinction (FS8-05 / DES-004)</h2>
          {currentRole === 'Admin' && (
            <div className="flex gap-2">
              <button
                type="button"
                className="px-3 py-1.5 rounded-xl bg-slate-900 text-white text-xs font-bold"
                onClick={async () => {
                  await pilotService.bulkVerify();
                  await refresh();
                }}
              >
                Bulk verify delivered
              </button>
              <button
                type="button"
                className="px-3 py-1.5 rounded-xl bg-[#D0B335] text-slate-950 text-xs font-bold"
                onClick={async () => {
                  await pilotService.bulkDecommission();
                  await refresh();
                }}
              >
                Decommission verified
              </button>
            </div>
          )}
        </div>
        {covSummary && (
          <p className="text-[11px] text-slate-500">
            Open Musts: {((covSummary.open_must_check_ids as string[]) || []).join(', ') || 'none'}
          </p>
        )}
        <table className="w-full text-xs">
          <thead className="text-left text-[10px] uppercase text-slate-500">
            <tr>
              <th className="py-2">Check</th>
              <th className="py-2">Plugin</th>
              <th className="py-2">Status</th>
            </tr>
          </thead>
          <tbody>
            {coverage.map((row) => (
              <tr key={row.check_id} className="border-t border-slate-100">
                <td className="py-2 font-mono font-bold">{row.check_id}</td>
                <td className="py-2">{row.plugin}</td>
                <td className="py-2">
                  {currentRole === 'Admin' ? (
                    <select
                      className="border rounded-lg px-2 py-1"
                      value={row.status}
                      onChange={async (e) => {
                        try {
                          await pilotService.setCoverageStatus(row.check_id, e.target.value);
                          await refresh();
                        } catch {
                          addToast({
                            type: 'error',
                            title: row.check_id,
                            message: 'Transition invalide',
                          });
                        }
                      }}
                    >
                      {[
                        'planned',
                        'delivered',
                        'verified_in_production',
                        'script_decommissioned',
                        'waived',
                      ].map((s) => (
                        <option key={s} value={s}>
                          {s}
                        </option>
                      ))}
                    </select>
                  ) : (
                    row.status
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Sign-off */}
      {currentRole === 'Admin' && (
        <div className="cbc-card p-5 space-y-3">
          <h2 className="text-sm font-black flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-[#D0B335]" />
            Lot 1 sign-off (FS8-06)
          </h2>
          <div className="flex flex-wrap gap-2 items-end">
            <select
              value={signRole}
              onChange={(e) => setSignRole(e.target.value)}
              className="px-3 py-2 rounded-xl border text-xs"
            >
              <option value="cbc_ops">CBC ops</option>
              <option value="tech_lead">Tech lead</option>
              <option value="sponsor">Sponsor</option>
            </select>
            <input
              value={signName}
              onChange={(e) => setSignName(e.target.value)}
              placeholder="Name"
              className="px-3 py-2 rounded-xl border text-xs"
            />
            <button
              type="button"
              className="px-3 py-2 rounded-xl bg-emerald-700 text-white text-xs font-bold"
              onClick={async () => {
                if (!signName.trim()) return;
                await pilotService.createSignoff({
                  role: signRole,
                  name: signName.trim(),
                  decision: 'approved',
                  comment: 'Lot 1 UAT sign-off',
                });
                setSignName('');
                addToast({ type: 'success', title: 'Sign-off', message: 'Recorded' });
                await refresh();
              }}
            >
              Approve & sign
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
