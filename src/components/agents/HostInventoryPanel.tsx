/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useEffect, useMemo, useState } from 'react';
import { AlertTriangle, Package, Search } from 'lucide-react';
import { HostInventory, agentsService } from '../../services/api/agents.service';

/**
 * Inventaire logiciel d'un hôte : applications et pilotes installés.
 *
 * Le relevé est daté et **rare** — il interroge la base de registre ou le
 * gestionnaire de paquets, et ne bouge qu'à l'occasion d'une installation.
 * La date est donc affichée : lire une liste d'applications sans savoir de
 * quand elle date conduirait à conclure sur un état périmé.
 *
 * Une section indisponible est dite comme telle, jamais rendue par une liste
 * vide : « aucun pilote installé » et « les pilotes n'ont pas pu être lus »
 * appellent des décisions opposées.
 */

type Tab = 'applications' | 'drivers';

export const HostInventoryPanel: React.FC<{ agentId: string }> = ({ agentId }) => {
  const [inventory, setInventory] = useState<HostInventory | null>(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const [tab, setTab] = useState<Tab>('applications');
  const [query, setQuery] = useState('');

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    agentsService
      .getInventory(agentId)
      .then((data) => {
        if (!cancelled) setInventory(data);
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [agentId]);

  const rows = useMemo(() => {
    if (!inventory) return [];
    const source = tab === 'applications' ? inventory.applications : inventory.drivers;
    const needle = query.trim().toLowerCase();
    if (!needle) return source;
    return source.filter((r) =>
      [r.name, (r as { version?: string | null }).version, (r as { publisher?: string | null }).publisher]
        .filter(Boolean)
        .some((v) => String(v).toLowerCase().includes(needle))
    );
  }, [inventory, tab, query]);

  if (loading) {
    return <div className="cbc-card p-6 text-[12.5px] text-[var(--color-tx2)]">Chargement de l’inventaire…</div>;
  }

  if (failed) {
    return <div className="cbc-card p-6 text-[12.5px] text-[var(--color-tx2)]">Inventaire indisponible.</div>;
  }

  const collectedAt = inventory?.collected_at;
  if (!collectedAt) {
    return (
      <div className="cbc-card p-6">
        <div className="flex items-start gap-3">
          <Package className="w-5 h-5 text-[var(--color-tx3)] shrink-0 mt-0.5" />
          <div>
            <h3 className="text-[14px] font-bold m-0">Inventaire pas encore remonté</h3>
            <p className="text-[12.5px] text-[var(--color-tx2)] mt-1.5 mb-0 max-w-2xl">
              L’agent transmet son inventaire logiciel peu après son premier battement,
              puis à cadence lente. Un hôte fraîchement enrôlé n’a donc encore rien
              envoyé — ce n’est pas un défaut.
            </p>
          </div>
        </div>
      </div>
    );
  }

  const unavailable = inventory?.unavailable || [];
  const truncated = inventory?.truncated || [];

  return (
    <div className="space-y-4">
      <div className="cbc-card px-5 py-3.5 flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-2.5">
          <Package className="w-4 h-4 text-[#A68523]" />
          <span className="text-[13.5px] font-bold">Inventaire logiciel</span>
          <span className="text-[11.5px] text-[var(--color-tx2)]">
            relevé le {new Date(collectedAt).toLocaleString()}
          </span>
        </div>
        <div className="flex items-center gap-2">
          {(['applications', 'drivers'] as Tab[]).map((id) => (
            <button
              key={id}
              type="button"
              onClick={() => setTab(id)}
              className={`px-3 py-1.5 rounded-lg text-[12.5px] font-semibold ${
                tab === id ? 'bg-slate-900 text-white' : 'text-[var(--color-tx2)] hover:bg-[var(--color-ln2)]'
              }`}
            >
              {id === 'applications' ? 'Applications' : 'Pilotes'} (
              {id === 'applications'
                ? inventory?.applications.length ?? 0
                : inventory?.drivers.length ?? 0}
              )
            </button>
          ))}
        </div>
      </div>

      {(unavailable.length > 0 || truncated.length > 0) && (
        <div className="cbc-card p-4 border-amber-200">
          <div className="flex items-start gap-2.5">
            <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
            <div className="text-[12.5px] text-[var(--color-tx2)]">
              {unavailable.length > 0 && (
                <p className="m-0">
                  Sections que l’hôte n’a pas pu lire : <strong>{unavailable.join(', ')}</strong>.
                  Une liste vide ici ne veut donc pas dire « rien d’installé ».
                </p>
              )}
              {truncated.map((note) => (
                <p key={note} className="m-0 mt-1">
                  Liste tronquée — {note}.
                </p>
              ))}
            </div>
          </div>
        </div>
      )}

      <div className="cbc-card overflow-hidden">
        <div className="px-5 py-3 border-b border-[var(--color-ln2)] flex items-center gap-2">
          <Search className="w-3.5 h-3.5 text-[var(--color-tx3)]" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={tab === 'applications' ? 'Filtrer par nom, version, éditeur…' : 'Filtrer par nom…'}
            className="flex-1 text-[12.5px] outline-none bg-transparent"
          />
          <span className="text-[11.5px] text-[var(--color-tx3)] tnum">{rows.length}</span>
        </div>

        {rows.length === 0 ? (
          <p className="px-5 py-6 text-[12.5px] text-[var(--color-tx2)] m-0">
            {query ? 'Aucune correspondance.' : 'Rien à afficher.'}
          </p>
        ) : (
          <div className="overflow-x-auto max-h-[420px] overflow-y-auto">
            <table className="w-full text-[12.5px]">
              <thead className="sticky top-0 bg-[var(--color-panel)]">
                <tr className="text-left text-[10.5px] uppercase tracking-wider text-[var(--color-tx3)] border-b border-[var(--color-ln2)]">
                  <th className="px-5 py-2.5 font-bold">Nom</th>
                  <th className="px-5 py-2.5 font-bold">Version</th>
                  <th className="px-5 py-2.5 font-bold">
                    {tab === 'applications' ? 'Éditeur' : 'État'}
                  </th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r, i) => (
                  <tr key={`${r.name}-${i}`} className="border-b border-[var(--color-ln2)] last:border-0">
                    <td className="px-5 py-2 font-semibold">
                      {r.name}
                      {tab === 'drivers' && (r as { display_name?: string | null }).display_name && (
                        <span className="text-[var(--color-tx2)] font-normal">
                          {' '}
                          — {(r as { display_name?: string | null }).display_name}
                        </span>
                      )}
                    </td>
                    <td className="px-5 py-2 tnum text-[var(--color-tx2)]">
                      {(r as { version?: string | null }).version || '—'}
                    </td>
                    <td className="px-5 py-2 text-[var(--color-tx2)]">
                      {tab === 'applications'
                        ? (r as { publisher?: string | null }).publisher || '—'
                        : (r as { state?: string | null }).state || '—'}
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
