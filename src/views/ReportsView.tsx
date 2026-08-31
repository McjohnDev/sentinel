/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useEffect, useState } from 'react';
import { Plus } from 'lucide-react';
import { useI18n } from '../i18n';
import { useApp } from '../context/AppContext';
import { analysisService } from '../services/api/analysis.service';
import { PageHeader } from '../components/layout/PageHeader';

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export const ReportsView: React.FC = () => {
  const { t } = useI18n();
  const { addToast, currentRole } = useApp();
  const [schedules, setSchedules] = useState<
    Array<{ id: string; name: string; format: string; cron: string; enabled: boolean; last_status?: string }>
  >([]);
  const [name, setName] = useState('Daily fleet');
  const [format, setFormat] = useState<'csv' | 'pdf'>('csv');

  const refresh = async () => {
    setSchedules(await analysisService.listReportSchedules());
  };

  useEffect(() => {
    void refresh().catch(() => undefined);
  }, []);

  return (
    <div className="space-y-5">
      <PageHeader
        title={t('reports.title')}
        subtitle={t('reports.subtitle')}
        primaryAction={
          <button
            type="button"
            className="cbc-btn-primary"
            onClick={async () => {
              const blob = await analysisService.generateReport('pdf');
              downloadBlob(blob, 'cbc-fleet-report.pdf');
              addToast({ type: 'success', title: 'PDF', message: 'Téléchargement lancé' });
            }}
          >
            {t('reports.pdf')}
          </button>
        }
        secondaryActions={
          <button
            type="button"
            className="cbc-btn-secondary"
            onClick={async () => {
              const blob = await analysisService.generateReport('csv');
              downloadBlob(blob, 'cbc-fleet-report.csv');
              addToast({ type: 'success', title: 'CSV', message: 'Téléchargement lancé' });
            }}
          >
            {t('reports.csv')}
          </button>
        }
      />

      {currentRole === 'Admin' && (
        <div className="cbc-card p-4 flex flex-wrap gap-2 items-end">
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="cbc-input max-w-[220px]"
          />
          <select
            value={format}
            onChange={(e) => setFormat(e.target.value as 'csv' | 'pdf')}
            className="cbc-input max-w-[120px]"
          >
            <option value="csv">CSV</option>
            <option value="pdf">PDF</option>
          </select>
          <button
            className="cbc-btn-secondary"
            onClick={async () => {
              await analysisService.createReportSchedule({
                name,
                format,
                cron: '0 7 * * *',
                enabled: true,
              });
              await refresh();
            }}
          >
            <Plus className="w-4 h-4" />
            Schedule
          </button>
        </div>
      )}

      <div className="cbc-card overflow-hidden">
        <table className="w-full text-xs">
          <thead className="bg-slate-50 text-[10px] uppercase text-slate-500 text-left">
            <tr>
              <th className="px-4 py-2">Name</th>
              <th className="px-4 py-2">Format</th>
              <th className="px-4 py-2">Cron</th>
              <th className="px-4 py-2">Last status</th>
            </tr>
          </thead>
          <tbody>
            {schedules.map((s) => (
              <tr key={s.id} className="border-t border-slate-100">
                <td className="px-4 py-2 font-bold">{s.name}</td>
                <td className="px-4 py-2">{s.format}</td>
                <td className="px-4 py-2 font-mono">{s.cron}</td>
                <td className="px-4 py-2">{s.last_status || '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {schedules.length === 0 && <p className="p-4 text-xs text-slate-500">No schedules yet.</p>}
      </div>
    </div>
  );
};
