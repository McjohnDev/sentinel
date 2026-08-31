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
      className="fixed inset-0 z-[100] flex items-start justify-center pt-[12vh] px-4 bg-slate-950/40 animate-fade-in"
      onClick={onClose}
    >
      <div
        className="w-full max-w-lg bg-white border border-slate-200 rounded-xl overflow-hidden animate-modal-in shadow-lg"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-2 px-3 border-b border-slate-200">
          <Search className="w-4 h-4 text-slate-400 shrink-0" />
          <input
            autoFocus
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Hôtes, alertes, écrans…"
            className="flex-1 py-3 border-0 text-sm outline-none bg-transparent"
          />
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 text-slate-400 hover:text-slate-700 rounded-lg"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
        <div className="max-h-72 overflow-y-auto py-1">
          {items.length === 0 ? (
            <p className="px-4 py-6 text-xs text-slate-500 text-center">Aucun résultat</p>
          ) : (
            items.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => {
                  navigate(item.path);
                  onClose();
                }}
                className="w-full text-left px-4 py-2.5 hover:bg-slate-50 flex items-center justify-between gap-2"
              >
                <span className="text-sm font-semibold text-slate-900">{item.label}</span>
                <span className="text-[10px] text-slate-400 uppercase tracking-wide">{item.group}</span>
              </button>
            ))
          )}
        </div>
      </div>
    </div>
  );
};
