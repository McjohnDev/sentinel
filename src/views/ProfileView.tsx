/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState } from 'react';
import { useApp } from '../context/AppContext';
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

  const roleLabel = currentRole === 'Admin' ? 'Administrateur' : currentRole === 'Operator' ? 'Opérateur' : 'Lecture seule';

  return (
    <div className="space-y-5 max-w-[720px]">
      <PageHeader
        title="Profil"
        subtitle={`${currentUser?.name || '—'} · ${currentUser?.email || '—'} · ${roleLabel}`}
      />

      <div className="cbc-card p-5 space-y-3">
        <label className="block">
          <span className="text-xs font-semibold text-slate-700">Nom</span>
          <input value={currentUser?.name || ''} readOnly className="cbc-input mt-1.5 bg-slate-50" />
        </label>
        <label className="block">
          <span className="text-xs font-semibold text-slate-700">E-mail</span>
          <input value={currentUser?.email || ''} readOnly className="cbc-input mt-1.5 bg-slate-50" />
        </label>
        <div>
          <span className="text-xs font-semibold text-slate-700">Langue</span>
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
        onSubmit={(e) => {
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
          setCurrent('');
          setNext('');
          setConfirm('');
          addToast({ type: 'success', title: 'Mot de passe', message: 'Changement enregistré localement. Synchronisation annuaire à brancher.' });
        }}
      >
        <h2 className="text-sm font-bold m-0">Changement de mot de passe</h2>
        <label className="block">
          <span className="text-xs font-semibold text-slate-700">Actuel</span>
          <input type="password" value={current} onChange={(e) => setCurrent(e.target.value)} className="cbc-input mt-1.5" autoComplete="current-password" />
        </label>
        <label className="block">
          <span className="text-xs font-semibold text-slate-700">Nouveau</span>
          <input type="password" value={next} onChange={(e) => setNext(e.target.value)} className="cbc-input mt-1.5" autoComplete="new-password" />
        </label>
        <label className="block">
          <span className="text-xs font-semibold text-slate-700">Confirmation</span>
          <input type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)} className="cbc-input mt-1.5" autoComplete="new-password" />
        </label>
        {error && <p className="text-xs text-rose-600">{error}</p>}
        <button type="submit" className="cbc-btn-primary">
          Mettre à jour
        </button>
      </form>
    </div>
  );
};
