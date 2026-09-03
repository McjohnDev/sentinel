/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState } from 'react';
import { useApp } from '../context/AppContext';
import { usersService } from '../services/api/users.service';
import { useI18n } from '../i18n';
import { PageHeader } from '../components/layout/PageHeader';
import { SegmentedControl } from '../components/layout/SegmentedControl';

export const ProfileView: React.FC = () => {
  const { currentUser, currentRole, addToast } = useApp();
  const { lang, setLang } = useI18n();
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  const roleLabel = currentRole === 'Admin' ? 'Administrateur' : currentRole === 'Operator' ? 'Opérateur' : 'Lecture seule';

  return (
    <div className="space-y-5 max-w-[720px]">
      <PageHeader
        title="Profil"
        subtitle={`${currentUser?.name || '—'} · ${currentUser?.email || '—'} · ${roleLabel}`}
      />

      <div className="cbc-card p-5 space-y-3">
        <label className="block">
          <span className="text-xs font-semibold text-[var(--color-tx2)]">Nom</span>
          <input value={currentUser?.name || ''} readOnly className="cbc-input mt-1.5 bg-[var(--color-ln2)]" />
        </label>
        <label className="block">
          <span className="text-xs font-semibold text-[var(--color-tx2)]">E-mail</span>
          <input value={currentUser?.email || ''} readOnly className="cbc-input mt-1.5 bg-[var(--color-ln2)]" />
        </label>
        <div>
          <span className="text-xs font-semibold text-[var(--color-tx2)]">Langue</span>
          <div className="mt-2">
            <SegmentedControl
              options={[
                { id: 'fr', label: 'FR', active: lang === 'fr', onClick: () => setLang('fr') },
                { id: 'en', label: 'EN', active: lang === 'en', onClick: () => setLang('en') },
              ]}
            />
          </div>
        </div>
      </div>

      <form
        className="cbc-card p-5 space-y-3"
        onSubmit={async (e) => {
          e.preventDefault();
          setError('');
          if (next.length < 8) {
            setError('Le mot de passe doit contenir au moins 8 caractères.');
            return;
          }
          if (next !== confirm) {
            setError('Les mots de passe ne correspondent pas.');
            return;
          }
          if (!current) {
            setError('Le mot de passe actuel est requis.');
            return;
          }
          setSaving(true);
          try {
            await usersService.changeOwnPassword(current, next);
            setCurrent('');
            setNext('');
            setConfirm('');
            addToast({
              type: 'success',
              title: 'Mot de passe',
              message: 'Mot de passe mis à jour.',
            });
          } catch (err) {
            // Le serveur porte la raison du refus (secret courant invalide,
            // compte d'annuaire, nouveau mot de passe identique) : la relayer
            // telle quelle plutôt que d'afficher un succès non acquis.
            const detail =
              (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
              'Le changement de mot de passe a échoué.';
            setError(detail);
          } finally {
            setSaving(false);
          }
        }}
      >
        <h2 className="text-sm font-bold m-0">Changement de mot de passe</h2>
        <label className="block">
          <span className="text-xs font-semibold text-[var(--color-tx2)]">Actuel</span>
          <input type="password" value={current} onChange={(e) => setCurrent(e.target.value)} className="cbc-input mt-1.5" autoComplete="current-password" />
        </label>
        <label className="block">
          <span className="text-xs font-semibold text-[var(--color-tx2)]">Nouveau</span>
          <input type="password" value={next} onChange={(e) => setNext(e.target.value)} className="cbc-input mt-1.5" autoComplete="new-password" />
        </label>
        <label className="block">
          <span className="text-xs font-semibold text-[var(--color-tx2)]">Confirmation</span>
          <input type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)} className="cbc-input mt-1.5" autoComplete="new-password" />
        </label>
        {error && <p className="text-xs text-rose-600">{error}</p>}
        <button type="submit" className="cbc-btn-primary" disabled={saving}>
          {saving ? 'Mise à jour…' : 'Mettre à jour'}
        </button>
      </form>
    </div>
  );
};
