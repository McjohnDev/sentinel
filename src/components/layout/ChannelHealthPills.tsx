/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';

interface Channel {
  label: string;
  /** Couleur CSS littérale ou jeton `var(--color-x)`. */
  color: string;
}

interface ChannelHealthPillsProps {
  channels: Channel[];
  onClick?: () => void;
}

export const ChannelHealthPills: React.FC<ChannelHealthPillsProps> = ({ channels, onClick }) => (
  <button
    type="button"
    onClick={onClick}
    title="Canaux de notification"
    className="hidden md:flex items-center gap-2.5 px-2.5 py-1 rounded-full border cursor-pointer transition-colors"
    style={{ borderColor: 'var(--color-ln)', color: 'var(--color-tx2)' }}
  >
    {channels.map((c) => (
      <span key={c.label} className="flex items-center gap-1.5">
        <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: c.color }} />
        <span className="font-mono text-[9.5px] tracking-[0.05em]">{c.label}</span>
      </span>
    ))}
  </button>
);
