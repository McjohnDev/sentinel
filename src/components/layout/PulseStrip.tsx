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
  color: string;
  onClick?: () => void;
}

interface PulseStripProps {
  items: PulseItem[];
}

export const PulseStrip: React.FC<PulseStripProps> = ({ items }) => (
  <div className="cbc-card flex overflow-hidden mb-4">
    {items.map((item, idx) => (
      <button
        key={item.id}
        type="button"
        onClick={item.onClick}
        disabled={!item.onClick}
        className={`flex-1 text-left bg-transparent border-0 px-[18px] py-3.5 transition-colors ${
          item.onClick ? 'cursor-pointer hover:bg-slate-50' : 'cursor-default'
        } ${idx < items.length - 1 ? 'border-r border-slate-200' : ''}`}
      >
        <div className="text-[10.5px] font-bold uppercase tracking-wider text-slate-400">
          {item.label}
        </div>
        <div className="flex items-baseline gap-2 mt-2">
          <span className={`tnum text-[21px] font-extrabold tracking-tight ${item.color}`}>
            {item.value}
          </span>
          {item.unit && (
            <span className="text-[11.5px] font-semibold text-[#777777]">{item.unit}</span>
          )}
        </div>
      </button>
    ))}
  </div>
);
