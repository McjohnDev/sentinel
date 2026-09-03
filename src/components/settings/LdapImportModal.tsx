/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState } from 'react';
import { Check, Search, UserPlus, X } from 'lucide-react';
import { LdapCandidate, usersService } from '../../services/api/users.service';
import { useApp } from '../../context/AppContext';

/**
 * Import d'un compte depuis l'annuaire.
 *
 * L'écran de création classique demande un mot de passe. Pour un compte
 * d'annuaire, ce serait un contresens : la plateforme détiendrait un secret
 * qu'elle n'a pas à connaître, et la révocation cesserait d'être immédiate —
 * un départ traité côté annuaire laisserait un accès local vivant.
 *
 * Ici aucun mot de passe n'est saisi ni stocké. L'authentification reste à
 * l'annuaire ; la plateforme ne tient que le rôle.
 *
 * Le rôle choisi est un **amorçage**. Comme pour un compte créé à la première
 * connexion, l'annuaire ne le réécrira plus ensuite : une promotion accordée
 * ici survit aux connexions suivantes.
 */

const ROLES = [
  { value: 'admin', label: 'Administrateur' },
  { value: 'operator', label: 'Opérateur' },
  { value: 'read_only', label: 'Lecture seule' },
];

interface Props {
  open: boolean;
  onClose: () => void;
  onImported: () => void;
}

export const LdapImportModal: React.FC<Props> = ({ open, onClose, onImported }) => {
  const { addToast } = useApp();
  const [term, setTerm] = useState('');
  const [results, setResults] = useState<LdapCandidate[] | null>(null);
  const [searching, setSearching] = useState(false);
  const [importing, setImporting] = useState<string | null>(null);
  const [roles, setRoles] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);

  if (!open) return null;

  const search = async () => {
    if (term.trim().length < 2) {
      setError('Saisir au moins deux caractères — en dessous, la recherche ramène tout l’annuaire.');
      return;
    }
    setSearching(true);
    setError(null);
    try {
      setResults(await usersService.searchLdap(term.trim()));
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Recherche impossible.');
      setResults(null);
    } finally {
      setSearching(false);
    }
  };

  const doImport = async (candidate: LdapCandidate) => {
    setImporting(candidate.username);
    try {
      await usersService.importFromLdap(candidate.username, roles[candidate.username] || candidate.suggested_role);
      addToast({
        type: 'success',
        title: 'Compte importé',
        message: `${candidate.display_name || candidate.username} — authentification par l’annuaire.`,
      });
      setResults((rows) =>
        (rows || []).map((r) => (r.username === candidate.username ? { ...r, already_imported: true } : r))
      );
      onImported();
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
      addToast({
        type: 'error',
        title: 'Import impossible',
        message: typeof detail === 'string' ? detail : 'Vérifier la configuration de l’annuaire.',
      });
    } finally {
      setImporting(null);
    }
  };

  return (
    <>
      <div className="fixed inset-0 z-40 bg-slate-950/40" onClick={onClose} />
      <div className="fixed inset-0 z-50 grid place-items-center p-4 pointer-events-none">
        <div className="cbc-card w-full max-w-[720px] pointer-events-auto overflow-hidden">
          <div className="px-5 py-4 border-b border-[var(--color-ln2)] flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <UserPlus className="w-4 h-4 text-[#A68523]" />
              <h3 className="text-[15px] font-bold m-0">Importer depuis l’annuaire</h3>
            </div>
            <button
              type="button"
              onClick={onClose}
              className="w-[30px] h-[30px] grid place-items-center rounded-lg text-[var(--color-tx3)] hover:bg-[var(--color-ln2)]"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          <div className="p-5">
            <p className="text-[12.5px] text-[var(--color-tx2)] mt-0 mb-4">
              Aucun mot de passe n’est saisi ni conservé : l’authentification reste à
              l’annuaire, et un départ traité de son côté ferme l’accès immédiatement.
            </p>

            <div className="flex items-center gap-2">
              <div className="flex items-center gap-2 flex-1 cbc-input py-1.5">
                <Search className="w-3.5 h-3.5 text-[var(--color-tx3)] shrink-0" />
                <input
                  autoFocus
                  value={term}
                  onChange={(e) => setTerm(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') void search();
                  }}
                  placeholder="Nom, identifiant ou adresse"
                  className="flex-1 text-[13px] outline-none bg-transparent"
                />
              </div>
              <button
                type="button"
                disabled={searching}
                onClick={() => void search()}
                className="cbc-btn-primary py-2 px-4 text-[12.5px] disabled:opacity-50"
              >
                {searching ? 'Recherche…' : 'Rechercher'}
              </button>
            </div>

            {error && <p className="text-[12.5px] text-rose-600 mt-3 mb-0">{error}</p>}

            {results !== null && (
              <div className="mt-4 border border-[var(--color-ln)] rounded-xl overflow-hidden max-h-[340px] overflow-y-auto">
                {results.length === 0 ? (
                  <p className="text-[12.5px] text-[var(--color-tx2)] px-4 py-5 m-0">
                    Aucun compte ne correspond dans l’annuaire.
                  </p>
                ) : (
                  results.map((row) => (
                    <div
                      key={row.dn}
                      className="px-4 py-3 border-b border-[var(--color-ln2)] last:border-0 flex items-center gap-3 flex-wrap"
                    >
                      <div className="min-w-0 flex-1">
                        <div className="text-[13px] font-semibold">
                          {row.display_name || row.username}
                          <span className="ml-2 text-[11.5px] text-[var(--color-tx2)] tnum">{row.username}</span>
                        </div>
                        <div className="text-[11.5px] text-[var(--color-tx2)] truncate">
                          {[row.email, row.department, row.title].filter(Boolean).join(' · ') || row.dn}
                        </div>
                      </div>

                      {row.already_imported ? (
                        <span className="inline-flex items-center gap-1.5 text-[12px] text-emerald-700 font-semibold">
                          <Check className="w-3.5 h-3.5" />
                          Déjà présent
                        </span>
                      ) : (
                        <>
                          <select
                            value={roles[row.username] || row.suggested_role}
                            onChange={(e) => setRoles((r) => ({ ...r, [row.username]: e.target.value }))}
                            className="cbc-input py-1 text-[12.5px]"
                            title="Rôle d’amorçage — l’annuaire ne le réécrira pas ensuite"
                          >
                            {ROLES.map((r) => (
                              <option key={r.value} value={r.value}>
                                {r.label}
                              </option>
                            ))}
                          </select>
                          <button
                            type="button"
                            disabled={importing === row.username}
                            onClick={() => void doImport(row)}
                            className="cbc-btn-secondary py-1.5 px-3 text-[12.5px] disabled:opacity-50"
                          >
                            {importing === row.username ? 'Import…' : 'Importer'}
                          </button>
                        </>
                      )}
                    </div>
                  ))
                )}
              </div>
            )}

            <p className="text-[11.5px] text-[var(--color-tx2)] mt-4 mb-0">
              Le rôle est un point de départ : l’annuaire ne le réécrira plus, une
              promotion accordée ici survit aux connexions suivantes. Un compte non
              importé sera créé automatiquement à sa première connexion réussie.
            </p>
          </div>
        </div>
      </div>
    </>
  );
};
