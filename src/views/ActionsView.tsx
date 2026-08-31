/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useEffect, useState } from 'react';
import { Send } from 'lucide-react';
import { useApp } from '../context/AppContext';
import { actionsService, ActionTask } from '../services/api/actions.service';
import { PageHeader } from '../components/layout/PageHeader';

export const ActionsView: React.FC = () => {
  const { agents, addToast, currentRole } = useApp();
  const [plugins, setPlugins] = useState<Array<{ plugin: string; requires_approval_when_live: boolean }>>([]);
  const [tasks, setTasks] = useState<ActionTask[]>([]);
  const [agentId, setAgentId] = useState('');
  const [plugin, setPlugin] = useState('health.check');
  const [dryRun, setDryRun] = useState(true);
  const [serviceName, setServiceName] = useState('nginx');
  const [operation, setOperation] = useState('status');

  const refresh = async () => {
    const [p, t] = await Promise.all([actionsService.listPlugins(), actionsService.listTasks()]);
    setPlugins(p);
    setTasks(t);
    if (!agentId && agents[0]) setAgentId(agents[0].id);
    if (!plugin && p[0]) setPlugin(p[0].plugin);
  };

  useEffect(() => {
    void refresh().catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [agents.length]);

  const canEdit = currentRole === 'Admin' || currentRole === 'Operator';

  return (
    <div className="space-y-5">
      <PageHeader
        title="Actions à distance"
        subtitle="Lot 2 — task.v1 signé · dry-run par défaut · L0 rejette · L1 via capability."
      />

      {canEdit && (
        <div className="cbc-card p-5 space-y-3">
          <h2 className="text-sm font-black">Nouvelle action</h2>
          <div className="flex flex-wrap gap-2 items-end">
            <select
              className="px-3 py-2 rounded-xl border text-xs"
              value={agentId}
              onChange={(e) => setAgentId(e.target.value)}
            >
              {agents.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.hostname || a.name || a.id}
                </option>
              ))}
            </select>
            <select
              className="px-3 py-2 rounded-xl border text-xs"
              value={plugin}
              onChange={(e) => setPlugin(e.target.value)}
            >
              {plugins.map((p) => (
                <option key={p.plugin} value={p.plugin}>
                  {p.plugin}
                </option>
              ))}
            </select>
            {plugin === 'service.manage' && (
              <>
                <input
                  className="px-3 py-2 rounded-xl border text-xs"
                  value={serviceName}
                  onChange={(e) => setServiceName(e.target.value)}
                  placeholder="service"
                />
                <select
                  className="px-3 py-2 rounded-xl border text-xs"
                  value={operation}
                  onChange={(e) => setOperation(e.target.value)}
                >
                  {['status', 'start', 'stop', 'restart'].map((o) => (
                    <option key={o} value={o}>
                      {o}
                    </option>
                  ))}
                </select>
              </>
            )}
            {plugin === 'pci.hygiene' && (
              <span className="text-[11px] text-slate-500 max-w-xs">
                Checklist hygiène PCI (Req 1/2/5/10) — score uniquement, pas une AoC/ASV.
              </span>
            )}
            <label className="inline-flex items-center gap-1 text-xs font-bold px-2">
              <input type="checkbox" checked={dryRun} onChange={(e) => setDryRun(e.target.checked)} />
              Dry-run
            </label>
            <button
              type="button"
            className="cbc-btn-primary"
              onClick={async () => {
                if (!agentId) return;
                const input =
                  plugin === 'service.manage'
                    ? { service: serviceName, operation }
                    : plugin === 'metrics.on_demand'
                      ? { families: ['cpu', 'memory'] }
                      : plugin === 'pci.hygiene'
                        ? {}
                        : {};
                const res = await actionsService.createTask({
                  agent_id: agentId,
                  plugin,
                  input,
                  dry_run: dryRun,
                });
                addToast({
                  type: 'success',
                  title: 'Action',
                  message: res.approval_id
                    ? `Pending approval ${res.approval_id}`
                    : `Queued ${res.task?.id}`,
                });
                await refresh();
              }}
            >
              <Send className="w-4 h-4" />
              Submit
            </button>
          </div>
          {currentRole === 'Admin' && agentId && (
            <button
              type="button"
              className="text-xs font-bold text-blue-700"
              onClick={async () => {
                await actionsService.setCapability(agentId, 'L1');
                addToast({
                  type: 'success',
                  title: 'Capability',
                  message: 'Agent marked L1 — also publish group config capability_level',
                });
              }}
            >
              Mark agent L1 (platform flag)
            </button>
          )}
        </div>
      )}

      <div className="cbc-card overflow-hidden">
        <table className="w-full text-xs">
          <thead className="bg-slate-50 text-[10px] uppercase text-slate-500 text-left">
            <tr>
              <th className="px-4 py-2">Task</th>
              <th className="px-4 py-2">Plugin</th>
              <th className="px-4 py-2">Dry-run</th>
              <th className="px-4 py-2">Status</th>
              <th className="px-4 py-2">Result</th>
            </tr>
          </thead>
          <tbody>
            {tasks.map((t) => (
              <tr key={t.id} className="border-t border-slate-100">
                <td className="px-4 py-2 font-mono">{t.id.slice(0, 8)}…</td>
                <td className="px-4 py-2 font-bold">{t.plugin}</td>
                <td className="px-4 py-2">{t.dry_run ? 'yes' : 'no'}</td>
                <td className="px-4 py-2">{t.status}</td>
                <td className="px-4 py-2 max-w-xs truncate" title={JSON.stringify(t.result || t.rejection_reason || '')}>
                  {(() => {
                    if (t.rejection_reason) return t.rejection_reason;
                    const out = (t.result as { output?: { score?: number; grade?: string; schema?: string } })?.output
                      || (t.result as { score?: number; grade?: string; schema?: string } | null);
                    if (out && (out as { schema?: string }).schema === 'pci.hygiene.v1') {
                      const o = out as { score?: number; grade?: string };
                      return `PCI ${o.score ?? '?'}% (${o.grade || '—'})`;
                    }
                    if (t.plugin === 'pci.hygiene' && out && typeof (out as { score?: number }).score === 'number') {
                      const o = out as { score: number; grade?: string };
                      return `PCI ${o.score}% (${o.grade || '—'})`;
                    }
                    return t.result ? JSON.stringify(t.result).slice(0, 80) : '—';
                  })()}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {tasks.length === 0 && <p className="p-4 text-xs text-slate-500">No tasks yet.</p>}
      </div>
    </div>
  );
};
