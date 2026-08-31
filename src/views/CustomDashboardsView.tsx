/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useEffect, useState } from 'react';
import { Plus, Share2, Trash2 } from 'lucide-react';
import { useApp } from '../context/AppContext';
import { useI18n } from '../i18n';
import { analysisService } from '../services/api/analysis.service';
import { PageHeader } from '../components/layout/PageHeader';

type Widget = { id: string; type: string; title: string };

type Board = {
  id: string;
  name: string;
  widgets: Widget[];
  shared: boolean;
  owner_id?: string;
};

const WIDGET_CATALOG: Widget[] = [
  { id: 'kpi-agents', type: 'kpi_agents', title: 'Agents online' },
  { id: 'kpi-alerts', type: 'kpi_alerts', title: 'Open alerts' },
  { id: 'kpi-critical', type: 'kpi_critical', title: 'Critical alerts' },
  { id: 'list-alerts', type: 'list_alerts', title: 'Recent alerts' },
];

export const CustomDashboardsView: React.FC = () => {
  const { t } = useI18n();
  const { agents, alerts, addToast, currentUser } = useApp();
  const [boards, setBoards] = useState<Board[]>([]);
  const [selectedId, setSelectedId] = useState('');
  const [name, setName] = useState('Ops board');

  const refresh = async () => {
    const data = await analysisService.listDashboards();
    setBoards(data);
    if (!selectedId && data[0]) setSelectedId(data[0].id);
  };

  useEffect(() => {
    void refresh().catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const selected = boards.find((b) => b.id === selectedId);

  const renderWidget = (w: Widget) => {
    const open = alerts.filter((a) => a.status === 'open');
    if (w.type === 'kpi_agents') {
      return (
        <p className="text-2xl font-black">
          {agents.filter((a) => a.status === 'online').length}/{agents.length}
        </p>
      );
    }
    if (w.type === 'kpi_alerts') return <p className="text-2xl font-black text-amber-600">{open.length}</p>;
    if (w.type === 'kpi_critical') {
      return (
        <p className="text-2xl font-black text-rose-600">
          {open.filter((a) => a.severity === 'critical').length}
        </p>
      );
    }
    return (
      <ul className="text-xs space-y-1 max-h-28 overflow-auto">
        {alerts.slice(0, 5).map((a) => (
          <li key={a.id} className="truncate">
            {a.severity} — {a.message}
          </li>
        ))}
      </ul>
    );
  };

  return (
    <div className="space-y-5">
      <PageHeader
        title={t('dashboards.title')}
        subtitle={t('dashboards.subtitle')}
        primaryAction={
          <button
            type="button"
            onClick={async () => {
              const created = await analysisService.createDashboard({
                name: name || 'Board',
                widgets: WIDGET_CATALOG.slice(0, 3),
                shared: false,
              });
              addToast({ type: 'success', title: 'Tableau', message: created.name });
              await refresh();
              setSelectedId(created.id);
            }}
            className="cbc-btn-primary"
          >
            <Plus className="w-4 h-4" />
            {t('dashboards.create')}
          </button>
        }
        secondaryActions={
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="cbc-input max-w-[200px] py-2"
          />
        }
      />

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        <div className="cbc-card p-3 space-y-2">
          {boards.length === 0 ? (
            <p className="text-xs text-slate-500 p-2">{t('dashboards.empty')}</p>
          ) : (
            boards.map((b) => (
              <button
                key={b.id}
                onClick={() => setSelectedId(b.id)}
                className={`w-full text-left px-3 py-2 rounded-xl text-xs font-semibold ${
                  selectedId === b.id ? 'bg-slate-900 text-white' : 'bg-slate-50 hover:bg-slate-100'
                }`}
              >
                {b.name}
                {b.shared ? ` · ${t('dashboards.shared')}` : ''}
              </button>
            ))
          )}
        </div>

        <div className="lg:col-span-3 space-y-3">
          {selected && (
            <div className="flex flex-wrap gap-2 items-center">
              <button
                className="inline-flex items-center gap-1 px-3 py-1.5 rounded-xl border text-xs font-bold"
                onClick={async () => {
                  await analysisService.updateDashboard(selected.id, {
                    name: selected.name,
                    widgets: selected.widgets,
                    shared: !selected.shared,
                  });
                  await refresh();
                }}
              >
                <Share2 className="w-3.5 h-3.5" />
                {selected.shared ? 'Unshare' : t('dashboards.shared')}
              </button>
              {selected.owner_id === currentUser?.id && (
                <button
                  className="inline-flex items-center gap-1 px-3 py-1.5 rounded-xl border border-rose-200 text-rose-700 text-xs font-bold"
                  onClick={async () => {
                    await analysisService.deleteDashboard(selected.id);
                    setSelectedId('');
                    await refresh();
                  }}
                >
                  <Trash2 className="w-3.5 h-3.5" />
                  Delete
                </button>
              )}
              <div className="flex flex-wrap gap-1">
                {WIDGET_CATALOG.map((w) => (
                  <button
                    key={w.id}
                    className="px-2 py-1 rounded-lg bg-slate-100 text-[11px] font-semibold"
                    onClick={async () => {
                      const widgets = [...(selected.widgets || [])];
                      if (!widgets.find((x) => x.id === w.id)) widgets.push(w);
                      await analysisService.updateDashboard(selected.id, {
                        name: selected.name,
                        widgets,
                        shared: selected.shared,
                      });
                      await refresh();
                    }}
                  >
                    + {w.title}
                  </button>
                ))}
              </div>
            </div>
          )}

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {(selected?.widgets || []).map((w) => (
              <div key={w.id} className="cbc-card p-4">
                <p className="text-[11px] font-bold uppercase text-slate-500 mb-2">{w.title}</p>
                {renderWidget(w)}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
