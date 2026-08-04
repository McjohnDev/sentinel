/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';

interface ProgressBarProps {
  value: number; // 0 - 100
  label?: string;
  showValue?: boolean;
  type?: 'cpu' | 'ram' | 'disk' | 'general';
  warningThreshold?: number;
  criticalThreshold?: number;
  size?: 'sm' | 'md' | 'lg';
}

export const ProgressBar: React.FC<ProgressBarProps> = ({
  value,
  label,
  showValue = true,
  type = 'general',
  warningThreshold = 80,
  criticalThreshold = 90,
  size = 'md',
}) => {
  const normalizedVal = Math.min(100, Math.max(0, value));

  let barColor = 'bg-emerald-500';
  let textColor = 'text-emerald-700';

  if (type === 'disk') {
    warningThreshold = warningThreshold || 85;
    criticalThreshold = criticalThreshold || 95;
  }

  if (normalizedVal >= criticalThreshold) {
    barColor = 'bg-rose-600 animate-pulse';
    textColor = 'text-rose-700 font-bold';
  } else if (normalizedVal >= warningThreshold) {
    barColor = 'bg-amber-500';
    textColor = 'text-amber-700 font-semibold';
  }

  const heightClasses = {
    sm: 'h-1.5',
    md: 'h-2.5',
    lg: 'h-4',
  };

  return (
    <div className="w-full">
      {(label || showValue) && (
        <div className="flex justify-between items-center text-xs mb-1 font-medium text-slate-600">
          {label && <span>{label}</span>}
          {showValue && <span className={`${textColor}`}>{normalizedVal}%</span>}
        </div>
      )}
      <div className={`w-full bg-slate-100 rounded-full overflow-hidden ${heightClasses[size]} border border-slate-200/60`}>
        <div
          className={`${barColor} ${heightClasses[size]} rounded-full transition-all duration-500 ease-out`}
          style={{ width: `${normalizedVal}%` }}
        />
      </div>
    </div>
  );
};
