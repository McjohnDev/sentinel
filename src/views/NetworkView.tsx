/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useEffect, useState } from 'react';
import { Plus, RefreshCw, Trash2, Box } from 'lucide-react';
import { useI18n } from '../i18n';
import { useApp } from '../context/AppContext';
import { analysisService } from '../services/api/analysis.service';
import { PageHeader } from '../components/layout/PageHeader';

type Device = {
  id: string;
  name: string;
  host: string;
  icmp_status: string;
  snmp_status: string;
  sys_descr?: string;
  last_rtt_ms?: number;
  error_message?: string;
};

type Connector = {
  id: string;
  name: string;
  kind: string;
  status: string;
  endpoint?: string;
  last_payload?: Record<string, unknown> | null;
  error_message?: string;
};

export const NetworkView: React.FC = () => {
  const { t } = useI18n();
  const { addToast, currentRole } = useApp();
  const [devices, setDevices] = useState<Device[]>([]);
  const [connectors, setConnectors] = useState<Connector[]>([]);
  const [name, setName] = useState('');
  const [host, setHost] = useState('');
  const [community, setCommunity] = useState('public');
  const [dockerName, setDockerName] = useState('Docker local');
  const [dockerEndpoint, setDockerEndpoint] = useState('http://host.docker.internal:2375');

  const refresh = async () => {
    const [d, c] = await Promise.all([
      analysisService.listNetworkDevices(),
      analysisService.listConnectors(),
    ]);
    setDevices(d);
    setConnectors(c);
  };

  useEffect(() => {
    void refresh().catch(() => undefined);
  }, []);

  const statusColor = (s: string) => {
    if (s === 'up') return 'text-emerald-700 bg-emerald-50';
    if (s === 'down') return 'text-rose-700 bg-rose-50';
    if (s === 'degraded') return 'text-amber-700 bg-amber-50';
    return 'text-slate-600 bg-slate-50';
  };

  return (
    <div className="space-y-5">
      <PageHeader
        title={t('network.title')}
        subtitle={t('network.subtitle')}
        primaryAction={
          currentRole !== 'ReadOnly' ? (
            <button
              type="button"
              onClick={async () => {
                await analysisService.probeAllDevices();
                addToast({ type: 'success', title: 'Réseau', message: 'Sondage terminé' });
                await refresh();
              }}
              className="cbc-btn-primary"
            >
              <RefreshCw className="w-4 h-4" />
              {t('network.probeAll')}
            </button>
          ) : undefined
        }
      />

      {currentRole !== 'ReadOnly' && (
        <div className="cbc-card p-4 flex flex-wrap gap-2 items-end">
          <input
            placeholder="Name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="px-3 py-2 rounded-xl border text-xs"
          />
          <input
            placeholder="IP / host"
            value={host}
            onChange={(e) => setHost(e.target.value)}
            className="px-3 py-2 rounded-xl border text-xs"
          />
          <input
            placeholder="SNMP community"
            value={community}
            onChange={(e) => setCommunity(e.target.value)}
            className="px-3 py-2 rounded-xl border text-xs"
          />
          <button
            onClick={async () => {
              if (!name || !host) return;
              await analysisService.createNetworkDevice({
                name,
                host,
                snmp_community: community,
              });
              setName('');
              setHost('');
              await refresh();
            }}
            className="inline-flex items-center gap-1 px-3 py-2 rounded-xl bg-[#D0B335] text-slate-950 text-xs font-bold"
          >
            <Plus className="w-4 h-4" />
            {t('network.add')}
          </button>
        </div>
      )}

      <div className="cbc-card overflow-hidden">
        <table className="w-full text-xs">
          <thead className="bg-slate-50 text-left text-[10px] uppercase text-slate-500">
            <tr>
              <th className="px-4 py-2">Name</th>
              <th className="px-4 py-2">Host</th>
              <th className="px-4 py-2">ICMP</th>
              <th className="px-4 py-2">SNMP</th>
              <th className="px-4 py-2">RTT</th>
              <th className="px-4 py-2">sysDescr</th>
              <th className="px-4 py-2" />
            </tr>
          </thead>
          <tbody>
            {devices.map((d) => (
              <tr key={d.id} className="border-t border-slate-100">
                <td className="px-4 py-2 font-bold">{d.name}</td>
                <td className="px-4 py-2 font-mono">{d.host}</td>
                <td className="px-4 py-2">
                  <span className={`px-2 py-0.5 rounded-md font-semibold ${statusColor(d.icmp_status)}`}>
                    {d.icmp_status}
                  </span>
                </td>
                <td className="px-4 py-2">
                  <span className={`px-2 py-0.5 rounded-md font-semibold ${statusColor(d.snmp_status)}`}>
                    {d.snmp_status}
                  </span>
                </td>
                <td className="px-4 py-2">{d.last_rtt_ms != null ? `${d.last_rtt_ms} ms` : '—'}</td>
                <td className="px-4 py-2 max-w-xs truncate" title={d.sys_descr || d.error_message || ''}>
                  {d.sys_descr || d.error_message || '—'}
                </td>
                <td className="px-4 py-2 text-right space-x-2">
                  <button
                    className="font-bold text-blue-700"
                    onClick={async () => {
                      await analysisService.probeDevice(d.id);
                      await refresh();
                    }}
                  >
                    {t('network.probe')}
                  </button>
                  {currentRole !== 'ReadOnly' && (
                    <button
                      className="text-rose-600"
                      onClick={async () => {
                        await analysisService.deleteDevice(d.id);
                        await refresh();
                      }}
                    >
                      <Trash2 className="w-3.5 h-3.5 inline" />
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {devices.length === 0 && (
          <p className="p-4 text-xs text-slate-500">No network devices yet.</p>
        )}
      </div>

      <div className="cbc-card p-5 space-y-3">
        <h2 className="text-sm font-black flex items-center gap-2">
          <Box className="w-4 h-4 text-blue-600" />
          Docker host connector (PLT-004)
        </h2>
        {currentRole === 'Admin' && (
          <div className="flex flex-wrap gap-2">
            <input
              value={dockerName}
              onChange={(e) => setDockerName(e.target.value)}
              className="px-3 py-2 rounded-xl border text-xs"
            />
            <input
              value={dockerEndpoint}
              onChange={(e) => setDockerEndpoint(e.target.value)}
              className="px-3 py-2 rounded-xl border text-xs min-w-[260px] font-mono"
            />
            <button
              className="px-3 py-2 rounded-xl bg-slate-900 text-white text-xs font-bold"
              onClick={async () => {
                await analysisService.createConnector({
                  name: dockerName,
                  kind: 'docker_host',
                  endpoint: dockerEndpoint,
                });
                await refresh();
              }}
            >
              Add connector
            </button>
          </div>
        )}
        <div className="space-y-2">
          {connectors.map((c) => (
            <div key={c.id} className="p-3 rounded-xl bg-slate-50 border border-slate-200 text-xs flex justify-between gap-3">
              <div>
                <p className="font-bold">
                  {c.name} · {c.kind} ·{' '}
                  <span className={statusColor(c.status)}>{c.status}</span>
                </p>
                <p className="text-slate-500 font-mono">{c.endpoint || '—'}</p>
                {c.last_payload && (
                  <p className="mt-1">
                    running {String(c.last_payload.containers_running)} / {String(c.last_payload.containers_total)} · v
                    {String(c.last_payload.server_version || '?')}
                  </p>
                )}
                {c.error_message && <p className="text-rose-600 mt-1">{c.error_message}</p>}
              </div>
              <button
                className="font-bold text-blue-700 h-fit"
                onClick={async () => {
                  await analysisService.probeConnector(c.id);
                  await refresh();
                }}
              >
                Probe
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
