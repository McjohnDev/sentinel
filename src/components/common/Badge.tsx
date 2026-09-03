/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import { AgentStatus, AlertSeverity, AlertStatus, OperatingSystem, Role } from '../../types';
import { Monitor, Terminal, Apple, ShieldCheck, AlertTriangle, AlertCircle, Info, Wifi, WifiOff } from 'lucide-react';

interface BadgeProps {
  type?: 'status' | 'severity' | 'alertStatus' | 'os' | 'role';
  value: string;
  size?: 'sm' | 'md' | 'lg';
  showIcon?: boolean;
}

export const Badge: React.FC<BadgeProps> = ({
  type = 'status',
  value,
  size = 'md',
  showIcon = true,
}) => {
  const sizeClasses = {
    sm: 'text-[11px] px-2 py-0.5 font-medium rounded-md gap-1',
    md: 'text-xs px-2.5 py-1 font-semibold rounded-md gap-1.5',
    lg: 'text-sm px-3 py-1.5 font-bold rounded-lg gap-2',
  };

  // Status Badge
  if (type === 'status') {
    const status = value as AgentStatus;
    switch (status) {
      case 'online':
        return (
          <span className={`inline-flex items-center bg-emerald-50 text-emerald-700 border border-emerald-200/80 ${sizeClasses[size]}`}>
            {showIcon && <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>}
            En ligne
          </span>
        );
      case 'offline':
        return (
          <span className={`inline-flex items-center bg-rose-50 text-rose-700 border border-rose-200/80 ${sizeClasses[size]}`}>
            {showIcon && <WifiOff className="w-3 h-3 text-rose-500" />}
            Hors ligne
          </span>
        );
      case 'obsolete':
        return (
          <span className={`inline-flex items-center bg-amber-50 text-amber-700 border border-amber-200/80 ${sizeClasses[size]}`}>
            {showIcon && <AlertTriangle className="w-3 h-3 text-amber-500" />}
            Obsolète
          </span>
        );
      case 'revoked':
        return (
          <span className={`inline-flex items-center bg-[var(--color-ln2)] text-[var(--color-tx2)] border border-slate-300 ${sizeClasses[size]}`}>
            {showIcon && <ShieldCheck className="w-3 h-3 text-[var(--color-tx2)]" />}
            Révoqué
          </span>
        );
      default:
        return (
          <span className={`inline-flex items-center bg-[var(--color-ln2)] text-[var(--color-tx2)] border border-[var(--color-ln)] ${sizeClasses[size]}`}>
            {value}
          </span>
        );
    }
  }

  // Severity Badge
  if (type === 'severity') {
    const severity = value as AlertSeverity;
    switch (severity) {
      case 'critical':
        return (
          <span className={`inline-flex items-center bg-rose-600 text-white shadow-xs font-semibold ${sizeClasses[size]}`}>
            {showIcon && <AlertCircle className="w-3.5 h-3.5" />}
            Critique
          </span>
        );
      case 'major':
      case 'warning':
        return (
          <span className={`inline-flex items-center bg-amber-500 text-white shadow-xs font-semibold ${sizeClasses[size]}`}>
            {showIcon && <AlertTriangle className="w-3.5 h-3.5" />}
            {severity === 'warning' ? 'Warning' : 'Major'}
          </span>
        );
      case 'minor':
        return (
          <span className={`inline-flex items-center bg-orange-400 text-white shadow-xs font-semibold ${sizeClasses[size]}`}>
            {showIcon && <AlertTriangle className="w-3.5 h-3.5" />}
            Minor
          </span>
        );
      case 'info':
        return (
          <span className={`inline-flex items-center bg-blue-600 text-white shadow-xs font-semibold ${sizeClasses[size]}`}>
            {showIcon && <Info className="w-3.5 h-3.5" />}
            Info
          </span>
        );
    }
  }

  // Alert Status Badge
  if (type === 'alertStatus') {
    const status = value as AlertStatus;
    switch (status) {
      case 'open':
        return (
          <span className={`inline-flex items-center bg-rose-100 text-rose-800 border border-rose-200 font-semibold ${sizeClasses[size]}`}>
            <span className="w-1.5 h-1.5 rounded-full bg-rose-600"></span>
            Ouverte
          </span>
        );
      case 'acknowledged':
        return (
          <span className={`inline-flex items-center bg-[var(--color-ln2)] text-[var(--color-tx2)] border border-slate-300 font-medium ${sizeClasses[size]}`}>
            Acquittée
          </span>
        );
      case 'resolved':
        return (
          <span className={`inline-flex items-center bg-emerald-100 text-emerald-800 border border-emerald-200 font-medium ${sizeClasses[size]}`}>
            Résolue
          </span>
        );
    }
  }

  // Operating System Badge
  if (type === 'os') {
    const os = value.toLowerCase() as OperatingSystem;
    switch (os) {
      case 'windows':
        return (
          <span className={`inline-flex items-center bg-blue-50 text-blue-700 border border-blue-200/80 ${sizeClasses[size]}`}>
            {showIcon && <Monitor className="w-3.5 h-3.5 text-blue-600" />}
            Windows
          </span>
        );
      case 'linux':
        return (
          <span className={`inline-flex items-center bg-amber-50 text-amber-800 border border-amber-200/80 ${sizeClasses[size]}`}>
            {showIcon && <Terminal className="w-3.5 h-3.5 text-amber-600" />}
            Linux
          </span>
        );
      case 'macos':
        return (
          <span className={`inline-flex items-center bg-purple-50 text-purple-700 border border-purple-200/80 ${sizeClasses[size]}`}>
            {showIcon && <Apple className="w-3.5 h-3.5 text-purple-600" />}
            macOS
          </span>
        );
      default:
        return (
          <span className={`inline-flex items-center bg-[var(--color-ln2)] text-[var(--color-tx2)] ${sizeClasses[size]}`}>
            {value}
          </span>
        );
    }
  }

  // Role Badge
  if (type === 'role') {
    const role = value as Role;
    switch (role) {
      case 'Admin':
        return (
          <span className={`inline-flex items-center bg-[#D0B335]/15 text-[#8D771B] border border-[#D0B335]/40 font-semibold ${sizeClasses[size]}`}>
            Administrateur
          </span>
        );
      case 'Operator':
        return (
          <span className={`inline-flex items-center bg-blue-50 text-blue-700 border border-blue-200 ${sizeClasses[size]}`}>
            Opérateur
          </span>
        );
      case 'Security':
        return (
          <span className={`inline-flex items-center bg-violet-50 text-violet-700 border border-violet-200 ${sizeClasses[size]}`}>
            Sécurité
          </span>
        );
      case 'ReadOnly':
        return (
          <span className={`inline-flex items-center bg-[var(--color-ln2)] text-[var(--color-tx2)] border border-[var(--color-ln)] ${sizeClasses[size]}`}>
            Lecture seule
          </span>
        );
    }
  }

  return (
    <span className={`inline-flex items-center bg-[var(--color-ln2)] text-[var(--color-tx2)] border border-[var(--color-ln)] ${sizeClasses[size]}`}>
      {value}
    </span>
  );
};
