/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, X } from 'lucide-react';
import { useI18n } from '../../i18n';
import { NAV_GROUPS } from './navGroups';

interface CommandPaletteProps {
  open: boolean;
  onClose: () => void;
}

export const CommandPalette: React.FC<CommandPaletteProps> = ({ open, onClose }) => {
  const navigate = useNavigate();
  const { t } = useI18n();
  const [query, setQuery] = useState('');

  useEffect(() => {
    if (!open) {
      setQuery('');
      return;
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  const items = useMemo(() => {
    const flat = NAV_GROUPS.flatMap((g) =>
      g.items.map((item) => ({
        id: item.id,
        label: t(item.labelKey),
        group: t(g.labelKey),
        path: item.path,
      }))
    );
    const q = query.trim().toLowerCase();
    if (!q) return flat.slice(0, 8);
    return flat.filter(
      (i) =>
        i.label.toLowerCase().includes(q) ||
        i.group.toLowerCase().includes(q) ||
        i.path.toLowerCase().includes(q)
    );
  }, [query, t]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[100] flex items-start justify-center pt-[14vh] px-4 animate-fade-in"
      style={{ background: 'rgba(9,11,16,.45)' }}
      onClick={onClose}
    >
      <div
        className="w-full max-w-lg rounded-2xl overflow-hidden animate-modal-in border"
        style={{
          background: 'var(--color-panel)',
          borderColor: 'var(--color-ln)',
          boxShadow: '0 32px 80px rgba(0,0,0,.35)',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-2 px-4 border-b" style={{ borderColor: 'var(--color-ln)' }}>
          <Search className="w-4 h-4 shrink-0" style={{ color: 'var(--color-tx3)' }} />
          <input
            autoFocus
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Hôtes, alertes, écrans…"
            className="flex-1 py-3 border-0 text-[14px] outline-none bg-transparent"
            style={{ color: 'var(--color-tx)' }}
          />
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg"
            style={{ color: 'var(--color-tx3)' }}
          >
            <X className="w-4 h-4" />
          </button>
        </div>
        <div className="max-h-72 overflow-y-auto p-1.5">
          {items.length === 0 ? (
            <p className="px-4 py-6 text-xs text-center" style={{ color: 'var(--color-tx3)' }}>
              Aucun résultat
            </p>
          ) : (
            items.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => {
                  navigate(item.path);
                  onClose();
                }}
                className="w-full text-left px-3 py-2.5 rounded-xl flex items-center justify-between gap-2 cbc-hover"
                style={{ color: 'var(--color-tx)' }}
                onMouseDown={(e) => e.preventDefault()}
              >
                <span className="text-[13px] font-semibold">{item.label}</span>
                <span
                  className="font-mono text-[8.5px] tracking-[0.08em] border rounded px-1.5 py-0.5"
                  style={{ borderColor: 'var(--color-ln)', color: 'var(--color-tx3)' }}
                >
                  {item.group.toUpperCase()}
                </span>
              </button>
            ))
          )}
        </div>
        <div
          className="px-4 py-1.5 border-t font-mono text-[9.5px]"
          style={{ borderColor: 'var(--color-ln)', color: 'var(--color-tx3)' }}
        >
          ↵ ouvrir · esc fermer
        </div>
      </div>
    </div>
  );
};
