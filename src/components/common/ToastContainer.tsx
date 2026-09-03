/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { useApp } from '../../context/AppContext';
import { CheckCircle2, AlertCircle, Info, AlertTriangle, X } from 'lucide-react';

const TONE: Record<string, { border: string; icon: React.ReactNode }> = {
  info: { border: 'var(--color-blu-b)', icon: <Info className="w-[18px] h-[18px]" style={{ color: 'var(--color-blu)' }} /> },
  success: {
    border: 'var(--color-grn-b)',
    icon: <CheckCircle2 className="w-[18px] h-[18px]" style={{ color: 'var(--color-grn)' }} />,
  },
  error: {
    border: 'var(--color-red-b)',
    icon: <AlertCircle className="w-[18px] h-[18px]" style={{ color: 'var(--color-red)' }} />,
  },
  warning: {
    border: 'var(--color-amb-b)',
    icon: <AlertTriangle className="w-[18px] h-[18px]" style={{ color: 'var(--color-amb)' }} />,
  },
};

export const ToastContainer: React.FC = () => {
  const { toasts, removeToast } = useApp();

  return (
    <div className="fixed bottom-5 right-5 z-50 flex flex-col gap-2 max-w-md w-full pointer-events-none px-4 sm:px-0">
      <AnimatePresence>
        {toasts.map((toast) => {
          const tone = TONE[toast.type] || TONE.info;
          return (
            <motion.div
              key={toast.id}
              initial={{ opacity: 0, y: 20, scale: 0.95 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, scale: 0.9, transition: { duration: 0.15 } }}
              className="pointer-events-auto flex items-start gap-3 p-4 rounded-xl border"
              style={{
                background: 'var(--color-panel)',
                borderColor: tone.border,
                boxShadow: '0 14px 36px rgba(0,0,0,.18)',
              }}
            >
              {tone.icon}
              <div className="flex-1 min-w-0">
                <h4 className="text-sm font-semibold tracking-tight m-0" style={{ color: 'var(--color-tx)' }}>
                  {toast.title}
                </h4>
                <p className="text-xs mt-0.5 leading-relaxed" style={{ color: 'var(--color-tx2)' }}>
                  {toast.message}
                </p>
              </div>
              <button
                onClick={() => removeToast(toast.id)}
                className="p-1 rounded-md shrink-0"
                style={{ color: 'var(--color-tx3)' }}
                aria-label="Fermer la notification"
              >
                <X className="w-4 h-4" />
              </button>
            </motion.div>
          );
        })}
      </AnimatePresence>
    </div>
  );
};
