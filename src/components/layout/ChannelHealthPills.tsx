/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';

interface Channel {
  label: string;
  color: string;
}

interface ChannelHealthPillsProps {
  channels: Channel[];
  onClick?: () => void;
}

export const ChannelHealthPills: React.FC<ChannelHealthPillsProps> = ({
  channels,
  onClick,
}) => (
  <button
    type="button"
    onClick={onClick}
    title="Canaux de notification"
    className="hidden md:flex items-center gap-2.5 px-2.5 py-1.5 rounded-lg border border-slate-200 bg-white hover:bg-slate-50 transition-colors cursor-pointer"
  >
    {channels.map((c) => (
      <span key={c.label} className="flex items-center gap-1.5">
        <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: c.color }} />
        <span className="text-[11px] font-semibold text-slate-600">{c.label}</span>
      </span>
    ))}
  </button>
);
