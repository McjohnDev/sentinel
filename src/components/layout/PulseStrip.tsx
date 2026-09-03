/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';

export interface PulseItem {
  id: string;
  label: string;
  value: string | number;
  unit?: string;
  /** Ligne courte sous la valeur — ce qui explique le chiffre, pas un
   *  simple habillage. Omise si rien de plus précis n'est connu. */
  sub?: string;
  color: string;
  onClick?: () => void;
}

interface PulseStripProps {
  items: PulseItem[];
}

export const PulseStrip: React.FC<PulseStripProps> = ({ items }) => (
  <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
    {items.map((item) => (
      <button
        key={item.id}
        type="button"
        onClick={item.onClick}
        disabled={!item.onClick}
        className={`cbc-card text-left px-3.5 py-3 ${item.onClick ? 'cbc-hover' : ''}`}
      >
        <div
          className="font-mono text-[10px] tracking-[0.08em] uppercase"
          style={{ color: 'var(--color-tx3)' }}
        >
          {item.label}
        </div>
        <div className="flex items-baseline gap-1.5 mt-1">
          <span className={`tnum text-[21px] font-bold tracking-tight ${item.color}`}>
            {item.value}
          </span>
          {item.unit && (
            <span className="text-[11px] font-medium" style={{ color: 'var(--color-tx2)' }}>
              {item.unit}
            </span>
          )}
        </div>
        {item.sub && (
          <div className="text-[11px] mt-0.5 truncate" style={{ color: 'var(--color-tx3)' }}>
            {item.sub}
          </div>
        )}
      </button>
    ))}
  </div>
);
