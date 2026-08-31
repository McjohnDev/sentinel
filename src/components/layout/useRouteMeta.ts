/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { useLocation } from 'react-router-dom';
import { useI18n } from '../../i18n';
import { NAV_GROUPS } from './navGroups';

export function useRouteMeta() {
  const { pathname } = useLocation();
  const { t, lang } = useI18n();

  for (const group of NAV_GROUPS) {
    for (const item of group.items) {
      const active =
        item.id === 'agents'
          ? pathname === '/agents' ||
            pathname === '/fleet' ||
            pathname.startsWith('/agents/') ||
            pathname.startsWith('/fleet/')
          : pathname === item.path;

      if (active) {
        return {
          groupLabel: t(group.labelKey),
          pageLabel: t(item.labelKey),
          pathname,
        };
      }
    }
  }

  if (pathname.startsWith('/agents/') || pathname.startsWith('/fleet/')) {
    return {
      groupLabel: t('nav.group.exploit'),
      pageLabel: lang === 'fr' ? 'Parc' : 'Fleet',
      pathname,
    };
  }

  if (pathname === '/profile') {
    return {
      groupLabel: t('nav.group.admin'),
      pageLabel: t('nav.profile'),
      pathname,
    };
  }

  return {
    groupLabel: t('nav.group.exploit'),
    pageLabel: t('nav.dashboard'),
    pathname,
  };
}
