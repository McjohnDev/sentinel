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
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
  ChevronDown,
  Menu,
  Server,
  Activity,
} from 'lucide-react';
import { Badge } from '../common/Badge';

interface HeaderProps {
  onToggleSidebarMobile?: () => void;
}

export const Header: React.FC<HeaderProps> = ({ onToggleSidebarMobile }) => {
  const navigate = useNavigate();
  const {
    selectedAgentId,
    agents,
    alerts,
    currentRole,
    setCurrentRole,
    currentUser,
    logout,
    autoRefresh,
    toggleAutoRefresh,
    refreshData,
    acknowledgeAlert,
  } = useApp();

  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const [roleMenuOpen, setRoleMenuOpen] = useState(false);

  const notifRef = useRef<HTMLDivElement>(null);
  const userRef = useRef<HTMLDivElement>(null);
  const roleRef = useRef<HTMLDivElement>(null);

  const openAlerts = alerts.filter((a) => a.status === 'open');
  const criticalAlertsCount = openAlerts.filter((a) => a.severity === 'critical').length;
  const targetAgent = selectedAgentId ? agents.find((a) => a.id === selectedAgentId) : null;

  const totalAgents = agents.length;
  const onlineAgents = agents.filter((a) => a.status === 'online').length;
  const offlineAgents = agents.filter((a) => a.status === 'offline').length;
  const warningAgents = agents.filter((a) => a.status === 'warning').length;
  const openAlertsCount = openAlerts.length;

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

  // Compute Breadcrumb titles
  const getBreadcrumb = () => {
    const currentPath = window.location.pathname;

    if (currentPath === '/dashboard') {
      return [{ title: 'Tableau de bord', path: '/dashboard' }];
    }
    if (currentPath === '/agents') {
      return [{ title: 'Gestion des agents', path: '/agents' }];
    }
    if (currentPath.startsWith('/agents/')) {
      return [
        { title: 'Gestion des agents', path: '/agents' },
        { title: 'Détails agent', path: currentPath },
      ];
    }
    if (currentPath === '/alerts') {
      return [{ title: 'Gestion des alertes', path: '/alerts' }];
    }
    if (currentPath === '/settings') {
      return [{ title: 'Paramètres', path: '/settings' }];
    }
    if (currentPath === '/users') {
      return [{ title: 'Gestion utilisateurs', path: '/users' }];
    }
    return [{ title: 'Tableau de bord', path: '/dashboard' }];
  };

  const breadcrumbs = getBreadcrumb();

  return (
    <header className="h-16 bg-white border-b border-slate-200/90 px-4 sm:px-6 flex items-center justify-between sticky top-0 z-30 shadow-2xs">
      {/* Left: Hamburger (mobile) + Breadcrumb */}
      <div className="flex items-center gap-3">
        <button
          onClick={onToggleSidebarMobile}
          className="lg:hidden p-2 text-slate-500 hover:text-slate-900 rounded-lg hover:bg-slate-100"
          aria-label="Ouvrir le menu"
        >
          <Menu className="w-5 h-5" />
        </button>

        <nav aria-label="Fil d'ariane" className="hidden sm:flex items-center gap-1.5 text-xs">
          <span className="font-semibold text-slate-400">CBC Supervision</span>
          {breadcrumbs.map((crumb, idx) => (
            <React.Fragment key={idx}>
              <span className="text-slate-300">/</span>
              {idx === breadcrumbs.length - 1 ? (
                <span className="font-bold text-slate-900">{crumb.title}</span>
              ) : (
                <button
                  onClick={() => navigate(crumb.path)}
                  className="font-medium text-slate-500 hover:text-slate-900 transition-colors"
                >
                  {crumb.title}
                </button>
              )}
            </React.Fragment>
          ))}
        </nav>
      </div>

      {/* Right: Actions, Pulse Status, Perspective Switcher, Notifications, Profile */}
      <div className="flex items-center gap-2 sm:gap-3">
        {/* Compact Permanent KPI Stats Pills */}
        <div className="hidden lg:flex items-center gap-2">
          {/* Agents Pill */}
          <button
            onClick={() => navigate('/agents')}
            className="flex items-center gap-1.5 px-2.5 py-1 bg-slate-50 hover:bg-slate-100 border border-slate-200/80 rounded-lg text-xs transition-colors cursor-pointer"
            title="Voir tous les agents enrôlés"
          >
            <Server className="w-3.5 h-3.5 text-slate-500" />
            <span className="font-semibold text-slate-600">Agents:</span>
            <span className="font-bold text-slate-900">{onlineAgents}/{totalAgents}</span>
            {offlineAgents > 0 && (
              <span className="text-[10px] font-bold px-1.5 py-0.2 bg-rose-100 text-rose-700 rounded-full">
                {offlineAgents} HS
              </span>
            )}
          </button>

          {/* Alertes Pill */}
          <button
            onClick={() => navigate('/alerts')}
            className={`flex items-center gap-1.5 px-2.5 py-1 border rounded-lg text-xs transition-colors cursor-pointer ${
              openAlertsCount > 0
                ? 'bg-amber-50 hover:bg-amber-100 border-amber-200/80 text-amber-900 font-bold'
                : 'bg-slate-50 hover:bg-slate-100 border-slate-200/80 text-slate-600 font-medium'
            }`}
            title="Voir le centre d'alertes"
          >
            <Bell className="w-3.5 h-3.5 text-amber-600" />
            <span className="font-semibold">Alertes:</span>
            <span className="font-extrabold">{openAlertsCount}</span>
          </button>
        </div>

        {/* System Health Pulse Indicator */}
        <div className="hidden md:flex items-center gap-2 px-3 py-1 rounded-full bg-slate-50 border border-slate-200 text-xs">
          {criticalAlertsCount > 0 ? (
            <>
              <span className="w-2 h-2 rounded-full bg-rose-500 animate-ping"></span>
              <span className="font-semibold text-rose-700">
                {criticalAlertsCount} Alerte{criticalAlertsCount > 1 ? 's' : ''} Critique{criticalAlertsCount > 1 ? 's' : ''}
              </span>
            </>
          ) : (
            <>
              <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
              <span className="font-medium text-slate-700">Système opérationnel</span>
            </>
          )}
        </div>

        {/* Auto Refresh & Manual Trigger */}
        <div className="flex items-center bg-slate-100 rounded-lg p-1 border border-slate-200/60">
          <button
            onClick={refreshData}
            title="Rafraîchir les métriques"
            className="p-1.5 text-slate-600 hover:text-slate-900 hover:bg-white rounded-md transition-all shadow-2xs"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={toggleAutoRefresh}
            className={`px-2 py-0.5 text-[11px] font-semibold rounded-md transition-all ${
              autoRefresh ? 'bg-emerald-600 text-white shadow-2xs' : 'text-slate-500 hover:text-slate-900'
            }`}
          >
            {autoRefresh ? '30s Auto' : 'Pause'}
          </button>
        </div>

        {/* Perspective Switcher (Instant RBAC Simulation for Evaluators) */}
        <div className="relative" ref={roleRef}>
          <button
            onClick={() => setRoleMenuOpen(!roleMenuOpen)}
            className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg border border-[#D0B335]/40 bg-[#D0B335]/10 hover:bg-[#D0B335]/20 text-xs font-semibold text-slate-900 transition-colors"
            title="Changer de rôle pour tester les permissions"
          >
            <ShieldCheck className="w-3.5 h-3.5 text-[#8D771B]" />
            <span className="hidden sm:inline text-slate-800">Rôle:</span>
            <span className="text-[#8D771B] font-bold">
              {currentRole === 'Admin' ? 'Admin' : currentRole === 'Operator' ? 'Opérateur' : 'Lecture'}
            </span>
            <ChevronDown className="w-3 h-3 text-slate-500" />
          </button>

          {roleMenuOpen && (
            <div className="absolute right-0 mt-2 w-56 bg-white rounded-xl shadow-xl border border-slate-200 py-1 z-50 animate-in fade-in slide-in-from-top-2">
              <div className="px-3 py-2 border-b border-slate-100 bg-slate-50">
                <p className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">
                  Tester les permissions RBAC
                </p>
              </div>
              <button
                onClick={() => {
                  setCurrentRole('Admin');
                  setRoleMenuOpen(false);
                }}
                className={`w-full text-left px-3 py-2 text-xs flex items-center justify-between hover:bg-slate-50 ${
                  currentRole === 'Admin' ? 'bg-amber-50 font-bold text-slate-900' : 'text-slate-700'
                }`}
              >
                <span>Administrateur (Tous droits)</span>
                {currentRole === 'Admin' && <CheckCircle2 className="w-4 h-4 text-[#D0B335]" />}
              </button>
              <button
                onClick={() => {
                  setCurrentRole('Operator');
                  setRoleMenuOpen(false);
                }}
                className={`w-full text-left px-3 py-2 text-xs flex items-center justify-between hover:bg-slate-50 ${
                  currentRole === 'Operator' ? 'bg-amber-50 font-bold text-slate-900' : 'text-slate-700'
                }`}
              >
                <span>Opérateur (Monitoring & Ack)</span>
                {currentRole === 'Operator' && <CheckCircle2 className="w-4 h-4 text-[#D0B335]" />}
              </button>
              <button
                onClick={() => {
                  setCurrentRole('ReadOnly');
                  setRoleMenuOpen(false);
                }}
                className={`w-full text-left px-3 py-2 text-xs flex items-center justify-between hover:bg-slate-50 ${
                  currentRole === 'ReadOnly' ? 'bg-amber-50 font-bold text-slate-900' : 'text-slate-700'
                }`}
              >
                <span>Lecture seule (Consultation)</span>
                {currentRole === 'ReadOnly' && <CheckCircle2 className="w-4 h-4 text-[#D0B335]" />}
              </button>
            </div>
          )}
        </div>

        {/* Notifications Dropdown */}
        <div className="relative" ref={notifRef}>
          <button
            onClick={() => setNotificationsOpen(!notificationsOpen)}
            className="relative p-2 text-slate-600 hover:text-slate-900 hover:bg-slate-100 rounded-lg transition-colors"
            aria-label="Alertes non acquittées"
          >
            <Bell className="w-5 h-5" />
            {openAlerts.length > 0 && (
              <span className="absolute top-1.5 right-1.5 w-4 h-4 rounded-full bg-rose-600 text-white text-[10px] font-bold flex items-center justify-center border-2 border-white shadow-xs">
                {openAlerts.length}
              </span>
            )}
          </button>

          {notificationsOpen && (
            <div className="absolute right-0 mt-2 w-80 sm:w-96 bg-white rounded-2xl shadow-2xl border border-slate-200 overflow-hidden z-50">
              <div className="px-4 py-3 bg-slate-900 text-white flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Bell className="w-4 h-4 text-[#D0B335]" />
                  <span className="text-xs font-bold tracking-tight">Alertes non acquittées</span>
                </div>
                <span className="text-[11px] bg-slate-800 text-slate-300 px-2 py-0.5 rounded-full font-mono">
                  {openAlerts.length} ouverte{openAlerts.length > 1 ? 's' : ''}
                </span>
              </div>

              <div className="max-h-80 overflow-y-auto divide-y divide-slate-100">
                {openAlerts.length === 0 ? (
                  <div className="p-6 text-center text-xs text-slate-500">
                    <CheckCircle2 className="w-8 h-8 text-emerald-500 mx-auto mb-2" />
                    Aucune alerte non acquittée. Tout fonctionne parfaitement !
                  </div>
                ) : (
                  openAlerts.map((alt) => (
                    <div key={alt.id} className="p-3.5 hover:bg-slate-50 transition-colors">
                      <div className="flex items-start justify-between gap-2">
                        <div className="flex items-center gap-1.5">
                          <Badge type="severity" value={alt.severity} size="sm" />
                          <span className="text-xs font-bold text-slate-900 truncate max-w-[160px]">
                            {alt.agentName}
                          </span>
                        </div>
                        <span className="text-[10px] text-slate-400">{alt.timestamp}</span>
                      </div>
                      <p className="text-xs text-slate-600 mt-1 line-clamp-2">{alt.message}</p>
                      {currentRole !== 'ReadOnly' && (
                        <div className="mt-2 flex justify-end">
                          <button
                            onClick={() => acknowledgeAlert(alt.id)}
                            className="text-[11px] font-semibold text-blue-600 hover:text-blue-800 hover:underline"
                          >
                            Acquitter
                          </button>
                        </div>
                      )}
                    </div>
                  ))
                )}
              </div>

              <div className="p-2.5 bg-slate-50 border-t border-slate-100 text-center">
                <button
                  onClick={() => {
                    navigate('/alerts');
                    setNotificationsOpen(false);
                  }}
                  className="text-xs font-bold text-[#8D771B] hover:text-slate-900 transition-colors"
                >
                  Voir toutes les alertes →
                </button>
              </div>
            </div>
          )}
        </div>

        {/* User Profile Dropdown */}
        <div className="relative" ref={userRef}>
          <button
            onClick={() => setUserMenuOpen(!userMenuOpen)}
            className="flex items-center gap-2 p-1.5 hover:bg-slate-100 rounded-xl transition-colors"
          >
            <div className="w-8 h-8 rounded-full bg-slate-900 text-[#D0B335] font-bold text-xs flex items-center justify-center border border-[#D0B335]/30">
              {currentUser?.name.substring(0, 2).toUpperCase() || 'CB'}
            </div>
            <div className="hidden xl:block text-left">
              <p className="text-xs font-bold text-slate-900 leading-tight">{currentUser?.name}</p>
              <p className="text-[10px] text-slate-500">{currentRole}</p>
            </div>
            <ChevronDown className="w-3.5 h-3.5 text-slate-400" />
          </button>

          {userMenuOpen && (
            <div className="absolute right-0 mt-2 w-56 bg-white rounded-xl shadow-xl border border-slate-200 py-1 z-50">
              <div className="px-4 py-3 border-b border-slate-100">
                <p className="text-xs font-bold text-slate-900">{currentUser?.name}</p>
                <p className="text-[11px] text-slate-500 truncate">{currentUser?.email}</p>
              </div>

              <button
                onClick={() => {
                  navigate('/users');
                  setUserMenuOpen(false);
                }}
                className="w-full text-left px-4 py-2 text-xs font-medium text-slate-700 hover:bg-slate-50 flex items-center gap-2"
              >
                <UserIcon className="w-4 h-4 text-slate-400" />
                Mon Profil & Sécurité
              </button>

              <button
                onClick={() => {
                  navigate('/settings');
                  setUserMenuOpen(false);
                }}
                className="w-full text-left px-4 py-2 text-xs font-medium text-slate-700 hover:bg-slate-50 flex items-center gap-2"
              >
                <Settings className="w-4 h-4 text-slate-400" />
                Paramètres Système
              </button>

              <div className="border-t border-slate-100 my-1"></div>

              <button
                onClick={() => {
                  logout();
                  setUserMenuOpen(false);
                }}
                className="w-full text-left px-4 py-2 text-xs font-semibold text-rose-600 hover:bg-rose-50 flex items-center gap-2"
              >
                <LogOut className="w-4 h-4 text-rose-500" />
                Se déconnecter
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
};
