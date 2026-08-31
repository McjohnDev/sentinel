/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useEffect, useState } from 'react';
import { Search } from 'lucide-react';
import { logsService } from '../services/api/logs.service';
import { PageHeader } from '../components/layout/PageHeader';

export const LogsView: React.FC = () => {
  const [q, setQ] = useState('');
  const [host, setHost] = useState('');
  const [severity, setSeverity] = useState('');
  const [source, setSource] = useState('');
  const [rows, setRows] = useState<
    Array<{ ts: string; message: string; host?: string; severity?: string; source?: string; channel?: string }>
  >([]);
  const [status, setStatus] = useState('');
  const [loading, setLoading] = useState(false);

  const runSearch = () => {
    setLoading(true);
    logsService
      .search({ q, host, severity, source, hours: 24, limit: 200 })
      .then((res) => {
        setStatus(res.status);
        setRows(res.result || []);
      })
      .catch(() => setStatus('error'))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    runSearch();
    // initial load only
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="space-y-5">
      <PageHeader
        title="Journaux"
        subtitle="Recherche plein texte sur les journaux collectés (Loki local)."
      />

      <div className="cbc-card p-4 flex flex-wrap gap-3 items-end">
        <label className="flex-1 min-w-[160px]">
          <span className="text-[11px] font-bold text-slate-500 uppercase">Texte</span>
          <div className="relative mt-1">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              className="cbc-input pl-9"
              placeholder="erreur, nginx, …"
            />
          </div>
        </label>
        <label className="w-40">
          <span className="text-[11px] font-bold text-slate-500 uppercase">Hôte</span>
          <input
            value={host}
            onChange={(e) => setHost(e.target.value)}
            className="cbc-input mt-1"
            placeholder="web-01"
          />
        </label>
        <label className="w-36">
          <span className="text-[11px] font-bold text-slate-500 uppercase">Gravité</span>
          <select
            value={severity}
            onChange={(e) => setSeverity(e.target.value)}
            className="cbc-input mt-1"
          >
            <option value="">Toutes</option>
            <option value="info">info</option>
            <option value="warning">warning</option>
            <option value="error">error</option>
            <option value="critical">critical</option>
          </select>
        </label>
        <label className="w-40">
          <span className="text-[11px] font-bold text-slate-500 uppercase">Source</span>
          <select
            value={source}
            onChange={(e) => setSource(e.target.value)}
            className="cbc-input mt-1"
          >
            <option value="">Toutes</option>
            <option value="file">fichier</option>
            <option value="journald">journald</option>
            <option value="winevt">Event Log</option>
          </select>
        </label>
        <button
          onClick={runSearch}
          className="cbc-btn-primary"
        >
          {loading ? 'Recherche…' : 'Rechercher'}
        </button>
      </div>

      <div className="cbc-card overflow-hidden">
        {rows.length === 0 ? (
          <p className="p-6 text-sm text-slate-500">
            Aucun journal{status ? ` (${status})` : ''}. Activez `logs.enabled` dans l’agent et vérifiez GET /health/logs.
          </p>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left text-[11px] uppercase text-slate-500">
              <tr>
                <th className="px-4 py-2">Heure</th>
                <th className="px-4 py-2">Hôte</th>
                <th className="px-4 py-2">Source</th>
                <th className="px-4 py-2">Gravité</th>
                <th className="px-4 py-2">Message</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={`${r.ts}-${i}`} className="border-t border-slate-100">
                  <td className="px-4 py-2 whitespace-nowrap text-slate-500">{new Date(r.ts).toLocaleString()}</td>
                  <td className="px-4 py-2">{r.host}</td>
                  <td className="px-4 py-2">{r.source || 'file'}{r.channel ? `/${r.channel}` : ''}</td>
                  <td className="px-4 py-2">{r.severity}</td>
                  <td className="px-4 py-2 font-mono text-xs break-all">{r.message}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
};
