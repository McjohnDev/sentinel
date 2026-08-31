/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../../context/AppContext';
import {
  Bell,
  RefreshCw,
  User as UserIcon,
  LogOut,
  Settings,
  CheckCircle2,
  ChevronDown,
  Menu,
  Search,
} from 'lucide-react';
import { useI18n } from '../../i18n';
import { useRouteMeta } from './useRouteMeta';
import { SegmentedControl } from './SegmentedControl';
import { ChannelHealthPills } from './ChannelHealthPills';
import { CommandPalette } from './CommandPalette';
import { BackendNotificationChannelStatus } from '../../services/types/api.types';

interface HeaderProps {
  onToggleSidebarMobile?: () => void;
}

const showRbacSimulator = process.env.NODE_ENV === 'development';

export const Header: React.FC<HeaderProps> = ({ onToggleSidebarMobile }) => {
  const navigate = useNavigate();
  const { t, lang, setLang } = useI18n();
  const { groupLabel, pageLabel } = useRouteMeta();
  const {
    alerts,
    currentRole,
    setCurrentRole,
    currentUser,
    logout,
    autoRefresh,
    toggleAutoRefresh,
    refreshData,
  } = useApp();

  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const [roleMenuOpen, setRoleMenuOpen] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [channelStatus, setChannelStatus] = useState<BackendNotificationChannelStatus | null>(null);

  const notifRef = useRef<HTMLDivElement>(null);
  const userRef = useRef<HTMLDivElement>(null);
  const roleRef = useRef<HTMLDivElement>(null);

  const openAlerts = alerts.filter((a) => a.status === 'open');
  const criticalAlertsCount = openAlerts.filter((a) => a.severity === 'critical').length;

  const initials =
    currentUser?.name
      ?.split(' ')
      .map((p) => p[0])
      .join('')
      .substring(0, 2)
      .toUpperCase() || 'CB';

  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const response = await fetch('/api/system/notification-channel-status', {
          headers: { Authorization: `Bearer ${localStorage.getItem('access_token')}` },
        });
        if (response.ok) setChannelStatus(await response.json());
      } catch {
        /* optional */
      }
    };
    fetchStatus();
    const interval = setInterval(fetchStatus, 60000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setPaletteOpen(true);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (notifRef.current && !notifRef.current.contains(e.target as Node)) {
        setNotificationsOpen(false);
      }
      if (userRef.current && !userRef.current.contains(e.target as Node)) {
        setUserMenuOpen(false);
      }
      if (roleRef.current && !roleRef.current.contains(e.target as Node)) {
        setRoleMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const mailColor =
    channelStatus?.status === 'operational'
      ? '#059669'
      : channelStatus?.status === 'degraded'
        ? '#D97706'
        : channelStatus?.status === 'error'
          ? '#E11D48'
          : '#94A3B8';

  const pulseStyle =
    criticalAlertsCount > 0
      ? {
          bd: 'border-rose-200',
          bg: 'bg-rose-50',
          fg: 'text-rose-700',
          dot: 'bg-rose-600',
          text:
            lang === 'fr'
              ? `${criticalAlertsCount} alerte${criticalAlertsCount > 1 ? 's' : ''} critique${criticalAlertsCount > 1 ? 's' : ''}`
              : `${criticalAlertsCount} critical alert${criticalAlertsCount > 1 ? 's' : ''}`,
        }
      : {
          bd: 'border-emerald-200',
          bg: 'bg-emerald-50',
          fg: 'text-emerald-800',
          dot: 'bg-emerald-600',
          text: lang === 'fr' ? 'Système opérationnel' : 'System operational',
        };

  return (
    <>
      <header className="h-16 bg-white border-b border-slate-200 flex items-center justify-between px-4 sm:px-6 sticky top-0 z-30 shrink-0">
        <div className="flex items-center gap-3 min-w-0">
          <button
            type="button"
            onClick={onToggleSidebarMobile}
            className="lg:hidden p-2 text-slate-500 hover:text-slate-900 rounded-lg hover:bg-slate-100"
            aria-label="Ouvrir le menu"
          >
            <Menu className="w-5 h-5" />
          </button>

          <nav aria-label="Fil d'ariane" className="hidden sm:flex items-center gap-2 text-[12.5px] text-slate-500 min-w-0 truncate">
            <span>CBC Supervision</span>
            <span className="text-slate-300">/</span>
            <span>{groupLabel}</span>
            <span className="text-slate-300">/</span>
            <span className="text-slate-900 font-semibold truncate">{pageLabel}</span>
          </nav>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <button
            type="button"
            onClick={() => navigate('/alerts')}
            className={`hidden sm:flex items-center gap-1.5 px-2.5 py-1.5 rounded-2xl border cursor-pointer ${pulseStyle.bd} ${pulseStyle.bg}`}
          >
            <span className={`w-1.5 h-1.5 rounded-full animate-pulse-dot ${pulseStyle.dot}`} />
            <span className={`text-[11.5px] font-semibold ${pulseStyle.fg}`}>{pulseStyle.text}</span>
          </button>

          <ChannelHealthPills
            channels={[
              { label: 'Mail', color: mailColor },
              { label: 'Webhook', color: '#059669' },
            ]}
            onClick={() => navigate('/settings')}
          />

          <button
            type="button"
            onClick={() => setPaletteOpen(true)}
            title="Rechercher (⌘K)"
            className="w-[34px] h-[34px] border border-slate-200 bg-white rounded-lg flex items-center justify-center text-slate-600 hover:bg-slate-50"
          >
            <Search className="w-4 h-4" />
          </button>

          <div className="hidden sm:flex items-center gap-1">
            <button
              type="button"
              onClick={refreshData}
              title="Rafraîchir"
              className="p-1.5 text-slate-600 hover:text-slate-900 hover:bg-white rounded-md"
            >
              <RefreshCw className="w-3.5 h-3.5" />
            </button>
            <SegmentedControl
              options={[
                {
                  id: 'auto',
                  label: '30s Auto',
                  active: autoRefresh,
                  onClick: () => !autoRefresh && toggleAutoRefresh(),
                },
                {
                  id: 'pause',
                  label: 'Pause',
                  active: !autoRefresh,
                  onClick: () => autoRefresh && toggleAutoRefresh(),
                },
              ]}
            />
          </div>

          <SegmentedControl
            options={[
              {
                id: 'fr',
                label: 'FR',
                active: lang === 'fr',
                onClick: () => setLang('fr'),
              },
              {
                id: 'en',
                label: 'EN',
                active: lang === 'en',
                onClick: () => setLang('en'),
              },
            ]}
          />

          {showRbacSimulator && (
            <div className="relative hidden xl:block" ref={roleRef}>
              <button
                type="button"
                onClick={() => setRoleMenuOpen(!roleMenuOpen)}
                className="px-2 py-1 rounded-lg border border-[#D0B335]/40 bg-[#D0B335]/10 text-[11px] font-semibold text-[#8D771B]"
              >
                RBAC · {currentRole}
              </button>
              {roleMenuOpen && (
                <div className="absolute right-0 mt-2 w-48 bg-white rounded-xl border border-slate-200 py-1 z-50 shadow-lg">
                  {(['Admin', 'Operator', 'ReadOnly'] as const).map((role) => (
                    <button
                      key={role}
                      type="button"
                      onClick={() => {
                        setCurrentRole(role);
                        setRoleMenuOpen(false);
                      }}
                      className="w-full text-left px-3 py-2 text-xs hover:bg-slate-50"
                    >
                      {role}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}

          <div className="relative" ref={notifRef}>
            <button
              type="button"
              onClick={() => setNotificationsOpen(!notificationsOpen)}
              className="relative w-[34px] h-[34px] border border-slate-200 bg-white rounded-lg flex items-center justify-center text-slate-600 hover:bg-slate-50"
            >
              <Bell className="w-4 h-4" />
              {openAlerts.length > 0 && (
                <span className="absolute -top-1.5 -right-1.5 min-w-[17px] h-[17px] px-1 rounded-full bg-rose-600 text-white text-[9.5px] font-bold flex items-center justify-center">
                  {openAlerts.length}
                </span>
              )}
            </button>

            {notificationsOpen && (
              <div className="absolute right-0 mt-2 w-[340px] bg-white rounded-xl border border-slate-200 overflow-hidden z-50 animate-modal-in shadow-lg">
                <div className="px-4 py-3 border-b border-slate-200 text-xs font-bold">
                  {lang === 'fr' ? 'Alertes ouvertes' : 'Open alerts'} ({openAlerts.length})
                </div>
                <div className="max-h-80 overflow-y-auto">
                  {openAlerts.length === 0 ? (
                    <div className="p-6 text-center text-xs text-slate-500">
                      <CheckCircle2 className="w-8 h-8 text-emerald-500 mx-auto mb-2" />
                      {lang === 'fr' ? 'Aucune alerte ouverte.' : 'No open alerts.'}
                    </div>
                  ) : (
                    openAlerts.map((alt) => (
                      <div
                        key={alt.id}
                        className="px-4 py-3 border-b border-slate-50 hover:bg-slate-50 flex gap-2.5 cursor-pointer"
                        onClick={() => {
                          navigate('/alerts');
                          setNotificationsOpen(false);
                        }}
                      >
                        <span
                          className={`w-1.5 h-1.5 rounded-full mt-1.5 shrink-0 ${
                            alt.severity === 'critical' ? 'bg-rose-600' : 'bg-amber-500'
                          }`}
                        />
                        <div className="flex-1 min-w-0">
                          <div className="text-xs font-semibold truncate">{alt.agentName}</div>
                          <div className="text-[11.5px] text-slate-500 line-clamp-2 mt-0.5">{alt.message}</div>
                        </div>
                        <span className="tnum text-[11px] text-slate-400 shrink-0">{alt.timestamp}</span>
                      </div>
                    ))
                  )}
                </div>
              </div>
            )}
          </div>

          <div className="w-px h-6 bg-slate-200 hidden sm:block" />

          <div className="relative" ref={userRef}>
            <button
              type="button"
              onClick={() => setUserMenuOpen(!userMenuOpen)}
              className="flex items-center gap-2 hover:bg-slate-50 rounded-lg px-1 py-1"
            >
              <div className="w-[30px] h-[30px] rounded-full bg-[#D0B335]/10 border border-[#D0B335]/30 text-[#A68523] text-[11px] font-bold flex items-center justify-center">
                {initials}
              </div>
              <div className="hidden xl:block text-left">
                <p className="text-xs font-semibold text-slate-900 leading-tight truncate max-w-[120px]">
                  {currentUser?.name?.split(' ').map((n, i) => (i === 0 ? n : n[0] + '.')).join(' ')}
                </p>
                <p className="text-[10.5px] text-[#777777]">{roleLabel(currentRole)}</p>
              </div>
              <ChevronDown className="w-3.5 h-3.5 text-slate-400 hidden xl:block" />
            </button>

            {userMenuOpen && (
              <div className="absolute right-0 mt-2 w-56 bg-white rounded-xl border border-slate-200 py-1 z-50 shadow-lg">
                <div className="px-4 py-3 border-b border-slate-100">
                  <p className="text-xs font-bold text-slate-900">{currentUser?.name}</p>
                  <p className="text-[11px] text-slate-500 truncate">{currentUser?.email}</p>
                </div>
                <button
                  type="button"
                  onClick={() => {
                    navigate('/profile');
                    setUserMenuOpen(false);
                  }}
                  className="w-full text-left px-4 py-2 text-xs font-medium text-slate-700 hover:bg-slate-50 flex items-center gap-2"
                >
                  <UserIcon className="w-4 h-4 text-slate-400" />
                  Mon profil
                </button>
                <button
                  type="button"
                  onClick={() => {
                    navigate('/settings');
                    setUserMenuOpen(false);
                  }}
                  className="w-full text-left px-4 py-2 text-xs font-medium text-slate-700 hover:bg-slate-50 flex items-center gap-2"
                >
                  <Settings className="w-4 h-4 text-slate-400" />
                  {t('nav.settings')}
                </button>
                <div className="border-t border-slate-100 my-1" />
                <button
                  type="button"
                  onClick={() => {
                    logout();
                    setUserMenuOpen(false);
                  }}
                  className="w-full text-left px-4 py-2 text-xs font-semibold text-rose-600 hover:bg-rose-50 flex items-center gap-2"
                >
                  <LogOut className="w-4 h-4 text-rose-500" />
                  {t('nav.logout')}
                </button>
              </div>
            )}
          </div>
        </div>
      </header>

      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} />
    </>
  );
};

function roleLabel(role: string): string {
  if (role === 'Admin') return 'Administrateur';
  if (role === 'Operator') return 'Opérateur';
  return 'Consultation';
}
