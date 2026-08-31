/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useApp } from '../../context/AppContext';
import { LogOut, X } from 'lucide-react';
import { useI18n } from '../../i18n';
import { NAV_GROUPS, isNavActive } from './navGroups';

interface SidebarProps {
  isMobileOpen?: boolean;
  onCloseMobile?: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ isMobileOpen, onCloseMobile }) => {
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const { alerts, currentUser, logout, currentRole } = useApp();
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

  const sidebarContent = (
    <div
      className="flex flex-col h-full text-slate-200 w-[250px] border-r border-slate-800 select-none"
      style={{ background: '#020617' }}
    >
      <div className="flex items-center gap-2.5 px-[18px] pt-[18px] pb-4">
        <div className="w-8 h-8 rounded-lg bg-[#D0B335] text-[#020617] text-[11.5px] font-extrabold flex items-center justify-center shrink-0">
          CBC
        </div>
        <div>
          <div className="text-[13px] font-bold text-slate-50">CBC Supervision</div>
          <div className="text-[10px] font-semibold tracking-wide text-slate-500 mt-0.5">
            ISO 27001 · COBAC
          </div>
        </div>
        {isMobileOpen && (
          <button
            type="button"
            onClick={onCloseMobile}
            className="lg:hidden ml-auto text-slate-400 hover:text-white p-1 rounded-lg"
          >
            <X className="w-5 h-5" />
          </button>
        )}
      </div>

      <div className="flex-1 overflow-y-auto px-3 pb-2">
        {NAV_GROUPS.map((group) => (
          <div key={group.id} className="pt-3.5 first:pt-0">
            <div className="px-2 pb-1.5 text-[10px] font-bold uppercase tracking-[0.12em] text-slate-500">
              {t(group.labelKey)}
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
                  className={`w-full flex items-center gap-2.5 px-2.5 py-2 rounded-xl text-xs font-semibold mb-0.5 transition-colors ${
                    active ? 'cbc-nav-active' : 'cbc-nav-item border border-transparent'
                  }`}
                >
                  <Icon
                    className={`w-4 h-4 shrink-0 ${active ? 'text-[#D0B335]' : 'text-slate-500'}`}
                  />
                  <span className="flex-1 text-left">{t(item.labelKey)}</span>
                  {item.healthDot && (
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 shrink-0" />
                  )}
                  {badge !== undefined && (
                    <span className="min-w-[19px] px-1.5 py-0.5 rounded-full bg-rose-600 text-white text-[10px] font-bold text-center">
                      {badge}
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        ))}
      </div>

      <div className="px-3 pb-3 mt-auto">
        <div className="h-px bg-slate-800 mb-3" />
        <button
          type="button"
          onClick={() => navigateTo('/profile')}
          className="w-full flex items-center gap-2.5 p-2 rounded-xl hover:bg-white/5 transition-colors text-left"
        >
          <div className="w-[30px] h-[30px] rounded-full bg-[#D0B335]/10 border border-[#D0B335]/30 text-[#D0B335] text-[11px] font-bold flex items-center justify-center shrink-0">
            {initials.substring(0, 2)}
          </div>
          <div className="min-w-0">
            <p className="text-xs font-semibold text-slate-200 truncate">{currentUser?.name}</p>
            <p className="text-[10.5px] text-slate-500 truncate">{currentUser?.email}</p>
            <p className="text-[10.5px] text-slate-600 mt-0.5">{roleLabel}</p>
          </div>
        </button>
        <button
          type="button"
          onClick={logout}
          className="w-full mt-1 flex items-center gap-2.5 px-2.5 py-2 rounded-xl text-xs font-semibold text-slate-500 hover:bg-white/5 hover:text-slate-200 transition-colors"
        >
          <LogOut className="w-4 h-4" />
          {t('nav.logout')}
        </button>
      </div>
    </div>
  );

  return (
    <>
      <aside className="hidden lg:block h-screen sticky top-0 z-40 shrink-0">{sidebarContent}</aside>

      {isMobileOpen && (
        <div className="fixed inset-0 z-50 lg:hidden flex">
          <div className="fixed inset-0 bg-slate-950/80" onClick={onCloseMobile} />
          <div className="relative z-10 max-w-[250px]">{sidebarContent}</div>
        </div>
      )}
    </>
  );
};
