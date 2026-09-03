/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState, useEffect } from 'react';
import { Modal } from './Modal';
import { Badge } from './Badge';
import { Alert } from '../../types';
import { useApp } from '../../context/AppContext';
import { UserCheck, MessageSquare, ShieldCheck, User as UserIcon } from 'lucide-react';

interface AcknowledgeModalProps {
  isOpen: boolean;
  onClose: () => void;
  alert: Alert | null;
  onConfirm: (alertId: string, comment: string, operatorName: string) => void;
  /**
   * Même formulaire pour l'acquittement et la clôture : les deux collectent
   * un intervenant et un compte rendu. Seuls les libellés changent.
   */
  mode?: 'acknowledge' | 'resolve';
}

export const AcknowledgeModal: React.FC<AcknowledgeModalProps> = ({
  isOpen,
  onClose,
  alert,
  onConfirm,
  mode = 'acknowledge',
}) => {
  const { currentUser, users } = useApp();
  const [operatorName, setOperatorName] = useState('');
  const [comment, setComment] = useState('');

  useEffect(() => {
    if (isOpen && currentUser) {
      setOperatorName(currentUser.name || 'Opérateur CBC');
      setComment('');
    }
  }, [isOpen, currentUser]);

  if (!alert) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!operatorName.trim()) return;
    onConfirm(alert.id, comment.trim(), operatorName.trim());
    onClose();
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={mode === 'resolve' ? "Clôture de l'alerte" : "Prise en charge & Acquittement de l'alerte"}
      footer={
        <>
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 bg-[var(--color-ln2)] hover:bg-slate-200 text-[var(--color-tx2)] text-xs font-semibold rounded-xl transition-colors cursor-pointer"
          >
            Annuler
          </button>
          <button
            type="button"
            onClick={handleSubmit}
            disabled={!operatorName.trim()}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold rounded-xl shadow-xs transition-colors flex items-center gap-2 cursor-pointer disabled:opacity-50"
          >
            <UserCheck className="w-4 h-4" />
            {mode === 'resolve' ? 'Confirmer la résolution' : "Confirmer l'acquittement"}
          </button>
        </>
      }
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Alert Details Summary */}
        <div className="p-3.5 bg-[var(--color-ln2)] border border-[var(--color-ln)]/80 rounded-xl space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Badge type="severity" value={alert.severity} size="sm" />
              <span className="font-bold text-xs text-[var(--color-tx)]">{alert.agentName}</span>
            </div>
            <span className="text-[11px] font-mono text-[var(--color-tx3)]">{alert.timestamp}</span>
          </div>
          <p className="text-xs text-[var(--color-tx2)] leading-relaxed font-medium">{alert.message}</p>
        </div>

        {/* Operator Name Input */}
        <div>
          <label className="block text-xs font-bold text-[var(--color-tx)] mb-1 flex items-center gap-1.5">
            <UserIcon className="w-3.5 h-3.5 text-blue-600" />
            Nom de l'opérateur / Intervenant <span className="text-rose-500">*</span>
          </label>
          <div className="relative">
            <input
              type="text"
              required
              value={operatorName}
              onChange={(e) => setOperatorName(e.target.value)}
              placeholder="Ex: Jean-Paul Nkouam (Opérateur SOC)"
              className="w-full px-3 py-2 bg-[var(--color-panel)] border border-[var(--color-ln)] rounded-xl text-xs text-[var(--color-tx)] focus:outline-none focus:ring-2 focus:ring-[#D0B335] font-medium shadow-2xs"
            />
          </div>

          {/* Quick suggestions from users list */}
          {users.length > 0 && (
            <div className="mt-2 flex flex-wrap items-center gap-1.5">
              <span className="text-[10px] font-semibold text-[var(--color-tx3)]">Suggestions :</span>
              {users.map((u) => (
                <button
                  key={u.id}
                  type="button"
                  onClick={() => setOperatorName(`${u.name} (${u.role})`)}
                  className="text-[10px] px-2 py-0.5 bg-[var(--color-ln2)] hover:bg-slate-200 text-[var(--color-tx2)] rounded-lg transition-colors font-medium cursor-pointer"
                >
                  {u.name}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Comment / Intervention Report */}
        <div>
          <label className="block text-xs font-bold text-[var(--color-tx)] mb-1 flex items-center gap-1.5">
            <MessageSquare className="w-3.5 h-3.5 text-[#8D771B]" />
            Commentaire d'intervention (Optionnel)
          </label>
          <textarea
            rows={3}
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder="Ex: Analyse en cours. Service redémarré avec succès. Ticket JIRA #CBC-402 créé."
            className="w-full p-3 bg-[var(--color-panel)] border border-[var(--color-ln)] rounded-xl text-xs text-[var(--color-tx)] focus:outline-none focus:ring-2 focus:ring-[#D0B335] font-medium shadow-2xs"
          />
        </div>

        <div className="p-3 bg-blue-50/60 border border-blue-100 rounded-xl flex items-start gap-2.5 text-blue-900 text-[11px] leading-relaxed">
          <ShieldCheck className="w-4 h-4 text-blue-600 shrink-0 mt-0.5" />
          <span>
            Cet acquittement sera inscrit dans le journal d'audit avec votre nom et l'horodatage exact pour garantir la traçabilité des opérations.
          </span>
        </div>
      </form>
    </Modal>
  );
};
