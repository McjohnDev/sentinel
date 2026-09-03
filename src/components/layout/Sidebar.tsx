/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useApp } from '../../context/AppContext';
import { LogOut, Search, X } from 'lucide-react';
import { useI18n } from '../../i18n';
import { NAV_GROUPS, isNavActive } from './navGroups';

interface SidebarProps {
  isMobileOpen?: boolean;
  onCloseMobile?: () => void;
  onOpenPalette?: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ isMobileOpen, onCloseMobile, onOpenPalette }) => {
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const { alerts, currentUser, logout, currentRole, sidebarSurface: sf } = useApp();
  const { t } = useI18n();

  const openAlertsCount = alerts.filter((a) => a.status === 'open').length;
  const initials =
    currentUser?.name
      ?.split(' ')
      .map((p) => p[0])
      .join('')
      .substring(0, 2)
      .toUpperCase() || 'CB';

  const roleLabel =
    currentRole === 'Admin'
      ? 'Administrateur'
      : currentRole === 'Operator'
        ? 'Opérateur'
        : 'Consultation';

  const navigateTo = (path: string) => {
    navigate(path);
    onCloseMobile?.();
  };

  // Variables posées localement sur la coquille : `.cbc-nav-item`,
  // `.cbc-nav-active` et `.cbc-hover` (index.css) les lisent avec un repli
  // sur les jetons de thème — une barre laterale personnalisée en marine
  // reste donc lisible sans qu'aucune règle partagée n'ait à le savoir.
  const scopeVars: React.CSSProperties = {
    background: sf.background,
    borderColor: sf.ln,
    ['--surface-fg' as string]: sf.fg,
    ['--surface-fg2' as string]: sf.fg2,
    ['--surface-fg3' as string]: sf.fg3,
    ['--surface-hover' as string]: sf.hover,
    ['--surface-acc' as string]: 'var(--color-acc)',
    ['--surface-acc-t' as string]: sf.accT,
  };

  const sidebarContent = (
    <div className="flex flex-col h-full w-[216px] border-r select-none" style={scopeVars}>
      <div className="flex items-center gap-2.5 px-3.5 pt-3.5 pb-3">
        <div
          className="w-[30px] h-[30px] rounded-[7px] flex items-center justify-center text-[9.5px] font-bold shrink-0"
          style={{
            background: 'linear-gradient(135deg,#E5C26C,#B68D2C)',
            color: '#191204',
          }}
        >
          CBC
        </div>
        <div className="min-w-0">
          <div className="text-[13px] font-semibold tracking-tight" style={{ color: 'var(--surface-fg)' }}>
            Supervision
          </div>
          <div
            className="font-mono text-[8.5px] tracking-[0.08em] mt-px"
            style={{ color: 'var(--surface-fg3)' }}
          >
            ISO 27001 · COBAC
          </div>
        </div>
        <div className="flex-1" />
        <span
          className="font-mono text-[8.5px] px-[5px] py-0.5 rounded tracking-[0.06em] shrink-0"
          style={{ background: 'var(--color-grn-t)', color: 'var(--color-grn)' }}
        >
          PROD
        </span>
        {isMobileOpen && (
          <button
            type="button"
            onClick={onCloseMobile}
            className="lg:hidden p-1 rounded-lg"
            style={{ color: 'var(--surface-fg3)' }}
          >
            <X className="w-5 h-5" />
          </button>
        )}
      </div>

      <button
        type="button"
        onClick={onOpenPalette}
        className="mx-3 mb-2 flex items-center gap-2 px-2.5 py-1.5 rounded-lg border text-[12px] cursor-pointer transition-colors"
        style={{ borderColor: 'var(--surface-fg3)', color: 'var(--surface-fg3)', opacity: 0.92 }}
      >
        <Search className="w-3.5 h-3.5 shrink-0" />
        <span className="flex-1 text-left">Rechercher…</span>
        <span
          className="font-mono text-[9px] border rounded px-1 py-px"
          style={{ borderColor: 'var(--surface-fg3)' }}
        >
          ⌘K
        </span>
      </button>

      <nav className="flex-1 overflow-y-auto px-2.5 pb-2">
        {NAV_GROUPS.map((group) => (
          <div key={group.id} className="pt-3 first:pt-0">
            <div
              className="font-mono text-[8.5px] tracking-[0.14em] px-2 pb-1"
              style={{ color: 'var(--surface-fg3)' }}
            >
              {t(group.labelKey).toUpperCase()}
            </div>
            {group.items.map((item) => {
              const active = isNavActive(pathname, item);
              const Icon = item.icon;
              let badge: number | undefined;
              if (item.badgeKey === 'alerts' && openAlertsCount > 0) {
                badge = openAlertsCount;
              }

              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => navigateTo(item.path)}
                  className={`w-full flex items-center gap-2.5 px-2.5 py-2 rounded-xl text-[12.5px] font-semibold mb-0.5 transition-colors ${
                    active ? 'cbc-nav-active' : 'cbc-nav-item border border-transparent'
                  }`}
                >
                  <Icon
                    className="w-4 h-4 shrink-0"
                    style={{ color: active ? 'var(--surface-acc)' : 'var(--surface-fg3)' }}
                  />
                  <span className="flex-1 text-left truncate">{t(item.labelKey)}</span>
                  {item.healthDot && (
                    <span
                      className="w-1.5 h-1.5 rounded-full shrink-0"
                      style={{ background: 'var(--color-grn)' }}
                    />
                  )}
                  {badge !== undefined && (
                    <span
                      className="min-w-[19px] px-1.5 py-0.5 rounded-full text-white text-[10px] font-bold text-center"
                      style={{ background: 'var(--color-red)' }}
                    >
                      {badge}
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        ))}
      </nav>

      <div className="px-2.5 pb-2.5 mt-auto">
        <div className="h-px mb-2.5" style={{ background: 'var(--surface-fg3)', opacity: 0.25 }} />
        <div className="flex items-center gap-2.5 px-1 py-1.5">
          <button
            type="button"
            onClick={() => navigateTo('/profile')}
            className="flex items-center gap-2.5 flex-1 min-w-0 text-left rounded-xl px-1.5 py-1 cbc-hover"
            style={{ color: 'var(--surface-fg)' }}
          >
            <div
              className="w-[27px] h-[27px] rounded-full border flex items-center justify-center text-[11px] font-bold shrink-0"
              style={{ background: 'var(--surface-acc-t)', borderColor: 'var(--color-acc-b)', color: 'var(--surface-acc)' }}
            >
              {initials.substring(0, 1)}
            </div>
            <div className="min-w-0">
              <p className="text-[12px] font-semibold truncate">{currentUser?.name}</p>
              <p
                className="font-mono text-[8.5px] tracking-[0.05em] truncate"
                style={{ color: 'var(--surface-fg3)' }}
              >
                {roleLabel.toUpperCase()}
              </p>
            </div>
          </button>
          <button
            type="button"
            onClick={logout}
            title={t('nav.logout')}
            className="p-1.5 rounded-lg shrink-0 cbc-hover"
            style={{ color: 'var(--surface-fg3)' }}
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );

  return (
    <>
      <aside className="hidden lg:block h-screen sticky top-0 z-40 shrink-0">{sidebarContent}</aside>

      {isMobileOpen && (
        <div className="fixed inset-0 z-50 lg:hidden flex">
          <div className="fixed inset-0 bg-black/50" onClick={onCloseMobile} />
          <div className="relative z-10 max-w-[216px]">{sidebarContent}</div>
        </div>
      )}
    </>
  );
};
