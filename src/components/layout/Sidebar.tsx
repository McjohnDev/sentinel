/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../../context/AppContext';
import {
  LayoutDashboard,
  Server,
  Bell,
  Settings,
  Users,
  ShieldAlert,
  ShieldCheck,
  LogOut,
  X,
} from 'lucide-react';

interface SidebarProps {
  isMobileOpen?: boolean;
  onCloseMobile?: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ isMobileOpen, onCloseMobile }) => {
  const navigate = useNavigate();
  const { agents, alerts, currentUser, logout, currentRole } = useApp();

  const openAlertsCount = alerts.filter((a) => a.status === 'open').length;
  const onlineAgentsCount = agents.filter((a) => a.status === 'online').length;

  const navItems: { id: string; path: string; label: string; icon: React.ReactNode; badge?: string | number; badgeColor?: string }[] = [
    {
      id: 'dashboard',
      path: '/dashboard',
      label: 'Tableau de bord',
      icon: <LayoutDashboard className="w-4 h-4" />,
    },
    {
      id: 'agents',
      path: '/agents',
      label: 'Gestion des agents',
      icon: <Server className="w-4 h-4" />,
      badge: `${onlineAgentsCount}/${agents.length}`,
      badgeColor: 'bg-emerald-900/60 text-emerald-300 border-emerald-700/50',
    },
    {
      id: 'alerts',
      path: '/alerts',
      label: 'Gestion des alertes',
      icon: <Bell className="w-4 h-4" />,
      badge: openAlertsCount > 0 ? openAlertsCount : undefined,
      badgeColor: 'bg-rose-900/80 text-rose-200 border-rose-700/50 font-bold',
    },
    {
      id: 'users',
      path: '/users',
      label: 'Gestion utilisateurs',
      icon: <Users className="w-4 h-4" />,
    },
    {
      id: 'settings',
      path: '/settings',
      label: 'Paramètres',
      icon: <Settings className="w-4 h-4" />,
    },
  ];

  const sidebarContent = (
    <div className="flex flex-col h-full bg-slate-950 text-slate-200 w-[250px] border-r border-slate-800/80 select-none">
      {/* Brand Header */}
      <div className="p-5 border-b border-slate-800/80 flex items-center justify-between">
        <div className="flex items-center gap-3">
          {/* Commercial Bank Logo SVG */}
          <div className="bg-white p-1.5 rounded-lg">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 600 350"
              width="80"
              height="47"
              className="flex-shrink-0"
            >
            <g transform="translate(0, 10)">
              <g id="logo-mark">
                <path d="M 245,50 C 232,50 225,57 225,70 L 225,140 C 225,153 232,160 245,160 L 278,160 L 278,50 Z" fill="#D3A029" />
                <path d="M 286,50 L 320,50 C 333,50 340,57 340,70 L 340,98 C 340,103 337,105 332,105 L 286,105 Z" fill="#050505" />
                <path d="M 286,111 L 332,111 C 337,111 340,113 340,118 L 340,140 C 340,153 333,160 320,160 L 286,160 Z" fill="#A0A2A5" />
              </g>

              <g id="logo-text">
                <text x="300" y="235" textAnchor="middle" fontSize="52" letterSpacing="-1.5">
                  <tspan fill="#000000">Commercial</tspan><tspan fill="#D3A029">Bank</tspan>
                </text>
              </g>
            </g>
          </svg>
          </div>
          <div>
            <h1 className="text-sm font-extrabold text-white tracking-tight">
              CBC Supervision
            </h1>
            <button
              type="button"
              onClick={() => {
                navigate('/settings');
                if (onCloseMobile) onCloseMobile();
              }}
              className="mt-1 flex items-center gap-1 text-[9px] font-bold text-slate-400 hover:text-[#D0B335] transition-colors cursor-pointer group"
              title="Consulter le dossier d'homologation & certifications ISO 27001"
            >
              <ShieldCheck className="w-3 h-3 text-[#D0B335] group-hover:scale-110 transition-transform" />
              <span>Conforme ISO 27001 & COBAC</span>
            </button>
          </div>
        </div>
        {isMobileOpen && (
          <button
            onClick={onCloseMobile}
            className="lg:hidden text-slate-400 hover:text-white p-1 rounded-lg"
          >
            <X className="w-5 h-5" />
          </button>
        )}
      </div>

      {/* Navigation List */}
      <div className="flex-1 py-4 px-3 space-y-1 overflow-y-auto">
        <div className="px-3 pb-2 text-[10px] font-bold text-slate-500 uppercase tracking-widest">
          Menu principal
        </div>

        {navItems.map((item) => {
          const isActive = window.location.pathname === item.path || (item.id === 'agents' && window.location.pathname.startsWith('/agents/'));

          return (
            <button
              key={item.id}
              onClick={() => {
                navigate(item.path);
                if (onCloseMobile) onCloseMobile();
              }}
              className={`w-full flex items-center justify-between px-3 py-2.5 rounded-xl text-xs font-semibold transition-all duration-200 ${
                isActive
                  ? 'bg-slate-850 text-white shadow-xs border border-slate-700/60 font-bold'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900/60'
              }`}
            >
              <div className="flex items-center gap-3">
                <span className={isActive ? 'text-[#D0B335]' : 'text-slate-400'}>{item.icon}</span>
                <span>{item.label}</span>
              </div>
              {item.badge !== undefined && (
                <span
                  className={`px-2 py-0.5 text-[10px] rounded-full border ${
                    item.badgeColor || 'bg-slate-800 text-slate-300 border-slate-700'
                  }`}
                >
                  {item.badge}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Role / User Footer */}
      <div className="p-3 m-3 rounded-xl bg-slate-900/90 border border-slate-800 flex flex-col gap-2">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-lg bg-[#D0B335]/20 text-[#D0B335] text-xs font-bold flex items-center justify-center border border-[#D0B335]/40">
            {currentUser?.name.substring(0, 1)}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-xs font-bold text-white truncate">{currentUser?.name}</p>
            <p className="text-[10px] text-slate-400 truncate">{currentUser?.email}</p>
          </div>
        </div>

        <div className="flex items-center justify-between pt-1 border-t border-slate-800/80">
          <span className="text-[10px] font-semibold text-[#D0B335] uppercase tracking-wider flex items-center gap-1">
            <ShieldAlert className="w-3 h-3" />
            {currentRole}
          </span>
          <button
            onClick={logout}
            className="text-[11px] text-slate-400 hover:text-rose-400 flex items-center gap-1 transition-colors"
            title="Se déconnecter"
          >
            <LogOut className="w-3 h-3" />
            Quitter
          </button>
        </div>
      </div>
    </div>
  );

  return (
    <>
      {/* Desktop Fixed Sidebar */}
      <aside className="hidden lg:block h-screen sticky top-0 z-40 shrink-0">
        {sidebarContent}
      </aside>

      {/* Mobile Drawer Overlay */}
      {isMobileOpen && (
        <div className="fixed inset-0 z-50 lg:hidden flex">
          <div
            className="fixed inset-0 bg-slate-950/80 backdrop-blur-xs"
            onClick={onCloseMobile}
          />
          <div className="relative z-10 flex-1 max-w-[250px]">{sidebarContent}</div>
        </div>
      )}
    </>
  );
};
