/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../../context/AppContext';
import { Bell, CheckCircle2, Menu, Moon, Pause, Play, Search, Sun } from 'lucide-react';
import { useI18n } from '../../i18n';
import { useRouteMeta } from './useRouteMeta';
import { SegmentedControl } from './SegmentedControl';
import { ChannelHealthPills } from './ChannelHealthPills';
import { BackendNotificationChannelStatus } from '../../services/types/api.types';

interface HeaderProps {
  onToggleSidebarMobile?: () => void;
  onOpenPalette?: () => void;
}

const showRbacSimulator = process.env.NODE_ENV === 'development';

export const Header: React.FC<HeaderProps> = ({ onToggleSidebarMobile, onOpenPalette }) => {
  const navigate = useNavigate();
  const { t, lang, setLang } = useI18n();
  const { groupLabel, pageLabel } = useRouteMeta();
  const {
    alerts,
    currentRole,
    setCurrentRole,
    theme,
    toggleTheme,
    autoRefresh,
    toggleAutoRefresh,
    navbarSurface: sf,
  } = useApp();

  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [roleMenuOpen, setRoleMenuOpen] = useState(false);
  const [channelStatus, setChannelStatus] = useState<BackendNotificationChannelStatus | null>(null);
  const [now, setNow] = useState(() => new Date().toLocaleTimeString('fr-FR'));

  const notifRef = useRef<HTMLDivElement>(null);
  const roleRef = useRef<HTMLDivElement>(null);

  const openAlerts = alerts.filter((a) => a.status === 'open');
  const criticalAlertsCount = openAlerts.filter((a) => a.severity === 'critical').length;

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

  // Horloge visible en permanence, comme repère de fraîcheur de l'écran —
  // utile quand l'auto-rafraîchissement est en pause.
  useEffect(() => {
    const id = setInterval(() => setNow(new Date().toLocaleTimeString('fr-FR')), 1000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (notifRef.current && !notifRef.current.contains(e.target as Node)) {
        setNotificationsOpen(false);
      }
      if (roleRef.current && !roleRef.current.contains(e.target as Node)) {
        setRoleMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const mailOk = channelStatus?.status === 'operational';
  const mailColor = mailOk
    ? 'var(--color-grn)'
    : channelStatus?.status === 'degraded'
      ? 'var(--color-amb)'
      : channelStatus?.status === 'error'
        ? 'var(--color-red)'
        : 'var(--color-tx3)';

  const pillTone =
    criticalAlertsCount > 0
      ? { bg: 'var(--color-red-t)', bd: 'var(--color-red-b)', fg: 'var(--color-red)', dot: 'var(--color-red)' }
      : { bg: 'var(--color-grn-t)', bd: 'var(--color-grn-b)', fg: 'var(--color-grn)', dot: 'var(--color-grn)' };
  const pillText =
    criticalAlertsCount > 0
      ? lang === 'fr'
        ? `${criticalAlertsCount} critique${criticalAlertsCount > 1 ? 's' : ''}`
        : `${criticalAlertsCount} critical`
      : lang === 'fr'
        ? 'Système opérationnel'
        : 'System operational';

  // Meme principe que la sidebar : les variables sont posees localement sur
  // le bandeau, lues avec repli par les regles partagees.
  const scopeVars: React.CSSProperties = {
    background: sf.background,
    borderColor: sf.ln,
    ['--surface-fg' as string]: sf.fg,
    ['--surface-fg2' as string]: sf.fg2,
    ['--surface-fg3' as string]: sf.fg3,
    ['--surface-hover' as string]: sf.hover,
  };

  return (
    <header
      className="h-12 border-b flex items-center gap-2 px-4 sticky top-0 z-30 shrink-0"
      style={scopeVars}
    >
      <button
        type="button"
        onClick={onToggleSidebarMobile}
        className="lg:hidden p-2 rounded-lg -ml-2"
        style={{ color: 'var(--surface-fg2)' }}
        aria-label="Ouvrir le menu"
      >
        <Menu className="w-5 h-5" />
      </button>

      <nav aria-label="Fil d'ariane" className="hidden sm:flex items-center gap-2 min-w-0 truncate">
        <span
          className="font-mono text-[9.5px] tracking-[0.1em]"
          style={{ color: 'var(--surface-fg3)' }}
        >
          {groupLabel.toUpperCase()}
        </span>
        <span className="text-[11px]" style={{ color: 'var(--surface-fg3)' }}>
          /
        </span>
        <span className="text-[12.5px] font-semibold truncate" style={{ color: 'var(--surface-fg)' }}>
          {pageLabel}
        </span>
      </nav>

      <div className="flex-1" />

      <div className="flex items-center gap-1.5 shrink-0">
        <button
          type="button"
          onClick={() => navigate('/alerts')}
          className="hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-full border cursor-pointer"
          style={{ background: pillTone.bg, borderColor: pillTone.bd }}
        >
          <span
            className="w-1.5 h-1.5 rounded-full animate-pulse-dot"
            style={{ background: pillTone.dot }}
          />
          <span className="text-[11px] font-semibold" style={{ color: pillTone.fg }}>
            {pillText}
          </span>
        </button>

        <ChannelHealthPills
          channels={[
            { label: 'MAIL', color: mailColor },
            { label: 'WEBHOOK', color: 'var(--color-grn)' },
          ]}
          onClick={() => navigate('/integrations')}
        />

        <button
          type="button"
          onClick={toggleAutoRefresh}
          title={autoRefresh ? 'Mettre en pause' : 'Reprendre'}
          className="hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-full border cursor-pointer"
          style={{ borderColor: 'var(--surface-fg3)', color: 'var(--surface-fg2)', opacity: 0.92 }}
        >
          {autoRefresh ? <Pause className="w-3 h-3" /> : <Play className="w-3 h-3" />}
          <span className="text-[11px]">{autoRefresh ? 'Auto · 30 s' : 'En pause'}</span>
        </button>

        <button
          type="button"
          onClick={onOpenPalette}
          title="Rechercher (⌘K)"
          className="w-[30px] h-[30px] border rounded-lg flex items-center justify-center sm:hidden"
          style={{ borderColor: 'var(--surface-fg3)', color: 'var(--surface-fg2)' }}
        >
          <Search className="w-4 h-4" />
        </button>

        <span
          className="font-mono text-[11px] tnum hidden md:inline-block min-w-[58px] text-right"
          style={{ color: 'var(--surface-fg2)' }}
        >
          {now}
        </span>

        <SegmentedControl
          options={[
            { id: 'fr', label: 'FR', active: lang === 'fr', onClick: () => setLang('fr') },
            { id: 'en', label: 'EN', active: lang === 'en', onClick: () => setLang('en') },
          ]}
        />

        {showRbacSimulator && (
          <div className="relative hidden xl:block" ref={roleRef}>
            <button
              type="button"
              onClick={() => setRoleMenuOpen(!roleMenuOpen)}
              className="px-2 py-1 rounded-lg border text-[11px] font-semibold"
              style={{ borderColor: 'var(--color-acc-b)', background: 'var(--color-acc-t)', color: 'var(--color-acc)' }}
            >
              RBAC · {currentRole}
            </button>
            {roleMenuOpen && (
              <div
                className="absolute right-0 mt-2 w-48 rounded-xl border py-1 z-50 shadow-lg"
                style={{ background: 'var(--color-panel)', borderColor: 'var(--color-ln)' }}
              >
                {(['Admin', 'Operator', 'ReadOnly'] as const).map((role) => (
                  <button
                    key={role}
                    type="button"
                    onClick={() => {
                      setCurrentRole(role);
                      setRoleMenuOpen(false);
                    }}
                    className="w-full text-left px-3 py-2 text-xs"
                    style={{ color: 'var(--color-tx)' }}
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
            className="relative w-[30px] h-[30px] border rounded-lg flex items-center justify-center"
            style={{ borderColor: 'var(--surface-fg3)', color: 'var(--surface-fg2)' }}
          >
            <Bell className="w-4 h-4" />
            {openAlerts.length > 0 && (
              <span
                className="absolute -top-1.5 -right-1.5 min-w-[17px] h-[17px] px-1 rounded-full text-white text-[9.5px] font-bold flex items-center justify-center"
                style={{ background: 'var(--color-red)' }}
              >
                {openAlerts.length}
              </span>
            )}
          </button>

          {notificationsOpen && (
            <div
              className="absolute right-0 mt-2 w-[340px] rounded-xl border overflow-hidden z-50 animate-modal-in shadow-lg"
              style={{ background: 'var(--color-panel)', borderColor: 'var(--color-ln)' }}
            >
              <div
                className="px-4 py-3 border-b text-xs font-bold"
                style={{ borderColor: 'var(--color-ln)', color: 'var(--color-tx)' }}
              >
                {lang === 'fr' ? 'Alertes ouvertes' : 'Open alerts'} ({openAlerts.length})
              </div>
              <div className="max-h-80 overflow-y-auto">
                {openAlerts.length === 0 ? (
                  <div className="p-6 text-center text-xs" style={{ color: 'var(--color-tx2)' }}>
                    <CheckCircle2 className="w-8 h-8 mx-auto mb-2" style={{ color: 'var(--color-grn)' }} />
                    {lang === 'fr' ? 'Aucune alerte ouverte.' : 'No open alerts.'}
                  </div>
                ) : (
                  openAlerts.map((alt) => (
                    <div
                      key={alt.id}
                      className="px-4 py-3 border-b flex gap-2.5 cbc-hover"
                      style={{ borderColor: 'var(--color-ln2)' }}
                      onClick={() => {
                        navigate('/alerts');
                        setNotificationsOpen(false);
                      }}
                    >
                      <span
                        className="w-1.5 h-1.5 rounded-full mt-1.5 shrink-0"
                        style={{
                          background:
                            alt.severity === 'critical' ? 'var(--color-red)' : 'var(--color-amb)',
                        }}
                      />
                      <div className="flex-1 min-w-0">
                        <div className="text-xs font-semibold truncate" style={{ color: 'var(--color-tx)' }}>
                          {alt.agentName}
                        </div>
                        <div
                          className="text-[11.5px] line-clamp-2 mt-0.5"
                          style={{ color: 'var(--color-tx2)' }}
                        >
                          {alt.message}
                        </div>
                      </div>
                      <span
                        className="tnum text-[11px] shrink-0"
                        style={{ color: 'var(--color-tx3)' }}
                      >
                        {alt.timestamp}
                      </span>
                    </div>
                  ))
                )}
              </div>
            </div>
          )}
        </div>

        <button
          type="button"
          onClick={toggleTheme}
          title={theme === 'dark' ? 'Passer au thème clair' : 'Passer au thème sombre'}
          className="w-[30px] h-[30px] border rounded-lg flex items-center justify-center"
          style={{ borderColor: 'var(--surface-fg3)', color: 'var(--surface-fg2)' }}
        >
          {theme === 'dark' ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
        </button>
      </div>
    </header>
  );
};
