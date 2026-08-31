/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useEffect, useState } from 'react';
import { Check, X } from 'lucide-react';
import { useApp } from '../context/AppContext';
import { actionsService, ApprovalRow } from '../services/api/actions.service';
import { PageHeader } from '../components/layout/PageHeader';

export const ApprovalsView: React.FC = () => {
  const { addToast, currentRole } = useApp();
  const [rows, setRows] = useState<ApprovalRow[]>([]);
  const [filter, setFilter] = useState('pending');

  const refresh = async () => {
    setRows(await actionsService.listApprovals(filter));
  };

  useEffect(() => {
    void refresh().catch(() => undefined);
  }, [filter]);

  return (
    <div className="space-y-5">
      <PageHeader
        title="Approbations"
        subtitle="File d'attente SEC-005 — approve / deny avant dispatch agent."
        secondaryActions={
          <select
            className="cbc-input py-2 max-w-[180px]"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          >
            <option value="pending">En attente</option>
            <option value="approved">Approuvées</option>
            <option value="denied">Refusées</option>
            <option value="all">Toutes</option>
          </select>
        }
      />

      <div className="space-y-3">
        {rows.length === 0 && (
          <p className="text-sm text-slate-500 cbc-card p-4">Aucune demande.</p>
        )}
        {rows.map((a) => (
          <div key={a.id} className="cbc-card p-4 text-xs space-y-2">
            <div className="flex justify-between gap-2">
              <p className="font-bold">
                {a.task?.plugin || 'task'} · {a.status}
              </p>
              <span className="font-mono text-slate-500">{a.id.slice(0, 8)}…</span>
            </div>
            <p className="text-slate-600">
              Agent {a.task?.agent_id?.slice(0, 8)}… · dry-run={String(a.task?.dry_run)} · by{' '}
              {a.requested_by || '—'}
            </p>
            <pre className="bg-slate-50 p-2 rounded-lg overflow-auto max-h-24">
              {JSON.stringify(a.task?.input || {}, null, 2)}
            </pre>
            {currentRole === 'Admin' && a.status === 'pending' && (
              <div className="flex gap-2">
                <button
                  type="button"
                  className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg bg-emerald-700 text-white font-semibold"
                  onClick={async () => {
                    await actionsService.decide(a.id, 'approved', 'OK');
                    addToast({ type: 'success', title: 'Approved', message: a.id });
                    await refresh();
                  }}
                >
                  <Check className="w-3.5 h-3.5" />
                  Approve
                </button>
                <button
                  type="button"
                  className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg bg-rose-700 text-white font-semibold"
                  onClick={async () => {
                    await actionsService.decide(a.id, 'denied', 'Denied');
                    addToast({ type: 'success', title: 'Denied', message: a.id });
                    await refresh();
                  }}
                >
                  <X className="w-3.5 h-3.5" />
                  Deny
                </button>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};
