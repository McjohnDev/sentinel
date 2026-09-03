/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import { Inbox } from 'lucide-react';

interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  description: string;
  actionLabel?: string;
  onAction?: () => void;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  icon,
  title,
  description,
  actionLabel,
  onAction,
}) => {
  return (
    <div className="flex flex-col items-center justify-center p-12 text-center bg-[var(--color-panel)] rounded-2xl border border-dashed border-[var(--color-ln)]">
      <div className="w-16 h-16 rounded-2xl bg-[var(--color-ln2)] border border-[var(--color-ln2)] flex items-center justify-center text-[var(--color-tx3)] mb-4 shadow-xs">
        {icon || <Inbox className="w-8 h-8 text-[var(--color-tx3)]" />}
      </div>
      <h3 className="text-base font-bold text-[var(--color-tx)] tracking-tight">{title}</h3>
      <p className="text-xs text-[var(--color-tx2)] max-w-md mt-1 mb-6 leading-relaxed">
        {description}
      </p>
      {actionLabel && onAction && (
        <button
          onClick={onAction}
          className="inline-flex items-center gap-2 px-4 py-2 bg-[#D0B335] hover:bg-[#b89d2d] text-slate-950 text-xs font-bold rounded-xl shadow-xs transition-colors"
        >
          {actionLabel}
        </button>
      )}
    </div>
  );
};
