/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';

interface SegmentedOption {
  id: string;
  label: string;
  active: boolean;
  onClick: () => void;
}

interface SegmentedControlProps {
  options: SegmentedOption[];
  className?: string;
}

export const SegmentedControl: React.FC<SegmentedControlProps> = ({ options, className = '' }) => (
  <div
    className={`flex p-0.5 rounded-lg gap-0.5 ${className}`}
    style={{ background: 'var(--color-ln2)' }}
  >
    {options.map((opt) => (
      <button
        key={opt.id}
        type="button"
        onClick={opt.onClick}
        className="border-0 px-2 py-1 rounded-md text-[11px] font-semibold cursor-pointer transition-colors"
        style={
          opt.active
            ? { background: 'var(--color-panel)', color: 'var(--color-tx)', boxShadow: 'var(--shadow-card)' }
            : { background: 'transparent', color: 'var(--color-tx3)' }
        }
      >
        {opt.label}
      </button>
    ))}
  </div>
);
