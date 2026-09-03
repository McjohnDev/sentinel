/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { AlertTriangle, Network, Trash2, Upload } from 'lucide-react';
import {
  VlanImportResult,
  VlanSubnet,
  vlanSubnetsService,
} from '../../services/api/agents.service';
import { useApp } from '../../context/AppContext';

/**
 * Import du plan d'adressage fourni par l'équipe réseau.
 *
 * Une table `sous-réseau → VLAN`, et non une liste d'hôtes : une machine sur
 * port d'accès ne peut pas connaître son VLAN, mais l'agent remonte son
 * adresse IP à chaque battement. Le VLAN se déduit donc pour tout le parc
 * sans saisie par hôte, et la déduction suit d'elle-même quand une machine
 * change d'adresse. Une liste `hôte → VLAN` serait juste le jour de son
 * export et fausse dès la première machine rebranchée.
 *
 * Les lignes rejetées sont affichées, jamais tues : un import à moitié
 * appliqué rattacherait des hôtes à un VLAN qui n'est pas le leur.
 */
export const VlanPlanPanel: React.FC = () => {
  const { currentRole, addToast } = useApp();
  const [rows, setRows] = useState<VlanSubnet[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<VlanImportResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const isAdmin = currentRole === 'Admin';

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      setRows(await vlanSubnetsService.list());
    } catch {
      setError('Plan d’adressage indisponible.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  const onFile = async (file: File) => {
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const imported = await vlanSubnetsService.import(file);
      setResult(imported);
      await reload();
      addToast({
        type: imported.rejected.length ? 'info' : 'success',
        title: 'Plan d’adressage importé',
        message: `${imported.imported} sous-réseau(x) — ${imported.rejected.length} ligne(s) rejetée(s).`,
      });
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Import impossible.');
    } finally {
      setBusy(false);
      if (fileRef.current) fileRef.current.value = '';
    }
  };

  const onClear = async () => {
    setBusy(true);
    try {
      await vlanSubnetsService.clear();
      setResult(null);
      await reload();
      addToast({
        type: 'success',
        title: 'Plan d’adressage vidé',
        message: 'Les VLAN déduits disparaissent avec lui.',
      });
    } catch {
      setError('Suppression impossible.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-5">
      <div className="cbc-card p-6">
        <div className="flex items-start gap-4">
          <div className="w-10 h-10 rounded-xl bg-amber-50 text-[#A68523] grid place-items-center shrink-0">
            <Network className="w-5 h-5" />
          </div>
          <div className="min-w-0 flex-1">
            <h3 className="text-[15px] font-extrabold tracking-tight m-0">
              Plan d’adressage réseau
            </h3>
            <p className="text-[12.5px] text-[var(--color-tx2)] mt-2 leading-relaxed max-w-3xl mb-0">
              Fichier fourni par l’équipe réseau, associant chaque sous-réseau à son
              VLAN. La plupart des hôtes sont sur port d’accès et ne peuvent pas
              connaître leur VLAN : la plateforme le déduit de leur adresse IP,
              remontée à chaque battement. Aucune saisie par hôte n’est nécessaire, et
              la déduction suit une machine qui change d’adresse.
            </p>

            <div className="mt-4 p-3 rounded-xl bg-[var(--color-ln2)] border border-[var(--color-ln)]">
              <div className="text-[10.5px] font-bold uppercase tracking-wider text-[var(--color-tx3)] mb-1.5">
                Format attendu — CSV ou .xlsx
              </div>
              <pre className="text-[12px] text-[var(--color-tx2)] m-0 whitespace-pre overflow-x-auto">
{`Sous-réseau     ; VLAN ; Libellé
10.20.4.0/24    ; 20   ; Monétique
10.20.8.0/24    ; 30   ; Agences`}
              </pre>
              <p className="text-[11.5px] text-[var(--color-tx2)] mt-2 mb-0">
                Le séparateur point-virgule d’Excel, les en-têtes accentués et
                « VLAN 20 » écrit en toutes lettres sont acceptés. Un import
                remplace le plan précédent.
              </p>
            </div>

            {isAdmin && (
              <div className="flex items-center gap-2.5 mt-4 flex-wrap">
                <input
                  ref={fileRef}
                  type="file"
                  accept=".csv,.xlsx,.xlsm,text/csv"
                  className="hidden"
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file) void onFile(file);
                  }}
                />
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => fileRef.current?.click()}
                  className="cbc-btn-primary py-2 px-3.5 text-[12.5px] inline-flex items-center gap-2 disabled:opacity-50"
                >
                  <Upload className="w-3.5 h-3.5" />
                  {busy ? 'Import en cours…' : 'Importer un fichier'}
                </button>
                {rows.length > 0 && (
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => void onClear()}
                    className="cbc-btn-secondary py-2 px-3.5 text-[12.5px] inline-flex items-center gap-2 disabled:opacity-50"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                    Vider le plan
                  </button>
                )}
              </div>
            )}

            {error && (
              <div className="mt-4 p-3.5 rounded-xl bg-rose-50 border border-rose-200 flex items-start gap-2.5">
                <AlertTriangle className="w-4 h-4 text-rose-700 shrink-0 mt-0.5" />
                <div>
                  <p className="text-[12.5px] font-semibold text-rose-800 m-0">Import refusé</p>
                  <p className="text-[12.5px] text-rose-700 mt-1 mb-0 leading-relaxed">{error}</p>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {result && result.rejected.length > 0 && (
        <div className="cbc-card p-5 border-amber-200">
          <div className="flex items-center gap-2 mb-3">
            <AlertTriangle className="w-4 h-4 text-amber-600" />
            <h4 className="text-[13.5px] font-bold m-0">
              {result.rejected.length} ligne(s) non importée(s)
            </h4>
          </div>
          <p className="text-[12px] text-[var(--color-tx2)] mb-3">
            Ces lignes sont restées hors du plan. Les hôtes qu’elles devaient
            couvrir n’auront pas de VLAN déduit.
          </p>
          <ul className="space-y-1.5">
            {result.rejected.map((r) => (
              <li key={`${r.line}-${r.reason}`} className="text-[12.5px] text-[var(--color-tx2)]">
                <span className="tnum font-semibold">Ligne {r.line}</span> — {r.reason}
                {r.value ? <span className="text-[var(--color-tx2)]"> « {r.value} »</span> : null}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="cbc-card overflow-hidden">
        <div className="px-5 py-3.5 border-b border-[var(--color-ln2)] flex items-center justify-between">
          <h4 className="text-[13.5px] font-bold m-0">Sous-réseaux ({rows.length})</h4>
          {rows[0]?.imported_at && (
            <span className="text-[11.5px] text-[var(--color-tx2)]">
              Importé par {rows[0].imported_by || '—'}
              {rows[0].source_file ? ` · ${rows[0].source_file}` : ''}
            </span>
          )}
        </div>

        {loading ? (
          <p className="text-[12.5px] text-[var(--color-tx2)] px-5 py-6 m-0">Chargement…</p>
        ) : rows.length === 0 ? (
          <p className="text-[12.5px] text-[var(--color-tx2)] px-5 py-6 m-0">
            Aucun plan importé. Les hôtes n’auront de VLAN que s’il est saisi sur
            leur fiche, ou s’ils étiquettent eux-mêmes.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-[12.5px]">
              <thead>
                <tr className="text-left text-[10.5px] uppercase tracking-wider text-[var(--color-tx3)] border-b border-[var(--color-ln2)]">
                  <th className="px-5 py-2.5 font-bold">Sous-réseau</th>
                  <th className="px-5 py-2.5 font-bold">VLAN</th>
                  <th className="px-5 py-2.5 font-bold">Libellé</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.id} className="border-b border-[var(--color-ln2)] last:border-0">
                    <td className="px-5 py-2.5 tnum font-semibold">{r.cidr}</td>
                    <td className="px-5 py-2.5 tnum">{r.vlan}</td>
                    <td className="px-5 py-2.5 text-[var(--color-tx2)]">{r.label || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
