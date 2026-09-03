/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useCallback, useEffect, useState } from 'react';
import { Download, RefreshCw } from 'lucide-react';
import { useApp } from '../context/AppContext';
import { PageHeader } from '../components/layout/PageHeader';
import { auditService, AuditEntry } from '../services/api/audit.service';

/**
 * Écran Audit.
 *
 * Cet écran reconstituait auparavant sa propre piste d'audit dans le
 * navigateur, à partir des alertes et des utilisateurs, avec une adresse IP
 * codée en dur (`10.1.1.40`) sur chaque ligne et une entrée d'exemple
 * injectée — puis proposait ce résultat à l'export « pour COBAC ». Le journal
 * d'audit réel du serveur n'était jamais consulté.
 *
 * Les lignes proviennent désormais de `GET /api/audit`, et l'export CSV est
 * produit par le serveur à partir des lignes persistées.
 */
export const AuditView: React.FC = () => {
  const { addToast } = useApp();

  const [rows, setRows] = useState<AuditEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await auditService.list({ limit: 200 });
      setRows(result.data);
      setTotal(result.pagination.total);
    } catch (err: any) {
      const status = err?.response?.status;
      setError(
        status === 403
          ? "Votre rôle ne donne pas accès à la piste d'audit."
          : "La piste d'audit n'a pas pu être chargée."
      );
      setRows([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const exportCobac = async () => {
    setExporting(true);
    try {
      // Le serveur construit le CSV : le fichier réglementaire ne peut donc
      // pas contenir de données reconstituées côté navigateur.
      await auditService.downloadExport();
      addToast({
        type: 'success',
        title: 'Export COBAC',
        message: 'Fichier CSV généré à partir du journal serveur.',
      });
    } catch {
      addToast({
        type: 'error',
        title: 'Export impossible',
        message: "La piste d'audit n'a pas pu être exportée.",
      });
    } finally {
      setExporting(false);
    }
  };

  const formatDate = (iso: string) => {
    if (!iso) return '—';
    const d = new Date(iso);
    return Number.isNaN(d.getTime()) ? iso : d.toLocaleString('fr-FR');
  };

  return (
    <div className="space-y-5">
      <PageHeader
        title="Audit"
        subtitle={
          loading
            ? 'Chargement du journal…'
            : `Traçabilité des actions — ${total} évènement(s) enregistré(s).`
        }
        secondaryActions={
          <button type="button" className="cbc-btn-secondary" onClick={() => void load()}>
            <RefreshCw className="w-3.5 h-3.5" />
            Actualiser
          </button>
        }
        primaryAction={
          <button
            type="button"
            className="cbc-btn-primary"
            onClick={() => void exportCobac()}
            disabled={exporting || !!error}
          >
            <Download className="w-3.5 h-3.5" />
            {exporting ? 'Export en cours…' : 'Exporter pour COBAC'}
          </button>
        }
      />

      {error && (
        <div className="cbc-card p-4 border border-rose-200 bg-rose-50">
          <p className="text-[13px] font-semibold text-rose-800">{error}</p>
        </div>
      )}

      <div className="cbc-card overflow-hidden">
        {loading ? (
          <div className="py-16 text-center text-[13px] text-[var(--color-tx3)]">Chargement…</div>
        ) : rows.length === 0 && !error ? (
          <div className="py-16 text-center">
            <div className="text-[15px] font-bold">Aucun évènement</div>
            <div className="text-[13px] text-[#777] mt-2">
              Le journal d'audit est vide. Les actions d'administration y sont
              enregistrées au fur et à mesure.
            </div>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full border-collapse">
              <thead>
                <tr className="bg-[var(--color-ln2)] border-b border-[var(--color-ln)]">
                  {['Horodatage', 'Acteur', 'Action', 'Cible', 'Adresse IP', 'Statut'].map((c) => (
                    <th
                      key={c}
                      className="text-left px-3 py-2.5 text-[10.5px] font-bold uppercase tracking-wider text-[var(--color-tx3)] whitespace-nowrap"
                    >
                      {c}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.id} className="border-b border-[var(--color-ln2)]">
                    <td className="p-3 tnum text-[12.5px] text-[var(--color-tx2)] whitespace-nowrap">
                      {formatDate(r.created_at)}
                    </td>
                    <td className="p-3 text-[13px] font-semibold">{r.username || r.user_id || '—'}</td>
                    <td className="p-3 tnum text-[12.5px]">{r.event_type}</td>
                    <td className="p-3 text-[12.5px] text-[var(--color-tx2)]">{r.target || '—'}</td>
                    {/* Adresse réellement observée sur la requête, jamais une
                        valeur d'affichage. Vide si le serveur ne l'a pas
                        enregistrée — c'est une information plus honnête
                        qu'une IP inventée. */}
                    <td className="p-3 tnum text-[12.5px] text-[var(--color-tx2)]">{r.ip_address || '—'}</td>
                    <td className="p-3">
                      <span
                        className={`inline-flex px-2 py-0.5 rounded-md border text-[11px] font-semibold ${
                          r.status === 'success'
                            ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
                            : 'bg-rose-50 text-rose-800 border-rose-200'
                        }`}
                      >
                        {r.status === 'success' ? 'Succès' : 'Échec'}
                      </span>
                    </td>
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
