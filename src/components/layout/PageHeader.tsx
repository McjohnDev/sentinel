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
  <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 mb-1">
    <div>
      <h1
        className="text-[20px] font-bold tracking-tight m-0"
        style={{ color: 'var(--color-tx)' }}
      >
        {title}
      </h1>
      {subtitle && (
        <p className="text-[12.5px] mt-[3px]" style={{ color: 'var(--color-tx2)' }}>
          {subtitle}
        </p>
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
