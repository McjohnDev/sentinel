import React, { useState } from 'react';
import { AlertTriangle, X } from 'lucide-react';

interface EnrolmentSheetProps {
  open: boolean;
  token: string | null;
  expiresAt?: string;
  onClose: () => void;
}

export const EnrolmentSheet: React.FC<EnrolmentSheetProps> = ({ open, token, expiresAt, onClose }) => {
  const [os, setOs] = useState<'Windows' | 'Linux' | 'macOS'>('Windows');
  const [copied, setCopied] = useState<'token' | 'cmd' | null>(null);

  if (!open) return null;

  const cmds: Record<string, string> = {
    Windows: `msiexec /i CBCAgent.msi /qn ENROLL_TOKEN=${token || '…'} PLATFORM_URL=https://supervision.cbc.cm`,
    Linux: `sudo CBC_ENROLL_TOKEN=${token || '…'} ./install-cbc-agent.sh --url https://supervision.cbc.cm`,
    macOS: `sudo CBC_ENROLL_TOKEN=${token || '…'} installer -pkg CBCAgent.pkg -target /`,
  };

  const copy = async (text: string, which: 'token' | 'cmd') => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(which);
      setTimeout(() => setCopied(null), 1600);
    } catch {
      /* ignore */
    }
  };

  return (
    <div
      className="fixed inset-0 z-[46] grid place-items-center p-6 bg-slate-950/40 animate-fade-in"
      onClick={onClose}
    >
      <div
        className="w-full max-w-[640px] bg-white rounded-2xl overflow-hidden animate-modal-in"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="px-6 py-5 border-b border-slate-200 flex items-start justify-between gap-3">
          <div>
            <h2 className="text-[17px] font-extrabold m-0">Enrôler un agent</h2>
            <p className="text-[12.5px] leading-relaxed text-[#777] mt-2 mb-0">
              Trois étapes : générer un jeton, installer l'agent, attendre le premier heartbeat.
            </p>
          </div>
          <button type="button" onClick={onClose} className="w-[30px] h-[30px] grid place-items-center rounded-lg text-slate-400 hover:bg-slate-100">
            <X className="w-4 h-4" />
          </button>
        </div>
        <div className="px-6 py-5">
          <div className="flex items-center gap-2.5 px-3.5 py-2.5 rounded-lg bg-amber-50 border border-amber-200 mb-4">
            <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
            <span className="text-xs leading-relaxed text-amber-800">
              Ce jeton n'est affiché qu'une seule fois. Copiez-le avant de fermer.
            </span>
          </div>
          <div className="flex items-center gap-2.5 px-4 py-3.5 rounded-xl bg-slate-950">
            <span className="tnum flex-1 text-[13.5px] text-[#D0B335] break-all">{token || '—'}</span>
            {expiresAt && <span className="tnum text-[11px] text-slate-500 shrink-0">{expiresAt}</span>}
            <button
              type="button"
              onClick={() => token && copy(token, 'token')}
              className="px-3 py-1.5 rounded-lg border border-slate-800 text-[11.5px] font-semibold text-slate-200 shrink-0 hover:bg-slate-900"
            >
              {copied === 'token' ? 'Copié' : 'Copier'}
            </button>
          </div>
          <div className="flex gap-0.5 mt-5 border-b border-slate-200">
            {(['Windows', 'Linux', 'macOS'] as const).map((tab) => (
              <button
                key={tab}
                type="button"
                onClick={() => setOs(tab)}
                className={`px-3.5 py-2.5 border-0 bg-transparent text-[12.5px] font-semibold border-b-2 ${
                  os === tab ? 'border-[#D0B335] text-slate-900' : 'border-transparent text-slate-500'
                }`}
              >
                {tab}
              </button>
            ))}
          </div>
          <div className="mt-4">
            <div className="text-[11px] font-semibold text-slate-400 mb-2">Commande d'installation</div>
            <div className="flex items-start gap-2.5 p-4 rounded-lg bg-slate-50 border border-slate-200">
              <code className="tnum flex-1 text-xs leading-relaxed text-slate-700 break-all font-mono">{cmds[os]}</code>
              <button type="button" onClick={() => copy(cmds[os], 'cmd')} className="cbc-btn-secondary py-1.5 shrink-0">
                {copied === 'cmd' ? 'Copié' : 'Copier'}
              </button>
            </div>
          </div>
          <div className="flex items-center gap-3 mt-5 px-4 py-3 rounded-xl border border-dashed border-slate-300">
            <span className="w-2 h-2 rounded-full bg-[#D0B335] animate-pulse-dot shrink-0" />
            <span className="text-[12.5px] font-semibold text-slate-600">En écoute du premier heartbeat…</span>
            <span className="tnum text-[11.5px] text-slate-400 ml-auto">aucun agent détecté</span>
          </div>
        </div>
        <div className="px-6 py-4 border-t border-slate-200 bg-slate-50 flex justify-end">
          <button type="button" onClick={onClose} className="cbc-btn-secondary">
            Fermer
          </button>
        </div>
      </div>
    </div>
  );
};
