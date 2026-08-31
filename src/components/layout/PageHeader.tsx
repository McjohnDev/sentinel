/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { ReactNode } from 'react';

interface PageHeaderProps {
  title: string;
  subtitle?: string;
  primaryAction?: ReactNode;
  secondaryActions?: ReactNode;
}

export const PageHeader: React.FC<PageHeaderProps> = ({
  title,
  subtitle,
  primaryAction,
  secondaryActions,
}) => (
  <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4 mb-1">
    <div>
      <h1 className="text-xl font-extrabold text-slate-900 tracking-tight">{title}</h1>
      {subtitle && (
        <p className="text-[13px] leading-relaxed text-[#777777] mt-1.5">{subtitle}</p>
      )}
    </div>
    {(primaryAction || secondaryActions) && (
      <div className="flex flex-wrap items-center gap-2 shrink-0">
        {secondaryActions}
        {primaryAction}
      </div>
    )}
  </div>
);
