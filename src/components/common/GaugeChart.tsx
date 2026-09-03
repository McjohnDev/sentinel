/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';

interface GaugeChartProps {
  value: number; // 0 - 100
  title: string;
  subValue?: string;
  size?: number; // default 140
  warningThreshold?: number;
  criticalThreshold?: number;
}

export const GaugeChart: React.FC<GaugeChartProps> = ({
  value,
  title,
  subValue,
  size = 130,
  warningThreshold = 80,
  criticalThreshold = 90,
}) => {
  const normalizedValue = Math.min(100, Math.max(0, value));
  const strokeWidth = 10;
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  // 75% arc gauge
  const arcLength = circumference * 0.75;
  const strokeDashoffset = arcLength - (arcLength * normalizedValue) / 100;

  let strokeColor = '#10B981'; // Emerald
  let badgeBg = 'bg-emerald-50 text-emerald-700 border-emerald-200';

  if (normalizedValue >= criticalThreshold) {
    strokeColor = '#EF4444'; // Red
    badgeBg = 'bg-rose-50 text-rose-700 border-rose-200 font-bold';
  } else if (normalizedValue >= warningThreshold) {
    strokeColor = '#F59E0B'; // Amber
    badgeBg = 'bg-amber-50 text-amber-700 border-amber-200 font-semibold';
  }

  return (
    <div className="flex flex-col items-center bg-[var(--color-panel)] p-4 rounded-xl border border-[var(--color-ln)]/80 shadow-xs">
      <div className="text-xs font-semibold text-[var(--color-tx2)] uppercase tracking-wider mb-2">
        {title}
      </div>
      <div className="relative flex items-center justify-center" style={{ width: size, height: size }}>
        <svg width={size} height={size} className="transform -rotate-225">
          {/* Background Track */}
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke="#F1F5F9"
            strokeWidth={strokeWidth}
            strokeDasharray={`${arcLength} ${circumference}`}
            strokeLinecap="round"
          />
          {/* Active Progress */}
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke={strokeColor}
            strokeWidth={strokeWidth}
            strokeDasharray={`${arcLength} ${circumference}`}
            strokeDashoffset={strokeDashoffset}
            strokeLinecap="round"
            className="transition-all duration-700 ease-out"
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
          <span className="text-2xl font-bold text-[var(--color-tx)] tracking-tight">
            {normalizedValue}%
          </span>
          {subValue && (
            <span className="text-[11px] text-[var(--color-tx2)] font-medium px-1 truncate max-w-[100px]">
              {subValue}
            </span>
          )}
        </div>
      </div>
      <div className={`mt-2 text-xs px-2.5 py-0.5 rounded-full border ${badgeBg}`}>
        {normalizedValue >= criticalThreshold
          ? 'Critique'
          : normalizedValue >= warningThreshold
          ? 'Attention'
          : 'Normal'}
      </div>
    </div>
  );
};
