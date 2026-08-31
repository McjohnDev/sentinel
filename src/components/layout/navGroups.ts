/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { LucideIcon } from 'lucide-react';
import {
  LayoutDashboard,
  Server,
  Bell,
  FileSearch,
  LayoutGrid,
  TrendingUp,
  Network,
  FileDown,
  Workflow,
  ShieldCheck,
  Zap,
  SlidersHorizontal,
  Plug,
  Users,
  Settings,
} from 'lucide-react';

export interface NavItem {
  id: string;
  path: string;
  labelKey: string;
  icon: LucideIcon;
  badgeKey?: 'alerts' | 'approvals';
  healthDot?: boolean;
}

export interface NavGroup {
  id: string;
  labelKey: string;
  items: NavItem[];
}

export const NAV_GROUPS: NavGroup[] = [
  {
    id: 'exploit',
    labelKey: 'nav.group.exploit',
    items: [
      { id: 'dashboard', path: '/dashboard', labelKey: 'nav.dashboard', icon: LayoutDashboard },
      { id: 'agents', path: '/agents', labelKey: 'nav.agents', icon: Server },
      { id: 'alerts', path: '/alerts', labelKey: 'nav.alerts', icon: Bell, badgeKey: 'alerts' },
      { id: 'logs', path: '/logs', labelKey: 'nav.logs', icon: FileSearch },
    ],
  },
  {
    id: 'analyze',
    labelKey: 'nav.group.analyze',
    items: [
      { id: 'dashboards', path: '/dashboards', labelKey: 'nav.dashboards', icon: LayoutGrid },
      { id: 'trends', path: '/trends', labelKey: 'nav.trends', icon: TrendingUp },
      { id: 'reports', path: '/reports', labelKey: 'nav.reports', icon: FileDown },
      { id: 'network', path: '/network', labelKey: 'nav.network', icon: Network },
    ],
  },
  {
    id: 'automate',
    labelKey: 'nav.group.automate',
    items: [
      { id: 'automation', path: '/automation', labelKey: 'nav.automation', icon: Workflow },
      { id: 'approvals', path: '/approvals', labelKey: 'nav.approvals', icon: ShieldCheck, badgeKey: 'approvals' },
      { id: 'actions', path: '/actions', labelKey: 'nav.actions', icon: Zap },
    ],
  },
  {
    id: 'configure',
    labelKey: 'nav.group.configure',
    items: [
      { id: 'rules', path: '/rules', labelKey: 'nav.rules', icon: SlidersHorizontal },
      { id: 'integrations', path: '/integrations', labelKey: 'nav.integrations', icon: Plug, healthDot: true },
    ],
  },
  {
    id: 'admin',
    labelKey: 'nav.group.admin',
    items: [
      { id: 'users', path: '/users', labelKey: 'nav.users', icon: Users },
      { id: 'audit', path: '/audit', labelKey: 'nav.audit', icon: FileSearch },
      { id: 'settings', path: '/settings', labelKey: 'nav.settings', icon: Settings },
    ],
  },
];

export function isNavActive(path: string, item: NavItem): boolean {
  if (item.id === 'agents') {
    return path === '/agents' || path === '/fleet' || path.startsWith('/agents/') || path.startsWith('/fleet/');
  }
  return path === item.path;
}
