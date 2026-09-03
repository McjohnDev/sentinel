import React from 'react';

interface FilterChipProps {
  label: string;
  active: boolean;
  onClick: () => void;
  pill?: boolean;
}

export const FilterChip: React.FC<FilterChipProps> = ({ label, active, onClick, pill }) => (
  <button
    type="button"
    onClick={onClick}
    className={`px-3 py-1.5 border text-xs font-semibold cursor-pointer ${
      pill ? 'rounded-2xl' : 'rounded-lg'
    } ${active ? 'bg-slate-900 text-white border-slate-900' : 'bg-[var(--color-panel)] text-[var(--color-tx2)] border-[var(--color-ln)] hover:bg-[var(--color-ln2)]'}`}
  >
    {label}
  </button>
);
