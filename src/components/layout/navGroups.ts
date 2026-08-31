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

/**
 * Navigation réduite au périmètre en cours de reconstruction.
 *
 * Les groupes « Analyser » (tableaux personnalisés, tendances, rapports,
 * réseau) et « Automatiser » (scénarios, approbations, actions) ont été
 * retirés : aucune de ces surfaces ne figure dans les points 1 à 10 en cours
 * d'implémentation, et elles présentaient des écrans dont le socle est
 * précisément ce que l'on reprend à zéro.
 *
 * Ce qui reste correspond au parcours visé : enrôler un hôte, le voir, le
 * configurer, être alerté, tracer qui a fait quoi.
 */
export const NAV_GROUPS: NavGroup[] = [
  {
    id: 'exploit',
    labelKey: 'nav.group.exploit',
    items: [
      { id: 'dashboard', path: '/dashboard', labelKey: 'nav.dashboard', icon: LayoutDashboard },
      { id: 'agents', path: '/agents', labelKey: 'nav.agents', icon: Server },
      { id: 'alerts', path: '/alerts', labelKey: 'nav.alerts', icon: Bell, badgeKey: 'alerts' },
    ],
  },
  {
    id: 'configure',
    labelKey: 'nav.group.configure',
    items: [
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
