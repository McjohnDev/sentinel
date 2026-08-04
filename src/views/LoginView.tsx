/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState } from 'react';
import { useApp } from '../context/AppContext';
import { Lock, Mail, Eye, EyeOff, ShieldCheck, ArrowRight, Info } from 'lucide-react';
import { Modal } from '../components/common/Modal';

export const LoginView: React.FC = () => {
  const { login, users } = useApp();
  const [email, setEmail] = useState('jp.mbida@cbcam.cm');
  const [password, setPassword] = useState('Password123!');
  const [showPassword, setShowPassword] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const [loading, setLoading] = useState(false);
  const [forgotModalOpen, setForgotModalOpen] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg('');

    if (!email || !email.includes('@')) {
      setErrorMsg('Veuillez saisir une adresse email bancaire valide.');
      return;
    }
    if (!password) {
      setErrorMsg('Veuillez saisir votre mot de passe.');
      return;
    }

    setLoading(true);

    try {
      // Extraire le username de l'email (partie avant @)
      const username = email.split('@')[0];
      await login(username, password);
    } catch (error) {
      setErrorMsg('Identifiants invalides ou erreur serveur.');
    } finally {
      setLoading(false);
    }
  };

  const handleQuickLogin = async (roleIndex: number) => {
    const demoUsers = [
      { email: 'admin@cbc.cm', password: 'Admin12' },
      { email: 'operator@cbcam.cm', password: 'Operator123!' },
      { email: 'readonly@cbcam.cm', password: 'Readonly123!' },
    ];

    const user = demoUsers[roleIndex] || demoUsers[0];
    setEmail(user.email);
    setPassword(user.password);
    setLoading(true);

    try {
      // Extraire le username de l'email (partie avant @)
      const username = user.email.split('@')[0];
      await login(username, user.password);
    } catch (error) {
      setErrorMsg('Erreur de connexion.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col justify-between relative overflow-hidden font-sans">
      {/* Background Decorative Grid */}
      <div className="absolute inset-0 bg-[radial-gradient(#D0B335_1px,transparent_1px)] [background-size:32px_32px] opacity-10 pointer-events-none" />

      {/* Top Banner */}
      <div className="relative z-10 p-6 flex justify-between items-center max-w-7xl mx-auto w-full">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[#E6CA4E] to-[#D0B335] text-slate-950 font-black text-base flex items-center justify-center shadow-lg shadow-[#D0B335]/20 border border-amber-300/40">
            CBC
          </div>
          <div>
            <h1 className="text-base font-extrabold text-white tracking-tight">
              Commercial Bank Cameroun
            </h1>
            <p className="text-xs text-[#D0B335] font-semibold tracking-wider uppercase">
              Supervision Platform v1.0
            </p>
          </div>
        </div>

        <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-full bg-slate-900 border border-slate-800 text-xs text-slate-400">
          <ShieldCheck className="w-4 h-4 text-[#D0B335]" />
          Accès Sécurisé HTTPS / SSL
        </div>
      </div>

      {/* Main Login Form Container */}
      <div className="relative z-10 my-auto p-4 sm:p-6 flex justify-center items-center">
        <div className="w-full max-w-md bg-white rounded-3xl shadow-2xl border border-slate-200 p-8">
          <div className="text-center mb-6">
            <h2 className="text-2xl font-black text-slate-900 tracking-tight">Connexion</h2>
            <p className="text-xs text-slate-500 mt-1">
              Accédez à la console de supervision centralisée CBC
            </p>
          </div>

          {errorMsg && (
            <div className="mb-4 p-3 rounded-xl bg-rose-50 border border-rose-200 text-xs text-rose-700 font-medium">
              {errorMsg}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1.5">
                Adresse Email Professionnelle
              </label>
              <div className="relative">
                <Mail className="w-4 h-4 text-slate-400 absolute left-3.5 top-3" />
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="nom@cbcam.cm"
                  className="w-full pl-10 pr-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-[#D0B335] focus:bg-white transition-all font-medium"
                  required
                />
              </div>
            </div>

            <div>
              <div className="flex justify-between items-center mb-1.5">
                <label className="text-xs font-bold text-slate-700">Mot de passe</label>
                <button
                  type="button"
                  onClick={() => setForgotModalOpen(true)}
                  className="text-[11px] font-semibold text-[#8D771B] hover:underline"
                >
                  Mot de passe oublié ?
                </button>
              </div>
              <div className="relative">
                <Lock className="w-4 h-4 text-slate-400 absolute left-3.5 top-3" />
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••••••"
                  className="w-full pl-10 pr-10 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-[#D0B335] focus:bg-white transition-all font-medium"
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3.5 top-3 text-slate-400 hover:text-slate-600"
                  aria-label="Afficher ou masquer le mot de passe"
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 bg-[#D0B335] hover:bg-[#b89d2d] text-slate-950 text-xs font-bold rounded-xl shadow-md transition-all flex items-center justify-center gap-2 group mt-2"
            >
              {loading ? (
                <div className="w-4 h-4 border-2 border-slate-950 border-t-transparent rounded-full animate-spin" />
              ) : (
                <>
                  <span>Se connecter</span>
                  <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
                </>
              )}
            </button>
          </form>

          {/* Preset Demo Logins for Quick QA Evaluation */}
          <div className="mt-8 pt-6 border-t border-slate-100">
            <p className="text-[11px] font-bold text-slate-400 text-center uppercase tracking-wider mb-3">
              Démo — Accès direct par rôle
            </p>
            <div className="grid grid-cols-3 gap-2">
              <button
                onClick={() => handleQuickLogin(0)}
                className="p-2 bg-amber-50 hover:bg-amber-100 border border-amber-200 rounded-xl text-[11px] font-bold text-slate-900 text-center transition-colors"
              >
                Admin
              </button>
              <button
                onClick={() => handleQuickLogin(1)}
                className="p-2 bg-blue-50 hover:bg-blue-100 border border-blue-200 rounded-xl text-[11px] font-bold text-slate-900 text-center transition-colors"
              >
                Opérateur
              </button>
              <button
                onClick={() => handleQuickLogin(2)}
                className="p-2 bg-slate-100 hover:bg-slate-200 border border-slate-300 rounded-xl text-[11px] font-bold text-slate-900 text-center transition-colors"
              >
                Lecture
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Footer */}
      <footer className="relative z-10 p-6 text-center text-xs text-slate-500 border-t border-slate-900">
        Commercial Bank Cameroun © 2026. Tous droits réservés. Direction des Systèmes d'Information.
      </footer>

      {/* Forgot Password Modal */}
      <Modal
        isOpen={forgotModalOpen}
        onClose={() => setForgotModalOpen(false)}
        title="Récupération de mot de passe"
        footer={
          <button
            onClick={() => setForgotModalOpen(false)}
            className="px-4 py-2 bg-slate-900 text-white text-xs font-bold rounded-xl hover:bg-slate-800"
          >
            Fermer
          </button>
        }
      >
        <div className="space-y-3">
          <div className="p-3 bg-amber-50 border border-amber-200 rounded-xl flex items-start gap-2.5">
            <Info className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
            <p className="text-xs text-amber-900 leading-relaxed">
              Pour des raisons de sécurité bancaire, la réinitialisation automatique du mot de passe
              est désactivée en V1.
            </p>
          </div>
          <p className="text-xs text-slate-600">
            Veuillez contacter l'administrateur système DSI à l'adresse suivante :
            <strong className="block text-slate-900 font-mono mt-1">sysadmin@cbcam.cm</strong>
          </p>
        </div>
      </Modal>
    </div>
  );
};
