/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState } from 'react';
import { useApp } from '../context/AppContext';
import { Eye, EyeOff } from 'lucide-react';
import { Modal } from '../components/common/Modal';
import { useI18n } from '../i18n';

export const LoginView: React.FC = () => {
  const { t } = useI18n();
  const { login } = useApp();
  // Identifiant : nom de connexion OU adresse email. Le formulaire imposait
  // un email puis n'envoyait que la partie locale (`email.split('@')[0]`) :
  // impossible de se connecter avec son seul nom d'utilisateur, et deux
  // adresses de domaines différents se réduisaient au même identifiant.
  const [identifier, setIdentifier] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const [loading, setLoading] = useState(false);
  const [forgotModalOpen, setForgotModalOpen] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg('');

    const credential = identifier.trim();
    if (!credential) {
      setErrorMsg(t('login.errIdentifier'));
      return;
    }
    if (!password) {
      setErrorMsg(t('login.errPassword'));
      return;
    }

    setLoading(true);
    try {
      // Envoyé tel quel : c'est le serveur qui décide s'il s'agit d'un nom de
      // connexion, d'une adresse email ou d'un compte d'annuaire.
      await login(credential, password);
    } catch {
      setErrorMsg(t('login.errCredentials'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      className="min-h-screen flex items-center justify-center p-10"
      style={{
        background: '#020617',
        backgroundImage: 'radial-gradient(rgba(208,179,53,.10) 1px, transparent 1px)',
        backgroundSize: '22px 22px',
      }}
    >
      <div className="w-full max-w-[420px]">
        <div className="bg-[var(--color-panel)] rounded-2xl px-[34px] py-9">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-[#D0B335] text-[#020617] text-[13px] font-extrabold flex items-center justify-center">
              CBC
            </div>
            <div className="text-[11px] font-semibold uppercase tracking-wider text-[#777777]">
              Commercial Bank Cameroun
            </div>
          </div>

          <h1 className="text-[22px] font-extrabold tracking-tight mt-5 mb-0">CBC Supervision</h1>
          <p className="text-[13px] leading-relaxed text-[#777777] mt-2 mb-6">
            {t('login.tagline')}
          </p>

          <form onSubmit={handleSubmit}>
            <label className="block text-xs font-semibold text-[var(--color-tx2)] mb-1.5">{t('login.identifier')}</label>
            <input
              type="text"
              value={identifier}
              onChange={(e) => setIdentifier(e.target.value)}
              placeholder={t('login.identifierPlaceholder')}
              className="cbc-input mb-4"
              autoComplete="username"
              autoCapitalize="none"
              spellCheck={false}
            />

            <label className="block text-xs font-semibold text-[var(--color-tx2)] mb-1.5">{t('login.password')}</label>
            <div className="relative mb-5">
              <input
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="cbc-input pr-10"
                autoComplete="current-password"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-1 top-1 w-8 h-8 flex items-center justify-center text-[var(--color-tx3)] hover:bg-[var(--color-ln2)] rounded-lg"
                title={t('login.showPassword')}
              >
                {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="cbc-btn-primary w-full justify-center py-3 disabled:opacity-60"
            >
              {loading ? t('login.submitting') : t('login.submit')}
            </button>

            {errorMsg && (
              <p className="mt-3 text-center text-[12.5px] text-rose-600">{errorMsg}</p>
            )}
          </form>

          <div className="text-center mt-4">
            <button
              type="button"
              onClick={() => setForgotModalOpen(true)}
              className="text-[12.5px] font-medium text-[#A68523] hover:text-[#8A6D1B]"
            >
              {t('login.forgot')}
            </button>
          </div>

          <div className="flex items-center gap-3 my-6">
            <span className="flex-1 h-px bg-slate-200" />
            <span className="text-[11px] text-[var(--color-tx3)]">{t('login.or')}</span>
            <span className="flex-1 h-px bg-slate-200" />
          </div>

          <button
            type="button"
            disabled
            className="w-full py-2.5 border border-[var(--color-ln)] rounded-lg bg-[var(--color-panel)] text-[13px] font-semibold text-[var(--color-tx)] flex items-center justify-center gap-2 opacity-90 cursor-not-allowed"
          >
            {t('login.sso')}
            <span className="px-2 py-0.5 rounded-full bg-[var(--color-ln2)] text-[var(--color-tx2)] text-[10.5px] font-semibold">
              {t('login.ssoSoon')}
            </span>
          </button>
        </div>

        <p className="text-center text-[11px] leading-relaxed text-[var(--color-tx2)] mt-5">
          Usage interne CBC · ISO 27001 & COBAC
        </p>
      </div>

      <Modal
        isOpen={forgotModalOpen}
        onClose={() => setForgotModalOpen(false)}
        title="Mot de passe oublié"
        footer={
          <button type="button" onClick={() => setForgotModalOpen(false)} className="cbc-btn-secondary">
            Fermer
          </button>
        }
      >
        <p className="text-sm text-[var(--color-tx2)] leading-relaxed">
          Contactez votre administrateur DTDSI pour réinitialiser votre accès CBC Supervision.
        </p>
      </Modal>
    </div>
  );
};
