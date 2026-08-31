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

export const SegmentedControl: React.FC<SegmentedControlProps> = ({
  options,
  className = '',
}) => (
  <div className={`flex p-0.5 bg-slate-100 rounded-lg gap-0.5 ${className}`}>
    {options.map((opt) => (
      <button
        key={opt.id}
        type="button"
        onClick={opt.onClick}
        className={`border-0 px-2 py-1.5 rounded-md text-[11px] font-semibold cursor-pointer transition-colors ${
          opt.active
            ? 'bg-white text-slate-900 shadow-sm'
            : 'bg-transparent text-slate-500 hover:text-slate-900'
        }`}
      >
        {opt.label}
      </button>
    ))}
  </div>
);
